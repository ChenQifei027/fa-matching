import pytest
import json
import tempfile
import os
from core.database import (
    init_db, insert_institution, update_preference_profile,
    list_institutions_needing_analysis, list_recent_records,
    upsert_institution_by_name,
)

@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "test.db")
    init_db(p)
    return p

def test_upsert_institution_by_name_creates_new(db):
    iid = upsert_institution_by_name(db, "测试机构A", itjuzi_url="https://www.itjuzi.com/investfirm/999")
    assert iid > 0
    from core.database import get_institution
    inst = get_institution(db, iid)
    assert inst["name"] == "测试机构A"
    assert inst["source"] == "itjuzi_discovery"
    assert inst["itjuzi_url"] == "https://www.itjuzi.com/investfirm/999"

def test_upsert_institution_by_name_returns_existing(db):
    id1 = upsert_institution_by_name(db, "测试机构B")
    id2 = upsert_institution_by_name(db, "测试机构B")
    assert id1 == id2

def test_update_preference_profile(db):
    iid = insert_institution(db, name="测试机构C", source="manual")
    profile = {"investment_themes": ["AI"], "preferred_stages": ["A轮"], "summary": "测试", "recent_active": True, "records_count": 5}
    update_preference_profile(db, iid, json.dumps(profile))
    from core.database import get_institution
    inst = get_institution(db, iid)
    assert inst["preference_profile"] is not None
    assert inst["preference_analyzed_at"] is not None

def test_list_institutions_needing_analysis(db):
    from core.database import insert_investment_record
    iid = insert_institution(db, name="机构D", source="itjuzi_discovery")
    insert_investment_record(db, institution_id=iid, company_name="公司X", invested_date="2026-01-01")
    result = list_institutions_needing_analysis(db)
    assert any(r["id"] == iid for r in result)

def test_list_recent_records_filters_by_date(db):
    from core.database import insert_investment_record
    iid = insert_institution(db, name="机构E", source="itjuzi_discovery")
    insert_investment_record(db, institution_id=iid, company_name="新公司", invested_date="2025-06-01")
    insert_investment_record(db, institution_id=iid, company_name="旧公司", invested_date="2020-01-01")
    recent = list_recent_records(db, iid, years=2)
    names = [r["company_name"] for r in recent]
    assert "新公司" in names
    assert "旧公司" not in names
