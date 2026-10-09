import uuid
from datetime import date, timedelta

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Profile, School, XPEvent
from app.services import passwords

from .conftest import login


def _user(role: str, school_name: str = "SMK Taman Ilmu") -> tuple[str, dict]:
    with SessionLocal() as db:
        school = db.scalar(select(School).where(School.name == school_name))
        tag = uuid.uuid4().hex[:8]
        p = Profile(email=f"c{tag}@test.demo", username=f"c{tag}", full_name=f"Community {tag}", role=role, school_id=school.id)
        db.add(p)
        db.flush()
        passwords.set_password(db, p, "Secret123")
        db.commit()
        return p.id, p.email


def _login_new(client, role, school_name="SMK Taman Ilmu"):
    uid, email = _user(role, school_name)
    return uid, login(client, email, "Secret123")


def _post(client, headers, space="student", **extra):
    res = client.post("/api/community/posts", headers=headers, json={"space": space, "title": "How do I factorise this?", "body": "x² + 5x + 6", **extra})
    assert res.status_code == 200, res.text
    return res.json()


# ---- isolation ----------------------------------------------------------------

def test_student_community_is_private_to_its_school(client, student, farid):
    post = _post(client, student)
    _, outsider = _login_new(client, "student", "SMK Seri Bayu")
    assert client.get(f"/api/community/posts/{post['id']}", headers=outsider).status_code == 404
    assert all(p["id"] != post["id"] for p in client.get("/api/community/posts?space=student", headers=outsider).json())
    assert client.post(f"/api/community/posts/{post['id']}/comments", headers=outsider, json={"body": "hi"}).status_code == 404
    assert client.post(f"/api/community/posts/{post['id']}/report", headers=outsider, json={"reason": "spam"}).status_code == 404

    # Teachers of the same school can read and report, but not post, comment or vote.
    assert client.get(f"/api/community/posts/{post['id']}", headers=farid).status_code == 200
    assert client.post(f"/api/community/posts/{post['id']}/comments", headers=farid, json={"body": "x"}).status_code == 403
    assert client.post(f"/api/community/posts/{post['id']}/vote", headers=farid, json={"value": 1}).status_code == 403


def test_students_never_reach_the_teacher_community(client, student, farid):
    post = _post(client, farid, space="teacher")
    assert client.get("/api/community/posts?space=teacher", headers=student).status_code == 403
    assert client.get(f"/api/community/posts/{post['id']}", headers=student).status_code == 404
    assert client.post(f"/api/community/posts/{post['id']}/bookmark", headers=student).status_code in (404, 405)
    assert client.put(f"/api/community/posts/{post['id']}/bookmark", headers=student).status_code == 404
    # The teacher community is shared between schools.
    assert client.get(f"/api/community/posts/{post['id']}", headers=login(client, "lim@teacher.demo")).status_code == 200


# ---- voting -------------------------------------------------------------------

def test_one_vote_per_user(client, student):
    post = _post(client, student)
    ali = login(client, "ali@student.demo")
    url = f"/api/community/posts/{post['id']}/vote"
    assert client.post(url, headers=ali, json={"value": 1}).json()["score"] == 1
    assert client.post(url, headers=ali, json={"value": 1}).json()["score"] == 1
    assert client.post(url, headers=ali, json={"value": -1}).json()["score"] == -1
    assert client.post(url, headers=login(client, "sarah@student.demo"), json={"value": -1}).json()["score"] == -2
    assert client.post(url, headers=ali, json={"value": 0}).json()["score"] == -1
    assert client.post(url, headers=student, json={"value": 1}).status_code == 400
    assert client.post(url, headers=ali, json={"value": 5}).status_code == 422


# ---- reports and moderation -----------------------------------------------------

