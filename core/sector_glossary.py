# core/sector_glossary.py
import json
import re

SECTOR_PROMPT = """你是投资行业研究助手。请对以下"细分赛道"做结构化解释,便于早期项目投融资工作者快速理解。

赛道名:{name}

请严格返回 JSON(不要任何前后缀、不要 markdown 代码块),字段如下:

{{
  "description": "1-2 段话说明这个赛道是什么,不超过 150 字",
  "industry_overview": "3-5 句话说明行业发展阶段、市场规模、核心驱动力,不超过 200 字",
  "top_companies": [
    {{"name": "公司名", "desc": "一句话简介"}}
  ],
  "synonyms": ["近义/同义词1", "近义/同义词2"]
}}

要求:
- top_companies 给 3-8 家行业知名公司,每家一句话简介
- synonyms 给 0-5 个业内常用的近义或同义说法(按通用度排序)
- 任何字段无法可靠回答时,给出空字符串或空数组,不要编造
- 如果"{name}"看起来不是真实存在的赛道(疑似拼写错误或表述过宽),在 description 里说明,其他字段留空

只返回 JSON 本体,不要其他内容。"""


def generate_sector_explanation(name: str) -> dict:
    """调用 LLM 生成赛道解释。返回 dict,键固定为 description /
    industry_overview / top_companies / synonyms。LLM 失败或返回非 JSON
    时返回全默认值(空字符串/空数组),不抛异常。"""
    from core.llm import call_llm
    raw = call_llm(SECTOR_PROMPT.format(name=name)).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    defaults = {
        "description": "",
        "industry_overview": "",
        "top_companies": [],
        "synonyms": [],
    }
    result = {**defaults, **data}
    # Coerce None back to defaults — LLM may return {"top_companies": null}
    for key, default in defaults.items():
        if result[key] is None:
            result[key] = default
    return result
