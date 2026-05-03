import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="FA 投资匹配系统",
    page_icon="💼",
    layout="wide",
)

st.title("💼 FA 投资匹配系统")
st.markdown("""
**快速导航：**
- 📁 **项目管理** — 上传和管理项目 BP
- 🏦 **机构管理** — 管理投资机构信息
- 🔗 **匹配推荐** — 双向智能匹配
- ⚙️ **设置** — API Key 和账号配置
""")
