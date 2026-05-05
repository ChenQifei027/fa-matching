# pages/1_projects.py
import io
import json
import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from core.database import (
    init_db, insert_project, list_projects, get_project,
    update_project, delete_project,
    upsert_project_report, insert_funding_round,
    list_funding_rounds, delete_project_funding_rounds,
)
from core.bp_parser import extract_text_from_file, extract_project_info, extract_report_info
from core.scraper import scrape_company_funding

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fa_matching.db")
BP_DIR = Path(os.getenv("BP_DIR", "data/bps"))
BROWSER_STATE = os.getenv("BROWSER_STATE", "")
from core.llm import llm_is_configured

init_db(DB_PATH)
BP_DIR.mkdir(parents=True, exist_ok=True)


def _render_report_panel(db_path, project, browser_state):
    import pandas as pd

    pid = project["id"]
    has_cache = bool(project.get("report_generated_at"))

    title_col, close_col, export_col, regen_col = st.columns([5, 1, 2, 2])
    title_col.subheader(f"📊 {project['name']} — 项目报告")
    if close_col.button("✕ 关闭", key="close_report"):
        st.session_state.pop("report_project_id", None)
        st.rerun()

    def _do_generate(gen_key=None):
        try:
            with st.status("正在生成项目报告...", expanded=True) as status:
                st.write("LLM 分析 BP 文本...")
                bp_text = extract_text_from_file(project["file_path"]) if project.get("file_path") else ""
                report = extract_report_info(bp_text)
                upsert_project_report(db_path, pid, json.dumps(report, ensure_ascii=False))

                st.write("从 IT桔子 获取历史融资记录...")
                delete_project_funding_rounds(db_path, pid)
                rounds = scrape_company_funding(project["name"], browser_state)
                for r in rounds:
                    insert_funding_round(db_path, project_id=pid, **r)

                status.update(
                    label=f"报告生成完成，获取 {len(rounds)} 条融资记录",
                    state="complete"
                )
        except Exception as e:
            st.warning(f"报告生成部分失败：{e}")
        if gen_key:
            st.session_state.pop(gen_key, None)
        st.rerun()

    gen_key = f"report_generating_{pid}"
    if not has_cache:
        if st.session_state.get(gen_key):
            st.info("报告生成中，请稍候...")
            return
        st.session_state[gen_key] = True
        _do_generate(gen_key)
        return

    # Show cached report
    report = {}
    try:
        report = json.loads(project.get("report_json") or "{}")
    except Exception:
        pass

    rounds = list_funding_rounds(db_path, pid)
    gen_time = (project.get("report_generated_at") or "")[:16].replace("T", " ")

    if regen_col.button("🔄 重新生成", key="regen_report"):
        _do_generate(gen_key)
        return

    # Excel export
    output = io.BytesIO()
    basic_rows = [
        {"字段": "成立时间", "内容": report.get("founded_year", "")},
        {"字段": "总部",     "内容": report.get("headquarters", "")},
        {"字段": "领域赛道", "内容": report.get("sector", "")},
        {"字段": "主要产品", "内容": report.get("main_products", "")},
        {"字段": "核心团队", "内容": report.get("team", "")},
        {"字段": "主要客户", "内容": report.get("customers", "")},
    ]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(basic_rows).to_excel(writer, sheet_name="基本信息", index=False)
        if rounds:
            pd.DataFrame(rounds)[["round_date", "round_type", "amount", "investors"]] \
              .rename(columns={"round_date": "日期", "round_type": "轮次",
                               "amount": "金额", "investors": "投资方"}) \
              .to_excel(writer, sheet_name="融资历史", index=False)
        else:
            pd.DataFrame(columns=["日期", "轮次", "金额", "投资方"]).to_excel(
                writer, sheet_name="融资历史", index=False)

    export_col.download_button(
        "📥 导出 Excel",
        data=output.getvalue(),
        file_name=f"{project['name']}_报告.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="export_report",
    )

    st.caption(f"生成时间：{gen_time}")

    # Basic info table
    st.markdown("**基本信息**")
    label_map = {
        "founded_year": "成立时间",
        "headquarters": "总部",
        "sector": "领域赛道",
        "main_products": "主要产品",
        "team": "核心团队",
        "customers": "主要客户",
    }
    table_data = [{"字段": label_map[k], "内容": report.get(k, "") or "—"}
                  for k in label_map]
    st.dataframe(
        pd.DataFrame(table_data),
        use_container_width=True,
        hide_index=True,
        column_config={"字段": st.column_config.TextColumn(width="small"),
                       "内容": st.column_config.TextColumn(width="large")},
    )

    # Funding rounds table
    st.markdown("**历史融资记录（来自 IT桔子）**")
    if not rounds:
        st.info("IT桔子未找到该公司融资记录")
    else:
        df = pd.DataFrame(rounds)[["round_date", "round_type", "amount", "investors"]]
        df.columns = ["日期", "轮次", "金额", "投资方"]
        st.dataframe(df, use_container_width=True, hide_index=True)


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

            # 把解析结果存入 session_state，避免表单提交时丢失
            st.session_state["bp_parsed"] = {
                "info": info,
                "file_path": str(save_path),
                "default_name": Path(uploaded.name).stem,
            }
            st.rerun()

