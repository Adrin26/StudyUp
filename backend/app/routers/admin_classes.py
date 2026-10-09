from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AcademicYear, ClassStudent, Profile, SchoolClass, Subject, TeacherSubject
from ..permissions import require_admin
from ..schemas import ClassCreateIn, ClassUpdateIn, EnrolIn, TeacherAssignmentIn, TransferIn
from ..services import audit, enrolment, school_scope

router = APIRouter(prefix="/api/admin", tags=["admin: classes"])


def _ref(p: Profile | None) -> dict | None:
    return {"id": p.id, "name": p.full_name, "status": p.status} if p else None


def _class_rows(db: Session, classes: list[SchoolClass]) -> list[dict]:
    ids = [c.id for c in classes]
    students = dict(db.execute(
        select(ClassStudent.class_id, func.count()).where(ClassStudent.class_id.in_(ids), ClassStudent.status == "active").group_by(ClassStudent.class_id)
    ).all()) if ids else {}
    subjects = dict(db.execute(
        select(TeacherSubject.class_id, func.count(func.distinct(TeacherSubject.subject_id))).where(TeacherSubject.class_id.in_(ids)).group_by(TeacherSubject.class_id)
    ).all()) if ids else {}
    years = {y.id: y for y in db.scalars(select(AcademicYear).where(AcademicYear.id.in_({c.academic_year_id for c in classes})))} if ids else {}
    teachers = {p.id: p for p in db.scalars(select(Profile).where(Profile.id.in_({c.class_teacher_id for c in classes if c.class_teacher_id})))} if ids else {}
    return [
        {
            "id": c.id,
            "name": c.name,
            "form": c.form,
            "status": c.status,
            "academic_year": {"id": c.academic_year_id, "name": years[c.academic_year_id].name, "is_current": years[c.academic_year_id].is_current},
            "class_teacher": _ref(teachers.get(c.class_teacher_id)),
            "student_count": students.get(c.id, 0),
            "subject_count": subjects.get(c.id, 0),
        }
        for c in classes
    ]


def _assignment_rows(db: Session, stmt) -> list[dict]:
    rows = db.execute(
        stmt.add_columns(Profile, Subject, SchoolClass, AcademicYear)
        .join(Profile, Profile.id == TeacherSubject.teacher_id)
        .join(Subject, Subject.id == TeacherSubject.subject_id)
        .join(SchoolClass, SchoolClass.id == TeacherSubject.class_id)
        .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
        .order_by(SchoolClass.name, Subject.sort_order, Profile.full_name)
    )
    return [
        {
            "id": ts.id,
            "teacher": _ref(t),
            "subject": {"id": s.id, "name": s.name},
            "class": {"id": c.id, "name": c.name, "status": c.status, "academic_year": y.name},
        }
        for ts, t, s, c, y in rows
    ]


def _class_detail(db: Session, klass: SchoolClass) -> dict:
    out = _class_rows(db, [klass])[0]
    rows = db.execute(
        select(ClassStudent, Profile).join(Profile, Profile.id == ClassStudent.student_id).where(ClassStudent.class_id == klass.id).order_by(Profile.full_name)
    ).all()
    out["students"] = [
        {"id": p.id, "full_name": p.full_name, "student_number": p.student_number, "status": p.status, "enrolled_at": e.enrolled_at}
        for e, p in rows if e.status == "active"
    ]
    out["former_students"] = [
        {"id": p.id, "full_name": p.full_name, "student_number": p.student_number, "status": e.status, "enrolled_at": e.enrolled_at, "left_at": e.left_at}
        for e, p in rows if e.status != "active"
    ]
    out["teaching"] = _assignment_rows(db, select(TeacherSubject).where(TeacherSubject.class_id == klass.id))
    return out


def _check_class_teacher(db: Session, teacher_id: str | None, admin: Profile) -> Profile | None:
    return school_scope.active_teacher(db, teacher_id, admin) if teacher_id else None


