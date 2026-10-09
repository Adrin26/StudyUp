from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Lesson, LessonProgress, Profile, Question, QuestionSet, Subject, Topic
from ..permissions import require_teacher
from ..security import get_current_user
from ..services.progress import enrolled_subjects, subject_progress, topic_progress_map, topic_view
from ..services.question_bank import full_question
from ..services.access import ensure_teaches_subject

router = APIRouter(prefix="/api", tags=["subjects"])


def subject_payload(s: Subject) -> dict:
    return {"id": s.id, "code": s.code, "name": s.name, "icon": s.icon, "color": s.color, "description": s.description}


@router.get("/subjects")
def list_subjects(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "student":
        return [subject_payload(s) | {"topics_total": len(s.topics)} for s in db.scalars(select(Subject).order_by(Subject.sort_order))]
    progress = topic_progress_map(db, user.id)
    return [subject_payload(s) | subject_progress(list(s.topics), progress) for s in enrolled_subjects(db, user.id)]


@router.get("/subjects/{subject_id}/topics")
def subject_topics(subject_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    counts = dict(
        db.execute(
            select(Question.topic_id, func.count()).where(Question.subject_id == subject_id, Question.status == "published").group_by(Question.topic_id)
        ).all()
    )
    progress = topic_progress_map(db, user.id, subject_id) if user.role == "student" else {}
    topics = [topic_view(t, progress.get(t.id)) | {"question_count": counts.get(t.id, 0)} for t in subject.topics]
    return {"subject": subject_payload(subject) | subject_progress(list(subject.topics), progress), "topics": topics}


@router.get("/topics/{topic_id}")
def topic_detail(topic_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    progress = topic_progress_map(db, user.id, topic.subject_id).get(topic_id) if user.role == "student" else None
    lesson = db.scalar(select(Lesson).where(Lesson.topic_id == topic_id))
    lesson_info = None
    if lesson:
        lp = db.get(LessonProgress, {"student_id": user.id, "lesson_id": lesson.id}) if user.role == "student" else None
        lesson_info = {
            "id": lesson.id,
            "title": lesson.title,
            "summary": lesson.summary,
            "estimated_minutes": lesson.estimated_minutes,
            "slide_count": len(lesson.slides),
            "current_slide": lp.current_slide if lp else 0,
            "completed": lp.completed if lp else False,
        }
    history = []
    if user.role == "student":
        sets = db.scalars(
            select(QuestionSet)
            .where(QuestionSet.owner_id == user.id, QuestionSet.topic_id == topic_id, QuestionSet.kind == "quiz", QuestionSet.status == "completed")
            .order_by(QuestionSet.completed_at.desc())
            .limit(5)
        )
        history = [{"id": s.id, "completed_at": s.completed_at, "percentage": (s.result or {}).get("percentage")} for s in sets]
    question_count = db.scalar(select(func.count()).select_from(Question).where(Question.topic_id == topic_id, Question.status == "published"))
    return {
        "topic": topic_view(topic, progress) | {"question_count": question_count},
        "subject": subject_payload(topic.subject),
        "lesson": lesson_info,
        "quiz_history": history,
    }


@router.get("/topics/{topic_id}/questions")
def topic_questions(topic_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    ensure_teaches_subject(db, teacher, topic.subject_id)
    questions = db.scalars(select(Question).where(Question.topic_id == topic_id, Question.status == "published").order_by(Question.year, Question.question_number))
    return [full_question(q) for q in questions]
