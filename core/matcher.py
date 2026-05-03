# core/matcher.py
import json
import re

P2I_PROMPT = """你是一名专业的投资 FA 助手，请根据项目信息和投资机构列表，推荐最合适的投资机构。

项目信息：
{project_info}

投资机构列表：
{institutions_info}

请分析每家机构与该项目的匹配程度，返回推荐列表（按匹配度从高到低排序）。
JSON 格式，数组中每个元素包含：
- institution_id: 机构ID
- institution_name: 机构名称
- match_level: 匹配度（高/中/低）
- reason: 推荐理由（50字以内，说明具体匹配点）

只返回前10名，只返回 JSON 数组，不要其他内容。"""

I2P_PROMPT = """你是一名专业的投资 FA 助手，请根据投资机构的偏好和历史记录，从项目列表中推荐最合适的项目。

投资机构信息：
{institution_info}

项目列表：
{projects_info}

请分析每个项目与该机构的匹配程度，返回推荐列表（按匹配度从高到低排序）。
JSON 格式，数组中每个元素包含：
- project_id: 项目ID
- project_name: 项目名称
- match_level: 匹配度（高/中/低）
- reason: 推荐理由（50字以内，说明具体匹配点）

只返回 JSON 数组，不要其他内容。"""


def _fmt_project(p: dict) -> str:
    return (f"名称:{p.get('name')} | 赛道:{p.get('sector')} | 细分:{p.get('sub_sector')} | "
            f"阶段:{p.get('stage')} | 地点:{p.get('location')} | "
            f"简介:{p.get('description')} | 亮点:{p.get('highlights')} | "
            f"融资需求:{p.get('financing_need')}")


def _fmt_institution(inst: dict) -> str:
    return (f"ID:{inst.get('id')} | 名称:{inst.get('name')} | "
            f"偏好赛道:{inst.get('preferred_sectors')} | "
            f"偏好阶段:{inst.get('preferred_stages')} | "
            f"管理规模:{inst.get('aum')} | 地点:{inst.get('location')} | "
            f"特殊偏好:{inst.get('known_preferences')} | "
            f"历史投资:{inst.get('investment_records_summary', '')}")


def _parse_json_list(text: str) -> list:
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def match_project_to_institutions(project: dict, institutions: list, api_key: str = "") -> list:
    from core.llm import call_llm
    project_info = _fmt_project(project)
    institutions_info = "\n".join(_fmt_institution(i) for i in institutions)
    raw = call_llm(P2I_PROMPT.format(project_info=project_info,
                                     institutions_info=institutions_info))
    return _parse_json_list(raw)


def match_institution_to_projects(institution: dict, projects: list, api_key: str = "") -> list:
    from core.llm import call_llm
    institution_info = _fmt_institution(institution)
    projects_info = "\n".join(f"ID:{p.get('id')} | {_fmt_project(p)}" for p in projects)
    raw = call_llm(I2P_PROMPT.format(institution_info=institution_info,
                                     projects_info=projects_info))
    return _parse_json_list(raw)
