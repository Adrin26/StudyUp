import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import AuditLog, PasswordResetToken, Profile, School, utcnow
from app.services import passwords

from .conftest import login

BAD = "Incorrect email/username or password"


def make_user(role: str = "student", password: str = "Secret123", status: str = "active") -> Profile:
    """A throwaway account so tests that change passwords or status don't affect shared demo users."""
    with SessionLocal() as db:
        school = db.scalar(select(School).where(School.name == "SMK Taman Ilmu"))
        tag = uuid.uuid4().hex[:8]
        p = Profile(email=f"user{tag}@test.demo", username=f"user{tag}", full_name=f"Test {tag}", role=role, status=status, school_id=school.id)
        db.add(p)
        db.flush()
        passwords.set_password(db, p, password)
        db.commit()
        db.refresh(p)
        db.expunge(p)
        return p


def set_status(profile_id: str, status: str) -> None:
    with SessionLocal() as db:
        db.get(Profile, profile_id).status = status
        db.commit()


@pytest.fixture
def captured_reset(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr("app.services.mailer.send_password_reset", lambda to, name, link, ttl: sent.append(link.split("token=")[1]) or True)
    return sent


# --- login -------------------------------------------------------------------


def test_login_with_email_or_username(client):
    u = make_user()
    for ident in (u.email, u.username, u.email.upper()):
        res = client.post("/api/auth/login", json={"identifier": ident, "password": "Secret123"})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["user"]["role"] == "student" and body["expires_in"] > 0
        assert not any("password" in k for k in body["user"])
    with SessionLocal() as db:
        assert db.get(Profile, u.id).last_login_at is not None


def test_wrong_password_and_unknown_user_look_identical(client):
    u = make_user()
    wrong = client.post("/api/auth/login", json={"identifier": u.email, "password": "Nope1234"})
    unknown = client.post("/api/auth/login", json={"identifier": "ghost@test.demo", "password": "Nope1234"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": BAD}


def test_login_is_rate_limited(client):
    u = make_user()
    for _ in range(get_settings().login_max_failures):
        assert client.post("/api/auth/login", json={"identifier": u.email, "password": "Nope1234"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"identifier": u.email, "password": "Secret123"})
    assert blocked.status_code == 429


def test_public_self_registration_does_not_exist(client):
    assert client.post("/api/auth/register", json={"email": "x@y.z", "password": "Secret123", "role": "admin"}).status_code in (404, 405)
    assert client.post("/api/auth/signup", json={"email": "x@y.z", "password": "Secret123", "role": "admin"}).status_code in (404, 405)


# --- disabled accounts -------------------------------------------------------


def test_disabled_account_cannot_sign_in_or_use_existing_session(client):
    u = make_user()
    headers = login(client, u.email, "Secret123")
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    set_status(u.id, "disabled")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 403 and me.json()["detail"]["code"] == "account_disabled"
    assert client.get("/api/students/me/dashboard", headers=headers).status_code == 403

    res = client.post("/api/auth/login", json={"identifier": u.email, "password": "Secret123"})
    assert res.status_code == 403 and res.json()["detail"]["code"] == "account_disabled"
    # A wrong password must not reveal that the account exists but is disabled.
    assert client.post("/api/auth/login", json={"identifier": u.email, "password": "Nope1234"}).json() == {"detail": BAD}

    set_status(u.id, "active")
    assert client.get("/api/auth/me", headers=headers).status_code == 200


# --- role guards -------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(client):
    for path in ("/api/auth/me", "/api/admin/overview", "/api/admin/audit-logs", "/api/teachers/me", "/api/students/me/dashboard"):
        res = client.get(path)
        assert res.status_code == 401, path
        assert res.json()["detail"]["code"] == "not_authenticated"


def test_garbage_token_is_treated_as_expired_session(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401 and res.json()["detail"]["code"] == "session_expired"


def test_students_and_teachers_cannot_use_admin_routes(client, student, farid):
    for headers in (student, farid):
        assert client.get("/api/admin/overview", headers=headers).status_code == 403
        assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403


def test_admin_is_not_a_teacher_or_student(client, admin):
    assert client.get("/api/teachers/me", headers=admin).status_code == 403
    assert client.get("/api/students/me/dashboard", headers=admin).status_code == 403


def test_admin_overview_counts_are_school_scoped(client, admin):
    data = client.get("/api/admin/overview", headers=admin).json()
    counts = data["counts"]
    with SessionLocal() as db:
        school = db.scalar(select(School).where(School.name == "SMK Taman Ilmu"))
        mine = list(db.scalars(select(Profile).where(Profile.school_id == school.id, Profile.status == "active")))
        lim = db.scalar(select(Profile).where(Profile.email == "lim@teacher.demo"))
    assert lim.school_id != school.id
    assert counts["active_students"] == sum(p.role == "student" for p in mine) >= 22
    assert counts["active_teachers"] == sum(p.role == "teacher" for p in mine) >= 3
    assert counts["classes"] == 2
    assert counts["subjects"] == 10 and counts["topics"] > 0
    assert all(a["role"] for a in data["recent_accounts"])


def test_disabled_users_are_excluded_from_active_counts(client, admin):
    before = client.get("/api/admin/overview", headers=admin).json()["counts"]["active_students"]
    make_user(status="disabled")
    assert client.get("/api/admin/overview", headers=admin).json()["counts"]["active_students"] == before


# --- teacher responsibilities are derived, not stored ------------------------


def test_teacher_responsibilities_come_from_assignments(client, farid, tan):
    assert client.get("/api/auth/me", headers=farid).json()["teacher_types"] == ["class_teacher", "subject_teacher"]
    assert client.get("/api/auth/me", headers=tan).json()["teacher_types"] == ["subject_teacher"]
    assert client.get("/api/teachers/me", headers=tan).json()["teacher_types"] == ["subject_teacher"]
    new_teacher = make_user(role="teacher")
    headers = login(client, new_teacher.email, "Secret123")
    assert client.get("/api/auth/me", headers=headers).json()["teacher_types"] == []
    assert client.get("/api/teachers/me", headers=headers).json()["subjects"] == []


# --- password recovery -------------------------------------------------------


def test_forgot_password_response_does_not_reveal_accounts(client, captured_reset):
    u = make_user()
    known = client.post("/api/auth/forgot-password", json={"identifier": u.email})
    unknown = client.post("/api/auth/forgot-password", json={"identifier": "ghost@test.demo"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(captured_reset) == 1


def test_disabled_accounts_get_no_reset_link(client, captured_reset):
    u = make_user(status="disabled")
    assert client.post("/api/auth/forgot-password", json={"identifier": u.email}).status_code == 202
    assert captured_reset == []


def test_password_reset_flow(client, captured_reset):
    u = make_user()
    old_session = login(client, u.email, "Secret123")
    client.post("/api/auth/forgot-password", json={"identifier": u.username})
    token = captured_reset[-1]

    with SessionLocal() as db:
        stored = db.scalar(select(PasswordResetToken).where(PasswordResetToken.profile_id == u.id))
        assert stored.token_hash != token, "raw token must not be stored"

    weak = client.post("/api/auth/reset-password", json={"token": token, "new_password": "short"})
    assert weak.status_code == 422
    ok = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewSecret456"})
    assert ok.status_code == 200, ok.text

    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Another789"}).status_code == 400
    assert client.get("/api/auth/me", headers=old_session).status_code == 401
    assert client.post("/api/auth/login", json={"identifier": u.email, "password": "Secret123"}).status_code == 401
    login(client, u.email, "NewSecret456")

    with SessionLocal() as db:
        actions = set(db.scalars(select(AuditLog.action).where(AuditLog.resource_id == u.id)))
    assert {"auth.password_reset_requested", "auth.password_reset_completed"} <= actions


def test_expired_and_superseded_reset_tokens_fail(client, captured_reset):
    u = make_user()
    client.post("/api/auth/forgot-password", json={"identifier": u.email})
    first = captured_reset[-1]
    client.post("/api/auth/forgot-password", json={"identifier": u.email})
    second = captured_reset[-1]
    assert client.post("/api/auth/reset-password", json={"token": first, "new_password": "NewSecret456"}).status_code == 400

    with SessionLocal() as db:
        for row in db.scalars(select(PasswordResetToken).where(PasswordResetToken.profile_id == u.id)):
            row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.post("/api/auth/reset-password", json={"token": second, "new_password": "NewSecret456"}).status_code == 400


def test_change_password(client):
    u = make_user()
    headers = login(client, u.email, "Secret123")
    wrong = client.post("/api/auth/change-password", headers=headers, json={"current_password": "Nope1234", "new_password": "NewSecret456"})
    assert wrong.status_code == 400
    same_as_email = client.post("/api/auth/change-password", headers=headers, json={"current_password": "Secret123", "new_password": u.email})
    assert same_as_email.status_code == 422

    ok = client.post("/api/auth/change-password", headers=headers, json={"current_password": "Secret123", "new_password": "NewSecret456"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401, "old sessions end after a password change"
    fresh = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=fresh).status_code == 200


def test_password_policy():
    assert passwords.password_problems("Secret123") == []
    assert passwords.password_problems("short1")
    assert passwords.password_problems("lettersonly")
    assert passwords.password_problems("12345678")
    assert passwords.password_problems("Ali12345", ("ali12345",))
    stored = passwords.hash_password("Secret123")
    assert stored.startswith("scrypt$") and "Secret123" not in stored
    assert passwords.verify_password("Secret123", stored) and not passwords.verify_password("Secret124", stored)


# --- audit log ---------------------------------------------------------------


def test_audit_log_is_admin_only_and_never_stores_secrets(client, admin, farid, captured_reset):
    u = make_user()
    client.post("/api/auth/forgot-password", json={"identifier": u.email})
    assert client.get("/api/admin/audit-logs", headers=farid).status_code == 403
    page = client.get("/api/admin/audit-logs?action=auth.", headers=admin).json()
    assert page["total"] >= 1 and all(i["action"].startswith("auth.") for i in page["items"])
    text = str(page).lower()
    assert captured_reset[-1].lower() not in text and "password_hash" not in text


# --- admin bootstrap (CLI only) ----------------------------------------------


def test_cli_create_admin(client, monkeypatch):
    from app import cli

    with SessionLocal() as db:
        school_id = db.scalar(select(School.id).where(School.name == "SMK Taman Ilmu"))
    monkeypatch.setenv("MINDA_ADMIN_PASSWORD", "AdminPass123")
    email = f"admin{uuid.uuid4().hex[:6]}@test.demo"
    args = ["create-admin", "--email", email, "--name", "Test Admin", "--school-id", school_id]
    cli.main(args)
    headers = login(client, email, "AdminPass123")
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "admin"
    assert client.get("/api/admin/overview", headers=headers).status_code == 200

    with pytest.raises(SystemExit):
        cli.main(args)  # duplicate email
    monkeypatch.setenv("MINDA_ADMIN_PASSWORD", "weak")
    with pytest.raises(SystemExit):
        cli.main(["create-admin", "--email", "other@test.demo", "--name", "X", "--school-id", school_id])


# --- AI feature flag ---------------------------------------------------------


def test_ai_routes_disappear_when_flag_is_off(client, student, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_features_enabled", False)
    assert client.get("/api/auth/config").json()["ai_enabled"] is False
    with SessionLocal() as db:
        from app.models import Question

        qid = db.scalar(select(Question.id).limit(1))
    assert client.post("/api/ai/hint", headers=student, json={"question_id": qid, "level": 1}).status_code == 404
    # Core learning still works without AI.
    assert client.get("/api/students/me/dashboard", headers=student).status_code == 200


def test_demo_accounts_hidden_outside_development(client, monkeypatch):
    assert any(a["role"] == "admin" for a in client.get("/api/auth/demo-accounts").json())
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert client.get("/api/auth/demo-accounts").status_code == 404
