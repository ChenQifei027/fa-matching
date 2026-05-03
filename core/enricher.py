# core/enricher.py
import json
import re

ENRICH_PROMPT = """你是一名专业的投资行业研究助手。请搜索并整理以下投资机构的公开信息，以 JSON 格式返回。

投资机构名称：{name}

请尽量填写以下字段，找不到的返回空字符串：
- website: 官方网站 URL
- founded_year: 成立年份
- aum: 管理资产规模（如"50亿人民币"、"10亿美元"）
- current_fund: 当前活跃基金期数（如"三期"、"Fund IV"）
- key_partners: 主要合伙人姓名（逗号分隔）
- notable_portfolio: 代表性被投项目（逗号分隔，列3-5个知名项目）
- preferred_locations: 偏好投资地域

只返回 JSON，不要其他内容。"""

def enrich_institution(name: str, api_key: str = "") -> dict:
    from core.llm import call_llm
    raw = call_llm(ENRICH_PROMPT.format(name=name)).strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    defaults = {"website": "", "founded_year": "", "aum": "", "current_fund": "",
                "key_partners": "", "notable_portfolio": "", "preferred_locations": ""}
    return {**defaults, **data}
