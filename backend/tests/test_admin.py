"""Phase 2: admin user management, school administration, classes and enrolment."""

import re
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import AcademicYear, AuditLog, Profile, School, SchoolClass
from app.services import mailer

from .conftest import login


@pytest.fixture
def outbox(monkeypatch):
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def _token(body: str) -> str:
    return re.search(r"token=([\w-]+)", body).group(1)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _lookups(client, admin) -> dict:
    return client.get("/api/admin/lookups", headers=admin).json()


def _class_id(client, admin, name: str) -> str:
    return next(c["id"] for c in _lookups(client, admin)["classes"] if c["name"] == name)


def _subject_id(client, admin, code: str) -> str:
    return next(s["id"] for s in _lookups(client, admin)["subjects"] if s["code"] == code)


def _new_class(client, admin, form: int = 4, **extra) -> dict:
    """Tests use their own classes so the seeded demo classes keep their exact rosters for other tests."""
    year = next(y["id"] for y in _lookups(client, admin)["academic_years"] if y["is_current"])
    res = client.post("/api/admin/classes", json={"name": f"{form} Test {_uid()}", "form": form, "academic_year_id": year, **extra}, headers=admin)
    assert res.status_code == 201, res.text
    return res.json()


def _new_user(client, admin, outbox, role="student", activate=True, **extra) -> tuple[dict, dict | None]:
    """Create an account through the API and, if asked, finish its invitation. Returns (user, auth headers)."""
    uid = _uid()
    body = {"role": role, "full_name": f"Test {role.title()} {uid}", "email": f"{role}{uid}@example.test", **extra}
    if role == "student":
        body.setdefault("student_number", f"T{uid}")
    else:
        body.setdefault("staff_number", f"ST{uid}")
    res = client.post("/api/admin/users", json=body, headers=admin)
    assert res.status_code == 201, res.text
    user = res.json()["user"]
    if not activate:
        return user, None
    token = _token(outbox[-1][2])
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Welcome123"}).status_code == 200
    return user, login(client, user["email"], "Welcome123")


# --- access -------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("get", "/api/admin/users"),
    ("post", "/api/admin/users"),
    ("get", "/api/admin/classes"),
    ("get", "/api/admin/school"),
    ("get", "/api/admin/academic-years"),
    ("get", "/api/admin/teacher-assignments"),
    ("post", "/api/admin/users/import/preview"),
])
def test_students_and_teachers_cannot_use_admin_endpoints(client, student, farid, method, path):
    for headers in (student, farid):
        res = getattr(client, method)(path, headers=headers, **({"json": {}} if method == "post" else {}))
        assert res.status_code == 403, (path, res.text)


def test_directory_is_scoped_to_the_admins_school(client, admin):
    teachers = client.get("/api/admin/users", params={"role": "teacher", "page_size": 100}, headers=admin).json()
    emails = {u["email"] for u in teachers["items"]}
    assert "farid@teacher.demo" in emails and "lim@teacher.demo" not in emails

    with SessionLocal() as db:
        lim = db.scalar(select(Profile).where(Profile.email == "lim@teacher.demo"))
    assert client.get(f"/api/admin/users/{lim.id}", headers=admin).status_code == 404
    assert client.post(f"/api/admin/users/{lim.id}/disable", headers=admin).status_code == 404


def test_directory_search_and_filters(client, admin):
    res = client.get("/api/admin/users", params={"q": "aisyah"}, headers=admin).json()
    assert [u["email"] for u in res["items"]] == ["aisyah@student.demo"]
    aisyah = res["items"][0]
    assert aisyah["class"]["name"] == "4 Bestari" and aisyah["student_number"]

    bestari = _class_id(client, admin, "4 Bestari")
    in_class = client.get("/api/admin/users", params={"class_id": bestari, "role": "student", "page_size": 100}, headers=admin).json()
    assert in_class["total"] >= 14 and all(u["class"]["name"] == "4 Bestari" for u in in_class["items"])

    farid = client.get("/api/admin/users", params={"q": "farid"}, headers=admin).json()["items"][0]
    assert {h["name"] for h in farid["homeroom"]} == {"4 Bestari"}
    assert {t["subject"]["name"] for t in farid["teaching"]} >= {"Mathematics"}


# --- creating accounts -------------------------------------------------------

