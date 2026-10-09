from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Question, Subject, Topic
from .grading import display_answer


def filter_questions(
    db: Session,
    subject_id: str | None = None,
    topic_ids: list[str] | None = None,
    years: list[int] | None = None,
    difficulties: list[str] | None = None,
    question_types: list[str] | None = None,
    papers: list[str] | None = None,
) -> list[Question]:
    stmt = select(Question).where(Question.status == "published")
    if subject_id:
        stmt = stmt.where(Question.subject_id == subject_id)
    if topic_ids:
        stmt = stmt.where(Question.topic_id.in_(topic_ids))
    if years:
        stmt = stmt.where(Question.year.in_(years))
    if difficulties and "any" not in difficulties:
        stmt = stmt.where(Question.difficulty.in_(difficulties))
    if question_types:
        stmt = stmt.where(Question.question_type.in_(question_types))
    if papers:
        stmt = stmt.where(Question.paper.in_(papers))
    return list(db.scalars(stmt))


def question_meta(db: Session, q: Question) -> dict:
    topic = db.get(Topic, q.topic_id)
    subject = db.get(Subject, q.subject_id)
    return {"topic_name": topic.name if topic else None, "subject_name": subject.name if subject else None}


def public_question(q: Question, meta: dict | None = None, marks: int | None = None) -> dict:
    """Question payload safe to send before the student answers (no answer/explanation)."""
    data = {
        "id": q.id,
        "subject_id": q.subject_id,
        "topic_id": q.topic_id,
        "year": q.year,
        "paper": q.paper,
        "question_number": q.question_number,
        "question_text": q.question_text,
        "question_type": q.question_type,
        "difficulty": q.difficulty,
        "marks": marks if marks is not None else q.marks,
        "options": q.options,
        "image_url": q.image_url,
        "skill": q.skill,
        "source": q.source,
    }
    if meta:
        data.update(meta)
    return data


def full_question(q: Question, meta: dict | None = None, marks: int | None = None) -> dict:
    return {
        **public_question(q, meta, marks),
        "correct_answer": q.correct_answer,
        "correct_display": display_answer(q),
        "explanation": q.explanation,
    }


def names_lookup(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    topics = {t.id: t.name for t in db.scalars(select(Topic))}
    subjects = {s.id: s.name for s in db.scalars(select(Subject))}
    return topics, subjects
