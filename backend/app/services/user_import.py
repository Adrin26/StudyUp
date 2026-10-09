"""CSV import of student and teacher accounts.

Preview and confirm run the same analysis; confirm re-validates on the server
and creates only the rows that are still valid, reporting the rest.
"""

import csv
import io

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Profile, SchoolClass
from ..schemas import UserCreateIn
from . import accounts, school_scope

REQUIRED_HEADERS = ("role", "full_name", "email")
OPTIONAL_HEADERS = ("username", "student_number", "staff_number", "form", "class", "department")
MAX_ROWS = 500
LABELS = {**accounts.FIELD_LABELS, "full_name": "Full name", "form": "Form", "role": "Role", "department": "Department", "class_id": "Class"}


def _messages(error: ValidationError) -> list[str]:
    out = []
    for e in error.errors():
        field = e["loc"][0] if e["loc"] else None
        msg = e["msg"].removeprefix("Value error, ")
        out.append(f"{LABELS.get(field, field)}: {msg}" if field else msg)
    return out


def analyse(db: Session, admin: Profile, text: str) -> dict:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    raw_headers = reader.fieldnames or []
    headers = [h.strip().lower() for h in raw_headers]
    header_errors = []
    if missing := [h for h in REQUIRED_HEADERS if h not in headers]:
        header_errors.append(f"Missing column(s): {', '.join(missing)}.")
    if unknown := [h for h in headers if h and h not in REQUIRED_HEADERS + OPTIONAL_HEADERS]:
        header_errors.append(f"Unknown column(s): {', '.join(unknown)}. Allowed: {', '.join(REQUIRED_HEADERS + OPTIONAL_HEADERS)}.")
    if len(set(headers)) != len(headers):
        header_errors.append("Each column may appear only once.")
    if header_errors:
        return {"header_errors": header_errors, "rows": [], "summary": {"total": 0, "ready": 0, "errors": 0}}

    year = school_scope.current_year(db, admin.school_id)
    classes = {}
    if year:
        classes = {c.name.lower(): c for c in db.scalars(select(SchoolClass).where(SchoolClass.academic_year_id == year.id, SchoolClass.status == "active"))}
    seen: dict[str, dict[str, int]] = {f: {} for f in accounts.FIELD_LABELS}
    rows = []
    for raw in reader:
        line = reader.line_num
        rec = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(rec.values()):
            continue
        if len(rows) >= MAX_ROWS:
            header_errors.append(f"Import at most {MAX_ROWS} rows at a time.")
            break
        errors: list[str] = []
        role = rec.get("role", "").lower()
        class_name = rec.get("class", "")
        klass = None
        if role == "admin":
            errors.append("Admin accounts cannot be imported. Use the server command instead.")
        if class_name:
            if role != "student":
                errors.append("Class: only students can be enrolled in a class.")
            elif year is None:
                errors.append("Class: set a current academic year before enrolling students.")
            elif (klass := classes.get(class_name.lower())) is None:
                errors.append(f"Class: '{class_name}' was not found in {year.name}.")

        model = None
        if role != "admin":
            payload = {k: rec.get(k) or None for k in ("full_name", "email", "username", "student_number", "staff_number", "form", "department")}
            try:
                model = UserCreateIn(role=role, class_id=klass.id if klass else None, send_invite=False, **payload)
            except ValidationError as exc:
                errors.extend(_messages(exc))

        username = None
        if model is not None:
            values = model.model_dump(include=set(accounts.FIELD_LABELS))
            errors.extend(accounts.conflicts(db, admin.school_id, values).values())
            username = model.username or accounts.suggest_username(db, model.email, set(seen["username"]))
            values["username"] = username
            for field, value in values.items():
                if not value:
                    continue
                key = value.lower()
                if key in seen[field]:
                    errors.append(f"{accounts.FIELD_LABELS[field]} {value} is repeated (also on line {seen[field][key]}).")
                else:
                    seen[field][key] = line

        rows.append({
            "line": line,
            "role": role or None,
            "full_name": rec.get("full_name") or None,
            "email": rec.get("email", "").lower() or None,
            "username": username,
            "id_number": rec.get("student_number") or rec.get("staff_number") or None,
            "class": klass.name if klass else (class_name or None),
            "status": "error" if errors else "ready",
            "errors": errors,
            "_model": model,
        })
    ready = sum(r["status"] == "ready" for r in rows)
    return {"header_errors": header_errors, "rows": rows, "summary": {"total": len(rows), "ready": ready, "errors": len(rows) - ready}}


def public(analysis: dict) -> dict:
    return {**analysis, "rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in analysis["rows"]]}
