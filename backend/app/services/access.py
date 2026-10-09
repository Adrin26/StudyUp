"""Backend authorization rules for teacher access to student data.

These mirror the Supabase RLS helper functions so the API stays safe even
when it connects with a privileged database role.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ClassStudent, Profile, SchoolClass, TeacherSubject


def class_teacher_class_ids(db: Session, teacher: Profile) -> list[str]:
    """Active classes the user is class teacher of. Archived classes grant no access."""
    stmt = select(SchoolClass.id).where(SchoolClass.status == "active")
    if teacher.role == "admin":
        return list(db.scalars(stmt.where(SchoolClass.school_id == teacher.school_id)))
    return list(db.scalars(stmt.where(SchoolClass.class_teacher_id == teacher.id)))


def subject_assignments(db: Session, teacher: Profile) -> list[TeacherSubject]:
    return list(db.scalars(
        select(TeacherSubject)
        .join(SchoolClass, SchoolClass.id == TeacherSubject.class_id)
        .where(TeacherSubject.teacher_id == teacher.id, SchoolClass.status == "active")
    ))


def teacher_responsibilities(db: Session, teacher: Profile) -> list[str]:
    """Derived from current assignments; there is no stored class/subject-teacher flag."""
    if teacher.role != "teacher":
        return []
    out = []
    if class_teacher_class_ids(db, teacher):
        out.append("class_teacher")
    if subject_assignments(db, teacher):
        out.append("subject_teacher")
    return out


def students_in_classes(db: Session, class_ids: list[str]) -> list[str]:
    """Students currently enrolled; transferred or withdrawn students no longer count."""
    if not class_ids:
        return []
    return list(db.scalars(
        select(ClassStudent.student_id).where(ClassStudent.class_id.in_(class_ids), ClassStudent.status == "active").distinct()
    ))


def visible_student_ids(db: Session, teacher: Profile, subject_id: str | None = None) -> set[str]:
    """Students a teacher may see, optionally restricted to one subject.

    Class teachers see every subject for students in their classes. Subject
    teachers see only the subjects they teach, for the classes they teach.
    """
    ids = set(students_in_classes(db, class_teacher_class_ids(db, teacher)))
    taught_classes = [
        ts.class_id for ts in subject_assignments(db, teacher) if subject_id is None or ts.subject_id == subject_id
    ]
    ids.update(students_in_classes(db, taught_classes))
    return ids


def ensure_can_view_student(db: Session, teacher: Profile, student_id: str, subject_id: str | None = None) -> None:
    if student_id not in visible_student_ids(db, teacher, subject_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this student")


def ensure_teaches_subject(db: Session, teacher: Profile, subject_id: str) -> None:
    if teacher.role == "admin" or class_teacher_class_ids(db, teacher):
        return
    if not any(ts.subject_id == subject_id for ts in subject_assignments(db, teacher)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this subject")


def ensure_can_view_class(db: Session, teacher: Profile, class_id: str) -> None:
    if class_id in class_teacher_class_ids(db, teacher):
        return
    if any(ts.class_id == class_id for ts in subject_assignments(db, teacher)):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this class")
