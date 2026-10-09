def _quadratic(client, headers):
    subjects = client.get("/api/subjects", headers=headers).json()
    maths = next(s for s in subjects if s["code"] == "MATH" or s["name"] == "Mathematics")
    topics = client.get(f"/api/subjects/{maths['id']}/topics", headers=headers).json()["topics"]
    return next(t for t in topics if t["name"] == "Quadratic Equations")


def test_quiz_is_ten_published_questions(client, student, admin):
    topic = _quadratic(client, student)
    questions = client.get("/api/admin/questions", headers=admin, params={"topic_id": topic["id"], "page_size": 1}).json()
    question_id = questions["items"][0]["id"]
    client.patch(f"/api/admin/questions/{question_id}", headers=admin, json={"status": "archived"})
    started = client.post("/api/quiz/start", headers=student, json={"topic_id": topic["id"]})
    assert started.status_code == 200, started.text
    body = started.json()
    assert len(body["questions"]) == 10
    assert all(q["id"] != question_id for q in body["questions"])
    client.patch(f"/api/admin/questions/{question_id}", headers=admin, json={"status": "published"})


def test_submitting_twice_does_not_award_xp_twice(client, student):
    topic = _quadratic(client, student)
    started = client.post("/api/quiz/start", headers=student, json={"topic_id": topic["id"]}).json()
    question = started["questions"][0]
    before = client.get("/api/students/me/dashboard", headers=student).json()["stats"]["xp"]
    answer = client.post(f"/api/quiz/{started['id']}/answer", headers=student, json={"question_id": question["id"], "answer": question["options"][0]["key"]})
    assert answer.status_code == 200, answer.text
    again = client.post(f"/api/quiz/{started['id']}/answer", headers=student, json={"question_id": question["id"], "answer": question["options"][0]["key"]})
    assert again.status_code == 200
    after_answer = client.get("/api/students/me/dashboard", headers=student).json()["stats"]["xp"]
    assert after_answer - before == answer.json()["xp_gained"]
    first = client.post("/api/quiz/submit", headers=student, json={"set_id": started["id"]})
    assert first.status_code == 200, first.text
    xp = client.get("/api/students/me/dashboard", headers=student).json()["stats"]["xp"]
    second = client.post("/api/quiz/submit", headers=student, json={"set_id": started["id"]})
    assert second.status_code == 200
    assert second.json()["score"] == first.json()["score"]
    assert client.get("/api/students/me/dashboard", headers=student).json()["stats"]["xp"] == xp


def test_past_year_filter(client, student):
    topic = _quadratic(client, student)
    page = client.get("/api/practice/questions", headers=student, params={"subject_id": topic["subject_id"], "topic_id": topic["id"], "year": 2019}).json()
    assert page["items"]
    assert all(item["year"] == 2019 for item in page["items"])
