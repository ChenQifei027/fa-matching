# tests/test_enricher.py
import pytest
from unittest.mock import MagicMock
from core.enricher import enrich_institution

def test_enrich_institution_returns_required_fields(mocker):
    mock_client = mocker.patch("core.enricher.anthropic.Anthropic")
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    mock_instance.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"website": "https://sequoiacap.com", "founded_year": "2005", "aum": "数百亿美元", "current_fund": "第八期", "key_partners": "沈南鹏", "notable_portfolio": "字节跳动,美团,滴滴", "preferred_locations": "全国"}')]
    )
    result = enrich_institution("红杉中国", api_key="test_key")
    assert result["website"] == "https://sequoiacap.com"
    assert result["key_partners"] == "沈南鹏"
    assert isinstance(result, dict)

def test_enrich_institution_handles_empty_response(mocker):
    mock_client = mocker.patch("core.enricher.anthropic.Anthropic")
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    mock_instance.messages.create.return_value = MagicMock(
        content=[MagicMock(text="{}")]
    )
    result = enrich_institution("未知机构XYZ", api_key="test_key")
    assert isinstance(result, dict)
    assert result.get("website", "") == ""
