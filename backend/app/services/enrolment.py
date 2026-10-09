"""Class enrolment rules.

A student has at most one active enrolment per academic year. Moving a student
closes the old row (status + left_at) instead of deleting it, so class history
survives transfers and year-end promotion.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AcademicYear, ClassStudent, Profile, SchoolClass, utcnow


def active_classes():
    return select(SchoolClass.id).where(SchoolClass.status == "active")


def current_class(db: Session, student_id: str) -> SchoolClass | None:
    """The student's active class, preferring the school's current academic year."""
    rows = db.execute(
        select(SchoolClass, AcademicYear.is_current)
        .join(ClassStudent, ClassStudent.class_id == SchoolClass.id)
        .join(AcademicYear, AcademicYear.id == SchoolClass.academic_year_id)
        .where(ClassStudent.student_id == student_id, ClassStudent.status == "active", SchoolClass.status == "active")
        .order_by(AcademicYear.is_current.desc(), AcademicYear.start_date.desc())
    ).first()
    return rows[0] if rows else None


def _active_in_year(db: Session, student_id: str, academic_year_id: str) -> ClassStudent | None:
    return db.scalar(
        select(ClassStudent)
        .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
        .where(ClassStudent.student_id == student_id, ClassStudent.status == "active", SchoolClass.academic_year_id == academic_year_id)
    )


def _open(db: Session, student: Profile, klass: SchoolClass) -> None:
    row = db.get(ClassStudent, (klass.id, student.id))
    if row is None:
        db.add(ClassStudent(class_id=klass.id, student_id=student.id, status="active", enrolled_at=utcnow()))
    else:  # returning to a class they left earlier
        row.status, row.enrolled_at, row.left_at = "active", utcnow(), None


def check_enrollable(student: Profile, klass: SchoolClass) -> None:
    if student.role != "student":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{student.full_name} is not a student")
    if student.school_id != klass.school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    if klass.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived classes cannot take new students")


def enrol(db: Session, student: Profile, klass: SchoolClass) -> str:
    """Returns "enrolled" or "already". Raises 409 if the student is in another class that year."""
    check_enrollable(student, klass)
    current = _active_in_year(db, student.id, klass.academic_year_id)
    if current is not None:
        if current.class_id == klass.id:
            return "already"
        other = db.get(SchoolClass, current.class_id)
        raise HTTPException(status.HTTP_409_CONFLICT, f"{student.full_name} is already in {other.name} this year. Use transfer instead.")
    _open(db, student, klass)
    if klass.form and student.form != klass.form:
        student.form = klass.form
    return "enrolled"


def transfer(db: Session, student: Profile, to_class: SchoolClass) -> SchoolClass | None:
    """Move a student into `to_class`, closing their active enrolment in the same academic year. Returns the old class."""
    check_enrollable(student, to_class)
    current = _active_in_year(db, student.id, to_class.academic_year_id)
    if current is not None and current.class_id == to_class.id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{student.full_name} is already in {to_class.name}")
    old = None
    if current is not None:
        current.status, current.left_at = "transferred", utcnow()
        old = db.get(SchoolClass, current.class_id)
    db.flush()
    _open(db, student, to_class)
    student.form = to_class.form
    return old


def withdraw(db: Session, student_id: str, klass: SchoolClass) -> None:
    row = db.get(ClassStudent, (klass.id, student_id))
    if row is None or row.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This student is not enrolled in the class")
    row.status, row.left_at = "withdrawn", utcnow()
