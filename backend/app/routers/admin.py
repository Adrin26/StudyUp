from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assignment, AuditLog, Profile, SchoolClass, Subject, TeacherSubject, Topic
from ..permissions import require_admin
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

    school_classes = select(SchoolClass.id).where(SchoolClass.school_id == admin.school_id)
    school_teachers = select(Profile.id).where(Profile.school_id == admin.school_id, Profile.role == "teacher")
    today = today_my()

    classes_without_teacher = list(db.scalars(
        select(SchoolClass.name).where(SchoolClass.school_id == admin.school_id, SchoolClass.class_teacher_id.is_(None)).order_by(SchoolClass.name)
    ))
    classes_without_subjects = list(db.scalars(
        select(SchoolClass.name)
        .where(SchoolClass.school_id == admin.school_id, ~SchoolClass.id.in_(select(TeacherSubject.class_id)))
        .order_by(SchoolClass.name)
    ))
    subjects_without_topics = list(db.scalars(
        select(Subject.name).where(~Subject.id.in_(select(Topic.subject_id))).order_by(Subject.sort_order)
    ))
    alerts = (
        [{"kind": "class_without_teacher", "message": f"Class {n} has no class teacher"} for n in classes_without_teacher]
        + [{"kind": "class_without_subjects", "message": f"Class {n} has no subject teachers assigned"} for n in classes_without_subjects]
        + [{"kind": "subject_without_topics", "message": f"{n} has no topics yet"} for n in subjects_without_topics]
    )

    recent_accounts = db.scalars(
        select(Profile).where(Profile.school_id == admin.school_id).order_by(Profile.created_at.desc()).limit(5)
    )
    recent_activity = db.execute(_school_audit(admin).order_by(AuditLog.created_at.desc()).limit(8)).all()

    return {
        "counts": {
            "active_students": members("student"),
            "active_teachers": members("teacher"),
            "classes": db.scalar(select(func.count()).select_from(school_classes.subquery())),
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
