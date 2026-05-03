# pages/3_matching.py
import os
import streamlit as st
from dotenv import load_dotenv
from core.database import init_db, list_projects, get_project, \
    list_institutions, get_institution, list_investment_records
from core.matcher import match_project_to_institutions, match_institution_to_projects

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fa_matching.db")
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

init_db(DB_PATH)

st.title("🔗 匹配推荐")

if not API_KEY:
    st.error("请先在「设置」页面配置 Claude API Key")
    st.stop()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📁 项目 → 推荐机构")
    projects = list_projects(DB_PATH)
    if not projects:
        st.info("暂无项目")
    else:
        project_options = {p["name"]: p["id"] for p in projects}
        default_name = next(
            (p["name"] for p in projects
             if p["id"] == st.session_state.get("match_project_id")),
            list(project_options.keys())[0]
        )
        selected_project_name = st.selectbox(
            "选择项目", list(project_options.keys()),
            index=list(project_options.keys()).index(default_name)
        )
        selected_pid = project_options[selected_project_name]

        if st.button("🚀 开始推荐机构", type="primary", key="btn_p2i"):
            project = get_project(DB_PATH, selected_pid)
            institutions = list_institutions(DB_PATH)
            if not institutions:
                st.warning("机构库为空，请先添加投资机构")
            else:
                enriched = []
                for inst in institutions:
                    records = list_investment_records(DB_PATH, inst["id"])
                    summary = "、".join(
                        f"{r['company_name']}({r['sector'] or ''})" for r in records[:10]
                    )
                    enriched.append({**inst, "investment_records_summary": summary})

                with st.spinner("Claude 正在分析匹配度..."):
                    results = match_project_to_institutions(project, enriched, API_KEY)

                st.session_state["p2i_results"] = results
                st.session_state["p2i_project_name"] = selected_project_name

    if "p2i_results" in st.session_state:
        st.markdown(f"**「{st.session_state['p2i_project_name']}」推荐机构：**")
        for r in st.session_state["p2i_results"]:
            level_color = {"高": "🟢", "中": "🟡", "低": "🔴"}.get(r.get("match_level", ""), "⚪")
            with st.container(border=True):
                st.markdown(f"{level_color} **{r.get('institution_name')}** — {r.get('match_level', '')}匹配")
                st.caption(r.get("reason", ""))

with col_right:
    st.subheader("🏦 机构 → 推荐项目")
    institutions = list_institutions(DB_PATH)
    if not institutions:
        st.info("暂无机构")
    else:
        inst_options = {i["name"]: i["id"] for i in institutions}
        default_inst = next(
            (i["name"] for i in institutions
             if i["id"] == st.session_state.get("match_institution_id")),
            list(inst_options.keys())[0]
        )
        selected_inst_name = st.selectbox(
            "选择机构", list(inst_options.keys()),
            index=list(inst_options.keys()).index(default_inst)
        )
        selected_iid = inst_options[selected_inst_name]

        if st.button("🚀 开始推荐项目", type="primary", key="btn_i2p"):
            institution = get_institution(DB_PATH, selected_iid)
            records = list_investment_records(DB_PATH, selected_iid)
            summary = "、".join(
                f"{r['company_name']}({r['sector'] or ''})" for r in records[:10]
            )
            enriched_institution = {**institution, "investment_records_summary": summary}
            projects = list_projects(DB_PATH)

            if not projects:
                st.warning("项目库为空，请先上传 BP")
            else:
                with st.spinner("Claude 正在分析匹配度..."):
                    results = match_institution_to_projects(enriched_institution, projects, API_KEY)

                st.session_state["i2p_results"] = results
                st.session_state["i2p_inst_name"] = selected_inst_name

    if "i2p_results" in st.session_state:
        st.markdown(f"**「{st.session_state['i2p_inst_name']}」推荐项目：**")
        for r in st.session_state["i2p_results"]:
            level_color = {"高": "🟢", "中": "🟡", "低": "🔴"}.get(r.get("match_level", ""), "⚪")
            with st.container(border=True):
                st.markdown(f"{level_color} **{r.get('project_name')}** — {r.get('match_level', '')}匹配")
                st.caption(r.get("reason", ""))
