# tests/test_matcher.py
from core.matcher import match_project_to_institutions, match_institution_to_projects

SAMPLE_PROJECT = {
    "id": 1, "name": "智检科技", "sector": "AI", "sub_sector": "AI+工业质检",
    "stage": "Pre-A", "location": "深圳", "description": "基于视觉AI的工业质检",
    "highlights": "准确率99.5%;服务50家工厂", "financing_need": "3000万"
}

SAMPLE_INSTITUTIONS = [
    {"id": 1, "name": "红杉中国", "preferred_sectors": "AI,消费",
     "preferred_stages": "A轮,B轮", "aum": "数百亿", "location": "北京",
     "known_preferences": "", "investment_records_summary": "字节跳动(AI),美团(消费)"},
    {"id": 2, "name": "真格基金", "preferred_sectors": "AI,教育",
     "preferred_stages": "天使,Pre-A", "aum": "10亿美元", "location": "北京",
     "known_preferences": "偏好早期", "investment_records_summary": "知乎(社区),VIPKID(教育)"},
]


def test_match_project_to_institutions(mocker):
    mocker.patch(
        "core.llm.call_llm",
        return_value='[{"institution_id": 2, "institution_name": "真格基金", "match_level": "高", "reason": "偏好AI早期"}, {"institution_id": 1, "institution_name": "红杉中国", "match_level": "中", "reason": "投资过AI"}]'
    )
    results = match_project_to_institutions(SAMPLE_PROJECT, SAMPLE_INSTITUTIONS)
    assert len(results) == 2
    assert results[0]["match_level"] == "高"
    assert "reason" in results[0]


SAMPLE_INSTITUTION = {
    "id": 1, "name": "真格基金", "preferred_sectors": "AI,教育",
    "preferred_stages": "天使,Pre-A", "known_preferences": "偏好早期技术项目",
    "investment_records_summary": "知乎(社区),VIPKID(教育),作业帮(教育)"
}

SAMPLE_PROJECTS = [
    {"id": 1, "name": "智检科技", "sector": "AI", "sub_sector": "AI+工业质检",
     "stage": "Pre-A", "description": "工业质检AI", "highlights": "准确率99.5%",
     "location": "深圳", "financing_need": "3000万"},
    {"id": 2, "name": "慧学教育", "sector": "教育", "sub_sector": "K12在线教育",
     "stage": "天使", "description": "AI辅助教学", "highlights": "月活10万学生",
     "location": "北京", "financing_need": "1000万"},
]


def test_match_institution_to_projects(mocker):
    mocker.patch(
        "core.llm.call_llm",
        return_value='[{"project_id": 2, "project_name": "慧学教育", "match_level": "高", "reason": "教育赛道匹配"}, {"project_id": 1, "project_name": "智检科技", "match_level": "中", "reason": "AI赛道"}]'
    )
    results = match_institution_to_projects(SAMPLE_INSTITUTION, SAMPLE_PROJECTS)
    assert len(results) == 2
    assert results[0]["project_name"] == "慧学教育"
