import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
_db_file = os.path.join(_tmp, "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["PRIVATE_UPLOAD_DIR"] = os.path.join(_tmp, "private_uploads")
os.environ["SMTP_HOST"] = ""
os.environ["AUTH_MODE"] = "local"
os.environ["ENVIRONMENT"] = "test"
os.environ["AI_FEATURES_ENABLED"] = "true"
os.environ["OPENAI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed.run import run as seed  # noqa: E402
from app.services.rate_limit import limiter  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded():
    seed(reset=True)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, identifier: str, password: str = "demo1234") -> dict:
    res = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def student(client):
    return login(client, "aisyah@student.demo")


@pytest.fixture
def farid(client):
    return login(client, "farid@teacher.demo")


@pytest.fixture
def tan(client):
    return login(client, "tan@teacher.demo")


@pytest.fixture
def admin(client):
    return login(client, "admin@school.demo")
