# tests/test_database.py
import json
import pytest
from core.database import init_db, insert_project, get_project, list_projects, \
    insert_institution, get_institution, insert_investment_record, list_investment_records, \
    update_project, update_institution, delete_project, upsert_project_report, insert_funding_round, list_funding_rounds, \
    delete_project_funding_rounds, upsert_project_research

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path

def test_init_db_creates_tables(db):
    import sqlite3
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"projects", "institutions", "investment_records", "project_funding_rounds"}.issubset(tables)
    conn.close()

def test_insert_and_get_project(db):
    project_id = insert_project(db, name="测试项目", sector="AI", sub_sector="AI+医疗")
    project = get_project(db, project_id)
    assert project["name"] == "测试项目"
    assert project["sector"] == "AI"
    assert project["sub_sector"] == "AI+医疗"

def test_list_projects(db):
    insert_project(db, name="项目A", sector="AI")
    insert_project(db, name="项目B", sector="消费")
    projects = list_projects(db)
    assert len(projects) == 2

def test_update_project(db):
    pid = insert_project(db, name="项目A", sector="AI")
    update_project(db, pid, sector="消费", stage="A轮")
    p = get_project(db, pid)
    assert p["sector"] == "消费"
    assert p["stage"] == "A轮"

def test_delete_project(db):
    pid = insert_project(db, name="项目A", sector="AI")
    delete_project(db, pid)
    assert get_project(db, pid) is None

def test_insert_and_get_institution(db):
    iid = insert_institution(db, name="红杉资本", location="北京")
    inst = get_institution(db, iid)
    assert inst["name"] == "红杉资本"
    assert inst["location"] == "北京"

def test_update_institution(db):
    iid = insert_institution(db, name="红杉资本")
    update_institution(db, iid, aum="100亿", preferred_sectors="AI,消费")
    inst = get_institution(db, iid)
    assert inst["aum"] == "100亿"
    assert inst["preferred_sectors"] == "AI,消费"

def test_insert_and_list_investment_records(db):
    iid = insert_institution(db, name="红杉资本")
    insert_investment_record(db, institution_id=iid, company_name="字节跳动",
                              sector="TMT", stage="A轮", amount="5000万",
                              invested_date="2018-01-01", source="itjuzi")
    records = list_investment_records(db, iid)
    assert len(records) == 1
    assert records[0]["company_name"] == "字节跳动"

def test_no_duplicate_investment_records(db):
    iid = insert_institution(db, name="红杉资本")
    insert_investment_record(db, institution_id=iid, company_name="字节跳动",
                              sector="TMT", stage="A轮", amount="5000万",
                              invested_date="2018-01-01", source="itjuzi")
    insert_investment_record(db, institution_id=iid, company_name="字节跳动",
                              sector="TMT", stage="A轮", amount="5000万",
                              invested_date="2018-01-01", source="itjuzi")
    records = list_investment_records(db, iid)
    assert len(records) == 1


def test_upsert_project_report_sets_fields(db):
    pid = insert_project(db, name="Test Co")
    upsert_project_report(db, pid, '{"founded_year":"2020"}')
    p = get_project(db, pid)
    assert p["report_json"] == '{"founded_year":"2020"}'
    assert p["report_generated_at"] is not None


def test_upsert_project_report_overwrites(db):
    pid = insert_project(db, name="Test Co")
    upsert_project_report(db, pid, '{"founded_year":"2020"}')
    upsert_project_report(db, pid, '{"founded_year":"2021"}')
    p = get_project(db, pid)
    assert json.loads(p["report_json"])["founded_year"] == "2021"


def test_upsert_project_report_raises_on_missing_project(db):
    with pytest.raises(ValueError, match="not found"):
        upsert_project_report(db, 99999, '{}')


def test_insert_and_list_funding_rounds(db):
    pid = insert_project(db, name="Test Co")
    insert_funding_round(db, project_id=pid, round_date="2023-01-01",
                         round_type="A轮", amount="数千万", investors="红杉")
    rows = list_funding_rounds(db, pid)
    assert len(rows) == 1
    assert rows[0]["round_type"] == "A轮"


