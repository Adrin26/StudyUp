"""School calendar: admin-managed school events and terms, plus each user's own deadlines and exams."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AcademicTerm, AcademicYear, Assignment, AssignmentStudent, CalendarEvent, ClassStudent, ExamPublication, Profile,
    QuestionSet, SchoolClass,
)
from ..permissions import require_admin
from ..schemas import CalendarEventIn
from ..security import get_current_user
from ..services import audit
from ..services.gamification import MALAYSIA_TZ

router = APIRouter(prefix="/api", tags=["calendar"])

AUDIENCES = {"student": ("all", "students"), "teacher": ("all", "teachers"), "admin": ("all", "teachers", "students")}
MAX_RANGE_DAYS = 400


def _local(dt: datetime) -> date:
    return dt.astimezone(MALAYSIA_TZ).date()


def _event_out(e: CalendarEvent, editable: bool) -> dict:
    return {
        "id": e.id, "source": "school", "kind": e.kind, "title": e.title, "description": e.description, "audience": e.audience,
        "start_date": e.start_date, "end_date": e.end_date, "link": None, "editable": editable,
    }


@router.get("/calendar")
def calendar(
    start: date = Query(...),
    end: date = Query(...),
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Choose a range of at most {MAX_RANGE_DAYS} days")
    items: list[dict] = []
    if user.school_id:
        events = db.scalars(select(CalendarEvent).where(
            CalendarEvent.school_id == user.school_id, CalendarEvent.audience.in_(AUDIENCES[user.role]),
            CalendarEvent.start_date <= end, CalendarEvent.end_date >= start,
        ))
        items += [_event_out(e, user.role == "admin") for e in events]
        terms = db.execute(
            select(AcademicTerm, AcademicYear.name).join(AcademicYear, AcademicYear.id == AcademicTerm.academic_year_id)
            .where(AcademicYear.school_id == user.school_id, AcademicTerm.start_date <= end, AcademicTerm.end_date >= start)
        ).all()
        items += [
            {"id": t.id, "source": "term", "kind": "term", "title": f"{t.name} ({year})", "description": None, "audience": "all",
             "start_date": t.start_date, "end_date": t.end_date, "link": None, "editable": False}
            for t, year in terms
        ]

    window_start = datetime.combine(start, time.min, tzinfo=MALAYSIA_TZ)
    window_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=MALAYSIA_TZ)
    if user.role == "student":
        rows = db.execute(
            select(Assignment, AssignmentStudent.status).join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
            .where(AssignmentStudent.student_id == user.id, Assignment.due_date >= start, Assignment.due_date <= end)
        ).all()
        items += [
            {"id": a.id, "source": "assignment", "kind": "deadline", "title": f"Due: {a.title}", "description": "Completed" if st == "completed" else None,
             "audience": "students", "start_date": a.due_date, "end_date": a.due_date, "link": f"/practice/set/{a.set_id}", "editable": False}
            for a, st in rows
        ]
        class_ids = select(ClassStudent.class_id).where(ClassStudent.student_id == user.id, ClassStudent.status == "active")
        pubs = db.execute(
            select(ExamPublication, QuestionSet.title).join(QuestionSet, QuestionSet.id == ExamPublication.exam_id)
            .where(ExamPublication.class_id.in_(class_ids), ExamPublication.opens_at < window_end, ExamPublication.closes_at >= window_start)
        ).all()
        items += [
            {"id": p.id, "source": "exam", "kind": "exam", "title": f"Exam: {title}", "description": None, "audience": "students",
             "start_date": _local(p.opens_at), "end_date": _local(p.closes_at), "link": "/exams", "editable": False}
            for p, title in pubs
        ]
    elif user.role == "teacher":
        mine = db.scalars(select(Assignment).where(Assignment.teacher_id == user.id, Assignment.due_date >= start, Assignment.due_date <= end))
        items += [
            {"id": a.id, "source": "assignment", "kind": "deadline", "title": f"Due: {a.title}", "description": None, "audience": "teachers",
             "start_date": a.due_date, "end_date": a.due_date, "link": "/teacher", "editable": False}
            for a in mine
        ]
        pubs = db.execute(
            select(ExamPublication, QuestionSet, SchoolClass.name)
            .join(QuestionSet, QuestionSet.id == ExamPublication.exam_id).join(SchoolClass, SchoolClass.id == ExamPublication.class_id)
            .where(QuestionSet.owner_id == user.id, ExamPublication.opens_at < window_end, ExamPublication.closes_at >= window_start)
        ).all()
        items += [
            {"id": p.id, "source": "exam", "kind": "exam", "title": f"Exam: {exam.title} · {cls}", "description": None, "audience": "teachers",
             "start_date": _local(p.opens_at), "end_date": _local(p.closes_at), "link": f"/teacher/exams/{exam.id}", "editable": False}
            for p, exam, cls in pubs
        ]
    items.sort(key=lambda i: (i["start_date"], i["title"]))
    return items


def _own_event(db: Session, event_id: str, admin: Profile) -> CalendarEvent:
    event = db.get(CalendarEvent, event_id)
    if event is None or event.school_id != admin.school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return event


@router.post("/admin/calendar", status_code=201)
def create_event(body: CalendarEventIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    event = CalendarEvent(school_id=admin.school_id, created_by=admin.id, **body.model_dump())
    db.add(event)
    db.flush()
    audit.record(db, "calendar.event_created", "calendar_event", event.id, actor=admin, school_id=admin.school_id,
                 details={"title": event.title, "start_date": str(event.start_date)}, request=request)
    db.commit()
    return _event_out(event, True)


@router.patch("/admin/calendar/{event_id}")
def update_event(event_id: str, body: CalendarEventIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    event = _own_event(db, event_id, admin)
    for k, v in body.model_dump().items():
        setattr(event, k, v)
    audit.record(db, "calendar.event_updated", "calendar_event", event.id, actor=admin, school_id=admin.school_id,
                 details={"title": event.title, "start_date": str(event.start_date)}, request=request)
    db.commit()
    return _event_out(event, True)


@router.delete("/admin/calendar/{event_id}", status_code=204)
def delete_event(event_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    event = _own_event(db, event_id, admin)
    audit.record(db, "calendar.event_deleted", "calendar_event", event.id, actor=admin, school_id=admin.school_id,
                 details={"title": event.title}, request=request)
    db.delete(event)
    db.commit()
