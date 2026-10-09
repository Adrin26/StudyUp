from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Badge, Profile, QuestionAttempt, QuestionSet, StudentBadge, StudentTopicProgress, Subject

MALAYSIA_TZ = timezone(timedelta(hours=8))
XP_PER_LEVEL = 500
XP_CORRECT = {"easy": 10, "medium": 15, "hard": 20}
XP_EFFORT = 2
XP_QUIZ_COMPLETE = 25
XP_PERFECT_QUIZ = 50
WEEKLY_QUESTION_GOAL = 50
DAILY_CHALLENGE_QUESTIONS = 10

BADGES = [
    ("first_steps", "First Steps", "Complete your first topic quiz.", "footprints", 50),
    ("perfect_10", "Perfect 10", "Score 100% on a topic quiz.", "sparkles", 100),
    ("streak_7", "On Fire", "Learn 7 days in a row.", "flame", 150),
    ("topic_master", "Topic Master", "Reach 80% mastery in any topic.", "crown", 100),
    ("algebra_explorer", "Algebra Explorer", "Reach 60% mastery in 3 Mathematics topics.", "compass", 150),
    ("century", "Century", "Answer 100 questions.", "target", 100),
]


def today_my() -> date:
    return datetime.now(MALAYSIA_TZ).date()


def xp_for_answer(difficulty: str, correct: bool) -> int:
    return XP_CORRECT.get(difficulty, 10) if correct else XP_EFFORT


def level_info(xp: int) -> dict:
    level = xp // XP_PER_LEVEL + 1
    into = xp % XP_PER_LEVEL
    return {"level": level, "xp_into_level": into, "xp_for_next": XP_PER_LEVEL, "progress": round(into / XP_PER_LEVEL * 100)}


def touch_streak(student: Profile, on: date | None = None) -> bool:
    """Update the daily streak. Returns True when the streak increased today."""
    on = on or today_my()
    last = student.last_active_date
    if last == on:
        return False
    student.current_streak = student.current_streak + 1 if last == on - timedelta(days=1) else 1
    student.longest_streak = max(student.longest_streak, student.current_streak)
    student.last_active_date = on
    return True


def effective_streak(student: Profile) -> int:
    """A streak only counts if the student was active today or yesterday."""
    if student.last_active_date is None:
        return 0
    if student.last_active_date >= today_my() - timedelta(days=1):
        return student.current_streak
    return 0


def ensure_badges(db: Session) -> None:
    existing = set(db.scalars(select(Badge.code)))
    for code, name, desc, icon, xp in BADGES:
        if code not in existing:
            db.add(Badge(code=code, name=name, description=desc, icon=icon, xp_reward=xp))
    db.flush()


def award_badges(db: Session, student: Profile, quiz_percentage: float | None = None) -> list[Badge]:
    owned = set(
        db.scalars(select(Badge.code).join(StudentBadge, StudentBadge.badge_id == Badge.id).where(StudentBadge.student_id == student.id))
    )
    progress = list(db.scalars(select(StudentTopicProgress).where(StudentTopicProgress.student_id == student.id)))
    math_id = db.scalar(select(Subject.id).where(Subject.code == "MATH"))
    quizzes_done = db.scalar(
        select(func.count()).select_from(QuestionSet).where(
            QuestionSet.owner_id == student.id, QuestionSet.kind == "quiz", QuestionSet.status == "completed"
        )
    )
    answered = db.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.student_id == student.id))

    earned_now = {
        "first_steps": quizzes_done >= 1,
        "perfect_10": quiz_percentage is not None and quiz_percentage >= 100,
        "streak_7": student.current_streak >= 7,
        "topic_master": any(p.mastery >= 80 for p in progress),
        "algebra_explorer": sum(1 for p in progress if p.subject_id == math_id and p.mastery >= 60) >= 3,
        "century": answered >= 100,
    }
    new: list[Badge] = []
    for code, ok in earned_now.items():
        if ok and code not in owned:
            badge = db.scalar(select(Badge).where(Badge.code == code))
            if badge:
                db.add(StudentBadge(student_id=student.id, badge_id=badge.id))
                student.xp += badge.xp_reward
                new.append(badge)
    return new
