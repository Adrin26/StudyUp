from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import (
    AcademicYear,
    AuditLog,
    ClassStudent,
    LocalCredential,
    PasswordResetToken,
    Profile,
    SchoolClass,
    StudentSubject,
    Subject,
    TeacherSubject,
    utcnow,
)
from ..permissions import require_admin
from ..schemas import ImportIn, StudentClassIn, SubjectIdsIn, UserCreateIn, UserUpdateIn
from ..services import accounts, audit, enrolment, school_scope, user_import
from ..services.rate_limit import limiter

router = APIRouter(prefix="/api/admin/users", tags=["admin: users"])


def _summaries(db: Session, users: list[Profile]) -> list[dict]:
    ids = [u.id for u in users]
    classes: dict[str, dict] = {}
    teaching: dict[str, list[dict]] = {}
    homeroom: dict[str, list[dict]] = {}
    if ids:
        rows = db.execute(
            select(ClassStudent.student_id, SchoolClass.id, SchoolClass.name)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
            .where(ClassStudent.student_id.in_(ids), ClassStudent.status == "active", SchoolClass.status == "active")
            .order_by(AcademicYear.is_current.asc(), AcademicYear.start_date.asc())
        )
        for sid, cid, name in rows:  # later rows (current year) win
            classes[sid] = {"id": cid, "name": name}
        rows = db.execute(
            select(TeacherSubject.id, TeacherSubject.teacher_id, Subject.id, Subject.name, SchoolClass.id, SchoolClass.name)
            .join(Subject, Subject.id == TeacherSubject.subject_id)
            .join(SchoolClass, SchoolClass.id == TeacherSubject.class_id)
            .where(TeacherSubject.teacher_id.in_(ids), SchoolClass.status == "active")
            .order_by(Subject.sort_order, SchoolClass.name)
        )
        for aid, tid, subj_id, subj, cid, cname in rows:
            teaching.setdefault(tid, []).append({"id": aid, "subject": {"id": subj_id, "name": subj}, "class": {"id": cid, "name": cname}})
        for c in db.scalars(select(SchoolClass).where(SchoolClass.class_teacher_id.in_(ids), SchoolClass.status == "active").order_by(SchoolClass.name)):
            homeroom.setdefault(c.class_teacher_id, []).append({"id": c.id, "name": c.name})
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "username": u.username,
            "role": u.role,
            "status": u.status,
            "student_number": u.student_number,
            "staff_number": u.staff_number,
            "form": u.form,
            "department": u.department,
            "class": classes.get(u.id),
            "homeroom": homeroom.get(u.id, []),
            "teaching": teaching.get(u.id, []),
            "created_at": u.created_at,
            "last_login_at": u.last_login_at,
        }
        for u in users
    ]


def _detail(db: Session, user: Profile, admin: Profile) -> dict:
    out = _summaries(db, [user])[0]
    out["credentials_set"] = db.get(LocalCredential, user.id) is not None
    out["manageable"] = user.role != "admin"
    out["subjects"] = [
        {"id": s.id, "name": s.name}
        for s in db.scalars(
            select(Subject).join(StudentSubject, StudentSubject.subject_id == Subject.id).where(StudentSubject.student_id == user.id).order_by(Subject.sort_order)
        )
    ]
    out["enrolments"] = [
        {"class_id": c.id, "class_name": c.name, "class_status": c.status, "academic_year": y.name, "status": e.status, "enrolled_at": e.enrolled_at, "left_at": e.left_at}
        for e, c, y in db.execute(
            select(ClassStudent, SchoolClass, AcademicYear)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
            .where(ClassStudent.student_id == user.id)
            .order_by(ClassStudent.enrolled_at.desc())
        )
    ]
    activity = db.execute(
        select(AuditLog, Profile)
        .outerjoin(Profile, Profile.id == AuditLog.actor_id)
        .where(or_(AuditLog.resource_id == user.id, AuditLog.actor_id == user.id), or_(AuditLog.school_id == admin.school_id, AuditLog.school_id.is_(None)))
        .order_by(AuditLog.created_at.desc())
        .limit(15)
    )
    out["recent_activity"] = [
        {"id": e.id, "action": e.action, "details": e.details or {}, "created_at": e.created_at, "actor": {"id": a.id, "name": a.full_name} if a else None}
        for e, a in activity
    ]
    return out


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


