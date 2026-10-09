from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ClassStudent, ExamAnswer, ExamAttempt, ExamPublication, Notification, Profile, Question, QuestionSet,
    QuestionSetQuestion, SchoolClass, Subject, utcnow,
)
from ..schemas import ExamAnswerIn, ExamGenerateIn, ExamPublishIn, ExamReplaceIn, ExamSaveIn
from ..permissions import require_student, require_teacher
from ..services import randomizer
from ..services.access import ensure_teaches_subject, ensure_teaches_subject_in_class, students_in_classes
from ..services.exam_generator import assign_marks, generate_exam, pick_replacement
from ..services.grading import display_answer, display_given, is_correct
from ..services.question_bank import filter_questions, full_question, names_lookup, public_question

router = APIRouter(prefix="/api/exams", tags=["exams"])
student_router = APIRouter(prefix="/api/my-exams", tags=["exams"])


def _pool(db: Session, body: ExamGenerateIn) -> list[Question]:
    return filter_questions(
        db,
        subject_id=body.subject_id,
        topic_ids=body.topic_ids or None,
        years=body.years or None,
        question_types=body.question_types or None,
    )


def _serialise(db: Session, questions: list[Question], marks: dict[str, int]) -> list[dict]:
    topics, subjects = names_lookup(db)
    return [
        full_question(q, {"topic_name": topics.get(q.topic_id), "subject_name": subjects.get(q.subject_id)}, marks.get(q.id))
        for q in questions
    ]


@router.post("/generate")
def generate(body: ExamGenerateIn, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    ensure_teaches_subject(db, teacher, body.subject_id)
    pool = _pool(db, body)
    if not pool:
        raise HTTPException(status.HTTP_409_CONFLICT, "No questions match these filters")
    seed = body.seed if body.seed is not None else randomizer.new_seed()
    exam = generate_exam(pool, body.num_questions, dict(body.difficulty_mix), body.total_marks, seed)
    return {
        "seed": exam.seed,
        "pool_size": len(pool),
        "warnings": exam.warnings,
        "difficulty_counts": exam.difficulty_counts,
        "total_marks": sum(exam.marks.values()),
        "questions": _serialise(db, exam.questions, exam.marks),
    }


@router.post("/replace")
def replace(body: ExamReplaceIn, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    ensure_teaches_subject(db, teacher, body.subject_id)
    current = db.get(Question, body.question_id)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    replacement = pick_replacement(_pool(db, body), current, set(body.current_ids), randomizer.new_seed())
    if replacement is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No other questions available for these filters")
    return _serialise(db, [replacement], {replacement.id: replacement.marks})[0]


@router.post("")
def save_exam(body: ExamSaveIn, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    ensure_teaches_subject(db, teacher, body.subject_id)
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(body.question_ids), Question.status == "published"))}
    missing = [qid for qid in body.question_ids if qid not in questions]
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{len(missing)} question(s) no longer exist")
    ordered = [questions[qid] for qid in body.question_ids]
    marks = body.marks or assign_marks(ordered, body.total_marks)
    exam = QuestionSet(
        kind="exam",
        title=body.title,
        owner_id=teacher.id,
        subject_id=body.subject_id,
        config=body.config,
        seed=body.seed,
        total_marks=sum(marks.get(q.id, q.marks) for q in ordered),
        status="saved",
    )
    exam.items = [QuestionSetQuestion(question_id=q.id, position=i, marks=marks.get(q.id, q.marks)) for i, q in enumerate(ordered)]
    db.add(exam)
    db.commit()
    return {"id": exam.id, "title": exam.title, "total_marks": exam.total_marks, "question_count": len(ordered)}