def test_admin_role_cannot_be_created_or_imported(client, admin):
    res = client.post("/api/admin/users", json={"role": "admin", "full_name": "Sneaky", "email": "sneaky@example.test"}, headers=admin)
    assert res.status_code == 422
    preview = client.post("/api/admin/users/import/preview", json={"csv": "role,full_name,email\nadmin,Sneaky,sneaky@example.test\n"}, headers=admin).json()
    assert preview["rows"][0]["status"] == "error"
    assert "Admin accounts cannot be imported" in preview["rows"][0]["errors"][0]


def test_create_student_sends_invitation_and_enrols(client, admin, outbox):
    klass = _new_class(client, admin)
    math = _subject_id(client, admin, "MATH")
    teacher, _ = _new_user(client, admin, outbox, role="teacher", activate=False)
    client.post("/api/admin/teacher-assignments", json={"teacher_id": teacher["id"], "subject_id": math, "class_id": klass["id"]}, headers=admin)
    user, headers = _new_user(client, admin, outbox, class_id=klass["id"])
    assert user["class"]["name"] == klass["name"]
    assert user["credentials_set"] is False  # nobody chose a password for them
    assert [s["id"] for s in user["subjects"]] == [math], "subjects default to those taught in the class"
    assert "Your MINDA account is ready" in outbox[-1][1]
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["role"] == "student" and me["class_name"] == klass["name"]

    with SessionLocal() as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "user.create", AuditLog.resource_id == user["id"]))
        assert entry is not None and "password" not in str(entry.details).lower()


def test_create_validates_role_fields_and_duplicates(client, admin):
    base = {"role": "student", "full_name": "Dup Test", "student_number": f"D{_uid()}"}
    assert client.post("/api/admin/users", json={**base, "email": "aisyah@student.demo"}, headers=admin).status_code == 409
    assert client.post("/api/admin/users", json={**base, "email": f"x{_uid()}@example.test", "username": "aisyah"}, headers=admin).status_code == 409

    with SessionLocal() as db:
        taken = db.scalar(select(Profile.student_number).where(Profile.email == "aisyah@student.demo"))
    res = client.post("/api/admin/users", json={**base, "email": f"x{_uid()}@example.test", "student_number": taken}, headers=admin)
    assert res.status_code == 409 and "Student ID" in res.json()["detail"]

    no_id = {"role": "student", "full_name": "No ID", "email": f"x{_uid()}@example.test"}
    assert client.post("/api/admin/users", json=no_id, headers=admin).status_code == 422
    teacher_with_class = {"role": "teacher", "full_name": "T", "email": f"x{_uid()}@example.test", "staff_number": "S1", "class_id": "x"}
    assert client.post("/api/admin/users", json=teacher_with_class, headers=admin).status_code == 422
    bad_email = {**base, "email": "not-an-email"}
    assert client.post("/api/admin/users", json=bad_email, headers=admin).status_code == 422


def test_teacher_responsibilities_follow_admin_assignments(client, admin, outbox):
    math = _subject_id(client, admin, "MATH")
    cemerlang = _new_class(client, admin)["id"]
    teacher, headers = _new_user(client, admin, outbox, role="teacher", assignments=[{"subject_id": math, "class_id": cemerlang}])
    assert client.get("/api/teachers/me", headers=headers).json()["teacher_types"] == ["subject_teacher"]
    assert client.get(f"/api/teachers/subjects/{math}/progress", headers=headers).status_code == 200

    phy = _subject_id(client, admin, "PHY")
    assert client.get(f"/api/teachers/subjects/{phy}/progress", headers=headers).status_code == 403

    created = client.post("/api/admin/teacher-assignments", json={"teacher_id": teacher["id"], "subject_id": phy, "class_id": cemerlang}, headers=admin)
    assert created.status_code == 201
    dup = client.post("/api/admin/teacher-assignments", json={"teacher_id": teacher["id"], "subject_id": phy, "class_id": cemerlang}, headers=admin)
    assert dup.status_code == 409
    assert client.get(f"/api/teachers/subjects/{phy}/progress", headers=headers).status_code == 200

    assert client.delete(f"/api/admin/teacher-assignments/{created.json()['id']}", headers=admin).status_code == 200
    assert client.get(f"/api/teachers/subjects/{phy}/progress", headers=headers).status_code == 403


# --- account status and passwords -------------------------------------------

