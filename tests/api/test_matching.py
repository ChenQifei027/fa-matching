import os, tempfile
_db = tempfile.mktemp(suffix=".db")
os.environ["DB_PATH"] = _db

from fastapi.testclient import TestClient
from api.main import app
from core.database import init_db
init_db(_db)

client = TestClient(app)


def test_project_not_found():
    assert client.post("/api/matching/project-to-institutions",
                       json={"project_id": 99999}).status_code == 404


def test_institution_not_found():
    assert client.post("/api/matching/institution-to-projects",
                       json={"institution_id": 99999}).status_code == 404


def test_project_match_returns_list():
    pid = client.post("/api/projects", json={"name": "P", "sector": "AI"}).json()["id"]
    r = client.post("/api/matching/project-to-institutions", json={"project_id": pid})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
