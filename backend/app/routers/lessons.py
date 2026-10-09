from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Lesson, LessonProgress, Profile
from ..schemas import LessonProgressIn
from ..permissions import require_student
from ..security import get_current_user
from ..services import gamification

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/topic/{topic_id}")
def lesson_for_topic(topic_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    lesson = db.scalar(select(Lesson).where(Lesson.topic_id == topic_id))
    if lesson is None or (user.role == "student" and lesson.status != "published"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No lesson for this topic yet")
    lp = db.get(LessonProgress, {"student_id": user.id, "lesson_id": lesson.id}) if user.role == "student" else None
    return {
        "id": lesson.id,
        "topic_id": lesson.topic_id,
        "title": lesson.title,
        "summary": lesson.summary,
        "estimated_minutes": lesson.estimated_minutes,
        "current_slide": lp.current_slide if lp else 0,
        "completed": lp.completed if lp else False,
        "slides": [{"id": s.id, "position": s.position, "type": s.slide_type, "title": s.title, "content": s.content} for s in lesson.slides],
    }


@router.put("/{lesson_id}/progress")
def save_progress(lesson_id: str, body: LessonProgressIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None or lesson.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    lp = db.get(LessonProgress, {"student_id": student.id, "lesson_id": lesson_id})
    if lp is None:
        lp = LessonProgress(student_id=student.id, lesson_id=lesson_id, current_slide=0, completed=False)
        db.add(lp)
    xp = 0
    if body.completed and not lp.completed:
        xp = gamification.award_xp(db, student, gamification.XP_LESSON_COMPLETE, "lesson_complete", lesson.id)
        gamification.touch_streak(student)
    lp.current_slide = min(body.current_slide, max(len(lesson.slides) - 1, 0))
    lp.completed = lp.completed or body.completed
    db.commit()
    return {"current_slide": lp.current_slide, "completed": lp.completed, "xp_gained": xp}
