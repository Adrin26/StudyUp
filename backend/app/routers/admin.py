from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assignment, AuditLog, ClassStudent, Lesson, Profile, Question, SchoolClass, Subject, TeacherSubject, Topic
from ..permissions import require_admin
from ..services import school_scope
from ..services.gamification import today_my

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _audit_item(entry: AuditLog, actor: Profile | None) -> dict:
    return {
        "id": entry.id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "details": entry.details or {},
        "ip_address": entry.ip_address,
        "created_at": entry.created_at,
        "actor": {"id": actor.id, "name": actor.full_name, "role": actor.role} if actor else None,
    }


def _school_audit(admin: Profile):
    return select(AuditLog, Profile).outerjoin(Profile, Profile.id == AuditLog.actor_id).where(
        or_(AuditLog.school_id == admin.school_id, AuditLog.school_id.is_(None))
    )


@router.get("/overview")
def overview(admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    def members(role: str):
        return db.scalar(select(func.count()).select_from(Profile).where(Profile.school_id == admin.school_id, Profile.role == role, Profile.status == "active"))

    active_classes = select(SchoolClass).where(SchoolClass.school_id == admin.school_id, SchoolClass.status == "active")
    school_teachers = select(Profile.id).where(Profile.school_id == admin.school_id, Profile.role == "teacher")
    today = today_my()
    year = school_scope.current_year(db, admin.school_id)

    classes_without_teacher = list(db.scalars(
        active_classes.with_only_columns(SchoolClass.name).where(SchoolClass.class_teacher_id.is_(None)).order_by(SchoolClass.name)
    ))
    classes_without_subjects = list(db.scalars(
        active_classes.with_only_columns(SchoolClass.name).where(~SchoolClass.id.in_(select(TeacherSubject.class_id))).order_by(SchoolClass.name)
    ))
    subjects_without_topics = list(db.scalars(
        select(Subject.name).where(~Subject.id.in_(select(Topic.subject_id))).order_by(Subject.sort_order)
    ))
    alerts = [{"kind": "no_current_year", "message": "No current academic year is set", "link": "/admin/school"}] if year is None else []
    alerts += (
        [{"kind": "class_without_teacher", "message": f"Class {n} has no class teacher", "link": "/admin/classes"} for n in classes_without_teacher]
        + [{"kind": "class_without_subjects", "message": f"Class {n} has no subject teachers assigned", "link": "/admin/teacher-assignments"} for n in classes_without_subjects]
        + [{"kind": "subject_without_topics", "message": f"{n} has no topics yet", "link": None} for n in subjects_without_topics]
    )
    if year is not None:
        placed = (
            select(ClassStudent.student_id)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(SchoolClass.academic_year_id == year.id, ClassStudent.status == "active")
        )
        unplaced = db.scalar(select(func.count()).select_from(Profile).where(
            Profile.school_id == admin.school_id, Profile.role == "student", Profile.status == "active", Profile.id.not_in(placed)
        ))
        if unplaced:
            alerts.append({"kind": "students_without_class", "message": f"{unplaced} active student{'s' if unplaced != 1 else ''} not in a class for {year.name}", "link": "/admin/users?role=student"})
    idle_teachers = db.scalar(select(func.count()).select_from(Profile).where(
        Profile.school_id == admin.school_id, Profile.role == "teacher", Profile.status == "active",
        Profile.id.not_in(select(TeacherSubject.teacher_id)),
        Profile.id.not_in(select(SchoolClass.class_teacher_id).where(SchoolClass.class_teacher_id.is_not(None))),
    ))
    if idle_teachers:
        alerts.append({"kind": "teachers_without_assignments", "message": f"{idle_teachers} active teacher{'s' if idle_teachers != 1 else ''} with no class or subject", "link": "/admin/teacher-assignments"})

    lessons_by_subject = dict(db.execute(
        select(Topic.subject_id, func.count(func.distinct(Topic.id))).join(Lesson, Lesson.topic_id == Topic.id).group_by(Topic.subject_id)
    ).all())
    questions_by_subject = dict(db.execute(
        select(Topic.subject_id, func.count(func.distinct(Topic.id))).join(Question, Question.topic_id == Topic.id)
        .where(Question.status == "published").group_by(Topic.subject_id)
    ).all())
    topics_by_subject = dict(db.execute(select(Topic.subject_id, func.count()).group_by(Topic.subject_id)).all())
    content = [
        {
            "subject": s.name,
            "topics": topics_by_subject.get(s.id, 0),
            "topics_with_lessons": lessons_by_subject.get(s.id, 0),
            "topics_with_questions": questions_by_subject.get(s.id, 0),
        }
        for s in db.scalars(select(Subject).order_by(Subject.sort_order))
    ]

    recent_accounts = db.scalars(
        select(Profile).where(Profile.school_id == admin.school_id).order_by(Profile.created_at.desc()).limit(5)
    )
    recent_activity = db.execute(_school_audit(admin).order_by(AuditLog.created_at.desc()).limit(8)).all()

    return {
        "current_academic_year": {"id": year.id, "name": year.name, "start_date": year.start_date, "end_date": year.end_date} if year else None,
        "content": content,
        "counts": {
            "active_students": members("student"),
            "active_teachers": members("teacher"),
            "classes": db.scalar(select(func.count()).select_from(active_classes.subquery())),
            "subjects": db.scalar(select(func.count()).select_from(Subject)),
            "topics": db.scalar(select(func.count()).select_from(Topic)),
            "active_assignments": db.scalar(
                select(func.count()).select_from(Assignment).where(
                    Assignment.teacher_id.in_(school_teachers), or_(Assignment.due_date.is_(None), Assignment.due_date >= today)
                )
            ),
        },
        "alerts": alerts,
        "recent_accounts": [
            {"id": p.id, "name": p.full_name, "role": p.role, "status": p.status, "created_at": p.created_at} for p in recent_accounts
        ],
        "recent_activity": [_audit_item(e, a) for e, a in recent_activity],
    }


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    action: str | None = Query(None, max_length=60),
    actor_id: str | None = None,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = _school_audit(admin)
    if action:
        query = query.where(AuditLog.action.startswith(action))
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    actions = sorted(db.scalars(
        select(AuditLog.action).where(or_(AuditLog.school_id == admin.school_id, AuditLog.school_id.is_(None))).distinct()
    ))
    return {"items": [_audit_item(e, a) for e, a in rows], "total": total, "page": page, "page_size": page_size, "actions": actions}
