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


_PRESETS = {
    "Claude (Anthropic)": {"base_url": "", "model": "claude-sonnet-4-6"},
    "DeepSeek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "阿里百炼 (Qwen)": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-turbo"},
    "Ollama (本地)": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b"},
}

st.title("⚙️ 设置")

# ── 推理模型配置 ──────────────────────────────────
st.subheader("推理模型配置")

preset = st.selectbox("快速填充预设", ["（手动填写）"] + list(_PRESETS.keys()))

cur_api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
cur_base_url = os.getenv("LLM_BASE_URL", "")
cur_model = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

if preset != "（手动填写）":
    default_url = _PRESETS[preset]["base_url"]
    default_model = _PRESETS[preset]["model"]
else:
    default_url = cur_base_url
    default_model = cur_model

api_key_input = st.text_input(
    "API Key", type="password", value=cur_api_key,
    placeholder="Anthropic: sk-ant-... | DeepSeek: sk-... | 阿里百炼: sk-..."
)
base_url_input = st.text_input(
    "API Base URL（Claude 可留空）", value=default_url,
    placeholder="https://api.deepseek.com/v1"
)
model_input = st.text_input("模型名称", value=default_model, placeholder="claude-sonnet-4-6")

if st.button("💾 保存模型配置"):
    set_key(str(ENV_PATH), "LLM_API_KEY", api_key_input)
    set_key(str(ENV_PATH), "LLM_BASE_URL", base_url_input)
    set_key(str(ENV_PATH), "LLM_MODEL", model_input)
    if not base_url_input and api_key_input.startswith("sk-ant-"):
        set_key(str(ENV_PATH), "ANTHROPIC_API_KEY", api_key_input)
    st.success("已保存，请重启应用生效")

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