def test_disable_blocks_existing_sessions_and_reactivate_restores(client, admin, outbox):
    user, headers = _new_user(client, admin, outbox)
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    res = client.post(f"/api/admin/users/{user['id']}/disable", headers=admin)
    assert res.status_code == 200 and res.json()["status"] == "disabled"
    blocked = client.get("/api/auth/me", headers=headers)
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "account_disabled"
    assert client.post(f"/api/admin/users/{user['id']}/reset-password", headers=admin).status_code == 409

    assert client.post(f"/api/admin/users/{user['id']}/reactivate", headers=admin).json()["status"] == "active"
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_disabling_revokes_pending_set_password_links(client, admin, outbox):
    user, _ = _new_user(client, admin, outbox, activate=False)
    token = _token(outbox[-1][2])
    client.post(f"/api/admin/users/{user['id']}/disable", headers=admin)
    client.post(f"/api/admin/users/{user['id']}/reactivate", headers=admin)
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Welcome123"}).status_code == 400


def test_admin_accounts_cannot_be_managed_through_the_api(client, admin):
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.post(f"/api/admin/users/{me['id']}/disable", headers=admin).status_code == 403
    assert client.patch(f"/api/admin/users/{me['id']}", json={"full_name": "Changed"}, headers=admin).status_code == 403


def test_admin_initiated_reset_sends_a_link_and_never_returns_a_password(client, admin, outbox):
    user, _ = _new_user(client, admin, outbox)
    res = client.post(f"/api/admin/users/{user['id']}/reset-password", headers=admin)
    assert res.status_code == 200
    body = res.json()
    assert body["initiated"] is True and body["delivered"] is True
    assert "token" not in str(body).lower() and "Welcome123" not in str(body)
    assert "Reset your MINDA password" in outbox[-1][1]

    token = _token(outbox[-1][2])
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Another456"}).status_code == 200
    login(client, user["email"], "Another456")


def test_edit_user_records_changed_fields(client, admin, outbox):
    user, _ = _new_user(client, admin, outbox, activate=False)
    res = client.patch(f"/api/admin/users/{user['id']}", json={"full_name": "Renamed Student", "form": 5}, headers=admin)
    assert res.status_code == 200 and res.json()["full_name"] == "Renamed Student"
    assert client.patch(f"/api/admin/users/{user['id']}", json={"staff_number": "X1"}, headers=admin).status_code == 422
    assert client.patch(f"/api/admin/users/{user['id']}", json={"email": "aisyah@student.demo"}, headers=admin).status_code == 409
    with SessionLocal() as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "user.update", AuditLog.resource_id == user["id"]))
        assert entry.details["fields"] == "form, full_name"


# --- classes and enrolment ---------------------------------------------------

def _current_year_id(client, admin) -> str:
    return next(y["id"] for y in _lookups(client, admin)["academic_years"] if y["is_current"])


def test_class_names_are_unique_within_a_year(client, admin):
    year = _current_year_id(client, admin)
    res = client.post("/api/admin/classes", json={"name": "4 bestari", "form": 4, "academic_year_id": year}, headers=admin)
    assert res.status_code == 409


def test_enrol_transfer_and_withdraw_keep_history(client, admin, outbox):
    klass = _new_class(client, admin)
    other = _new_class(client, admin)
    student, _ = _new_user(client, admin, outbox, activate=False)

    eligible = client.get(f"/api/admin/classes/{klass['id']}/eligible-students", headers=admin).json()
    assert student["id"] in {s["id"] for s in eligible}

    res = client.post(f"/api/admin/classes/{klass['id']}/students", json={"student_ids": [student["id"]]}, headers=admin).json()
    assert res["enrolled"] == [student["id"]]
    again = client.post(f"/api/admin/classes/{klass['id']}/students", json={"student_ids": [student["id"]]}, headers=admin).json()
    assert again["already_enrolled"] == [student["id"]]

    clash = client.post(f"/api/admin/classes/{other['id']}/students", json={"student_ids": [student["id"]]}, headers=admin).json()
    assert clash["failed"] and "Use transfer" in clash["failed"][0]["reason"]

    moved = client.post(f"/api/admin/classes/{klass['id']}/students/{student['id']}/transfer", json={"to_class_id": other["id"]}, headers=admin)
    assert moved.status_code == 200
    former = moved.json()["former_students"]
    assert [(f["id"], f["status"]) for f in former] == [(student["id"], "transferred")]
    assert former[0]["left_at"] is not None

    detail = client.get(f"/api/admin/users/{student['id']}", headers=admin).json()
    assert detail["class"]["name"] == other["name"]
    assert sorted(e["status"] for e in detail["enrolments"]) == ["active", "transferred"]

    assert client.delete(f"/api/admin/classes/{other['id']}/students/{student['id']}", headers=admin).status_code == 200
    detail = client.get(f"/api/admin/users/{student['id']}", headers=admin).json()
    assert detail["class"] is None and sorted(e["status"] for e in detail["enrolments"]) == ["transferred", "withdrawn"]

    with SessionLocal() as db:
        actions = set(db.scalars(select(AuditLog.action).where(AuditLog.resource_id == student["id"])))
    assert {"enrolment.enrol", "enrolment.transfer", "enrolment.withdraw"} <= actions