def test_insert_funding_round_deduplication(db):
    pid = insert_project(db, name="Test Co")
    insert_funding_round(db, project_id=pid, round_date="2023-01-01",
                         round_type="A轮", amount="数千万", investors="红杉")
    insert_funding_round(db, project_id=pid, round_date="2023-01-01",
                         round_type="A轮", amount="不同金额", investors="不同")
    rows = list_funding_rounds(db, pid)
    assert len(rows) == 1


def test_delete_project_funding_rounds(db):
    pid = insert_project(db, name="Test Co")
    insert_funding_round(db, project_id=pid, round_date="2023-01-01",
                         round_type="A轮", amount="数千万", investors="红杉")
    delete_project_funding_rounds(db, pid)
    assert list_funding_rounds(db, pid) == []


def test_list_funding_rounds_ordered_desc(db):
    pid = insert_project(db, name="Test Co")
    insert_funding_round(db, project_id=pid, round_date="2020-01-01",
                         round_type="Pre-A轮", amount="x", investors="x")
    insert_funding_round(db, project_id=pid, round_date="2023-06-01",
                         round_type="B轮", amount="y", investors="y")
    rows = list_funding_rounds(db, pid)
    assert rows[0]["round_date"] == "2023-06-01"


def test_delete_project_cascades_funding_rounds(db):
    pid = insert_project(db, name="Test Co")
    insert_funding_round(db, project_id=pid, round_date="2023-01-01",
                         round_type="A轮", amount="x", investors="y")
    delete_project(db, pid)
    assert list_funding_rounds(db, pid) == []
    assert get_project(db, pid) is None


def test_upsert_project_research_writes_json(db):
    pid = insert_project(db, name="绵存科技", sector="硬件")
    research = '{"industry_overview": "SSD存储行业..."}'
    upsert_project_research(db, pid, research)
    p = get_project(db, pid)
    assert p["research_json"] == research
    assert p["research_generated_at"] is not None


def test_upsert_project_research_overwrites(db):
    pid = insert_project(db, name="绵存科技", sector="硬件")
    upsert_project_research(db, pid, '{"industry_overview": "first"}')
    upsert_project_research(db, pid, '{"industry_overview": "second"}')
    p = get_project(db, pid)
    import json
    assert json.loads(p["research_json"])["industry_overview"] == "second"


def test_upsert_project_research_missing_project(db):
    import pytest
    with pytest.raises(ValueError, match="project 999 not found"):
        upsert_project_research(db, 999, '{}')


def test_sectors_upsert_and_get(db):
    from core.database import upsert_sector, get_sector

    upsert_sector(db, "全主动悬架",
                  description="一种电控悬架。",
                  industry_overview="国内规模化前夜。",
                  top_companies='[{"name":"A","desc":"x"}]',
                  synonyms='["主动悬架"]',
                  generated_by="claude-sonnet-4-6")
    row = get_sector(db, "全主动悬架")
    assert row["description"] == "一种电控悬架。"
    assert row["synonyms"] == '["主动悬架"]'
    assert row["generated_at"]  # 非空
    assert row["generated_by"] == "claude-sonnet-4-6"


def test_sectors_upsert_overwrites_existing(db):
    """Second upsert updates only the specified field; untouched fields survive."""
    from core.database import upsert_sector, get_sector

    upsert_sector(db, "AI芯片",
                  description="d1",
                  industry_overview="i1",
                  synonyms='["x"]')
    upsert_sector(db, "AI芯片", description="d2")
    row = get_sector(db, "AI芯片")
    assert row["description"] == "d2"          # updated field changed
    assert row["industry_overview"] == "i1"    # untouched field survived
    assert row["synonyms"] == '["x"]'          # untouched field survived


def test_get_sector_missing_returns_none(db):
    from core.database import get_sector
    assert get_sector(db, "不存在的赛道") is None


def test_delete_sector(db):
    from core.database import upsert_sector, get_sector, delete_sector
    upsert_sector(db, "X", description="d")
    delete_sector(db, "X")
    assert get_sector(db, "X") is None
