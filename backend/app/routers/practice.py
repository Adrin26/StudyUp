from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assignment, AssignmentStudent, Profile, Question, QuestionSet, QuestionSetQuestion, Subject, Topic, utcnow
from ..schemas import PracticeAnswerIn, PracticeGenerateIn
from ..security import get_current_user, require_student
from ..services import randomizer
from ..services.gamification import award_badges
from ..services.progress import record_attempt, recompute_topic
from ..services.question_bank import filter_questions, names_lookup, public_question
from .quiz import feedback, set_attempts

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.get("/filters")
def practice_filters(subject_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    base = select(Question).where(Question.subject_id == subject_id, Question.status == "published")
    topic_counts = dict(db.execute(select(Question.topic_id, func.count()).where(Question.subject_id == subject_id, Question.status == "published").group_by(Question.topic_id)).all())
    years = sorted({y for y in db.scalars(base.with_only_columns(Question.year).distinct()) if y}, reverse=True)
    papers = sorted({p for p in db.scalars(base.with_only_columns(Question.paper).distinct()) if p})
    return {
        "subject": {"id": subject.id, "name": subject.name},
        "topics": [{"id": t.id, "name": t.name, "question_count": topic_counts.get(t.id, 0)} for t in subject.topics],
        "years": years,
        "papers": papers,
        "difficulties": ["easy", "medium", "hard"],
        "question_types": ["mcq", "short_answer"],
    }


@router.get("/questions")
def browse_questions(
    subject_id: str,
    topic_id: str | None = None,
    year: int | None = None,
    paper: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Question).where(Question.subject_id == subject_id, Question.status == "published")
    if topic_id:
        stmt = stmt.where(Question.topic_id == topic_id)
    if year:
        stmt = stmt.where(Question.year == year)
    if paper:
        stmt = stmt.where(Question.paper == paper)
    if difficulty and difficulty != "any":
        stmt = stmt.where(Question.difficulty == difficulty)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Question.year.desc(), Question.paper, Question.question_number).offset((page - 1) * page_size).limit(page_size))
    topics, subjects = names_lookup(db)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [public_question(q, {"topic_name": topics.get(q.topic_id), "subject_name": subjects.get(q.subject_id)}) for q in rows],
    }


def _accessible_set(db: Session, set_id: str, student: Profile) -> tuple[QuestionSet, Assignment | None]:
    qs = db.get(QuestionSet, set_id)
    if qs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Practice set not found")
    if qs.kind == "practice" and qs.owner_id == student.id:
        return qs, None
    if qs.kind == "assignment":
        assignment = db.scalar(
            select(Assignment)
            .join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
            .where(Assignment.set_id == qs.id, AssignmentStudent.student_id == student.id)
        )
        if assignment:
            return qs, assignment
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Practice set not found")


def _set_payload(db: Session, qs: QuestionSet, student: Profile, assignment: Assignment | None) -> dict:
    attempts = set_attempts(db, qs.id, student.id)
    topics, subjects = names_lookup(db)
    status_row = db.get(AssignmentStudent, {"assignment_id": assignment.id, "student_id": student.id}) if assignment else None
    return {
        "id": qs.id,
        "kind": qs.kind,
        "title": qs.title,
        "seed": qs.seed,
        "config": qs.config,
        "status": status_row.status if status_row else qs.status,
        "assignment": {"id": assignment.id, "title": assignment.title, "instructions": assignment.instructions, "due_date": assignment.due_date} if assignment else None,
        "questions": [public_question(i.question, {"topic_name": topics.get(i.question.topic_id), "subject_name": subjects.get(i.question.subject_id)}) for i in qs.items],
        "answers": {i.question_id: feedback(i.question, attempts[i.question_id]) for i in qs.items if i.question_id in attempts},
    }


@router.post("/generate")
def generate_practice(body: PracticeGenerateIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    pool = filter_questions(
        db,
        subject_id=body.subject_id,
        topic_ids=body.topic_ids or None,
        years=body.years or None,
        difficulties=[body.difficulty],
        question_types=body.question_types or None,
    )
    if not pool:
        raise HTTPException(status.HTTP_409_CONFLICT, "No questions match these filters. Try selecting more topics or years.")
    seed = body.seed if body.seed is not None else randomizer.new_seed()
    chosen = randomizer.sample(pool, body.num_questions, seed, key=lambda q: q.id)
    subject = db.get(Subject, body.subject_id)
    qs = QuestionSet(
        kind="practice",
        title=f"{subject.name} Practice",
        owner_id=student.id,
        subject_id=body.subject_id,
        topic_id=body.topic_ids[0] if len(body.topic_ids) == 1 else None,
        config=body.model_dump(exclude={"seed"}) | {"pool_size": len(pool)},
        seed=seed,
        status="active",
    )
    qs.items = [QuestionSetQuestion(question_id=q.id, position=i, marks=q.marks) for i, q in enumerate(chosen)]
    db.add(qs)
    db.commit()
    return _set_payload(db, qs, student, None)


@router.get("/sets/{set_id}")
def get_set(set_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    qs, assignment = _accessible_set(db, set_id, student)
    return _set_payload(db, qs, student, assignment)


@router.post("/answer")
def answer(body: PracticeAnswerIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    context = "practice"
    if body.set_id:
        qs, assignment = _accessible_set(db, body.set_id, student)
        item = next((i for i in qs.items if i.question_id == body.question_id), None)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Question is not part of this set")
        existing = set_attempts(db, qs.id, student.id).get(body.question_id)
        if existing:
            return feedback(item.question, existing)
        question = item.question
        context = "assignment" if assignment else "practice"
    else:
        question = db.get(Question, body.question_id)
        if question is None or question.status != "published":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    attempt, xp = record_attempt(db, student, question, body.answer, body.set_id, context, body.time_spent_sec)
    progress = recompute_topic(db, student.id, question.topic_id)
    award_badges(db, student)
    db.commit()
    return feedback(question, attempt, xp) | {"topic_mastery": progress.mastery}


@router.post("/sets/{set_id}/complete")
def complete_set(set_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    qs, assignment = _accessible_set(db, set_id, student)
    attempts = set_attempts(db, qs.id, student.id)
    total = len(qs.items)
    correct = sum(1 for a in attempts.values() if a.is_correct)
    percentage = round(correct / total * 100, 1) if total else 0.0
    topics = {t.id: t.name for t in db.scalars(select(Topic))}
    per_topic: dict[str, list[bool]] = {}
    for item in qs.items:
        a = attempts.get(item.question_id)
        per_topic.setdefault(topics.get(item.question.topic_id, "?"), []).append(bool(a and a.is_correct))

    if assignment:
        row = db.get(AssignmentStudent, {"assignment_id": assignment.id, "student_id": student.id})
        row.status, row.score, row.completed_at = "completed", percentage, utcnow()
    elif qs.owner_id == student.id:
        qs.status = "completed"
        qs.completed_at = utcnow()
    db.commit()
    return {
        "score": correct,
        "answered": len(attempts),
        "total": total,
        "percentage": percentage,
        "by_topic": [{"topic": k, "correct": sum(v), "total": len(v)} for k, v in per_topic.items()],
    }
