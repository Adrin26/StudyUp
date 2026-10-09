from datetime import date, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Assignment, ExamPublication, Question, SchoolClass, utcnow

from .conftest import login


def _subject_id(client, headers, code):
    return next(s["id"] for s in client.get("/api/subjects", headers=headers).json() if s["code"] == code)


def _class_id(name):
    with SessionLocal() as db:
        return db.scalar(select(SchoolClass.id).where(SchoolClass.name == name))


def _correct(question_id):
    with SessionLocal() as db:
        return db.get(Question, question_id).correct_answer.split("|")[0]


def _me(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def _xp(client, headers):
    return client.get("/api/students/me/dashboard", headers=headers).json()["stats"]["xp"]


def _save_exam(client, teacher, code, n=4):
    subject = _subject_id(client, teacher, code)
    gen = client.post("/api/exams/generate", headers=teacher, json={"subject_id": subject, "num_questions": n, "total_marks": n, "seed": 11})
    assert gen.status_code == 200, gen.text
    ids = [q["id"] for q in gen.json()["questions"]]
    saved = client.post("/api/exams", headers=teacher, json={
        "title": f"{code} test", "subject_id": subject, "question_ids": ids, "total_marks": n, "config": {}, "seed": 11})
    assert saved.status_code == 200, saved.text
    return saved.json()["id"], ids


def _window(opens=-1, closes=2, release=3):
    now = utcnow()
    return {"opens_at": (now + timedelta(hours=opens)).isoformat(), "closes_at": (now + timedelta(hours=closes)).isoformat(),
            "release_at": (now + timedelta(hours=release)).isoformat()}


# ---- exam scope -------------------------------------------------------------

def test_exam_publish_is_scoped_to_teaching_assignments(client, farid, tan):
    exam_id, _ = _save_exam(client, farid, "MATH")
    bestari, cemerlang = _class_id("4 Bestari"), _class_id("4 Cemerlang")

    # Tan teaches Physics, not Maths, and does not own this exam.
    assert client.post(f"/api/exams/{exam_id}/publish", headers=tan, json={"class_id": bestari, **_window()}).status_code == 404

    phy_exam, _ = _save_exam(client, tan, "PHY")
    # Farid is class teacher of 4 Bestari only; he does not teach Physics in 4 Cemerlang.
    farid_phy, _ = _save_exam(client, farid, "PHY")
    assert client.post(f"/api/exams/{farid_phy}/publish", headers=farid, json={"class_id": cemerlang, **_window()}).status_code == 403
    assert client.post(f"/api/exams/{farid_phy}/publish", headers=farid, json={"class_id": bestari, **_window()}).status_code == 200
    assert client.post(f"/api/exams/{phy_exam}/publish", headers=tan, json={"class_id": cemerlang, **_window()}).status_code == 200


def test_exam_window_must_be_ordered(client, farid):
    exam_id, _ = _save_exam(client, farid, "MATH")
    bad = client.post(f"/api/exams/{exam_id}/publish", headers=farid, json={"class_id": _class_id("4 Bestari"), **_window(closes=2, release=1)})
    assert bad.status_code == 422


def test_students_outside_the_class_cannot_see_or_sit_the_exam(client, farid, student):
    exam_id, _ = _save_exam(client, farid, "MATH")
    pub = client.post(f"/api/exams/{exam_id}/publish", headers=farid, json={"class_id": _class_id("4 Bestari"), **_window()}).json()
    adam = login(client, "adam@student.demo")
    assert all(e["publication_id"] != pub["id"] for e in client.get("/api/my-exams", headers=adam).json())
    assert client.post(f"/api/my-exams/{pub['id']}/start", headers=adam).status_code == 404
    assert any(e["publication_id"] == pub["id"] for e in client.get("/api/my-exams", headers=student).json())
    # Students cannot reach teacher results.
    assert client.get(f"/api/exams/publications/{pub['id']}/results", headers=student).status_code == 403


def test_exam_not_open_yet(client, farid, student):
    exam_id, _ = _save_exam(client, farid, "MATH")
    pub = client.post(f"/api/exams/{exam_id}/publish", headers=farid, json={"class_id": _class_id("4 Bestari"), **_window(opens=1, closes=2, release=3)}).json()
    assert client.post(f"/api/my-exams/{pub['id']}/start", headers=student).status_code == 409


# ---- exam answer release ----------------------------------------------------

def test_exam_answers_hidden_until_release(client, farid, student):
    exam_id, ids = _save_exam(client, farid, "MATH")
    pub = client.post(f"/api/exams/{exam_id}/publish", headers=farid, json={"class_id": _class_id("4 Bestari"), **_window()}).json()
    xp_before = _xp(client, student)

    started = client.post(f"/api/my-exams/{pub['id']}/start", headers=student)
    assert started.status_code == 200, started.text
    assert all("correct_answer" not in q and "correct_display" not in q and "explanation" not in q for q in started.json()["questions"])

    first = client.post(f"/api/my-exams/{pub['id']}/answer", headers=student, json={"question_id": ids[0], "answer": _correct(ids[0])})
    assert first.status_code == 200
    assert set(first.json()) == {"question_id", "your_answer", "your_answer_display"}
    # The first answer stands.
    again = client.post(f"/api/my-exams/{pub['id']}/answer", headers=student, json={"question_id": ids[0], "answer": "zzz"})
    assert again.json()["your_answer"] == first.json()["your_answer"]

    # The AI answer checker must not reveal answers of an unreleased exam.
    assert client.post("/api/ai/similar-question/check", headers=student, json={"question_id": ids[0], "answer": "A"}).status_code == 404

    submitted = client.post(f"/api/my-exams/{pub['id']}/submit", headers=student).json()
    assert submitted["released"] is False and submitted["marks_awarded"] is None
    assert all("correct_display" not in q for q in submitted["questions"])
    assert client.post(f"/api/my-exams/{pub['id']}/answer", headers=student, json={"question_id": ids[1], "answer": "A"}).status_code == 409
    assert _xp(client, student) == xp_before

    results = client.get(f"/api/exams/publications/{pub['id']}/results", headers=farid).json()
    me = _me(client, student)
    row = next(r for r in results["students"] if r["student_id"] == me)
    assert row["status"] == "submitted" and row["marks"] >= 1

    with SessionLocal() as db:
        p = db.get(ExamPublication, pub["id"])
        p.closes_at = p.release_at = utcnow() - timedelta(minutes=1)
        db.commit()
    released = client.get(f"/api/my-exams/{pub['id']}", headers=student).json()
    assert released["released"] is True and released["marks_awarded"] == row["marks"]
    assert released["questions"][0]["is_correct"] is True and "correct_display" in released["questions"][0]


def test_unsubmitted_attempt_is_marked_when_the_window_closes(client, farid, student):
    exam_id, ids = _save_exam(client, farid, "MATH")
    pub = client.post(f"/api/exams/{exam_id}/publish", headers=farid, json={"class_id": _class_id("4 Bestari"), **_window()}).json()
    client.post(f"/api/my-exams/{pub['id']}/start", headers=student)
    client.post(f"/api/my-exams/{pub['id']}/answer", headers=student, json={"question_id": ids[0], "answer": _correct(ids[0])})
    with SessionLocal() as db:
        db.get(ExamPublication, pub["id"]).closes_at = utcnow() - timedelta(minutes=1)
        db.commit()
    mine = next(e for e in client.get("/api/my-exams", headers=student).json() if e["publication_id"] == pub["id"])
    assert mine["status"] == "submitted" and mine["released"] is False
    # Once students have started, the schedule is fixed and the exam cannot be deleted.
    assert client.post(f"/api/exams/{exam_id}/publish", headers=farid, json={"class_id": _class_id("4 Bestari"), **_window()}).status_code == 409
    assert client.delete(f"/api/exams/{exam_id}", headers=farid).status_code == 409


# ---- assignment window and feedback release ---------------------------------

def _assign(client, farid, student, **extra):
    math = _subject_id(client, farid, "MATH")
    res = client.post("/api/teachers/assignments", headers=farid, json={
        "title": "Held practice", "subject_id": math, "student_ids": [_me(client, student)], "num_questions": 3, **extra})
    assert res.status_code == 200, res.text
    return res.json()


def test_assignment_feedback_held_until_due(client, farid, student):
    due = (date.today() + timedelta(days=3)).isoformat()
    created = _assign(client, farid, student, due_date=due, feedback_release="after_due")
    qset = client.get(f"/api/practice/sets/{created['set_id']}", headers=student).json()
    assert qset["assignment"]["answers_visible"] is False
    q = qset["questions"][0]
    xp_before = _xp(client, student)

    ans = client.post("/api/practice/answer", headers=student, json={"set_id": created["set_id"], "question_id": q["id"], "answer": _correct(q["id"])})
    assert ans.status_code == 200, ans.text
    body = ans.json()
    assert body["feedback_hidden"] is True
    assert not {"is_correct", "correct_answer", "correct_display", "explanation", "attempt_id"} & set(body)
    assert _xp(client, student) == xp_before
    assert client.post("/api/ai/similar-question/check", headers=student, json={"question_id": q["id"], "answer": "A"}).status_code == 404

    done = client.post(f"/api/practice/sets/{created['set_id']}/complete", headers=student).json()
    assert done["feedback_hidden"] is True and "score" not in done
    mine = next(a for a in client.get("/api/students/me/assignments", headers=student).json() if a["id"] == created["id"])
    assert mine["score"] is None

    with SessionLocal() as db:
        db.get(Assignment, created["id"]).due_date = date.today() - timedelta(days=2)
        db.commit()
    after = client.get(f"/api/practice/sets/{created['set_id']}", headers=student).json()
    assert after["assignment"]["answers_visible"] is True
    assert after["answers"][q["id"]]["is_correct"] is True
    late = client.post("/api/practice/answer", headers=student, json={"set_id": created["set_id"], "question_id": qset["questions"][1]["id"], "answer": "A"})
    assert late.status_code == 409


def test_assignment_not_open_before_available_from(client, farid, student):
    opens = (utcnow() + timedelta(days=1)).isoformat()
    created = _assign(client, farid, student, available_from=opens)
    assert client.get(f"/api/practice/sets/{created['set_id']}", headers=student).status_code == 409
    q_id = client.get(f"/api/teachers/assignments", headers=farid).json()
    assert any(a["id"] == created["id"] and a["available_from"] for a in q_id)


def test_after_due_release_needs_a_due_date(client, farid, student):
    math = _subject_id(client, farid, "MATH")
    res = client.post("/api/teachers/assignments", headers=farid, json={
        "title": "x", "subject_id": math, "student_ids": [_me(client, student)], "feedback_release": "after_due"})
    assert res.status_code == 422
