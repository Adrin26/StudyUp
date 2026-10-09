"""Load records for an admin, restricted to the admin's own school.

Anything outside the school is reported as 404 so IDs from other schools
cannot be probed.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AcademicTerm, AcademicYear, Profile, SchoolClass, Subject


def _missing(label: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")


def member(db: Session, profile_id: str, admin: Profile, role: str | None = None) -> Profile:
    p = db.get(Profile, profile_id)
    if p is None or p.school_id != admin.school_id or (role and p.role != role):
        raise _missing((role or "user").capitalize())
    return p


def managed_member(db: Session, profile_id: str, admin: Profile) -> Profile:
    """A student or teacher the admin may change. Admin accounts are managed with the server CLI."""
    p = member(db, profile_id, admin)
    if p.role == "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin accounts are managed with the server CLI")
    return p


def active_teacher(db: Session, teacher_id: str, admin: Profile) -> Profile:
    t = member(db, teacher_id, admin, "teacher")
    if not t.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{t.full_name}'s account is disabled. Reactivate it first.")
    return t


def school_class(db: Session, class_id: str, admin: Profile, *, active: bool = False) -> SchoolClass:
    c = db.get(SchoolClass, class_id)
    if c is None or c.school_id != admin.school_id:
        raise _missing("Class")
    if active and c.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, f"{c.name} is archived")
    return c


def academic_year(db: Session, year_id: str, admin: Profile) -> AcademicYear:
    y = db.get(AcademicYear, year_id)
    if y is None or y.school_id != admin.school_id:
        raise _missing("Academic year")
    return y


def academic_term(db: Session, term_id: str, admin: Profile) -> AcademicTerm:
    t = db.get(AcademicTerm, term_id)
    if t is None:
        raise _missing("Term")
    academic_year(db, t.academic_year_id, admin)
    return t


def current_year(db: Session, school_id: str) -> AcademicYear | None:
    return db.scalar(select(AcademicYear).where(AcademicYear.school_id == school_id, AcademicYear.is_current.is_(True)))


def subjects(db: Session, subject_ids: list[str]) -> list[Subject]:
    """Subjects are central (not per school); every ID must exist."""
    unique = list(dict.fromkeys(subject_ids))
    if not unique:
        return []
    found = list(db.scalars(select(Subject).where(Subject.id.in_(unique)).order_by(Subject.sort_order)))
    if len(found) != len(unique):
        raise _missing("Subject")
    return found
