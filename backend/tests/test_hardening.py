import csv
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.database import SessionLocal
from app.models import Profile

from .test_community import _login_new, _user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _prod(**overrides) -> Settings:
    values = {
        "environment": "production",
        "app_secret": "x" * 40,
        "database_url": "postgresql+psycopg://u:p@db.example.com:5432/minda",
        "cors_origins": "https://minda.example.com",
        "frontend_url": "https://minda.example.com",
    } | overrides
    return Settings(_env_file=None, **values)


def test_production_settings_are_checked():
    assert _prod().environment == "production"
    for bad in (
        {"app_secret": "short"},
        {"database_url": "sqlite:///./x.db"},
        {"cors_origins": "*"},
        {"frontend_url": "http://localhost:5173"},
        {"smtp_host": "smtp.example.com"},
    ):
        with pytest.raises(ValidationError):
            _prod(**bad)
    assert _prod(smtp_host="smtp.example.com", smtp_from="MINDA <no-reply@example.com>").smtp_host


def test_security_headers_and_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["database"] == "ok"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"


def test_upload_contents_must_match_type(client, admin):
    question_id = client.get("/api/admin/questions?page_size=1", headers=admin).json()["items"][0]["id"]
    fake = client.post(f"/api/admin/questions/{question_id}/image", headers=admin,
                       files={"file": ("x.png", b"<html><script>alert(1)</script></html>", "image/png")})
    assert fake.status_code == 422
    real = client.post(f"/api/admin/questions/{question_id}/image", headers=admin, files={"file": ("diagram.png", PNG, "image/png")})
    assert real.status_code == 200, real.text
    served = client.get(real.json()["image_url"])
    assert served.status_code == 200 and served.content == PNG
    assert "sandbox" in served.headers["content-security-policy"]


def test_memo_attachments_follow_memo_visibility(client, admin, student, farid):
    memo = client.post("/api/admin/memos", headers=admin, json={"title": "Exam timetable", "body": "Attached.", "audience": "students"}).json()
    added = client.post(f"/api/admin/memos/{memo['id']}/attachments", headers=admin, files={"file": ("timetable.pdf", PDF, "application/pdf")})
    assert added.status_code == 201, added.text
    url = added.json()["attachments"][0]["url"]
    assert url.startswith(f"/api/memos/{memo['id']}/attachments/")

    # Draft: only the school's admin can download.
    assert client.get(url, headers=admin).content == PDF
    assert client.get(url, headers=student).status_code == 404
    assert client.get(url).status_code == 401

    client.post(f"/api/admin/memos/{memo['id']}/status", headers=admin, json={"status": "published"})
    got = client.get(url, headers=student)
    assert got.status_code == 200 and got.content == PDF
    assert "attachment" in got.headers["content-disposition"]
    assert client.get(url, headers=farid).status_code == 404  # teachers are not in the audience
    _, other_admin = _login_new(client, "admin", "SMK Seri Bayu")
    assert client.get(url, headers=other_admin).status_code == 404

    attachment_id = url.rsplit("/", 1)[1]
    removed = client.delete(f"/api/admin/memos/{memo['id']}/attachments/{attachment_id}", headers=admin)
    assert removed.status_code == 200 and removed.json()["attachments"] == []
    assert client.get(url, headers=student).status_code == 404


def test_seed_refuses_hosted_databases(monkeypatch):
    from sqlalchemy import create_engine

    from app.seed import run as seed_run

    monkeypatch.setattr(seed_run, "engine", create_engine("postgresql+psycopg://u:p@db.example.com:5432/minda"))
    with pytest.raises(SystemExit):
        seed_run.run()


def test_load_curriculum_into_empty_database(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = os.environ | {"DATABASE_URL": f"sqlite:///{tmp_path / 'fresh.db'}", "ENVIRONMENT": "test"}
    create = "import app.models; from app.database import Base, engine; Base.metadata.create_all(engine)"
    subprocess.run([sys.executable, "-c", create], cwd=backend, env=env, check=True)
    first = subprocess.run([sys.executable, "-m", "app.cli", "load-curriculum"], cwd=backend, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "sample questions" in first.stdout
    count = "from sqlalchemy import func, select; from app.database import SessionLocal; from app.models import Badge, Profile, Question; " \
            "db = SessionLocal(); print(db.scalar(select(func.count()).select_from(Question)), db.scalar(select(func.count()).select_from(Badge)), " \
            "db.scalar(select(func.count()).select_from(Profile)), db.scalar(select(func.count()).select_from(Question).where(Question.source != 'sample')))"
    questions, badges, people, not_sample = map(int, subprocess.run([sys.executable, "-c", count], cwd=backend, env=env, check=True, capture_output=True, text=True).stdout.split())
    assert questions > 100 and badges > 0 and people == 0 and not_sample == 0
    again = subprocess.run([sys.executable, "-m", "app.cli", "load-curriculum"], cwd=backend, env=env, capture_output=True, text=True)
    assert again.returncode == 1 and "already exist" in again.stderr


def test_acknowledgement_report_is_safe_csv(client, admin):
    uid, _ = _user("student")
    with SessionLocal() as db:
        db.get(Profile, uid).full_name = '=HYPERLINK("http://x"), Ali'
        db.commit()
    memo = client.post("/api/admin/memos", headers=admin, json={"title": "Fees", "body": "Pay.", "audience": "students"}).json()
    report = client.get(f"/api/admin/memos/{memo['id']}/acknowledgements", headers=admin)
    assert report.status_code == 200
    rows = list(csv.reader(io.StringIO(report.text)))
    assert rows[0] == ["name", "email", "role", "read", "acknowledged"]
    assert all(len(r) == 5 for r in rows)
    assert ["'=HYPERLINK(\"http://x\"), Ali"] == [r[0] for r in rows if "HYPERLINK" in r[0]]
