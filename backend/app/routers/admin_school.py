from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AcademicTerm, AcademicYear, Profile, School, SchoolClass
from ..permissions import require_admin
from ..schemas import TIMEZONES, AcademicTermIn, AcademicYearIn, SchoolUpdateIn
from ..services import audit, school_scope

router = APIRouter(prefix="/api/admin", tags=["admin: school"])

SCHOOL_FIELDS = ("name", "state", "address", "phone", "email", "logo_url", "timezone", "description")


def _school(db: Session, admin: Profile) -> School:
    school = db.get(School, admin.school_id) if admin.school_id else None
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Your account is not linked to a school")
    return school


def _school_payload(db: Session, school: School) -> dict:
    year = school_scope.current_year(db, school.id)
    return {
        **{f: getattr(school, f) for f in ("id", *SCHOOL_FIELDS)},
        "current_academic_year": {"id": year.id, "name": year.name} if year else None,
        "timezones": list(TIMEZONES),
    }


@router.get("/school")
def get_school(admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _school_payload(db, _school(db, admin))


@router.put("/school")
def update_school(body: SchoolUpdateIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    school = _school(db, admin)
    data = body.model_dump()
    changed = sorted(f for f in SCHOOL_FIELDS if getattr(school, f) != data[f])
    for f in changed:
        setattr(school, f, data[f])
    if changed:
        audit.record(db, "school.update", "school", school.id, actor=admin, request=request, details={"fields": ", ".join(changed)})
    db.commit()
    return _school_payload(db, school)


def _year_payload(db: Session, y: AcademicYear) -> dict:
    return {
        "id": y.id,
        "name": y.name,
        "start_date": y.start_date,
        "end_date": y.end_date,
        "is_current": y.is_current,
        "class_count": db.scalar(select(func.count()).select_from(SchoolClass).where(SchoolClass.academic_year_id == y.id)),
        "terms": [{"id": t.id, "name": t.name, "start_date": t.start_date, "end_date": t.end_date} for t in y.terms],
    }


def _ensure_unique_year_name(db: Session, admin: Profile, name: str, exclude_id: str | None = None) -> None:
    stmt = select(AcademicYear.id).where(AcademicYear.school_id == admin.school_id, func.lower(AcademicYear.name) == name.strip().lower())
    if exclude_id:
        stmt = stmt.where(AcademicYear.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Academic year {name} already exists")


def _make_current(db: Session, year: AcademicYear) -> None:
    db.execute(update(AcademicYear).where(AcademicYear.school_id == year.school_id, AcademicYear.id != year.id).values(is_current=False))
    year.is_current = True


@router.get("/academic-years")
def list_years(admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    years = db.scalars(select(AcademicYear).where(AcademicYear.school_id == admin.school_id).order_by(AcademicYear.start_date.desc()))
    return [_year_payload(db, y) for y in years]


@router.post("/academic-years", status_code=status.HTTP_201_CREATED)
def create_year(body: AcademicYearIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    _school(db, admin)
    _ensure_unique_year_name(db, admin, body.name)
    year = AcademicYear(school_id=admin.school_id, name=body.name.strip(), start_date=body.start_date, end_date=body.end_date)
    db.add(year)
    db.flush()
    if body.is_current or school_scope.current_year(db, admin.school_id) is None:
        _make_current(db, year)
    audit.record(db, "academic_year.create", "academic_year", year.id, actor=admin, request=request, details={"name": year.name})
    db.commit()
    return _year_payload(db, year)


@router.put("/academic-years/{year_id}")
def update_year(year_id: str, body: AcademicYearIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    year = school_scope.academic_year(db, year_id, admin)
    _ensure_unique_year_name(db, admin, body.name, exclude_id=year.id)
    outside = [t.name for t in year.terms if t.start_date < body.start_date or t.end_date > body.end_date]
    if outside:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"These terms would fall outside the year: {', '.join(outside)}")
    year.name, year.start_date, year.end_date = body.name.strip(), body.start_date, body.end_date
    if body.is_current and not year.is_current:
        _make_current(db, year)
    audit.record(db, "academic_year.update", "academic_year", year.id, actor=admin, request=request, details={"name": year.name})
    db.commit()
    return _year_payload(db, year)


@router.post("/academic-years/{year_id}/set-current")
def set_current_year(year_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    year = school_scope.academic_year(db, year_id, admin)
    if not year.is_current:
        _make_current(db, year)
        audit.record(db, "academic_year.set_current", "academic_year", year.id, actor=admin, request=request, details={"name": year.name})
        db.commit()
    return _year_payload(db, year)


def _check_term(year: AcademicYear, body: AcademicTermIn, exclude_id: str | None = None) -> None:
    if body.start_date < year.start_date or body.end_date > year.end_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Term dates must be within {year.name} ({year.start_date} to {year.end_date})")
    for t in year.terms:
        if t.id == exclude_id:
            continue
        if t.name.lower() == body.name.strip().lower():
            raise HTTPException(status.HTTP_409_CONFLICT, f"{year.name} already has a term named {t.name}")
        if body.start_date <= t.end_date and t.start_date <= body.end_date:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Dates overlap with {t.name}")


@router.post("/academic-years/{year_id}/terms", status_code=status.HTTP_201_CREATED)
def create_term(year_id: str, body: AcademicTermIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    year = school_scope.academic_year(db, year_id, admin)
    _check_term(year, body)
    term = AcademicTerm(academic_year_id=year.id, name=body.name.strip(), start_date=body.start_date, end_date=body.end_date)
    year.terms.append(term)
    db.flush()
    audit.record(db, "academic_term.create", "academic_term", term.id, actor=admin, request=request, details={"year": year.name, "name": term.name})
    db.commit()
    db.refresh(year)
    return _year_payload(db, year)


@router.put("/academic-terms/{term_id}")
def update_term(term_id: str, body: AcademicTermIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    term = school_scope.academic_term(db, term_id, admin)
    year = db.get(AcademicYear, term.academic_year_id)
    _check_term(year, body, exclude_id=term.id)
    term.name, term.start_date, term.end_date = body.name.strip(), body.start_date, body.end_date
    audit.record(db, "academic_term.update", "academic_term", term.id, actor=admin, request=request, details={"year": year.name, "name": term.name})
    db.commit()
    db.refresh(year)
    return _year_payload(db, year)


@router.delete("/academic-terms/{term_id}")
def delete_term(term_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    """Terms hold no student records yet, so they can be removed outright."""
    term = school_scope.academic_term(db, term_id, admin)
    year = db.get(AcademicYear, term.academic_year_id)
    audit.record(db, "academic_term.delete", "academic_term", term.id, actor=admin, request=request, details={"year": year.name, "name": term.name})
    year.terms.remove(term)
    db.commit()
    db.refresh(year)
    return _year_payload(db, year)
