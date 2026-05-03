# pages/1_projects.py
import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from core.database import init_db, insert_project, list_projects, get_project, \
    update_project, delete_project
from core.bp_parser import extract_text_from_file, extract_project_info

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fa_matching.db")
BP_DIR = Path(os.getenv("BP_DIR", "data/bps"))
from core.llm import llm_is_configured

init_db(DB_PATH)
BP_DIR.mkdir(parents=True, exist_ok=True)

st.title("📁 项目管理")

with st.expander("➕ 上传新 BP", expanded=False):
    uploaded = st.file_uploader("选择 BP 文件（PDF 或 PPTX）", type=["pdf", "pptx", "ppt"])
    if uploaded and st.button("开始解析"):
        if not llm_is_configured():
            st.error("请先在「设置」页面配置推理模型")
        else:
            save_path = BP_DIR / uploaded.name
            with open(save_path, "wb") as f:
                f.write(uploaded.getbuffer())

            with st.spinner("正在提取文本并分析 BP..."):
                text = extract_text_from_file(str(save_path))

            if not text.strip():
                st.warning("未能提取到文本（可能是图片型 PDF），请手动填写以下字段")
                text = ""

            with st.spinner("Claude 正在解析结构化信息..."):
                info = extract_project_info(text) if text else {}

            st.subheader("提取结果（可修改后保存）")
            with st.form("save_project_form"):
                name = st.text_input("项目名称", value=info.get("name", Path(uploaded.name).stem))
                col1, col2 = st.columns(2)
                sector = col1.text_input("赛道", value=info.get("sector", ""))
                sub_sector = col2.text_input("细分领域", value=info.get("sub_sector", ""))
                col3, col4 = st.columns(2)
                stage = col3.text_input("融资阶段", value=info.get("stage", ""))
                location = col4.text_input("所在地", value=info.get("location", ""))
                description = st.text_area("项目简介", value=info.get("description", ""))
                highlights = st.text_area("核心亮点", value=info.get("highlights", ""))
                financing_need = st.text_input("融资需求", value=info.get("financing_need", ""))

                if st.form_submit_button("✅ 确认保存"):
                    insert_project(
                        DB_PATH, name=name, file_path=str(save_path),
                        sector=sector, sub_sector=sub_sector, stage=stage,
                        location=location, description=description,
                        highlights=highlights, financing_need=financing_need
                    )
                    st.success(f"项目「{name}」已保存")
                    st.rerun()

projects = list_projects(DB_PATH)
st.subheader(f"项目列表（共 {len(projects)} 个）")

if not projects:
    st.info("暂无项目，请上传 BP")
else:
    selected_id = st.session_state.get("selected_project_id")

    for p in projects:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            col1.markdown(f"**{p['name']}**")
            col2.text(f"{p['sector']} · {p['sub_sector'] or ''}")
            col3.text(p['stage'] or "阶段未知")
            if col4.button("详情", key=f"detail_{p['id']}"):
                st.session_state["selected_project_id"] = p["id"]
                st.rerun()

    if selected_id:
        p = get_project(DB_PATH, selected_id)
        if p:
            st.divider()
            st.subheader(f"📄 {p['name']} — 详情")
            with st.form("edit_project_form"):
                col1, col2 = st.columns(2)
                sector = col1.text_input("赛道", value=p["sector"] or "")
                sub_sector = col2.text_input("细分领域", value=p["sub_sector"] or "")
                col3, col4 = st.columns(2)
                stage = col3.text_input("融资阶段", value=p["stage"] or "")
                location = col4.text_input("所在地", value=p["location"] or "")
                description = st.text_area("项目简介", value=p["description"] or "")
                highlights = st.text_area("核心亮点", value=p["highlights"] or "")
                financing_need = st.text_input("融资需求", value=p["financing_need"] or "")

                if st.form_submit_button("💾 保存修改"):
                    update_project(DB_PATH, selected_id, sector=sector, sub_sector=sub_sector,
                                   stage=stage, location=location, description=description,
                                   highlights=highlights, financing_need=financing_need)
                    st.success("已保存")
                    st.rerun()

            col_del, col_match = st.columns(2)
            if col_del.button("🗑️ 删除项目", type="secondary"):
                delete_project(DB_PATH, selected_id)
                st.session_state.pop("selected_project_id", None)
                st.rerun()
            if col_match.button("🔗 找匹配机构", type="primary"):
                st.session_state["match_project_id"] = selected_id
                st.switch_page("pages/3_matching.py")
