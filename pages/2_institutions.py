# pages/2_institutions.py
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from core.database import init_db, insert_institution, list_institutions, get_institution, \
    update_institution, delete_institution, insert_investment_record, list_investment_records
from core.scraper import scrape_institution_investments

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fa_matching.db")
from core.llm import llm_is_configured
BROWSER_STATE = os.getenv("BROWSER_STATE_PATH", "data/browser_state.json")

init_db(DB_PATH)

st.title("🏦 机构管理")

tab_list, tab_add, tab_import = st.tabs(["机构列表", "新增机构", "导入 Excel"])

with tab_add:
    st.subheader("新增投资机构")
    with st.form("add_institution_form"):
        name = st.text_input("机构名称 *", placeholder="如：红杉中国")
        location = st.text_input("总部地点")
        known_preferences = st.text_area("已知偏好备注", placeholder="如：需要能在湖州落地工厂")
        contact_name = st.text_input("对接联系人")
        contact_wechat = st.text_input("联系方式（微信/手机）")
        fa_fee_note = st.text_input("FA 费用条款备注")
        response_style = st.text_input("响应风格备注")
        track = st.checkbox("加入定期刷新列表", value=True)

        if st.form_submit_button("➕ 新增并自动补全信息"):
            if not name:
                st.error("机构名称不能为空")
            elif not llm_is_configured():
                st.error("请先在「设置」页面配置推理模型")
            else:
                iid = insert_institution(
                    DB_PATH, name=name, location=location,
                    known_preferences=known_preferences,
                    contact_name=contact_name, contact_wechat=contact_wechat,
                    fa_fee_note=fa_fee_note, response_style=response_style,
                    track_updates=1 if track else 0
                )
                with st.spinner(f"正在从 IT桔子 抓取「{name}」的信息..."):
                    result = scrape_institution_investments(name, BROWSER_STATE)
                    inst_info = {k: v for k, v in result["institution"].items() if v}
                    if inst_info:
                        update_institution(DB_PATH, iid, **inst_info)
                    for r in result["records"]:
                        insert_investment_record(DB_PATH, institution_id=iid, **r)
                    update_institution(DB_PATH, iid, last_scraped_at=datetime.now().isoformat())
                st.success(f"机构「{name}」已添加，抓取到 {len(result['records'])} 条投资记录")
                st.rerun()

with tab_import:
    st.subheader("批量导入 Excel")
    st.info("Excel 需包含列：`name`（必填），可选列：`location`、`known_preferences`、`contact_name`、`contact_wechat`")
    uploaded_excel = st.file_uploader("选择 Excel 文件", type=["xlsx", "xls"])
    if uploaded_excel:
        df = pd.read_excel(uploaded_excel)
        st.dataframe(df.head(5))
        if st.button("确认导入"):
            if "name" not in df.columns:
                st.error("Excel 中未找到 `name` 列")
            else:
                count = 0
                allowed_cols = {"name", "location", "known_preferences", "contact_name", "contact_wechat", "fa_fee_note"}
                for _, row in df.iterrows():
                    kwargs = {col: str(row[col]) for col in df.columns
                              if col in allowed_cols and pd.notna(row.get(col))}
                    if kwargs.get("name"):
                        insert_institution(DB_PATH, **kwargs)
                        count += 1
                st.success(f"成功导入 {count} 家机构")
                st.rerun()