def _ensure_unique_name(db: Session, academic_year_id: str, name: str, exclude_id: str | None = None) -> None:
    stmt = select(SchoolClass.id).where(SchoolClass.academic_year_id == academic_year_id, func.lower(SchoolClass.name) == name.strip().lower())
    if exclude_id:
        stmt = stmt.where(SchoolClass.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A class named {name.strip()} already exists in that academic year")


@router.get("/lookups")
def lookups(admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    """Options for admin forms: subjects, active classes, teachers and academic years in this school."""
    years = list(db.scalars(select(AcademicYear).where(AcademicYear.school_id == admin.school_id).order_by(AcademicYear.start_date.desc())))
    year_names = {y.id: y.name for y in years}
    classes = db.scalars(
        select(SchoolClass)
        .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
        .where(SchoolClass.school_id == admin.school_id, SchoolClass.status == "active")
        .order_by(AcademicYear.is_current.desc(), AcademicYear.start_date.desc(), SchoolClass.form, SchoolClass.name)
    )
    return {
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in db.scalars(select(Subject).order_by(Subject.sort_order))],
        "classes": [{"id": c.id, "name": c.name, "form": c.form, "academic_year_id": c.academic_year_id, "academic_year": year_names[c.academic_year_id]} for c in classes],
        "teachers": [
            {"id": t.id, "name": t.full_name, "status": t.status}
            for t in db.scalars(select(Profile).where(Profile.school_id == admin.school_id, Profile.role == "teacher").order_by(Profile.full_name))
        ],
        "academic_years": [{"id": y.id, "name": y.name, "is_current": y.is_current} for y in years],
    }


@router.get("/classes")
def list_classes(
    academic_year_id: str | None = None,
    status_: str = Query("active", alias="status", pattern="^(active|archived|all)$"),
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(SchoolClass)
        .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
        .where(SchoolClass.school_id == admin.school_id)
        .order_by(AcademicYear.start_date.desc(), SchoolClass.form, SchoolClass.name)
    )
    if academic_year_id:
        stmt = stmt.where(SchoolClass.academic_year_id == academic_year_id)
    if status_ != "all":
        stmt = stmt.where(SchoolClass.status == status_)
    return _class_rows(db, list(db.scalars(stmt)))


@router.post("/classes", status_code=status.HTTP_201_CREATED)
def create_class(body: ClassCreateIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    year = school_scope.academic_year(db, body.academic_year_id, admin)
    _ensure_unique_name(db, year.id, body.name)
    teacher = _check_class_teacher(db, body.class_teacher_id, admin)
    klass = SchoolClass(school_id=admin.school_id, academic_year_id=year.id, name=body.name.strip(), form=body.form, class_teacher_id=teacher.id if teacher else None)
    db.add(klass)
    db.flush()
    audit.record(db, "class.create", "class", klass.id, actor=admin, request=request, details={
        "name": klass.name, "year": year.name, "class_teacher": teacher.full_name if teacher else None,
    })
    db.commit()
    return _class_detail(db, klass)


@router.get("/classes/{class_id}")
def get_class(class_id: str, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _class_detail(db, school_scope.school_class(db, class_id, admin))


@router.patch("/classes/{class_id}")
def update_class(class_id: str, body: ClassUpdateIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    klass = school_scope.school_class(db, class_id, admin, active=True)
    data = body.model_dump(exclude_unset=True)
    details: dict = {}
    if data.get("name") is not None and data["name"].strip() != klass.name:
        _ensure_unique_name(db, klass.academic_year_id, data["name"], exclude_id=klass.id)
        details["name"] = f"{klass.name} → {data['name'].strip()}"
        klass.name = data["name"].strip()
    if data.get("form") is not None and data["form"] != klass.form:
        details["form"] = f"{klass.form} → {data['form']}"
        klass.form = data["form"]
    if "class_teacher_id" in data and data["class_teacher_id"] != klass.class_teacher_id:
        old = db.get(Profile, klass.class_teacher_id) if klass.class_teacher_id else None
        new = _check_class_teacher(db, data["class_teacher_id"], admin)
        details["class_teacher"] = f"{old.full_name if old else 'none'} → {new.full_name if new else 'none'}"
        klass.class_teacher_id = new.id if new else None
    if details:
        audit.record(db, "class.update", "class", klass.id, actor=admin, request=request, details={"class": klass.name, **details})
    db.commit()
    return _class_detail(db, klass)


def _set_class_status(db: Session, klass: SchoolClass, new_status: str, admin: Profile, request: Request) -> dict:
    if klass.status != new_status:
        if new_status == "active":
            _ensure_unique_name(db, klass.academic_year_id, klass.name, exclude_id=klass.id)
        klass.status = new_status
        audit.record(db, "class.archive" if new_status == "archived" else "class.restore", "class", klass.id, actor=admin, request=request,
                     details={"class": klass.name})
        db.commit()
    return _class_detail(db, klass)


@router.post("/classes/{class_id}/archive")
def archive_class(class_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    """Keeps the roster and enrolment history; teachers lose access through this class."""
    return _set_class_status(db, school_scope.school_class(db, class_id, admin), "archived", admin, request)


@router.post("/classes/{class_id}/restore")
def restore_class(class_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_class_status(db, school_scope.school_class(db, class_id, admin), "active", admin, request)


@router.get("/classes/{class_id}/eligible-students")
def eligible_students(
    class_id: str,
    q: str | None = Query(None, max_length=100),
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Active students not yet in any class for this class's academic year."""
    klass = school_scope.school_class(db, class_id, admin)
    placed = (
        select(ClassStudent.student_id)
        .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
        .where(SchoolClass.academic_year_id == klass.academic_year_id, ClassStudent.status == "active")
    )
    stmt = select(Profile).where(
        Profile.school_id == admin.school_id, Profile.role == "student", Profile.status == "active", Profile.id.not_in(placed)
    )
    if q and q.strip():
        term = q.strip().lower()
        stmt = stmt.where(or_(func.lower(Profile.full_name).contains(term, autoescape=True), func.lower(Profile.student_number).contains(term, autoescape=True)))
    return [
        {"id": p.id, "full_name": p.full_name, "student_number": p.student_number, "form": p.form}
        for p in db.scalars(stmt.order_by(Profile.form.desc(), Profile.full_name).limit(200))
    ]


@router.post("/classes/{class_id}/students")
def enrol_students(class_id: str, body: EnrolIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    klass = school_scope.school_class(db, class_id, admin, active=True)
    enrolled, already, failed = [], [], []
    for sid in dict.fromkeys(body.student_ids):
        try:
            student = school_scope.member(db, sid, admin, "student")
            result = enrolment.enrol(db, student, klass)
        except HTTPException as exc:
            failed.append({"id": sid, "reason": exc.detail})
            continue
        if result == "already":
            already.append(sid)
        else:
            enrolled.append(sid)
            audit.record(db, "enrolment.enrol", "profile", sid, actor=admin, request=request, details={"class": klass.name})
    db.commit()
    return {"enrolled": enrolled, "already_enrolled": already, "failed": failed, "class": _class_detail(db, klass)}


@router.post("/classes/{class_id}/students/{student_id}/transfer")
def transfer_student(class_id: str, student_id: str, body: TransferIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    source = school_scope.school_class(db, class_id, admin)
    target = school_scope.school_class(db, body.to_class_id, admin, active=True)
    student = school_scope.member(db, student_id, admin, "student")
    row = db.get(ClassStudent, (source.id, student.id))
    if row is None or row.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This student is not enrolled in the class")
    if target.academic_year_id != source.academic_year_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Transfers stay within one academic year. To move a student into next year's class, enrol them there.",
        )
    enrolment.transfer(db, student, target)
    audit.record(db, "enrolment.transfer", "profile", student.id, actor=admin, request=request, details={"from": source.name, "to": target.name})
    db.commit()
    return _class_detail(db, source)


@router.delete("/classes/{class_id}/students/{student_id}")
def withdraw_student(class_id: str, student_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    klass = school_scope.school_class(db, class_id, admin)
    school_scope.member(db, student_id, admin, "student")
    enrolment.withdraw(db, student_id, klass)
    audit.record(db, "enrolment.withdraw", "profile", student_id, actor=admin, request=request, details={"class": klass.name})
    db.commit()
    return _class_detail(db, klass)


@router.get("/teacher-assignments")
def list_teacher_assignments(
    teacher_id: str | None = None,
    class_id: str | None = None,
    subject_id: str | None = None,
    include_archived: bool = False,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(TeacherSubject).where(SchoolClass.school_id == admin.school_id)
    if not include_archived:
        stmt = stmt.where(SchoolClass.status == "active")
    if teacher_id:
        stmt = stmt.where(TeacherSubject.teacher_id == teacher_id)
    if class_id:
        stmt = stmt.where(TeacherSubject.class_id == class_id)
    if subject_id:
        stmt = stmt.where(TeacherSubject.subject_id == subject_id)
    return _assignment_rows(db, stmt)


@router.post("/teacher-assignments", status_code=status.HTTP_201_CREATED)
def create_teacher_assignment(body: TeacherAssignmentIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    teacher = school_scope.active_teacher(db, body.teacher_id, admin)
    subject = school_scope.subjects(db, [body.subject_id])[0]
    klass = school_scope.school_class(db, body.class_id, admin, active=True)
    exists = db.scalar(select(TeacherSubject.id).where(
        TeacherSubject.teacher_id == teacher.id, TeacherSubject.subject_id == subject.id, TeacherSubject.class_id == klass.id
    ))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{teacher.full_name} already teaches {subject.name} to {klass.name}")
    ts = TeacherSubject(teacher_id=teacher.id, subject_id=subject.id, class_id=klass.id)
    db.add(ts)
    db.flush()
    audit.record(db, "teacher_assignment.create", "profile", teacher.id, actor=admin, request=request,
                 details={"subject": subject.name, "class": klass.name})
    db.commit()
    return _assignment_rows(db, select(TeacherSubject).where(TeacherSubject.id == ts.id))[0]


@router.delete("/teacher-assignments/{assignment_id}")
def delete_teacher_assignment(assignment_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    ts = db.get(TeacherSubject, assignment_id)
    klass = db.get(SchoolClass, ts.class_id) if ts else None
    if ts is None or klass is None or klass.school_id != admin.school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    subject = db.get(Subject, ts.subject_id)
    audit.record(db, "teacher_assignment.delete", "profile", ts.teacher_id, actor=admin, request=request,
                 details={"subject": subject.name if subject else None, "class": klass.name})
    db.delete(ts)
    db.commit()
    return {"deleted": assignment_id}