def test_class_teacher_access_ends_when_class_is_archived(client, admin, outbox):
    teacher, headers = _new_user(client, admin, outbox, role="teacher")
    klass = _new_class(client, admin, form=5, class_teacher_id=teacher["id"])
    student, _ = _new_user(client, admin, outbox, activate=False)
    client.post(f"/api/admin/classes/{klass['id']}/students", json={"student_ids": [student["id"]]}, headers=admin)

    assert client.get("/api/teachers/me", headers=headers).json()["teacher_types"] == ["class_teacher"]
    assert client.get(f"/api/teachers/students/{student['id']}", headers=headers).status_code == 200

    archived = client.post(f"/api/admin/classes/{klass['id']}/archive", headers=admin)
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    assert archived.json()["students"], "roster history is kept"
    assert client.get("/api/teachers/me", headers=headers).json()["teacher_types"] == []
    assert client.get(f"/api/teachers/students/{student['id']}", headers=headers).status_code == 403
    assert client.post(f"/api/admin/classes/{klass['id']}/students", json={"student_ids": [student["id"]]}, headers=admin).status_code == 409


def test_classes_from_another_school_are_invisible(client, admin):
    with SessionLocal() as db:
        other = db.scalar(select(School).where(School.name == "SMK Seri Bayu"))
        year = AcademicYear(school_id=other.id, name=f"Y{_uid()}", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        db.add(year)
        db.flush()
        klass = SchoolClass(school_id=other.id, academic_year_id=year.id, name="1 Elsewhere", form=1)
        db.add(klass)
        db.commit()
        class_id, year_id = klass.id, year.id
    assert client.get(f"/api/admin/classes/{class_id}", headers=admin).status_code == 404
    assert client.post("/api/admin/classes", json={"name": "Nope", "form": 1, "academic_year_id": year_id}, headers=admin).status_code == 404
    assert class_id not in {c["id"] for c in client.get("/api/admin/classes", params={"status": "all"}, headers=admin).json()}


# --- school profile and academic calendar ------------------------------------

def test_school_profile_update_is_validated_and_audited(client, admin):
    school = client.get("/api/admin/school", headers=admin).json()
    assert school["name"] == "SMK Taman Ilmu" and school["current_academic_year"]
    payload = {k: school[k] for k in ("name", "state", "address", "phone", "email", "logo_url", "timezone", "description")}

    assert client.put("/api/admin/school", json={**payload, "logo_url": "http://insecure.example/logo.png"}, headers=admin).status_code == 422
    assert client.put("/api/admin/school", json={**payload, "timezone": "Mars/Base"}, headers=admin).status_code == 422
    res = client.put("/api/admin/school", json={**payload, "phone": "03-1234 5678"}, headers=admin)
    assert res.status_code == 200 and res.json()["phone"] == "03-1234 5678"
    with SessionLocal() as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "school.update").order_by(AuditLog.created_at.desc()))
        assert entry.details["fields"] == "phone"


