# tests/test_database.py
import pytest
from core.database import init_db, insert_project, get_project, list_projects, \
    insert_institution, get_institution, list_institutions, \
    insert_investment_record, list_investment_records, \
    update_project, update_institution, delete_project, delete_institution

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path

def test_init_db_creates_tables(db):
    import sqlite3
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"projects", "institutions", "investment_records"}.issubset(tables)
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
