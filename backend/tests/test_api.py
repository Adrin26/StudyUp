from sqlalchemy import select

from app.database import SessionLocal
from app.models import Question

from .conftest import login


def _subject_id(client, headers, code):
    return next(s["id"] for s in client.get("/api/subjects", headers=headers).json() if s["code"] == code)


def test_requires_auth(client):
    assert client.get("/api/students/me/dashboard").status_code == 401
    bad = client.post("/api/auth/login", json={"identifier": "aisyah@student.demo", "password": "nope"})
    assert bad.status_code == 401


def test_student_dashboard(client, student):
    data = client.get("/api/students/me/dashboard", headers=student).json()
    assert data["stats"]["streak"] == 7
    assert len(data["subjects"]) == 10
    assert data["recommendations"], "expected deterministic recommendations"
    assert any(a["title"] == "Quadratic Equations Booster" for a in data["assignments"])


def test_core_learning_loop(client, student):
    math_id = _subject_id(client, student, "MATH")
    topics = client.get(f"/api/subjects/{math_id}/topics", headers=student).json()["topics"]
    quad = next(t for t in topics if t["name"] == "Quadratic Equations")

    lesson = client.get(f"/api/lessons/topic/{quad['id']}", headers=student).json()
    assert len(lesson["slides"]) >= 5
    saved = client.put(f"/api/lessons/{lesson['id']}/progress", json={"current_slide": 2}, headers=student).json()
    assert saved["current_slide"] == 2

    quiz = client.post("/api/quiz/start", json={"topic_id": quad["id"]}, headers=student).json()
    assert len(quiz["questions"]) == 10
    assert all("correct_answer" not in q for q in quiz["questions"]), "answers must not leak before submission"

    with SessionLocal() as db:
        answers = {q.id: q.correct_answer.split("|")[0] for q in db.scalars(select(Question).where(Question.id.in_([q["id"] for q in quiz["questions"]])))}
    first_attempt = None
    for i, q in enumerate(quiz["questions"]):
        answer = answers[q["id"]] if i < 8 else "zzz"
        fb = client.post(f"/api/quiz/{quiz['id']}/answer", json={"question_id": q["id"], "answer": answer}, headers=student).json()
        assert fb["is_correct"] == (i < 8)
        if not fb["is_correct"] and first_attempt is None:
            first_attempt = fb["attempt_id"]

    result = client.post("/api/quiz/submit", json={"set_id": quiz["id"]}, headers=student).json()
    assert result["score"] == 8 and result["percentage"] == 80.0
    assert result["mastery_after"] > result["mastery_before"]
    assert len(result["wrong_questions"]) == 2
    assert result["xp_gained"] > 0

    explanation = client.post("/api/ai/explain", json={"attempt_id": first_attempt}, headers=student).json()
    assert explanation["source"] in ("fallback", "openai", "cache")
    assert explanation["data"]["steps"]
    fb = client.post("/api/ai/feedback", json={"interaction_id": explanation["interaction_id"], "helpful": True}, headers=student)
    assert fb.status_code == 200


def test_hint_never_contains_answer(client, student):
    with SessionLocal() as db:
        q = db.scalar(select(Question).where(Question.question_type == "mcq").limit(1))
    res = client.post("/api/ai/hint", json={"question_id": q.id, "level": 3}, headers=student).json()
    correct_text = next(o["text"] for o in q.options if o["key"] == q.correct_answer)
    assert correct_text.lower() not in res["data"]["hint"].lower()


def test_practice_generation_is_reproducible(client, student):
    math_id = _subject_id(client, student, "MATH")
    body = {"subject_id": math_id, "years": [2021, 2022], "num_questions": 5, "seed": 1234}
    a = client.post("/api/practice/generate", json=body, headers=student).json()
    b = client.post("/api/practice/generate", json=body, headers=student).json()
    assert [q["id"] for q in a["questions"]] == [q["id"] for q in b["questions"]]
    assert all(q["year"] in (2021, 2022) for q in a["questions"])


def test_subject_teacher_access_is_scoped(client, farid, tan, student):
    math_id = _subject_id(client, farid, "MATH")
    dash = client.get(f"/api/teachers/subjects/{math_id}/progress", headers=farid)
    assert dash.status_code == 200
    assert dash.json()["student_count"] == 22

    assert client.get(f"/api/teachers/subjects/{math_id}/progress", headers=tan).status_code == 403
    assert client.get(f"/api/teachers/subjects/{math_id}/progress", headers=student).status_code == 403


def test_class_teacher_overview(client, farid, tan):
    classes = client.get("/api/teachers/classes", headers=farid).json()
    bestari = next(c for c in classes if c["name"] == "4 Bestari")
    overview = client.get(f"/api/teachers/classes/{bestari['id']}/overview", headers=farid).json()
    assert overview["student_count"] == 14
    assert overview["subjects"] and overview["struggling_topics"]
    assert client.get(f"/api/teachers/classes/{bestari['id']}/overview", headers=tan).status_code == 403


def test_alerts_and_assignment(client, farid):
    alerts = client.get("/api/teachers/alerts", headers=farid).json()
    assert alerts
    alert = alerts[0]
    res = client.post("/api/teachers/assignments", headers=farid, json={
        "title": f"Practice: {alert['topic']}", "subject_id": alert["subject_id"], "topic_id": alert["topic_id"],
        "student_ids": [s["id"] for s in alert["students"]], "num_questions": 5,
    })
    assert res.status_code == 200, res.text


def test_exam_generate_and_save(client, farid):
    math_id = _subject_id(client, farid, "MATH")
    gen = client.post("/api/exams/generate", headers=farid, json={"subject_id": math_id, "num_questions": 10, "total_marks": 20, "seed": 5}).json()
    assert len(gen["questions"]) == 10 and gen["total_marks"] == 20
    ids = [q["id"] for q in gen["questions"]]
    rep = client.post("/api/exams/replace", headers=farid, json={"subject_id": math_id, "question_id": ids[0], "current_ids": ids}).json()
    assert rep["id"] not in ids
    saved = client.post("/api/exams", headers=farid, json={"title": "Mid-term", "subject_id": math_id, "question_ids": ids, "total_marks": 20})
    assert saved.status_code == 200 and saved.json()["total_marks"] == 20


def test_community_spaces(client, student, farid):
    assert client.get("/api/community/posts?space=teacher", headers=student).status_code == 403
    bad = client.post("/api/community/posts", headers=student, json={"space": "teacher", "title": "Hello", "body": "x"})
    assert bad.status_code == 403
    post = client.post("/api/community/posts", headers=student, json={"space": "student", "title": "Need help with indices", "body": "How do negative indices work?"}).json()
    voted = client.post(f"/api/community/posts/{post['id']}/vote", headers=student, json={"value": 1}).json()
    assert voted["score"] == 1
    other_school = login(client, "lim@teacher.demo")
    assert client.get(f"/api/community/posts/{post['id']}", headers=other_school).status_code == 404
