"""Deterministic study recommendations. The AI only phrases them."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AssignmentStudent, Assignment, Lesson, LessonProgress, Profile, Question
from .progress import enrolled_subjects, topic_progress_map

MAX_RECOMMENDATIONS = 4


def recommend(db: Session, student: Profile) -> list[dict]:
    recs: list[dict] = []
    subjects = enrolled_subjects(db, student.id)
    progress = topic_progress_map(db, student.id)
    topics = {t.id: (t, s) for s in subjects for t in s.topics}

    pending = db.execute(
        select(Assignment)
        .join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
        .where(AssignmentStudent.student_id == student.id, AssignmentStudent.status == "assigned")
        .order_by(Assignment.due_date.is_(None), Assignment.due_date)
        .limit(1)
    ).scalar_one_or_none()
    if pending:
        recs.append({
            "kind": "assignment",
            "title": f"Finish: {pending.title}",
            "reason": "Your teacher assigned this practice set.",
            "action": {"type": "assignment", "set_id": pending.set_id},
        })

    weak = sorted(
        (p for p in progress.values() if p.attempts_count > 0 and p.mastery < 60 and p.topic_id in topics),
        key=lambda p: p.mastery,
    )
    for p in weak[:2]:
        topic, subject = topics[p.topic_id]
        recs.append({
            "kind": "practice_topic",
            "title": f"Practice {topic.name}",
            "reason": f"Current mastery: {p.mastery:.0f}%",
            "subject": subject.name,
            "mastery": p.mastery,
            "action": {"type": "topic", "topic_id": topic.id},
        })

    in_progress = db.execute(
        select(Lesson, LessonProgress)
        .join(LessonProgress, LessonProgress.lesson_id == Lesson.id)
        .where(LessonProgress.student_id == student.id, LessonProgress.completed.is_(False))
        .order_by(LessonProgress.updated_at.desc())
        .limit(1)
    ).first()
    if in_progress and in_progress[0].topic_id in topics:
        lesson, lp = in_progress
        recs.append({
            "kind": "resume_lesson",
            "title": f"Resume lesson: {lesson.title}",
            "reason": f"You stopped at slide {lp.current_slide + 1}.",
            "action": {"type": "lesson", "topic_id": lesson.topic_id},
        })

    for subject in subjects:
        nxt = next((t for t in subject.topics if t.id not in progress), None)
        if nxt and len(recs) < MAX_RECOMMENDATIONS:
            has_questions = db.scalar(select(func.count()).select_from(Question).where(Question.topic_id == nxt.id, Question.status == "published"))
            if has_questions:
                recs.append({
                    "kind": "start_topic",
                    "title": f"Start {nxt.name}",
                    "reason": f"Next new topic in {subject.name}.",
                    "subject": subject.name,
                    "action": {"type": "topic", "topic_id": nxt.id},
                })
                break

    strong_subject = None
    for subject in subjects:
        scores = [progress[t.id].mastery for t in subject.topics if t.id in progress]
        if len(scores) >= 2 and sum(scores) / len(scores) >= 60:
            strong_subject = subject
            break
    if strong_subject:
        latest_year = db.scalar(select(func.max(Question.year)).where(Question.subject_id == strong_subject.id))
        if latest_year:
            real_paper = db.scalar(select(func.count()).select_from(Question).where(
                Question.subject_id == strong_subject.id, Question.year == latest_year, Question.source == "spm_past_year"))
            label = f"{latest_year} SPM" if real_paper else f"{latest_year}-style"
            recs.append({
                "kind": "past_year",
                "title": f"Try {label} {strong_subject.name} questions",
                "reason": "You're doing well — test yourself with exam-style questions.",
                "subject": strong_subject.name,
                "action": {"type": "past_year", "subject_id": strong_subject.id, "year": latest_year},
            })

    return recs[:MAX_RECOMMENDATIONS]
