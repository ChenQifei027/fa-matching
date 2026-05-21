# tests/api/test_sectors.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db))
    # 重新 import 让 module 内的 DB_PATH 模块级变量读到新值
    import importlib, api.main as main_mod, api.routers.sectors as sectors_mod
    importlib.reload(sectors_mod)
    importlib.reload(main_mod)
    return TestClient(main_mod.app), str(db)


def test_get_missing_sector_returns_404(client):
    c, _ = client
    assert c.get("/api/sectors/未生成的赛道").status_code == 404


def test_get_existing_sector_returns_data(client):
    c, db = client
    from core.database import upsert_sector
    upsert_sector(db, "AI芯片",
                  description="d", industry_overview="i",
                  top_companies='[{"name":"X","desc":"y"}]',
                  synonyms='["AI 加速器"]')
    r = c.get("/api/sectors/AI芯片")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "AI芯片"
    assert body["description"] == "d"
    assert body["top_companies"] == [{"name": "X", "desc": "y"}]
    assert body["synonyms"] == ["AI 加速器"]


def test_post_triggers_generation_and_stores(client, mocker):
    c, _ = client
    mocker.patch("core.sector_glossary.generate_sector_explanation",
                 return_value={"description": "gen-desc",
                               "industry_overview": "ov",
                               "top_companies": [{"name": "A", "desc": "x"}],
                               "synonyms": ["近义"]})
    r = c.post("/api/sectors/新赛道")
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    from api.jobs import get_job
    for _ in range(50):
        if get_job(job_id)["status"] in ("completed", "failed"):
            break
    assert get_job(job_id)["status"] == "completed"
    g = c.get("/api/sectors/新赛道")
    assert g.status_code == 200
    assert g.json()["description"] == "gen-desc"


def test_post_existing_without_force_is_409(client):
    c, db = client
    from core.database import upsert_sector
    upsert_sector(db, "已存在", description="old")
    r = c.post("/api/sectors/已存在")
    assert r.status_code == 409


def test_post_existing_with_force_regenerates(client, mocker):
    c, db = client
    from core.database import upsert_sector
    upsert_sector(db, "已存在", description="old")
    mocker.patch("core.sector_glossary.generate_sector_explanation",
                 return_value={"description": "new", "industry_overview": "",
                               "top_companies": [], "synonyms": []})
    r = c.post("/api/sectors/已存在?force=true")
    assert r.status_code == 202
    from api.jobs import get_job
    job_id = r.json()["job_id"]
    for _ in range(50):
        if get_job(job_id)["status"] in ("completed", "failed"):
            break
    assert get_job(job_id)["status"] == "completed"
    assert c.get("/api/sectors/已存在").json()["description"] == "new"
