from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Assignment,
    AssignmentStudent,
    ClassStudent,
    Notification,
    Profile,
    QuestionSet,
    QuestionSetQuestion,
    SchoolClass,
    Subject,
    Topic,
)
from ..schemas import AssignmentIn
from ..services import analytics, randomizer
from ..services.access import (
    class_teacher_class_ids,
    ensure_can_view_class,
    ensure_can_view_student,
    ensure_teaches_subject,
    students_in_classes,
    subject_assignments,
    visible_student_ids,
)
from ..services.question_bank import filter_questions
from ..security import require_teacher

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


def _students(db: Session, ids: set[str] | list[str]) -> list[Profile]:
    if not ids:
        return []
    return list(db.scalars(select(Profile).where(Profile.id.in_(list(ids))).order_by(Profile.full_name)))


def _class_students(db: Session, class_id: str) -> list[Profile]:
    return list(
        db.scalars(
            select(Profile).join(ClassStudent, ClassStudent.student_id == Profile.id).where(ClassStudent.class_id == class_id).order_by(Profile.full_name)
        )
    )


@router.get("/me")
def teacher_context(teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    classes = {c.id: c for c in db.scalars(select(SchoolClass))}
    subjects = {s.id: s for s in db.scalars(select(Subject))}
    homeroom = [classes[cid] for cid in class_teacher_class_ids(db, teacher) if cid in classes]
    teaching = subject_assignments(db, teacher)
    by_subject: dict[str, list[dict]] = {}
    for ts in teaching:
        by_subject.setdefault(ts.subject_id, []).append({"id": ts.class_id, "name": classes[ts.class_id].name})
    return {
        "teacher_types": teacher.teacher_types or [],
        "homeroom_classes": [{"id": c.id, "name": c.name, "form": c.form, "student_count": len(_class_students(db, c.id))} for c in homeroom],
        "subjects": [
            {"id": sid, "name": subjects[sid].name, "color": subjects[sid].color, "icon": subjects[sid].icon, "classes": cls}
            for sid, cls in sorted(by_subject.items(), key=lambda kv: subjects[kv[0]].sort_order)
        ],
    }


@router.get("/classes")
def teacher_classes(teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    ids = set(class_teacher_class_ids(db, teacher)) | {ts.class_id for ts in subject_assignments(db, teacher)}
    homeroom = set(class_teacher_class_ids(db, teacher))
    classes = db.scalars(select(SchoolClass).where(SchoolClass.id.in_(ids)).order_by(SchoolClass.name)) if ids else []
    return [{"id": c.id, "name": c.name, "form": c.form, "is_class_teacher": c.id in homeroom, "student_count": len(_class_students(db, c.id))} for c in classes]


@router.get("/subjects/{subject_id}/progress")
def subject_progress(subject_id: str, class_id: str | None = None, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    ensure_teaches_subject(db, teacher, subject_id)
    ids = visible_student_ids(db, teacher, subject_id)
    if class_id:
        ensure_can_view_class(db, teacher, class_id)
        ids &= {s.id for s in _class_students(db, class_id)}
    return analytics.subject_dashboard(db, subject, _students(db, ids))


@router.get("/students/{student_id}")
def student_detail(student_id: str, subject_id: str | None = None, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    ensure_can_view_student(db, teacher, student_id, subject_id)
    student = db.get(Profile, student_id)
    if student is None or student.role != "student":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    homeroom_students = set(students_in_classes(db, class_teacher_class_ids(db, teacher)))
    if subject_id:
        allowed: list[str] | None = [subject_id]
    elif student_id in homeroom_students:
        allowed = None
    else:
        allowed = sorted({ts.subject_id for ts in subject_assignments(db, teacher) if student_id in students_in_classes(db, [ts.class_id])})
    return analytics.student_detail(db, student, allowed)


@router.get("/classes/{class_id}/overview")
def class_overview(class_id: str, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    if class_id not in class_teacher_class_ids(db, teacher):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the class teacher can view the whole-class overview")
    klass = db.get(SchoolClass, class_id)
    return {"class": {"id": klass.id, "name": klass.name, "form": klass.form}, **analytics.class_overview(db, _class_students(db, class_id))}


@router.get("/alerts")
def alerts(teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    classes = {c.id: c for c in db.scalars(select(SchoolClass))}
    groups: dict[tuple[str, str], list[Profile]] = {}
    for ts in subject_assignments(db, teacher):
        groups[(ts.class_id, ts.subject_id)] = _class_students(db, ts.class_id)
    for cid in class_teacher_class_ids(db, teacher):
        students = _class_students(db, cid)
        for subject in db.scalars(select(Subject)):
            groups.setdefault((cid, subject.id), students)
    return analytics.intervention_alerts(db, [(classes[cid].name, sid, studs) for (cid, sid), studs in groups.items()])


@router.post("/assignments")
def create_assignment(body: AssignmentIn, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    ensure_teaches_subject(db, teacher, body.subject_id)
    allowed = visible_student_ids(db, teacher, body.subject_id)
    denied = [sid for sid in body.student_ids if sid not in allowed]
    if denied:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Some selected students are not in your classes")

    if body.exam_id:
        exam = db.get(QuestionSet, body.exam_id)
        if exam is None or exam.owner_id != teacher.id or exam.kind != "exam":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
        question_ids = [i.question_id for i in exam.items]
        seed = exam.seed
    else:
        pool = filter_questions(db, subject_id=body.subject_id, topic_ids=[body.topic_id] if body.topic_id else None)
        if not pool:
            raise HTTPException(status.HTTP_409_CONFLICT, "No questions available for this topic")
        seed = randomizer.new_seed()
        question_ids = [q.id for q in randomizer.sample(pool, body.num_questions, seed, key=lambda q: q.id)]

    qset = QuestionSet(kind="assignment", title=body.title, owner_id=teacher.id, subject_id=body.subject_id, topic_id=body.topic_id, seed=seed, status="saved")
    qset.items = [QuestionSetQuestion(question_id=qid, position=i) for i, qid in enumerate(question_ids)]
    db.add(qset)
    db.flush()
    assignment = Assignment(
        teacher_id=teacher.id, title=body.title, instructions=body.instructions, subject_id=body.subject_id,
        topic_id=body.topic_id, set_id=qset.id, due_date=body.due_date,
    )
    db.add(assignment)
    db.flush()
    for sid in dict.fromkeys(body.student_ids):
        db.add(AssignmentStudent(assignment_id=assignment.id, student_id=sid))
        db.add(Notification(user_id=sid, kind="assignment", title=f"New practice from {teacher.full_name}", body=body.title, link=f"/practice/set/{qset.id}"))
    db.commit()
    return {"id": assignment.id, "set_id": qset.id, "student_count": len(set(body.student_ids)), "question_count": len(question_ids)}


@router.get("/assignments")
def list_assignments(teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    subjects = {s.id: s.name for s in db.scalars(select(Subject))}
    topics = {t.id: t.name for t in db.scalars(select(Topic))}
    out = []
    for a in db.scalars(select(Assignment).where(Assignment.teacher_id == teacher.id).order_by(Assignment.created_at.desc())):
        rows = list(db.scalars(select(AssignmentStudent).where(AssignmentStudent.assignment_id == a.id)))
        done = [r for r in rows if r.status == "completed"]
        out.append({
            "id": a.id,
            "title": a.title,
            "subject": subjects.get(a.subject_id),
            "topic": topics.get(a.topic_id),
            "due_date": a.due_date,
            "created_at": a.created_at,
            "assigned": len(rows),
            "completed": len(done),
            "average_score": round(sum(r.score or 0 for r in done) / len(done), 1) if done else None,
        })
    return out
