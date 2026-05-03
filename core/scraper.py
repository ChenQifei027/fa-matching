# core/scraper.py
import asyncio
import json
import random
import re
import time
from typing import Optional


async def _scrape_institution_investments(name: str, state_path: str) -> list:
    from browser_use import Agent
    from browser_use.browser.browser import Browser, BrowserConfig
    from core.llm import get_langchain_llm

    browser = Browser(config=BrowserConfig(headless=False))
    llm = get_langchain_llm()

    task = f"""
    在 IT桔子网站（https://www.itjuzi.com）上查找投资机构"{name}"的投资记录。
    步骤：
    1. 打开 https://www.itjuzi.com/investfirm，搜索"{name}"
    2. 点击该机构的详情页
    3. 找到"投资案例"或"投资记录"列表
    4. 收集所有投资记录，每条包含：被投公司名、所属行业、融资轮次、融资金额、投资时间
    5. 以 JSON 数组格式返回，格式：
       [{{"company_name": "", "sector": "", "stage": "", "amount": "", "invested_date": ""}}]
    只返回 JSON 数组，不要其他内容。
    """

    agent = Agent(task=task, llm=llm, browser=browser)
    try:
        result = await agent.run()
        raw = result.final_result() or "[]"
        raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        records = json.loads(raw)
        return records if isinstance(records, list) else []
    except Exception as e:
        print(f"[scraper] 爬取失败 {name}: {e}")
        return []
    finally:
        await browser.close()


def scrape_institution_investments(name: str, state_path: str) -> list:
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