def test_academic_years_and_terms(client, admin):
    original = _current_year_id(client, admin)
    name = f"20{_uid()[:2]}-test"
    year = client.post("/api/admin/academic-years", json={"name": name, "start_date": "2031-01-01", "end_date": "2031-12-31"}, headers=admin)
    assert year.status_code == 201 and year.json()["is_current"] is False
    year_id = year.json()["id"]
    assert client.post("/api/admin/academic-years", json={"name": name, "start_date": "2031-01-01", "end_date": "2031-12-31"}, headers=admin).status_code == 409
    assert client.post("/api/admin/academic-years", json={"name": "Backwards", "start_date": "2031-12-31", "end_date": "2031-01-01"}, headers=admin).status_code == 422

    term = {"name": "Term 1", "start_date": "2031-01-10", "end_date": "2031-05-30"}
    assert client.post(f"/api/admin/academic-years/{year_id}/terms", json=term, headers=admin).status_code == 201
    overlap = {"name": "Term 2", "start_date": "2031-05-01", "end_date": "2031-09-30"}
    assert client.post(f"/api/admin/academic-years/{year_id}/terms", json=overlap, headers=admin).status_code == 422
    outside = {"name": "Term 3", "start_date": "2032-01-01", "end_date": "2032-03-01"}
    assert client.post(f"/api/admin/academic-years/{year_id}/terms", json=outside, headers=admin).status_code == 422
    shrink = client.put(f"/api/admin/academic-years/{year_id}", json={"name": name, "start_date": "2031-03-01", "end_date": "2031-12-31"}, headers=admin)
    assert shrink.status_code == 422

    try:
        switched = client.post(f"/api/admin/academic-years/{year_id}/set-current", headers=admin).json()
        assert switched["is_current"] is True
        currents = [y for y in client.get("/api/admin/academic-years", headers=admin).json() if y["is_current"]]
        assert [y["id"] for y in currents] == [year_id]
    finally:
        client.post(f"/api/admin/academic-years/{original}/set-current", headers=admin)


# --- CSV import --------------------------------------------------------------

def test_csv_import_previews_then_creates_only_valid_rows(client, admin, outbox):
    uid = _uid()
    klass = _new_class(client, admin)
    csv_text = (
        "role,full_name,email,student_number,staff_number,class,form\n"
        f"student,Import Good {uid},good{uid}@example.test,I{uid},,{klass['name'].lower()},4\n"
        f"teacher,Import Teacher {uid},teach{uid}@example.test,,IT{uid},,\n"
        f"student,Dup Email,aisyah@student.demo,J{uid},,,\n"
        f"student,No Class {uid},noclass{uid}@example.test,K{uid},,9 Nowhere,\n"
        f"student,Repeat {uid},good{uid}@example.test,L{uid},,,\n"
        f"student,Missing ID {uid},missing{uid}@example.test,,,,\n"
    )
    preview = client.post("/api/admin/users/import/preview", json={"csv": csv_text}, headers=admin)
    assert preview.status_code == 200
    data = preview.json()
    assert data["summary"] == {"total": 6, "ready": 2, "errors": 4}
    by_line = {r["line"]: r for r in data["rows"]}
    assert by_line[2]["status"] == "ready" and by_line[2]["class"] == klass["name"]
    assert "already in use" in " ".join(by_line[4]["errors"])
    assert "not found" in " ".join(by_line[5]["errors"])
    assert "repeated" in " ".join(by_line[6]["errors"])
    assert "Student ID is required" in " ".join(by_line[7]["errors"])

    with SessionLocal() as db:
        assert db.scalar(select(Profile).where(Profile.email == f"good{uid}@example.test")) is None, "preview must not create accounts"

    result = client.post("/api/admin/users/import/confirm", json={"csv": csv_text}, headers=admin).json()
    assert result["summary"] == {"created": 2, "failed": 4}
    assert len(outbox) == 2
    created = client.get("/api/admin/users", params={"q": f"good{uid}"}, headers=admin).json()["items"][0]
    assert created["class"]["name"] == klass["name"]


def test_csv_import_rejects_bad_headers(client, admin):
    bad = "name,email\nSomeone,someone@example.test\n"
    preview = client.post("/api/admin/users/import/preview", json={"csv": bad}, headers=admin).json()
    assert preview["header_errors"] and preview["rows"] == []
    assert client.post("/api/admin/users/import/confirm", json={"csv": bad}, headers=admin).status_code == 422


def test_overview_reports_unplaced_students(client, admin):
    data = client.get("/api/admin/overview", headers=admin).json()
    assert data["current_academic_year"] is not None
    assert any(a["kind"] == "students_without_class" for a in data["alerts"])  # Zara Ahmad in the demo data
    assert {c["subject"] for c in data["content"]} >= {"Mathematics"}