@router.get("")
def list_users(
    q: str | None = Query(None, max_length=100),
    role: str | None = Query(None, pattern="^(admin|teacher|student)$"),
    status_: str | None = Query(None, alias="status", pattern="^(active|disabled)$"),
    class_id: str | None = None,
    subject_id: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Profile).where(Profile.school_id == admin.school_id)
    if q and q.strip():
        term = q.strip().lower()
        stmt = stmt.where(or_(*(
            func.lower(col).contains(term, autoescape=True)
            for col in (Profile.full_name, Profile.email, Profile.username, Profile.student_number, Profile.staff_number)
        )))
    if role:
        stmt = stmt.where(Profile.role == role)
    if status_:
        stmt = stmt.where(Profile.status == status_)
    if class_id:
        stmt = stmt.where(or_(
            Profile.id.in_(select(ClassStudent.student_id).where(ClassStudent.class_id == class_id, ClassStudent.status == "active")),
            Profile.id.in_(select(TeacherSubject.teacher_id).where(TeacherSubject.class_id == class_id)),
            Profile.id.in_(select(SchoolClass.class_teacher_id).where(SchoolClass.id == class_id)),
        ))
    if subject_id:
        stmt = stmt.where(or_(
            Profile.id.in_(select(StudentSubject.student_id).where(StudentSubject.subject_id == subject_id)),
            Profile.id.in_(select(TeacherSubject.teacher_id).where(TeacherSubject.subject_id == subject_id)),
        ))
    if created_from:
        stmt = stmt.where(Profile.created_at >= _day_start(created_from))
    if created_to:
        stmt = stmt.where(Profile.created_at < _day_start(created_to) + timedelta(days=1))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    users = list(db.scalars(stmt.order_by(func.lower(Profile.full_name)).offset((page - 1) * page_size).limit(page_size)))
    return {"items": _summaries(db, users), "total": total, "page": page, "page_size": page_size}


