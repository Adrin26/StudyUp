"""Availability and answer-release rules for assignments and published exams, checked on every student request."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Assignment, AssignmentStudent, ClassStudent, ExamPublication, Profile, QuestionSetQuestion, utcnow
from .gamification import today_my


def is_open(assignment: Assignment) -> bool:
    return assignment.available_from is None or assignment.available_from <= utcnow()


def is_past_due(assignment: Assignment) -> bool:
    return assignment.due_date is not None and today_my() > assignment.due_date


def ensure_can_answer(assignment: Assignment) -> None:
    if not is_open(assignment):
        raise HTTPException(status.HTTP_409_CONFLICT, "This assignment has not opened yet")
    if is_past_due(assignment):
        raise HTTPException(status.HTTP_409_CONFLICT, "This assignment is past its due date")


def answers_visible(assignment: Assignment) -> bool:
    return assignment.feedback_release == "immediate" or is_past_due(assignment)


def hide_feedback(result: dict) -> dict:
    """Keep only what a student may see before release: that the answer was recorded."""
    return {"question_id": result["question_id"], "your_answer": result["your_answer"],
            "your_answer_display": result["your_answer_display"], "feedback_hidden": True, "xp_gained": 0}


def held_set_ids(db: Session, student_id: str) -> set[str]:
    """Assignment sets whose answers this student may not see yet."""
    rows = db.scalars(
        select(Assignment).join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
        .where(AssignmentStudent.student_id == student_id, Assignment.feedback_release == "after_due")
    )
    return {a.set_id for a in rows if not is_past_due(a)}


def held_question_ids(db: Session, student: Profile) -> set[str]:
    """Questions whose answers are withheld from this student: held assignments plus unreleased exams for their classes."""
    set_ids = held_set_ids(db, student.id)
    class_ids = select(ClassStudent.class_id).where(ClassStudent.student_id == student.id, ClassStudent.status == "active")
    set_ids.update(db.scalars(
        select(ExamPublication.exam_id).where(ExamPublication.class_id.in_(class_ids), ExamPublication.release_at > utcnow())
    ))
    if not set_ids:
        return set()
    return set(db.scalars(select(QuestionSetQuestion.question_id).where(QuestionSetQuestion.set_id.in_(set_ids))))
