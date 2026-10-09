from datetime import datetime, time, timedelta

from sqlalchemy import case, func, or_, select, true
from sqlalchemy.orm import Session

from ..models import (
    Profile,
    Question,
    QuestionAttempt,
    StudentSubject,
    StudentTopicProgress,
    Subject,
    Topic,
)
from . import assignment_rules, gamification
from .grading import is_correct
from .mastery import compute_mastery, mastery_level


def record_attempt(
    db: Session,
    student: Profile,
    question: Question,
    answer: str,
    set_id: str | None,
    context: str,
    time_spent_sec: int | None = None,
    award_xp: bool = True,
) -> tuple[QuestionAttempt, int]:
    correct = is_correct(question, answer)
    attempt = QuestionAttempt(
        student_id=student.id,
        question_id=question.id,
        topic_id=question.topic_id,
        subject_id=question.subject_id,
        set_id=set_id,
        answer=answer,
        is_correct=correct,
        difficulty=question.difficulty,
        context=context,
        time_spent_sec=time_spent_sec,
    )
    db.add(attempt)
    db.flush()
    xp = gamification.xp_for_answer(question.difficulty, correct) if award_xp else 0
    gamification.award_xp(db, student, xp, "answer", attempt.id)
    gamification.touch_streak(student)
    db.flush()
    return attempt, xp


def get_progress(db: Session, student_id: str, topic_id: str) -> StudentTopicProgress | None:
    return db.get(StudentTopicProgress, {"student_id": student_id, "topic_id": topic_id})


def released(student_id: str, db: Session):
    """Filter out attempts on assignments whose answers are still held back from the student."""
    held = assignment_rules.held_set_ids(db, student_id)
    return or_(QuestionAttempt.set_id.is_(None), QuestionAttempt.set_id.not_in(held)) if held else true()


def recompute_topic(db: Session, student_id: str, topic_id: str) -> StudentTopicProgress:
    attempts = list(
        db.scalars(
            select(QuestionAttempt).where(
                QuestionAttempt.student_id == student_id, QuestionAttempt.topic_id == topic_id, released(student_id, db)
            )
        )
    )
    result = compute_mastery(attempts)
    progress = get_progress(db, student_id, topic_id)
    if progress is None:
        topic = db.get(Topic, topic_id)
        progress = StudentTopicProgress(student_id=student_id, topic_id=topic_id, subject_id=topic.subject_id, quizzes_completed=0)
        db.add(progress)
    progress.mastery = result.mastery
    progress.recent_score = result.recent_score
    progress.historical_score = result.historical_score
    progress.attempts_count = result.attempts
    progress.correct_count = result.correct
    progress.last_attempt_at = max((a.created_at for a in attempts), default=None)
    db.flush()
    return progress


def topic_progress_map(db: Session, student_id: str, subject_id: str | None = None) -> dict[str, StudentTopicProgress]:
    stmt = select(StudentTopicProgress).where(StudentTopicProgress.student_id == student_id)
    if subject_id:
        stmt = stmt.where(StudentTopicProgress.subject_id == subject_id)
    return {p.topic_id: p for p in db.scalars(stmt)}


def topic_view(topic: Topic, progress: StudentTopicProgress | None) -> dict:
    mastery = progress.mastery if progress else 0.0
    attempts = progress.attempts_count if progress else 0
    return {
        "id": topic.id,
        "subject_id": topic.subject_id,
        "name": topic.name,
        "description": topic.description,
        "form": topic.form,
        "mastery": mastery,
        "attempts": attempts,
        "level": mastery_level(mastery, attempts),
    }


def subject_progress(topics: list[Topic], progress: dict[str, StudentTopicProgress]) -> dict:
    """Subject progress = mean mastery across *all* topics (unstarted topics count as 0)."""
    total = len(topics)
    masteries = [progress[t.id].mastery if t.id in progress else 0.0 for t in topics]
    return {
        "progress": round(sum(masteries) / total, 1) if total else 0.0,
        "topics_total": total,
        "topics_mastered": sum(1 for m in masteries if m >= 80),
        "topics_started": sum(1 for t in topics if t.id in progress and progress[t.id].attempts_count > 0),
    }


def enrolled_subjects(db: Session, student_id: str) -> list[Subject]:
    stmt = (
        select(Subject)
        .join(StudentSubject, StudentSubject.subject_id == Subject.id)
        .where(StudentSubject.student_id == student_id, Subject.status == "published")
        .order_by(Subject.sort_order)
    )
    return list(db.scalars(stmt))


def student_stats(db: Session, student: Profile) -> dict:
    subjects = enrolled_subjects(db, student.id)
    progress = topic_progress_map(db, student.id)
    all_topics = [t for s in subjects for t in s.topics if t.status == "published"]
    overall = subject_progress(all_topics, progress)
    answered, correct = db.execute(
        select(func.count(QuestionAttempt.id), func.coalesce(func.sum(case((QuestionAttempt.is_correct, 1), else_=0)), 0)).where(
            QuestionAttempt.student_id == student.id, released(student.id, db)
        )
    ).one()
    today = gamification.today_my()
    today_start = datetime.combine(today, time.min, tzinfo=gamification.MALAYSIA_TZ)
    week_start = today_start - timedelta(days=today.weekday())

    def answered_since(start: datetime) -> int:
        return db.scalar(
            select(func.count()).select_from(QuestionAttempt).where(
                QuestionAttempt.student_id == student.id, QuestionAttempt.created_at >= start
            )
        )

    week_answered = answered_since(week_start)
    today_answered = answered_since(today_start)
    return {
        "overall_progress": overall["progress"],
        "topics_mastered": overall["topics_mastered"],
        "topics_total": overall["topics_total"],
        "questions_answered": answered,
        "average_score": round(correct / answered * 100, 1) if answered else 0.0,
        "xp": student.xp,
        "streak": gamification.effective_streak(student),
        "longest_streak": student.longest_streak,
        **gamification.level_info(student.xp),
        "weekly_goal": {"target": gamification.WEEKLY_QUESTION_GOAL, "done": week_answered},
        "daily_challenge": {"target": gamification.DAILY_CHALLENGE_QUESTIONS, "done": min(today_answered, gamification.DAILY_CHALLENGE_QUESTIONS)},
    }