with tab_list:
    institutions = list_institutions(DB_PATH)
    st.subheader(f"机构列表（共 {len(institutions)} 家）")

    tracked = [i for i in institutions if i.get("track_updates")]
    if tracked:
        col_refresh, col_info = st.columns([1, 3])
        if col_refresh.button(f"🔄 全量刷新（{len(tracked)} 家）"):
            progress = st.progress(0)
            for idx, inst in enumerate(tracked):
                with st.spinner(f"正在抓取「{inst['name']}」的信息..."):
                    result = scrape_institution_investments(inst["name"], BROWSER_STATE)
                    inst_info = {k: v for k, v in result["institution"].items() if v}
                    if inst_info:
                        update_institution(DB_PATH, inst["id"], **inst_info)
                    for r in result["records"]:
                        insert_investment_record(DB_PATH, institution_id=inst["id"], **r)
                    update_institution(DB_PATH, inst["id"],
                                       last_scraped_at=datetime.now().isoformat())
                progress.progress((idx + 1) / len(tracked))
            st.success("全量刷新完成")
            st.rerun()
        last_times = [i["last_scraped_at"] for i in tracked if i.get("last_scraped_at")]
        if last_times:
            col_info.text(f"上次更新：{min(last_times)[:10]}")

    if not institutions:
        st.info("暂无机构，请新增或导入")
    else:
        selected_iid = st.session_state.get("selected_institution_id")

        for inst in institutions:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                col1.markdown(f"**{inst['name']}**")
                col2.text(inst.get("aum") or "规模未知")
                col3.text(inst.get("preferred_sectors") or "偏好未知")
                if col4.button("详情", key=f"idetail_{inst['id']}"):
                    st.session_state["selected_institution_id"] = inst["id"]
                    st.rerun()

        if selected_iid:
            inst = get_institution(DB_PATH, selected_iid)
            if inst:
                st.divider()
                st.subheader(f"🏦 {inst['name']} — 详情")

                detail_tab1, detail_tab2 = st.tabs(["基本信息", "投资记录"])

                with detail_tab1:
                    with st.form("edit_institution_form"):
                        col1, col2 = st.columns(2)
                        website = col1.text_input("官网", value=inst.get("website") or "")
                        founded_year = col2.text_input("成立年份", value=inst.get("founded_year") or "")
                        col3, col4 = st.columns(2)
                        aum = col3.text_input("管理规模", value=inst.get("aum") or "")
                        current_fund = col4.text_input("当前基金期数", value=inst.get("current_fund") or "")
                        key_partners = st.text_input("主要合伙人", value=inst.get("key_partners") or "")
                        preferred_sectors = st.text_input("偏好赛道", value=inst.get("preferred_sectors") or "")
                        preferred_stages = st.text_input("偏好阶段", value=inst.get("preferred_stages") or "")
                        known_preferences = st.text_area("特殊偏好备注", value=inst.get("known_preferences") or "")
                        contact_name = st.text_input("对接联系人", value=inst.get("contact_name") or "")
                        contact_wechat = st.text_input("联系方式", value=inst.get("contact_wechat") or "")
                        fa_fee_note = st.text_input("FA 费用备注", value=inst.get("fa_fee_note") or "")
                        track = st.checkbox("加入定期刷新", value=bool(inst.get("track_updates")))

                        if st.form_submit_button("💾 保存"):
                            update_institution(DB_PATH, selected_iid,
                                               website=website, founded_year=founded_year,
                                               aum=aum, current_fund=current_fund,
                                               key_partners=key_partners,
                                               preferred_sectors=preferred_sectors,
                                               preferred_stages=preferred_stages,
                                               known_preferences=known_preferences,
                                               contact_name=contact_name,
                                               contact_wechat=contact_wechat,
                                               fa_fee_note=fa_fee_note,
                                               track_updates=1 if track else 0)
                            st.success("已保存")
                            st.rerun()

                    col_del, col_match = st.columns(2)
                    if col_del.button("🗑️ 删除机构", type="secondary"):
                        delete_institution(DB_PATH, selected_iid)
                        st.session_state.pop("selected_institution_id", None)
                        st.rerun()
                    if col_match.button("🔗 找匹配项目", type="primary"):
                        st.session_state["match_institution_id"] = selected_iid
                        st.switch_page("pages/3_matching.py")

                with detail_tab2:
                    records = list_investment_records(DB_PATH, selected_iid)
                    col_rec, col_scrape = st.columns([3, 1])
                    col_rec.text(f"已记录 {len(records)} 条投资记录")
                    if col_scrape.button("🔄 刷新记录"):
                        with st.spinner("正在从 IT桔子 抓取..."):
                            result = scrape_institution_investments(inst["name"], BROWSER_STATE)
                            inst_info = {k: v for k, v in result["institution"].items() if v}
                            if inst_info:
                                update_institution(DB_PATH, selected_iid, **inst_info)
                            for r in result["records"]:
                                insert_investment_record(DB_PATH, institution_id=selected_iid, **r)
                            update_institution(DB_PATH, selected_iid,
                                               last_scraped_at=datetime.now().isoformat())
                        st.success(f"抓取完成，新增 {len(result['records'])} 条")
                        st.rerun()

                    if records:
                        df_records = pd.DataFrame(records)
                        st.dataframe(
                            df_records[["company_name", "sector", "stage", "amount", "invested_date"]],
                            use_container_width=True
                        )
                    else:
                        st.info("暂无投资记录，点击「刷新记录」从 IT桔子 获取")