def test_report_and_moderate(client, student, admin):
    post = _post(client, student)
    ali = login(client, "ali@student.demo")
    assert client.post(f"/api/community/posts/{post['id']}/report", headers=student, json={"reason": "spam"}).status_code == 400
    assert client.post(f"/api/community/posts/{post['id']}/report", headers=ali, json={"reason": "inappropriate", "details": "rude"}).status_code == 200
    assert client.post(f"/api/community/posts/{post['id']}/report", headers=ali, json={"reason": "spam"}).status_code == 409

    queue = client.get("/api/community/reports", headers=admin).json()
    entry = next(e for e in queue if e["target_id"] == post["id"])
    assert entry["reports"][0]["reason"] == "inappropriate"
    assert client.get("/api/community/reports", headers=ali).status_code == 403

    _, other_admin = _login_new(client, "admin", "SMK Seri Bayu")
    assert all(e["target_id"] != post["id"] for e in client.get("/api/community/reports", headers=other_admin).json())
    assert client.post(f"/api/community/posts/{post['id']}/moderation", headers=other_admin, json={"action": "hide"}).status_code == 404
    farid = login(client, "farid@teacher.demo")
    assert client.post(f"/api/community/posts/{post['id']}/moderation", headers=farid, json={"action": "hide"}).status_code == 403

    hidden = client.post(f"/api/community/posts/{post['id']}/moderation", headers=admin, json={"action": "hide", "reason": "Please keep it kind"})
    assert hidden.status_code == 200 and hidden.json()["status"] == "hidden"
    assert client.get(f"/api/community/posts/{post['id']}", headers=ali).status_code == 404
    assert all(p["id"] != post["id"] for p in client.get("/api/community/posts?space=student", headers=ali).json())
    mine = client.get(f"/api/community/posts/{post['id']}", headers=student).json()
    assert mine["status"] == "hidden" and mine["moderation_reason"] == "Please keep it kind" and mine["can_comment"] is False
    notes = client.get("/api/notifications", headers=student).json()
    assert any(n["title"].startswith("Your post was hidden") for n in notes)
    assert all(e["target_id"] != post["id"] for e in client.get("/api/community/reports", headers=admin).json())

    client.post(f"/api/community/posts/{post['id']}/moderation", headers=admin, json={"action": "restore"})
    assert client.get(f"/api/community/posts/{post['id']}", headers=ali).status_code == 200


def test_comment_hidden_after_several_reports(client, student, admin):
    post = _post(client, student)
    ali = login(client, "ali@student.demo")
    comment = client.post(f"/api/community/posts/{post['id']}/comments", headers=ali, json={"body": "Just expand it"}).json()
    for email in ("sarah@student.demo", "john@student.demo", "amir@student.demo"):
        res = client.post(f"/api/community/comments/{comment['id']}/report", headers=login(client, email), json={"reason": "off_topic"})
        assert res.status_code == 200
    detail = client.get(f"/api/community/posts/{post['id']}", headers=student).json()
    assert all(c["id"] != comment["id"] for c in detail["comments"])
    assert any(n["title"] == "Reported content was hidden automatically" for n in client.get("/api/notifications", headers=admin).json())


# ---- content rules, replies, bookmarks, rate limits -------------------------------

def test_links_and_contact_details_blocked_for_students(client, student, farid):
    for body in ("see https://example.com", "visit cheats.xyz now", "email me at amir@gmail.com", "call 012-345 6789"):
        res = client.post("/api/community/posts", headers=student, json={"space": "student", "title": "Help", "body": body})
        assert res.status_code == 422, body
    assert _post(client, farid, space="teacher", body="Slides: https://example.com/slides")["id"]
    bad = client.post("/api/community/posts", headers=farid, json={"space": "teacher", "title": "Hi", "body": "javascript:alert(1)"})
    assert bad.status_code == 422


