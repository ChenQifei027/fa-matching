# tests/test_sector_glossary.py
import json
from core.sector_glossary import generate_sector_explanation


def _llm_payload(**overrides) -> str:
    base = {
        "description": "全主动悬架是一种电控悬架。",
        "industry_overview": "国内规模化前夜。",
        "top_companies": [{"name": "A 公司", "desc": "电磁作动器"}],
        "synonyms": ["主动悬架"],
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


def test_generate_parses_clean_json(mocker):
    mocker.patch("core.llm.call_llm", return_value=_llm_payload())
    out = generate_sector_explanation("全主动悬架")
    assert out["description"].startswith("全主动悬架")
    assert out["top_companies"] == [{"name": "A 公司", "desc": "电磁作动器"}]
    assert out["synonyms"] == ["主动悬架"]


def test_generate_strips_markdown_codefence(mocker):
    fenced = "```json\n" + _llm_payload() + "\n```"
    mocker.patch("core.llm.call_llm", return_value=fenced)
    out = generate_sector_explanation("AI芯片")
    assert out["description"]


def test_generate_handles_malformed_returns_defaults(mocker):
    mocker.patch("core.llm.call_llm", return_value="this is not json")
    out = generate_sector_explanation("不存在的词")
    assert out["description"] == ""
    assert out["top_companies"] == []
    assert out["synonyms"] == []


def test_generate_prompt_contains_sector_name(mocker):
    captured = {}
    def fake_call(prompt):
        captured["prompt"] = prompt
        return _llm_payload()
    mocker.patch("core.llm.call_llm", side_effect=fake_call)
    generate_sector_explanation("脑机接口")
    assert "脑机接口" in captured["prompt"]


def test_generate_null_list_fields_fall_back_to_defaults(mocker):
    """LLM may return {"top_companies": null}; we must coerce back to [] so callers don't crash."""
    mocker.patch("core.llm.call_llm",
                 return_value=_llm_payload(top_companies=None, synonyms=None, description=None))
    out = generate_sector_explanation("某赛道")
    assert out["top_companies"] == []
    assert out["synonyms"] == []
    assert out["description"] == ""  # None for string fields → default empty string too
