import os
import tempfile

import pytest

_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["AUTH_MODE"] = "demo"
os.environ["OPENAI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed.run import run as seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded():
    seed(reset=True)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str) -> dict:
    res = client.post("/api/auth/demo-login", json={"email": email, "password": "demo1234"})
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
