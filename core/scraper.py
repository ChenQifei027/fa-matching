# core/scraper.py
import asyncio
import json
import random
import re
import time
from typing import Optional


async def _scrape_institution_investments(name: str, state_path: str) -> dict:
    from browser_use import Agent
    from browser_use.browser.browser import Browser, BrowserConfig
    from core.llm import get_langchain_llm

    browser = Browser(config=BrowserConfig(headless=False))
    llm = get_langchain_llm()

    task = f"""
    在 IT桔子网站（https://www.itjuzi.com）上查找投资机构"{name}"的完整信息。
    步骤：
    1. 打开 https://www.itjuzi.com/investfirm，搜索"{name}"
    2. 点击该机构的详情页
    3. 收集机构基本信息：官网、成立年份、管理规模(AUM)、当前基金期数、主要合伙人、偏好赛道、偏好阶段
    4. 找到"投资案例"或"投资记录"列表，收集所有投资记录
    5. 以 JSON 格式返回：
       {{"institution": {{"website": "", "founded_year": "", "aum": "", "current_fund": "", "key_partners": "", "preferred_sectors": "", "preferred_stages": ""}},
        "records": [{{"company_name": "", "sector": "", "stage": "", "amount": "", "invested_date": ""}}]}}
    只返回 JSON，不要其他内容。
    """

    agent = Agent(task=task, llm=llm, browser=browser)
    try:
        result = await agent.run()
        raw = result.final_result() or "{}"
        raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        data = json.loads(raw)
        return {
            "institution": data.get("institution", {}) if isinstance(data, dict) else {},
            "records": data.get("records", []) if isinstance(data, dict) else [],
        }
    except Exception as e:
        print(f"[scraper] 爬取失败 {name}: {e}")
        return {"institution": {}, "records": []}
    finally:
        await browser.close()


def scrape_institution_investments(name: str, state_path: str) -> dict:
    """同步包装器，供 Streamlit 调用。加随机延迟避免触发风控。"""
    time.sleep(random.uniform(2, 5))
    return asyncio.run(_scrape_institution_investments(name, state_path))


async def _get_itjuzi_url(name: str) -> Optional[str]:
    from browser_use import Agent
    from browser_use.browser.browser import Browser, BrowserConfig
    from langchain_anthropic import ChatAnthropic

    browser = Browser(config=BrowserConfig(headless=True))
    llm = ChatAnthropic(model="claude-sonnet-4-6")
    task = f"""在 IT桔子（https://www.itjuzi.com/investfirm）搜索"{name}"，
    返回该机构详情页的完整 URL。只返回 URL，不要其他内容。"""
    agent = Agent(task=task, llm=llm, browser=browser)
    try:
        result = await agent.run()
        url = (result.final_result() or "").strip()
        return url if url.startswith("http") else None
    except Exception:
        return None
    finally:
        await browser.close()


def get_itjuzi_url(name: str) -> Optional[str]:
    return asyncio.run(_get_itjuzi_url(name))