@router.get("/{user_id}")
def get_user(user_id: str, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _detail(db, school_scope.member(db, user_id, admin), admin)


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email, username, student ID or staff ID is already in use") from None


def create_account(db: Session, body: UserCreateIn, admin: Profile, request: Request | None, *, via: str = "form", username: str | None = None) -> Profile:
    """Create a student or teacher in the admin's school. Validates references; the caller commits."""
    klass = school_scope.school_class(db, body.class_id, admin, active=True) if body.class_id else None
    subjects = school_scope.subjects(db, body.subject_ids)
    pairs = []
    for pair in dict.fromkeys((p.subject_id, p.class_id) for p in body.assignments):
        school_scope.subjects(db, [pair[0]])
        pairs.append((pair[0], school_scope.school_class(db, pair[1], admin, active=True).id))

    user = Profile(
        email=body.email,
        username=username or body.username or accounts.suggest_username(db, body.email),
        full_name=body.full_name,
        role=body.role,
        status=body.status,
        school_id=admin.school_id,
        student_number=body.student_number,
        staff_number=body.staff_number,
        form=body.form,
        department=body.department,
    )
    db.add(user)
    db.flush()
    if klass:
        enrolment.enrol(db, user, klass)
        if not subjects:  # default to what the class is taught
            subjects = school_scope.subjects(db, list(db.scalars(select(TeacherSubject.subject_id).where(TeacherSubject.class_id == klass.id).distinct())))
    for s in subjects:
        db.add(StudentSubject(student_id=user.id, subject_id=s.id))
    for subject_id, class_id in pairs:
        db.add(TeacherSubject(teacher_id=user.id, subject_id=subject_id, class_id=class_id))
    audit.record(db, "user.create", "profile", user.id, actor=admin, request=request, details={
        "role": user.role, "username": user.username, "via": via, "class": klass.name if klass else None, "teaching_assignments": len(pairs),
    })
    return user


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreateIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    accounts.require_local_accounts()
    accounts.raise_conflicts(accounts.conflicts(db, admin.school_id, body.model_dump(include=set(accounts.FIELD_LABELS))))
    user = create_account(db, body, admin, request)
    invitation = None
    if body.send_invite and user.is_active:
        delivered = accounts.send_set_password_link(db, user, admin, request, invitation=True)
        invitation = {"delivered": delivered, "message": accounts.delivery_message(delivered)}
    _commit_or_conflict(db)
    return {"user": _detail(db, user, admin), "invitation": invitation}


@router.patch("/{user_id}")
def update_user(user_id: str, body: UserUpdateIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    user = school_scope.managed_member(db, user_id, admin)
    data = body.model_dump(exclude_unset=True)
    for field in ("full_name", "email"):
        if field in data and data[field] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field.replace('_', ' ').capitalize()} cannot be empty")
    student_only, teacher_only = {"student_number", "form"}, {"staff_number", "department"}
    wrong = (teacher_only if user.role == "student" else student_only) & {k for k, v in data.items() if v is not None}
    if wrong:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{', '.join(sorted(wrong))} does not apply to a {user.role}")
    required = "student_number" if user.role == "student" else "staff_number"
    if required in data and not data[required]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Student ID is required" if user.role == "student" else "Staff ID is required")
    accounts.raise_conflicts(accounts.conflicts(db, user.school_id, {k: v for k, v in data.items() if k in accounts.FIELD_LABELS}, exclude_id=user.id))

    changed = sorted(k for k, v in data.items() if getattr(user, k) != v)
    for k in changed:
        setattr(user, k, data[k])
    if changed:
        audit.record(db, "user.update", "profile", user.id, actor=admin, request=request, details={"fields": ", ".join(changed)})
    _commit_or_conflict(db)
    return _detail(db, user, admin)


def _set_status(db: Session, user: Profile, new_status: str, admin: Profile, request: Request) -> dict:
    if user.status == new_status:
        return _detail(db, user, admin)
    user.status = new_status
    if new_status == "disabled":
        # Outstanding set/reset-password links must not revive a disabled account.
        db.execute(update(PasswordResetToken).where(PasswordResetToken.profile_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=utcnow()))
    audit.record(db, "user.disable" if new_status == "disabled" else "user.reactivate", "profile", user.id, actor=admin, request=request,
                 details={"role": user.role})
    db.commit()
    return _detail(db, user, admin)


@router.post("/{user_id}/disable")
def disable_user(user_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_status(db, school_scope.managed_member(db, user_id, admin), "disabled", admin, request)


@router.post("/{user_id}/reactivate")
def reactivate_user(user_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_status(db, school_scope.managed_member(db, user_id, admin), "active", admin, request)


@router.post("/{user_id}/reset-password")
def admin_reset_password(user_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    """Send a single-use set-password link. The admin never sees or chooses the password."""
    accounts.require_local_accounts()
    user = school_scope.managed_member(db, user_id, admin)
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Reactivate the account before resetting its password")
    limiter.check_and_hit(f"admin-reset:{user.id}", 5, get_settings().login_window_minutes * 60)
    first_time = db.get(LocalCredential, user.id) is None
    delivered = accounts.send_set_password_link(db, user, admin, request, invitation=first_time)
    db.commit()
    return {"initiated": True, "delivered": delivered, "message": accounts.delivery_message(delivered)}


@router.put("/{user_id}/class")
def set_student_class(user_id: str, body: StudentClassIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    """Place a student in a class: enrols, transfers within the same academic year, or withdraws (class_id = null)."""
    student = school_scope.member(db, user_id, admin, "student")
    current = enrolment.current_class(db, student.id)
    if body.class_id is None:
        if current is None:
            return _detail(db, student, admin)
        enrolment.withdraw(db, student.id, current)
        audit.record(db, "enrolment.withdraw", "profile", student.id, actor=admin, request=request, details={"class": current.name})
    else:
        target = school_scope.school_class(db, body.class_id, admin, active=True)
        if current is not None and current.academic_year_id == target.academic_year_id:
            if current.id != target.id:
                enrolment.transfer(db, student, target)
                audit.record(db, "enrolment.transfer", "profile", student.id, actor=admin, request=request, details={"from": current.name, "to": target.name})
        else:
            enrolment.enrol(db, student, target)
            audit.record(db, "enrolment.enrol", "profile", student.id, actor=admin, request=request, details={"class": target.name})
    db.commit()
    return _detail(db, student, admin)


@router.put("/{user_id}/subjects")
def set_student_subjects(user_id: str, body: SubjectIdsIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    student = school_scope.member(db, user_id, admin, "student")
    subjects = school_scope.subjects(db, body.subject_ids)
    db.execute(delete(StudentSubject).where(StudentSubject.student_id == student.id))
    for s in subjects:
        db.add(StudentSubject(student_id=student.id, subject_id=s.id))
    audit.record(db, "user.subjects_update", "profile", student.id, actor=admin, request=request, details={"subjects": len(subjects)})
    db.commit()
    return _detail(db, student, admin)


@router.post("/import/preview")
def import_preview(body: ImportIn, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return user_import.public(user_import.analyse(db, admin, body.csv))


@router.post("/import/confirm")
def import_confirm(body: ImportIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    accounts.require_local_accounts()
    analysis = user_import.analyse(db, admin, body.csv)
    if analysis["header_errors"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(analysis["header_errors"]))
    created, failed = [], []
    for row in analysis["rows"]:
        if row["status"] != "ready":
            failed.append({"line": row["line"], "email": row["email"], "errors": row["errors"]})
            continue
        try:
            with db.begin_nested():
                user = create_account(db, row["_model"], admin, request, via="import", username=row["username"])
                delivered = None
                if body.send_invites and user.is_active:
                    delivered = accounts.send_set_password_link(db, user, admin, request, invitation=True)
        except (HTTPException, IntegrityError) as exc:
            message = exc.detail if isinstance(exc, HTTPException) else "Email, username or ID is already in use"
            failed.append({"line": row["line"], "email": row["email"], "errors": [message]})
            continue
        created.append({"line": row["line"], "id": user.id, "full_name": user.full_name, "email": user.email, "username": user.username, "invitation_delivered": delivered})
    audit.record(db, "user.import", "profile", None, actor=admin, request=request, details={"created": len(created), "failed": len(failed)})
    db.commit()
    return {"created": created, "failed": failed, "summary": {"created": len(created), "failed": len(failed)}}