@router.get("")
def list_exams(teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    exams = db.scalars(select(QuestionSet).where(QuestionSet.owner_id == teacher.id, QuestionSet.kind == "exam").order_by(QuestionSet.created_at.desc()))
    subjects = {s.id: s.name for s in db.scalars(select(Subject))}
    return [
        {"id": e.id, "title": e.title, "subject": subjects.get(e.subject_id), "subject_id": e.subject_id, "total_marks": e.total_marks, "question_count": len(e.items), "created_at": e.created_at}
        for e in exams
    ]


def _owned_exam(db: Session, exam_id: str, teacher: Profile) -> QuestionSet:
    exam = db.get(QuestionSet, exam_id)
    if exam is None or exam.kind != "exam" or exam.owner_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    return exam


@router.get("/{exam_id}")
def get_exam(exam_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    exam = _owned_exam(db, exam_id, teacher)
    marks = {i.question_id: i.marks for i in exam.items}
    return {
        "id": exam.id,
        "title": exam.title,
        "subject_id": exam.subject_id,
        "total_marks": exam.total_marks,
        "config": exam.config,
        "created_at": exam.created_at,
        "questions": _serialise(db, [i.question for i in exam.items], marks),
    }


@router.delete("/{exam_id}", status_code=204)
def delete_exam(exam_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    exam = _owned_exam(db, exam_id, teacher)
    if db.scalar(select(func.count()).select_from(ExamPublication).where(ExamPublication.exam_id == exam.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This exam has been published to a class and keeps its results")
    db.delete(exam)
    db.commit()


# ---- Publishing (teacher) ----

def _attempt_count(db: Session, publication_id: str) -> int:
    return db.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.publication_id == publication_id)) or 0


def _publication_out(db: Session, p: ExamPublication) -> dict:
    cls = db.get(SchoolClass, p.class_id)
    return {
        "id": p.id, "class_id": p.class_id, "class_name": cls.name if cls else None,
        "opens_at": p.opens_at, "closes_at": p.closes_at, "release_at": p.release_at, "duration_minutes": p.duration_minutes,
        "attempts": _attempt_count(db, p.id),
    }


@router.post("/{exam_id}/publish")
def publish_exam(exam_id: str, body: ExamPublishIn, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    exam = _owned_exam(db, exam_id, teacher)
    cls = db.get(SchoolClass, body.class_id)
    if cls is None or cls.school_id != teacher.school_id or cls.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found")
    ensure_teaches_subject_in_class(db, teacher, cls.id, exam.subject_id)
    pub = db.scalar(select(ExamPublication).where(ExamPublication.exam_id == exam.id, ExamPublication.class_id == cls.id))
    if pub is not None and _attempt_count(db, pub.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Students have already started this exam; its schedule can no longer change")
    is_new = pub is None
    if is_new:
        pub = ExamPublication(exam_id=exam.id, class_id=cls.id, published_by=teacher.id)
        db.add(pub)
    pub.opens_at, pub.closes_at, pub.release_at, pub.duration_minutes = body.opens_at, body.closes_at, body.release_at, body.duration_minutes
    db.flush()
    if is_new:
        for sid in students_in_classes(db, [cls.id]):
            db.add(Notification(user_id=sid, kind="exam", title=f"New exam from {teacher.full_name}", body=exam.title, link="/exams"))
    db.commit()
    return _publication_out(db, pub)


@router.get("/{exam_id}/publications")
def list_publications(exam_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    exam = _owned_exam(db, exam_id, teacher)
    pubs = db.scalars(select(ExamPublication).where(ExamPublication.exam_id == exam.id).order_by(ExamPublication.opens_at))
    return [_publication_out(db, p) for p in pubs]


@router.delete("/publications/{publication_id}", status_code=204)
def unpublish(publication_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    pub = db.get(ExamPublication, publication_id)
    if pub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publication not found")
    _owned_exam(db, pub.exam_id, teacher)
    if _attempt_count(db, pub.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Students have already started this exam")
    db.delete(pub)
    db.commit()


@router.get("/publications/{publication_id}/results")
def publication_results(publication_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    pub = db.get(ExamPublication, publication_id)
    if pub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publication not found")
    exam = _owned_exam(db, pub.exam_id, teacher)
    ensure_teaches_subject_in_class(db, teacher, pub.class_id, exam.subject_id)
    attempts = {a.student_id: a for a in db.scalars(select(ExamAttempt).where(ExamAttempt.publication_id == pub.id))}
    for a in attempts.values():
        _finalise_if_expired(db, pub, exam, a)
    db.commit()
    roster = set(students_in_classes(db, [pub.class_id])) | set(attempts)
    students = db.scalars(select(Profile).where(Profile.id.in_(roster)).order_by(Profile.full_name)) if roster else []
    rows = []
    for s in students:
        a = attempts.get(s.id)
        state = "not_started" if a is None else ("submitted" if a.submitted_at else "in_progress")
        rows.append({
            "student_id": s.id, "name": s.full_name, "status": state,
            "marks": a.marks_awarded if a else None, "submitted_at": a.submitted_at if a else None,
        })
    marks = [r["marks"] for r in rows if r["marks"] is not None]
    return {
        "publication": _publication_out(db, pub),
        "exam": {"id": exam.id, "title": exam.title, "total_marks": exam.total_marks},
        "summary": {
            "students": len(rows), "submitted": len(marks),
            "average": round(sum(marks) / len(marks), 1) if marks else None,
        },
        "students": rows,
    }


# ---- Sitting an exam (student) ----

def _deadline(pub: ExamPublication, attempt: ExamAttempt) -> datetime:
    if pub.duration_minutes:
        return min(pub.closes_at, attempt.started_at + timedelta(minutes=pub.duration_minutes))
    return pub.closes_at


def _mark(db: Session, exam: QuestionSet, attempt: ExamAttempt) -> None:
    answers = db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id))
    attempt.marks_awarded = sum(a.marks_awarded for a in answers)
    attempt.total_marks = exam.total_marks


def _finalise_if_expired(db: Session, pub: ExamPublication, exam: QuestionSet, attempt: ExamAttempt) -> None:
    """Attempts left open past their deadline are submitted with whatever was answered."""
    if attempt.submitted_at is None and utcnow() >= _deadline(pub, attempt):
        _mark(db, exam, attempt)
        attempt.submitted_at = _deadline(pub, attempt)


def _student_publication(db: Session, publication_id: str, student: Profile) -> tuple[ExamPublication, QuestionSet]:
    """Only students currently enrolled in the class can see its exam; everyone else gets a 404."""
    pub = db.get(ExamPublication, publication_id)
    enrolled = pub is not None and db.scalar(select(func.count()).select_from(ClassStudent).where(
        ClassStudent.class_id == pub.class_id, ClassStudent.student_id == student.id, ClassStudent.status == "active"))
    if not enrolled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    return pub, db.get(QuestionSet, pub.exam_id)


def _my_attempt(db: Session, pub: ExamPublication, student: Profile) -> ExamAttempt | None:
    return db.scalar(select(ExamAttempt).where(ExamAttempt.publication_id == pub.id, ExamAttempt.student_id == student.id))


def _released(pub: ExamPublication) -> bool:
    return utcnow() >= pub.release_at


def _exam_payload(db: Session, pub: ExamPublication, exam: QuestionSet, attempt: ExamAttempt) -> dict:
    answers = {a.question_id: a for a in db.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id))}
    released = _released(pub) and attempt.submitted_at is not None
    questions = []
    for item in exam.items:
        q, a = item.question, answers.get(item.question_id)
        entry = public_question(q, marks=item.marks) | {
            "your_answer": a.answer if a else None,
            "your_answer_display": display_given(q, a.answer) if a else None,
        }
        if released:
            entry |= {"is_correct": bool(a and a.is_correct), "marks_awarded": a.marks_awarded if a else 0,
                      "correct_display": display_answer(q), "explanation": q.explanation}
        questions.append(entry)
    return {
        "publication_id": pub.id, "title": exam.title, "total_marks": exam.total_marks,
        "started_at": attempt.started_at, "deadline": _deadline(pub, attempt), "submitted_at": attempt.submitted_at,
        "release_at": pub.release_at, "released": released,
        "marks_awarded": attempt.marks_awarded if released else None,
        "questions": questions,
    }


@student_router.get("")
def my_exams(student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    class_ids = select(ClassStudent.class_id).where(ClassStudent.student_id == student.id, ClassStudent.status == "active")
    pubs = list(db.scalars(select(ExamPublication).where(ExamPublication.class_id.in_(class_ids)).order_by(ExamPublication.opens_at.desc())))
    subjects = {s.id: s.name for s in db.scalars(select(Subject))}
    now, out = utcnow(), []
    for p in pubs:
        exam = db.get(QuestionSet, p.exam_id)
        attempt = _my_attempt(db, p, student)
        if attempt:
            _finalise_if_expired(db, p, exam, attempt)
        released = _released(p) and attempt is not None and attempt.submitted_at is not None
        window = "upcoming" if now < p.opens_at else ("open" if now < p.closes_at else "closed")
        out.append({
            "publication_id": p.id, "title": exam.title, "subject": subjects.get(exam.subject_id),
            "question_count": len(exam.items), "total_marks": exam.total_marks,
            "opens_at": p.opens_at, "closes_at": p.closes_at, "release_at": p.release_at, "duration_minutes": p.duration_minutes,
            "window": window,
            "status": "not_started" if attempt is None else ("submitted" if attempt.submitted_at else "in_progress"),
            "released": released, "marks_awarded": attempt.marks_awarded if released else None,
        })
    db.commit()
    return out


@student_router.post("/{publication_id}/start")
def start_exam(publication_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    pub, exam = _student_publication(db, publication_id, student)
    attempt = _my_attempt(db, pub, student)
    if attempt is None:
        now = utcnow()
        if now < pub.opens_at:
            raise HTTPException(status.HTTP_409_CONFLICT, "This exam has not opened yet")
        if now >= pub.closes_at:
            raise HTTPException(status.HTTP_409_CONFLICT, "This exam has closed")
        attempt = ExamAttempt(publication_id=pub.id, student_id=student.id, started_at=now)
        db.add(attempt)
        db.flush()
    _finalise_if_expired(db, pub, exam, attempt)
    db.commit()
    return _exam_payload(db, pub, exam, attempt)


@student_router.get("/{publication_id}")
def get_my_exam(publication_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    pub, exam = _student_publication(db, publication_id, student)
    attempt = _my_attempt(db, pub, student)
    if attempt is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the exam first")
    _finalise_if_expired(db, pub, exam, attempt)
    db.commit()
    return _exam_payload(db, pub, exam, attempt)


@student_router.post("/{publication_id}/answer")
def answer_exam(publication_id: str, body: ExamAnswerIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    pub, exam = _student_publication(db, publication_id, student)
    attempt = _my_attempt(db, pub, student)
    if attempt is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the exam first")
    _finalise_if_expired(db, pub, exam, attempt)
    if attempt.submitted_at is not None:
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "This exam has been submitted")
    item = next((i for i in exam.items if i.question_id == body.question_id), None)
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Question is not part of this exam")
    existing = db.scalar(select(ExamAnswer).where(ExamAnswer.attempt_id == attempt.id, ExamAnswer.question_id == item.question_id))
    if existing is None:
        correct = is_correct(item.question, body.answer)
        existing = ExamAnswer(attempt_id=attempt.id, question_id=item.question_id, answer=body.answer,
                              is_correct=correct, marks_awarded=item.marks if correct else 0)
        db.add(existing)
        db.commit()
    return {"question_id": item.question_id, "your_answer": existing.answer,
            "your_answer_display": display_given(item.question, existing.answer)}


@student_router.post("/{publication_id}/submit")
def submit_exam(publication_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    pub, exam = _student_publication(db, publication_id, student)
    attempt = _my_attempt(db, pub, student)
    if attempt is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the exam first")
    _finalise_if_expired(db, pub, exam, attempt)
    if attempt.submitted_at is None:
        _mark(db, exam, attempt)
        attempt.submitted_at = utcnow()
    db.commit()
    return _exam_payload(db, pub, exam, attempt)
