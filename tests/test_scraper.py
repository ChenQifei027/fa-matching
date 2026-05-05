from core.scraper import _parse_company_funding_from_text


def test_parse_normal_rounds():
    lines = [
        "2020-04-13", "战略投资", "数千万人民币", "腾讯投资", "反馈",
        "2021-05-24", "Pre-A轮", "数千万人民币", "海贝资本（领投）", "高通Qualcomm", "反馈",
    ]
    result = _parse_company_funding_from_text(lines)
    assert len(result) == 2
    assert result[0]["round_date"] == "2020-04-13"
    assert result[0]["round_type"] == "战略投资"
    assert result[0]["amount"] == "数千万人民币"
    assert result[0]["investors"] == "腾讯投资"
    assert result[1]["investors"] == "海贝资本（领投）,高通Qualcomm"


def test_parse_filters_noise_tokens():
    lines = [
        "2022-06-01", "A轮", "未透露", "举报", "纠错", "红杉资本", "反馈",
    ]
    result = _parse_company_funding_from_text(lines)
    assert len(result) == 1
    assert result[0]["investors"] == "红杉资本"


def test_parse_empty_lines():
    assert _parse_company_funding_from_text([]) == []


def test_parse_no_date_lines():
    lines = ["这不是日期", "也不是", "随便什么"]
    assert _parse_company_funding_from_text(lines) == []


def test_parse_round_with_no_investors():
    lines = ["2023-01-01", "B轮", "未透露", "反馈"]
    result = _parse_company_funding_from_text(lines)
    assert len(result) == 1
    assert result[0]["investors"] == ""