def test_replies_notify_and_stay_one_level(client, student):
    post = _post(client, student)
    ali = login(client, "ali@student.demo")
    before = client.get("/api/notifications/unread-count", headers=student).json()["count"]
    top = client.post(f"/api/community/posts/{post['id']}/comments", headers=ali, json={"body": "Try factor pairs of 6"}).json()
    reply = client.post(f"/api/community/posts/{post['id']}/comments", headers=student, json={"body": "Thanks!", "parent_id": top["id"]})
    assert reply.status_code == 200 and reply.json()["parent_id"] == top["id"]
    nested = client.post(f"/api/community/posts/{post['id']}/comments", headers=ali, json={"body": "np", "parent_id": reply.json()["id"]})
    assert nested.status_code == 400
    assert client.get("/api/notifications/unread-count", headers=student).json()["count"] == before + 1
    assert any(n["title"].endswith("replied") for n in client.get("/api/notifications", headers=ali).json())

    note = client.get("/api/notifications?unread=true", headers=student).json()[0]
    assert client.post(f"/api/notifications/{note['id']}/read", headers=ali).status_code == 404
    assert client.post(f"/api/notifications/{note['id']}/read", headers=student).json()["read"] is True
    client.post("/api/notifications/read-all", headers=student)
    assert client.get("/api/notifications/unread-count", headers=student).json()["count"] == 0

    assert client.delete(f"/api/community/comments/{top['id']}", headers=student).status_code == 403
    assert client.delete(f"/api/community/comments/{top['id']}", headers=ali).status_code == 204
    assert client.get(f"/api/community/posts/{post['id']}", headers=student).json()["comment_count"] == 0


def test_bookmarks(client, student):
    post = _post(client, login(client, "ali@student.demo"))
    assert client.put(f"/api/community/posts/{post['id']}/bookmark", headers=student).status_code == 204
    saved = client.get("/api/community/posts?space=student&saved=true", headers=student).json()
    assert [p["id"] for p in saved if p["id"] == post["id"]] and all(p["bookmarked"] for p in saved)
    client.delete(f"/api/community/posts/{post['id']}/bookmark", headers=student)
    assert all(p["id"] != post["id"] for p in client.get("/api/community/posts?space=student&saved=true", headers=student).json())


def test_posting_is_rate_limited(client):
    _, headers = _login_new(client, "student")
    for _ in range(5):
        _post(client, headers)
    assert client.post("/api/community/posts", headers=headers, json={"space": "student", "title": "One more", "body": "x"}).status_code == 429


# ---- calendar -------------------------------------------------------------------

def test_calendar_audience_and_scope(client, admin, student, farid):
    day = date.today() + timedelta(days=10)
    created = client.post("/api/admin/calendar", headers=admin, json={"title": "Staff briefing", "kind": "meeting", "audience": "teachers", "start_date": day.isoformat()})
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    params = {"start": (day - timedelta(days=1)).isoformat(), "end": (day + timedelta(days=1)).isoformat()}
    assert any(i["id"] == event_id for i in client.get("/api/calendar", headers=farid, params=params).json())
    assert all(i["id"] != event_id for i in client.get("/api/calendar", headers=student, params=params).json())

    assert client.post("/api/admin/calendar", headers=farid, json={"title": "x", "start_date": day.isoformat()}).status_code == 403
    _, other_admin = _login_new(client, "admin", "SMK Seri Bayu")
    assert client.delete(f"/api/admin/calendar/{event_id}", headers=other_admin).status_code == 404
    bad = client.post("/api/admin/calendar", headers=admin, json={"title": "Bad", "start_date": day.isoformat(), "end_date": (day - timedelta(days=1)).isoformat()})
    assert bad.status_code == 422
    assert client.delete(f"/api/admin/calendar/{event_id}", headers=admin).status_code == 204


def test_calendar_shows_terms_and_personal_deadlines(client, student):
    today = date.today()
    items = client.get("/api/calendar", headers=student, params={"start": date(today.year, 1, 1).isoformat(), "end": date(today.year, 12, 31).isoformat()}).json()
    sources = {i["source"] for i in items}
    assert "term" in sources and "school" in sources


# ---- XP ledger ------------------------------------------------------------------

def test_xp_ledger_matches_total(client, student):
    xp = client.get("/api/students/me/xp", headers=student).json()
    assert sum(xp["by_reason"].values()) == xp["total"]
    assert client.get("/api/gamification/rules", headers=login(client, "farid@teacher.demo")).json()["earning"]
    with SessionLocal() as db:
        mismatched = db.execute(
            select(Profile.id).outerjoin(XPEvent, XPEvent.student_id == Profile.id).where(Profile.role == "student")
            .group_by(Profile.id, Profile.xp).having(func.coalesce(func.sum(XPEvent.amount), 0) != Profile.xp)
        ).all()
    assert mismatched == []
