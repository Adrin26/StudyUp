from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Profile, Question, QuestionSet, QuestionSetQuestion, Subject
from ..schemas import ExamGenerateIn, ExamReplaceIn, ExamSaveIn
from ..permissions import require_teacher
from ..services import randomizer
from ..services.access import ensure_teaches_subject
from ..services.exam_generator import assign_marks, generate_exam, pick_replacement
from ..services.question_bank import filter_questions, full_question, names_lookup

router = APIRouter(prefix="/api/exams", tags=["exams"])


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
    db.delete(_owned_exam(db, exam_id, teacher))
    db.commit()