if st.session_state.get("bp_parsed"):
    parsed = st.session_state["bp_parsed"]
    info = parsed["info"]
    st.subheader("提取结果（可修改后保存）")
    with st.form("save_project_form"):
        name = st.text_input("项目名称", value=info.get("name") or parsed["default_name"])
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
                DB_PATH, name=name, file_path=parsed["file_path"],
                sector=sector, sub_sector=sub_sector, stage=stage,
                location=location, description=description,
                highlights=highlights, financing_need=financing_need
            )
            st.session_state.pop("bp_parsed", None)
            st.success(f"项目「{name}」已保存")
            st.rerun()

projects = list_projects(DB_PATH)
st.subheader(f"项目列表（共 {len(projects)} 个）")

if not projects:
    st.info("暂无项目，请上传 BP")
else:
    selected_id = st.session_state.get("selected_project_id")

    # 表头行（7列，与数据行完全一致）
    COLS = [3, 2, 2, 1, 1, 1, 1]
    h1, h2, h3, h4, _, _, _ = st.columns(COLS)
    h1.markdown("**项目名称**")
    h2.markdown("**赛道**")
    h3.markdown("**细分领域**")
    h4.markdown("**融资阶段**")
    st.divider()

    confirm_del_id = st.session_state.get("confirm_delete_project_id")

    for p in projects:
        col1, col2, col3, col4, col_report, col5, col6 = st.columns(COLS)
        col1.markdown(f"**{p['name']}**")
        col2.write(p['sector'] or "—")
        col3.write(p['sub_sector'] or "—")
        col4.write(p['stage'] or "—")

        if col_report.button("📊", key=f"report_{p['id']}", help="生成项目报告"):
            st.session_state["report_project_id"] = p["id"]
            st.session_state.pop("selected_project_id", None)
            st.rerun()

        if confirm_del_id == p["id"]:
            if col5.button("✅", key=f"delyes_{p['id']}", help="确认删除"):
                delete_project(DB_PATH, p["id"])
                if st.session_state.get("selected_project_id") == p["id"]:
                    st.session_state.pop("selected_project_id", None)
                st.session_state.pop("confirm_delete_project_id", None)
                st.rerun()
            if col6.button("❌", key=f"delno_{p['id']}", help="取消"):
                st.session_state.pop("confirm_delete_project_id", None)
                st.rerun()
            col1.caption("⚠️ 确认删除？")
        else:
            if col5.button("详情", key=f"detail_{p['id']}"):
                st.session_state["selected_project_id"] = p["id"]
                st.session_state.pop("confirm_delete_project_id", None)
                st.session_state.pop("report_project_id", None)
                st.rerun()
            if col6.button("🗑️", key=f"pdel_{p['id']}", help="删除此项目"):
                st.session_state["confirm_delete_project_id"] = p["id"]
                st.rerun()
        st.divider()

    if selected_id:
        p = get_project(DB_PATH, selected_id)
        if p:
            st.divider()
            title_col, close_col = st.columns([5, 1])
            title_col.subheader(f"📄 {p['name']} — 详情")
            if close_col.button("✕ 关闭", key="close_project_detail"):
                st.session_state.pop("selected_project_id", None)
                st.session_state.pop("confirm_delete_project_detail", None)
                st.rerun()
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
            if st.session_state.get("confirm_delete_project_detail") == selected_id:
                col_del.warning("确认删除此项目？")
                c1, c2 = st.columns(2)
                if c1.button("✅ 确认删除", type="secondary"):
                    delete_project(DB_PATH, selected_id)
                    st.session_state.pop("selected_project_id", None)
                    st.session_state.pop("confirm_delete_project_detail", None)
                    st.rerun()
                if c2.button("❌ 取消"):
                    st.session_state.pop("confirm_delete_project_detail", None)
                    st.rerun()
            else:
                if col_del.button("🗑️ 删除项目", type="secondary"):
                    st.session_state["confirm_delete_project_detail"] = selected_id
                    st.rerun()
            if col_match.button("🔗 找匹配机构", type="primary"):
                st.session_state["match_project_id"] = selected_id
                st.switch_page("pages/3_matching.py")

    # --- Report panel ---
    report_pid = st.session_state.get("report_project_id")
    if report_pid:
        rp = get_project(DB_PATH, report_pid)
        if rp:
            st.divider()
            _render_report_panel(DB_PATH, rp, BROWSER_STATE)
