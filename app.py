import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="FA 投资匹配系统",
    page_icon="💼",
    layout="wide",
)

st.title("💼 FA 投资匹配系统")
st.caption("专为 FA 设计的项目与投资机构智能匹配工具")
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.page_link("pages/1_projects.py", label="📁 项目管理", use_container_width=True)
    st.caption("上传 BP，AI 自动提取赛道、阶段、亮点等结构化信息")

    st.page_link("pages/3_matching.py", label="🔗 匹配推荐", use_container_width=True)
    st.caption("双向智能匹配：给项目找投资机构 / 给机构找项目")

with col2:
    st.page_link("pages/2_institutions.py", label="🏦 机构管理", use_container_width=True)
    st.caption("管理投资机构信息，抓取 IT桔子 历史投资记录")

    st.page_link("pages/4_settings.py", label="⚙️ 设置", use_container_width=True)
    st.caption("配置 API Key、IT桔子 登录状态管理")
