import asyncio
import json
import os
import streamlit as st
from dotenv import load_dotenv, set_key
from pathlib import Path

load_dotenv()
ENV_PATH = Path(".env")
BROWSER_STATE = Path(os.getenv("BROWSER_STATE_PATH", "data/browser_state.json"))


def _check_itjuzi_status() -> bool:
    if not BROWSER_STATE.exists():
        return False
    try:
        data = json.loads(BROWSER_STATE.read_text())
        cookies = data.get("cookies", [])
        return any("itjuzi" in c.get("domain", "") for c in cookies)
    except Exception:
        return False


async def _do_login():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.itjuzi.com/user/login")
        try:
            await page.wait_for_function(
                "!window.location.href.includes('/user/login')",
                timeout=180000
            )
        except Exception:
            pass
        await asyncio.sleep(2)
        BROWSER_STATE.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(BROWSER_STATE))
        await context.close()
        await browser.close()


st.title("⚙️ 设置")

# ── Claude API Key ──────────────────────────────────
st.subheader("Claude API Key")
current_key = os.getenv("ANTHROPIC_API_KEY", "")
masked = f"{current_key[:8]}...{current_key[-4:]}" if len(current_key) > 12 else "未配置"
st.text(f"当前：{masked}")
new_key = st.text_input("输入新的 API Key", type="password", placeholder="sk-ant-...")
if st.button("保存 API Key") and new_key:
    set_key(str(ENV_PATH), "ANTHROPIC_API_KEY", new_key)
    st.success("API Key 已保存，请重启应用生效")

st.divider()

# ── IT桔子 登录 ──────────────────────────────────
st.subheader("IT桔子 账号")

logged_in = _check_itjuzi_status()
if logged_in:
    st.success("✅ 已登录 IT桔子")
else:
    st.warning("⚠️ 未登录 IT桔子，机构投资记录抓取功能不可用")

col_login, col_logout = st.columns(2)

if col_login.button("🔑 登录 IT桔子", disabled=logged_in):
    st.info("正在打开浏览器，请在弹出的窗口中完成登录，登录成功后页面会自动保存登录态...")
    try:
        asyncio.run(_do_login())
        st.success("登录成功！登录态已保存")
        st.rerun()
    except Exception as e:
        st.error(f"登录失败：{e}")

if col_logout.button("🚪 退出登录", disabled=not logged_in):
    if BROWSER_STATE.exists():
        BROWSER_STATE.unlink()
    st.success("已退出登录")
    st.rerun()

st.divider()

# ── 数据存储 ──────────────────────────────────
st.subheader("数据存储")
db_path = os.getenv("DB_PATH", "data/fa_matching.db")
bp_dir = os.getenv("BP_DIR", "data/bps")
st.text(f"数据库路径：{Path(db_path).absolute()}")
st.text(f"BP 文件目录：{Path(bp_dir).absolute()}")
