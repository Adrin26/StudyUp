from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assignment, AssignmentStudent, Badge, Profile, StudentBadge, Subject, Topic, XPEvent
from ..permissions import require_student
from ..services import assignment_rules
from ..services.progress import enrolled_subjects, student_stats, subject_progress, topic_progress_map, topic_view
from ..services.recommendations import recommend

router = APIRouter(prefix="/api/students/me", tags=["students"])


def _badges(db: Session, student: Profile) -> list[dict]:
    owned = {
        sb.badge_id: sb.earned_at for sb in db.scalars(select(StudentBadge).where(StudentBadge.student_id == student.id))
    }
    return [
        {"code": b.code, "name": b.name, "description": b.description, "icon": b.icon, "earned": b.id in owned, "earned_at": owned.get(b.id)}
        for b in db.scalars(select(Badge).order_by(Badge.xp_reward))
    ]


def _assignments(db: Session, student: Profile) -> list[dict]:
    rows = db.execute(
        select(Assignment, AssignmentStudent, Profile.full_name, Subject.name)
        .join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
        .join(Profile, Profile.id == Assignment.teacher_id)
        .join(Subject, Subject.id == Assignment.subject_id)
        .where(AssignmentStudent.student_id == student.id)
        .order_by(AssignmentStudent.status, Assignment.created_at.desc())
    ).all()
    topics = {t.id: t.name for t in db.scalars(select(Topic))}
    return [
        {
            "id": a.id,
            "title": a.title,
            "instructions": a.instructions,
            "teacher": teacher,
            "subject": subject,
            "topic": topics.get(a.topic_id),
            "set_id": a.set_id,
            "due_date": a.due_date,
            "available_from": a.available_from,
            "open": assignment_rules.is_open(a),
            "status": s.status,
            "score": s.score if assignment_rules.answers_visible(a) else None,
        }
        for a, s, teacher, subject in rows
    ]


@router.get("/dashboard")
def dashboard(student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    progress = topic_progress_map(db, student.id)
    subjects = []
    for s in enrolled_subjects(db, student.id):
        topics = [t for t in s.topics if t.status == "published"]
        sp = subject_progress(topics, progress)
        weakest = min((topic_view(t, progress[t.id]) for t in topics if t.id in progress and progress[t.id].attempts_count), key=lambda t: t["mastery"], default=None)
        subjects.append({"id": s.id, "name": s.name, "icon": s.icon, "color": s.color, **sp, "weakest_topic": weakest})
    return {
        "stats": student_stats(db, student),
        "subjects": subjects,
        "recommendations": recommend(db, student),
        "assignments": [a for a in _assignments(db, student) if a["status"] == "assigned"],
        "badges": _badges(db, student),
    }


@router.get("/progress")
def my_progress(student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    progress = topic_progress_map(db, student.id)
    return {
        "stats": student_stats(db, student),
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "color": s.color,
                **subject_progress([t for t in s.topics if t.status == "published"], progress),
                "topics": [topic_view(t, progress.get(t.id)) for t in s.topics],
            }
            for s in enrolled_subjects(db, student.id)
        ],
    }


@router.get("/assignments")
def my_assignments(student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    return _assignments(db, student)


@router.get("/badges")
def my_badges(student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    return _badges(db, student)


@router.get("/xp")
def my_xp(student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    events = db.scalars(select(XPEvent).where(XPEvent.student_id == student.id).order_by(XPEvent.created_at.desc()).limit(50))
    totals = dict(db.execute(select(XPEvent.reason, func.sum(XPEvent.amount)).where(XPEvent.student_id == student.id).group_by(XPEvent.reason)).all())
    return {
        "total": student.xp,
        "by_reason": totals,
        "recent": [{"id": e.id, "amount": e.amount, "reason": e.reason, "created_at": e.created_at} for e in events],
    }
