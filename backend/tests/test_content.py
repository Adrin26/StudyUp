def test_students_do_not_see_draft_content(client, admin, student):
    created = client.post("/api/admin/subjects", headers=admin, json={"code": "DRAFT1", "name": "Draft Subject", "forms": [4]})
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]
    assert created.json()["status"] == "draft"
    assert all(s["id"] != subject_id for s in client.get("/api/subjects", headers=student).json())
    assert client.get(f"/api/subjects/{subject_id}/topics", headers=student).status_code == 404

    published = client.post(f"/api/admin/subjects/{subject_id}/status", headers=admin, json={"status": "published"})
    assert published.status_code == 200
    assert client.get(f"/api/subjects/{subject_id}/topics", headers=student).status_code == 200

    topic = client.post("/api/admin/topics", headers=admin, json={"subject_id": subject_id, "name": "Hidden topic", "form": 4})
    assert topic.status_code == 201
    topic_id = topic.json()["id"]
    names = [t["name"] for t in client.get(f"/api/subjects/{subject_id}/topics", headers=student).json()["topics"]]
    assert "Hidden topic" not in names
    assert client.get(f"/api/topics/{topic_id}", headers=student).status_code == 404
    client.post(f"/api/admin/topics/{topic_id}/status", headers=admin, json={"status": "published"})
    assert client.get(f"/api/topics/{topic_id}", headers=student).status_code == 200


def test_students_cannot_open_a_draft_lesson(client, admin, student, farid):
    subjects = client.get("/api/admin/subjects", headers=admin).json()
    maths = next(s for s in subjects if s["code"] == "MATH")
    topics = client.get(f"/api/admin/subjects/{maths['id']}/topics", headers=admin).json()
    lesson = client.get(f"/api/lessons/topic/{topics[0]['id']}", headers=student)
    assert lesson.status_code == 200, lesson.text
    lesson_id = lesson.json()["id"]
    assert client.post(f"/api/admin/lessons/{lesson_id}/status", headers=admin, json={"status": "draft"}).status_code == 200
    assert client.get(f"/api/lessons/topic/{topics[0]['id']}", headers=student).status_code == 404
    assert client.get(f"/api/lessons/topic/{topics[0]['id']}", headers=farid).status_code == 200
    client.post(f"/api/admin/lessons/{lesson_id}/status", headers=admin, json={"status": "published"})


def test_questions_with_answers_are_archived_not_deleted(client, admin):
    page = client.get("/api/admin/questions?page_size=1", headers=admin)
    assert page.status_code == 200 and page.json()["total"] > 0
    question_id = page.json()["items"][0]["id"]
    removed = client.delete(f"/api/admin/questions/{question_id}", headers=admin)
    assert removed.status_code == 409
    archived = client.patch(f"/api/admin/questions/{question_id}", headers=admin, json={"status": "archived", "form": 4, "attribution": "Sample, not a past paper"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    client.patch(f"/api/admin/questions/{question_id}", headers=admin, json={"status": "published"})


def test_memo_visibility_and_acknowledgement(client, admin, student, farid):
    draft = client.post("/api/admin/memos", headers=admin, json={
        "title": "Sports day", "body": "Bring water.", "audience": "students", "requires_acknowledgement": True,
    })
    assert draft.status_code == 201, draft.text
    memo_id = draft.json()["id"]
    assert all(m["id"] != memo_id for m in client.get("/api/memos", headers=student).json())

    assert client.post(f"/api/admin/memos/{memo_id}/status", headers=admin, json={"status": "published"}).status_code == 200
    assert any(m["id"] == memo_id for m in client.get("/api/memos", headers=student).json())
    assert all(m["id"] != memo_id for m in client.get("/api/memos", headers=farid).json())

    opened = client.get(f"/api/memos/{memo_id}", headers=student)
    assert opened.status_code == 200 and opened.json()["read"] is True
    acked = client.post(f"/api/memos/{memo_id}/acknowledge", headers=student)
    assert acked.status_code == 200 and acked.json()["acknowledged"] is True
    assert client.post(f"/api/memos/{memo_id}/acknowledge", headers=farid).status_code == 404

    report = client.get(f"/api/admin/memos/{memo_id}/acknowledgements", headers=admin)
    assert report.status_code == 200
    assert "aisyah@student.demo" in report.text and "yes,yes" in report.text
    assert "farid@teacher.demo" not in report.text
