# IT桔子全量机构发现与智能匹配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 IT桔子 /investfirm 抓取今年投资数前200家机构及其近2年投资记录，用 LLM 生成偏好画像缓存入库，匹配时通过 Python 快速过滤 + LLM 深度排序向用户推荐最匹配的机构。

**Architecture:** 后台两个串行 Job（discover: 爬取机构列表+记录；analyze: LLM生成偏好画像），匹配时两阶段（Python 赛道/轮次过滤取前40 → 一次 LLM 调用排序 Top10）。所有新数据复用现有 `institutions` + `investment_records` 表，新增3列。

**Tech Stack:** Python/FastAPI, SQLite, browser-harness (scraping), Anthropic Claude (LLM), React/TypeScript (frontend)

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|---|---|---|
| 修改 | `core/database.py` | 新增3列迁移 + 5个新函数 |
| 修改 | `core/scraper.py` | 新增 `scrape_investfirm_list()` |
| 修改 | `core/matcher.py` | 新增 `analyze_preference_profile()` + `two_phase_match_p2i()` |
| 修改 | `api/routers/institutions.py` | 新增 discover / analyze-preferences / analyze-preference 端点 |
| 修改 | `api/routers/matching.py` | 新增 `project-to-institutions-full` 端点 |
| 修改 | `frontend/src/api/institutions.ts` | 新增类型 + discover/analyzeAll/analyzeOne 方法 |
| 修改 | `frontend/src/api/matching.ts` | 新增 `FullMatchResult` 类型 + `projectToInstitutionsFull` 方法 |
| 修改 | `frontend/src/pages/Institutions.tsx` | 发现机构按钮、偏好列、详情面板偏好展示、单机构分析按钮 |
| 修改 | `frontend/src/pages/Matching.tsx` | 新增"IT桔子全量"Tab + 两阶段匹配 UI |
| 新建 | `tests/test_preference_analysis.py` | 偏好分析和两阶段匹配逻辑单测 |

---

## Task 1: 数据库迁移与新增查询函数

**Files:**
- Modify: `core/database.py`
- Test: `tests/test_preference_analysis.py`

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_preference_analysis.py`：

```python
import pytest
import json
import tempfile
import os
from core.database import (
    init_db, insert_institution, update_preference_profile,
    list_institutions_needing_analysis, list_recent_records,
    upsert_institution_by_name,
)

@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "test.db")
    init_db(p)
    return p

def test_upsert_institution_by_name_creates_new(db):
    iid = upsert_institution_by_name(db, "测试机构A", itjuzi_url="https://www.itjuzi.com/investfirm/999")
    assert iid > 0
    from core.database import get_institution
    inst = get_institution(db, iid)
    assert inst["name"] == "测试机构A"
    assert inst["source"] == "itjuzi_discovery"
    assert inst["itjuzi_url"] == "https://www.itjuzi.com/investfirm/999"

def test_upsert_institution_by_name_returns_existing(db):
    id1 = upsert_institution_by_name(db, "测试机构B")
    id2 = upsert_institution_by_name(db, "测试机构B")
    assert id1 == id2

def test_update_preference_profile(db):
    iid = insert_institution(db, name="测试机构C", source="manual")
    profile = {"investment_themes": ["AI"], "preferred_stages": ["A轮"], "summary": "测试", "recent_active": True, "records_count": 5}
    update_preference_profile(db, iid, json.dumps(profile))
    from core.database import get_institution
    inst = get_institution(db, iid)
    assert inst["preference_profile"] is not None
    assert inst["preference_analyzed_at"] is not None

def test_list_institutions_needing_analysis(db):
    from core.database import insert_investment_record
    iid = insert_institution(db, name="机构D", source="itjuzi_discovery")
    insert_investment_record(db, institution_id=iid, company_name="公司X", invested_date="2026-01-01")
    result = list_institutions_needing_analysis(db)
    assert any(r["id"] == iid for r in result)

def test_list_recent_records_filters_by_date(db):
    from core.database import insert_investment_record
    iid = insert_institution(db, name="机构E", source="itjuzi_discovery")
    insert_investment_record(db, institution_id=iid, company_name="新公司", invested_date="2025-06-01")
    insert_investment_record(db, institution_id=iid, company_name="旧公司", invested_date="2020-01-01")
    recent = list_recent_records(db, iid, years=2)
    names = [r["company_name"] for r in recent]
    assert "新公司" in names
    assert "旧公司" not in names
```

- [ ] **Step 2: 运行确认测试失败**

```bash
cd /Users/cqf/Documents/vibe_coding/fa-matching
python -m pytest tests/test_preference_analysis.py -v 2>&1 | head -30
```

Expected: `ImportError` 或 `FAILED`（函数未定义）

- [ ] **Step 3: 在 `_migrate()` 中新增3列迁移**

在 `core/database.py` 的 `_migrate()` 函数中，在现有 `for ddl` 列表末尾追加：

```python
        "ALTER TABLE institutions ADD COLUMN source TEXT DEFAULT 'manual'",
        "ALTER TABLE institutions ADD COLUMN preference_profile TEXT",
        "ALTER TABLE institutions ADD COLUMN preference_analyzed_at TEXT",
```

- [ ] **Step 4: 新增5个函数**

在 `core/database.py` 末尾追加：

```python
def upsert_institution_by_name(db_path, name: str, **defaults) -> int:
    """按名称查找机构，存在则返回ID，否则以 source='itjuzi_discovery' 插入。"""
    with _conn(db_path) as conn:
        row = conn.execute("SELECT id FROM institutions WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        fields = {"name": name, "source": "itjuzi_discovery", **defaults}
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" * len(fields))
        cur = conn.execute(
            f"INSERT INTO institutions ({cols}) VALUES ({placeholders})",
            list(fields.values())
        )
        return cur.lastrowid


def update_preference_profile(db_path, institution_id: int, profile_json: str):
    now = datetime.now().isoformat()
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE institutions SET preference_profile=?, preference_analyzed_at=?, updated_at=? WHERE id=?",
            (profile_json, now, now, institution_id)
        )


def list_institutions_needing_analysis(db_path) -> list:
    """返回有投资记录但 preference_analyzed_at 为空或超过30天的机构。"""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    with _conn(db_path) as conn:
        rows = conn.execute("""
            SELECT DISTINCT i.* FROM institutions i
            JOIN investment_records ir ON ir.institution_id = i.id
            WHERE i.preference_analyzed_at IS NULL
               OR i.preference_analyzed_at < ?
            ORDER BY i.name
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]


def list_recent_records(db_path, institution_id: int, years: int = 2) -> list:
    """返回指定机构近 years 年的投资记录。"""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM investment_records WHERE institution_id=? AND invested_date>=? ORDER BY invested_date DESC",
            (institution_id, cutoff)
        ).fetchall()
        return [dict(r) for r in rows]


def list_institutions_with_profiles(db_path) -> list:
    """返回所有有 preference_profile 的机构。"""
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM institutions WHERE preference_profile IS NOT NULL AND preference_profile != '' ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_preference_analysis.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add core/database.py tests/test_preference_analysis.py
git commit -m "feat: add source/preference columns and DB functions for institution discovery"
```

---

## Task 2: LLM 偏好分析函数

**Files:**
- Modify: `core/matcher.py`
- Test: `tests/test_preference_analysis.py`（追加）

- [ ] **Step 1: 写失败的测试**

在 `tests/test_preference_analysis.py` 末尾追加：

```python
from unittest.mock import patch

def test_analyze_preference_profile_returns_valid_json():
    records = [
        {"company_name": "公司A", "sector": "AI", "stage": "A轮", "amount": "1亿人民币", "invested_date": "2025-06-01", "company_desc": "AI软件公司"},
        {"company_name": "公司B", "sector": "医疗健康", "stage": "B轮", "amount": "3亿人民币", "invested_date": "2025-03-01", "company_desc": "医疗器械"},
    ]
    fake_response = json.dumps({
        "investment_themes": ["AI", "医疗健康"],
        "preferred_stages": ["A轮", "B轮"],
        "typical_ticket": "1-3亿人民币",
        "geo_focus": [],
        "recent_active": True,
        "summary": "偏好AI和医疗，A/B轮，单笔1-3亿",
        "records_count": 2
    })
    with patch("core.matcher.call_llm", return_value=fake_response):
        from core.matcher import analyze_preference_profile
        profile = analyze_preference_profile("测试机构", records)
    assert profile["investment_themes"] == ["AI", "医疗健康"]
    assert profile["recent_active"] is True
    assert profile["records_count"] == 2

def test_analyze_preference_profile_empty_records():
    from core.matcher import analyze_preference_profile
    profile = analyze_preference_profile("测试机构", [])
    assert profile is None
```

- [ ] **Step 2: 运行确认失败**

```bash
python -m pytest tests/test_preference_analysis.py::test_analyze_preference_profile_returns_valid_json tests/test_preference_analysis.py::test_analyze_preference_profile_empty_records -v
```

Expected: `ImportError: cannot import name 'analyze_preference_profile'`

- [ ] **Step 3: 在 `core/matcher.py` 末尾追加函数**

```python
PREFERENCE_PROMPT = """你是专业的投资分析师。根据以下投资机构近2年的投资记录，分析该机构的投资偏好。

机构名称：{name}
近2年投资记录（共{count}条）：
{records_text}

只返回如下JSON，不要任何其他内容：
{{
  "investment_themes": ["赛道1","赛道2"],
  "preferred_stages": ["A轮","B轮"],
  "typical_ticket": "X亿人民币",
  "geo_focus": ["城市1"],
  "recent_active": true,
  "summary": "100字以内的投资偏好摘要",
  "records_count": {count}
}}"""


def analyze_preference_profile(institution_name: str, records: list) -> dict | None:
    """用 LLM 分析近2年投资记录，返回偏好画像 dict；记录为空时返回 None。"""
    if not records:
        return None
    from core.llm import call_llm
    lines = []
    for r in records:
        parts = [
            r.get("company_name", ""),
            r.get("sector", ""),
            r.get("stage", ""),
            r.get("amount", ""),
            r.get("invested_date", ""),
        ]
        desc = r.get("company_desc", "")
        if desc:
            parts.append(desc[:60])
        lines.append(" / ".join(p for p in parts if p))
    records_text = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))
    prompt = PREFERENCE_PROMPT.format(
        name=institution_name,
        count=len(records),
        records_text=records_text,
    )
    raw = call_llm(prompt)
    return _parse_preference_json(raw)


def _parse_preference_json(text: str) -> dict | None:
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


FULL_MATCH_PROMPT = """你是专业的投资 FA 助手。根据项目信息和各机构的投资偏好摘要，推荐最匹配的机构。

项目信息：
{project_info}

候选机构列表（已按赛道/轮次初步筛选）：
{candidates_info}

请从以上候选机构中选出最匹配的Top10，返回JSON数组，每条包含：
- institution_id: 机构ID（整数）
- institution_name: 机构名称
- score: 匹配分数（0-100）
- reason: 推荐理由（80字以内，具体说明偏好与项目的匹配点）

只返回 JSON 数组，不要其他内容。"""


def two_phase_match_p2i(project: dict, api_key: str = "") -> list:
    """两阶段匹配：从库中所有有偏好画像的机构里，为项目推荐Top10。"""
    import os
    import json as _json
    from core.llm import call_llm
    from core.database import list_institutions_with_profiles

    db_path = os.getenv("DB_PATH", "data/fa_matching.db")
    institutions = list_institutions_with_profiles(db_path)
    if not institutions:
        return []

    # 阶段一：Python 快速过滤
    project_sectors = set(s.strip().lower() for s in (
        (project.get("sector") or "") + "," + (project.get("sub_sector") or "")
    ).split(",") if s.strip())
    project_stage = (project.get("stage") or "").strip()

    scored = []
    for inst in institutions:
        try:
            profile = _json.loads(inst["preference_profile"])
        except Exception:
            continue
        inst_themes = set(t.strip().lower() for t in profile.get("investment_themes") or [])
        inst_stages = [s.strip() for s in profile.get("preferred_stages") or []]
        sector_score = len(project_sectors & inst_themes)
        stage_score = 1 if project_stage and any(project_stage in s or s in project_stage for s in inst_stages) else 0
        active_bonus = 1 if profile.get("recent_active") else 0
        total = sector_score * 2 + stage_score * 2 + active_bonus
        if total > 0:
            scored.append((total, inst, profile))

    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = scored[:40]
    if not candidates:
        return []

    # 阶段二：LLM 深度排序
    project_info = _fmt_project(project)
    candidates_info = "\n".join(
        f"ID:{inst['id']} | {inst['name']} | {profile.get('summary','')}"
        for _, inst, profile in candidates
    )
    raw = call_llm(FULL_MATCH_PROMPT.format(
        project_info=project_info,
        candidates_info=candidates_info,
    ))
    items = _parse_json_list(raw)

    inst_map = {inst["id"]: (inst, profile) for _, inst, profile in candidates}
    result = []
    for item in items:
        iid = item.get("institution_id")
        if iid not in inst_map:
            continue
        inst, profile = inst_map[iid]
        result.append({
            "id": iid,
            "name": item.get("institution_name", inst["name"]),
            "score": item.get("score", 50),
            "reason": item.get("reason", ""),
            "preferred_sectors": ",".join(profile.get("investment_themes") or []),
            "preferred_stages": ",".join(profile.get("preferred_stages") or []),
            "recent_active": profile.get("recent_active", True),
            "summary": profile.get("summary", ""),
        })
    return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_preference_analysis.py -v
```

Expected: 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add core/matcher.py tests/test_preference_analysis.py
git commit -m "feat: add analyze_preference_profile and two_phase_match_p2i"
```

---

## Task 3: 爬虫 — scrape_investfirm_list

**Files:**
- Modify: `core/scraper.py`

- [ ] **Step 1: 在 `core/scraper.py` 末尾追加函数**

```python
def scrape_investfirm_list(state_path: str, limit: int = 200) -> list:
    """从 IT桔子 /investfirm（按今年投资数降序）抓取前 limit 家机构。
    返回 list of {"name": str, "itjuzi_url": str}。
    """
    try:
        cookies = _get_chrome_cookies()
        js_links = json.dumps(
            'Array.from(document.querySelectorAll("a[href]"))'
            '.map(l=>({href:l.getAttribute("href"),text:l.innerText.trim()}))'
            '.filter(x=>x.href&&/\\/investfirm\\/\\d+$/.test(x.href)&&x.text&&x.text.length>1&&x.text.length<=40)'
        )
        limit_js = limit

        script = f"""
import json, time
{_inject_cookies_script(cookies)}
_orig_tab = current_tab()
_tid = new_tab()
def _cleanup():
    try: cdp("Target.closeTarget", targetId=_tid)
    except Exception: pass
    try: switch_tab(_orig_tab)
    except Exception: pass

goto_url("https://www.itjuzi.com/investfirm")
wait_for_network_idle(timeout=20)
time.sleep(4)

seen_hrefs = set()
results = []
for _ in range(60):
    links = js({js_links}) or []
    for l in links:
        href = l.get("href","")
        text = l.get("text","").strip()
        if href and text and href not in seen_hrefs:
            seen_hrefs.add(href)
            full_url = "https://www.itjuzi.com" + href if href.startswith("/") else href
            results.append({{"name": text, "itjuzi_url": full_url}})
    if len(results) >= {limit_js}:
        break
    js("window.scrollBy(0,1000)")
    time.sleep(0.6)
    wait_for_network_idle(timeout=8)

_cleanup()
print(json.dumps({{"institutions": results[:{limit_js}]}}, ensure_ascii=False))
"""
        result = subprocess.run(
            [HARNESS_BIN, "-c", script],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"[scraper] investfirm list 错误: {result.stderr[-300:]}")
            return []

        data = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    break
                except Exception:
                    continue

        return data.get("institutions", []) if data else []

    except Exception as e:
        print(f"[scraper] scrape_investfirm_list 失败: {e}")
        return []
```

- [ ] **Step 2: 手动冒烟测试（需要本地 Chrome + IT桔子 登录态）**

```bash
cd /Users/cqf/Documents/vibe_coding/fa-matching
python -c "
from core.scraper import scrape_investfirm_list
result = scrape_investfirm_list('', limit=5)
print(f'Got {len(result)} institutions')
for r in result:
    print(r)
"
```

Expected: 打印出5条机构名称和 URL，类似 `{'name': '红杉中国', 'itjuzi_url': 'https://www.itjuzi.com/investfirm/123'}`

若输出为空列表，检查浏览器 cookie 和 IT桔子 登录状态。

- [ ] **Step 3: Commit**

```bash
git add core/scraper.py
git commit -m "feat: add scrape_investfirm_list for top-200 institution discovery"
```

---

## Task 4: API — discover + analyze-preferences 端点

**Files:**
- Modify: `api/routers/institutions.py`

- [ ] **Step 1: 在 `api/routers/institutions.py` 顶部补充导入**

找到现有导入块，追加：

```python
from core.database import (
    init_db, list_institutions, get_institution,
    insert_institution, update_institution, delete_institution,
    insert_investment_record, list_investment_records,
    list_records_missing_desc, update_investment_record_desc,
    upsert_institution_by_name, update_preference_profile,
    list_institutions_needing_analysis, list_recent_records,
)
from core.scraper import scrape_institution_investments, scrape_event_description, scrape_investfirm_list
```

（替换原有的两行 `from core.database import ...` 和 `from core.scraper import ...`）

- [ ] **Step 2: 在文件末尾追加3个端点**

```python
def _discover_all(job_id: str):
    set_running(job_id)
    try:
        firms = scrape_investfirm_list(BROWSER_STATE, limit=200)
        discovered = 0
        records_added = 0
        for firm in firms:
            iid = upsert_institution_by_name(
                DB_PATH, firm["name"], itjuzi_url=firm["itjuzi_url"]
            )
            result = scrape_institution_investments(firm["name"], BROWSER_STATE)
            inst_info = {k: v for k, v in result["institution"].items() if v}
            if inst_info:
                update_institution(DB_PATH, iid, **inst_info)
            for r in result["records"]:
                insert_investment_record(DB_PATH, institution_id=iid, **r)
                records_added += 1
            discovered += 1
        set_done(job_id, {"discovered": discovered, "records_added": records_added})
    except Exception as e:
        set_failed(job_id, str(e))


@router.post("/discover", status_code=202)
def discover_institutions(background_tasks: BackgroundTasks):
    job_id = create_job()
    background_tasks.add_task(_discover_all, job_id)
    return {"job_id": job_id}


def _analyze_preferences(job_id: str):
    set_running(job_id)
    try:
        from core.matcher import analyze_preference_profile
        import json as _json
        institutions = list_institutions_needing_analysis(DB_PATH)
        analyzed = 0
        for inst in institutions:
            records = list_recent_records(DB_PATH, inst["id"], years=2)
            if not records:
                continue
            profile = analyze_preference_profile(inst["name"], records)
            if profile:
                update_preference_profile(DB_PATH, inst["id"], _json.dumps(profile, ensure_ascii=False))
                analyzed += 1
        set_done(job_id, {"analyzed": analyzed})
    except Exception as e:
        set_failed(job_id, str(e))


@router.post("/analyze-preferences", status_code=202)
def analyze_all_preferences(background_tasks: BackgroundTasks):
    job_id = create_job()
    background_tasks.add_task(_analyze_preferences, job_id)
    return {"job_id": job_id}


def _analyze_one_preference(job_id: str, institution_id: int):
    set_running(job_id)
    try:
        from core.matcher import analyze_preference_profile
        import json as _json
        inst = get_institution(DB_PATH, institution_id)
        if not inst:
            set_failed(job_id, "Institution not found")
            return
        records = list_recent_records(DB_PATH, institution_id, years=2)
        if not records:
            set_done(job_id, {"analyzed": 0, "reason": "no recent records"})
            return
        profile = analyze_preference_profile(inst["name"], records)
        if profile:
            update_preference_profile(DB_PATH, institution_id, _json.dumps(profile, ensure_ascii=False))
        set_done(job_id, {"analyzed": 1 if profile else 0})
    except Exception as e:
        set_failed(job_id, str(e))


@router.post("/{institution_id}/analyze-preference", status_code=202)
def analyze_one_preference(institution_id: int, background_tasks: BackgroundTasks):
    if not get_institution(DB_PATH, institution_id):
        raise HTTPException(404, "Institution not found")
    job_id = create_job()
    background_tasks.add_task(_analyze_one_preference, job_id, institution_id)
    return {"job_id": job_id}
```

- [ ] **Step 3: 验证端点注册**

```bash
curl -s http://127.0.0.1:8000/docs | grep -o 'discover\|analyze-preference' | head -10
```

或重启 API 后查看 http://127.0.0.1:8000/docs，确认3个新端点出现。

- [ ] **Step 4: Commit**

```bash
git add api/routers/institutions.py
git commit -m "feat: add discover, analyze-preferences, and analyze-preference API endpoints"
```

---

## Task 5: API — 全量匹配端点

**Files:**
- Modify: `api/routers/matching.py`

- [ ] **Step 1: 在 `api/routers/matching.py` 末尾追加端点**

```python
@router.post("/project-to-institutions-full")
def project_to_institutions_full(body: ProjectMatchReq):
    project = get_project(DB_PATH, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    from core.matcher import two_phase_match_p2i
    return two_phase_match_p2i(project)
```

同时在顶部 import 块中补充（如果未导入）：

```python
from core.database import (
    init_db, get_project, get_institution,
    list_institutions, list_projects, list_investment_records,
    list_institutions_with_profiles,
)
```

- [ ] **Step 2: 在 `api/routers/matching.py` 新增统计端点**（供前端显示"已分析X家"）

```python
@router.get("/full-match-stats")
def full_match_stats():
    from core.database import list_institutions_with_profiles, list_institutions
    total = len(list_institutions(DB_PATH))
    analyzed = len(list_institutions_with_profiles(DB_PATH))
    from core.database import list_institutions_needing_analysis
    from core.database import _conn
    # 找最近一次分析时间
    with _conn(DB_PATH) as conn:
        row = conn.execute(
            "SELECT MAX(preference_analyzed_at) as last FROM institutions WHERE preference_analyzed_at IS NOT NULL"
        ).fetchone()
        last_analyzed = row["last"] if row else None
    return {"total": total, "analyzed": analyzed, "last_analyzed_at": last_analyzed}
```

- [ ] **Step 3: 冒烟测试**

```bash
curl -s http://127.0.0.1:8000/api/matching/full-match-stats | python3 -m json.tool
```

Expected:
```json
{"total": 2, "analyzed": 0, "last_analyzed_at": null}
```

- [ ] **Step 4: Commit**

```bash
git add api/routers/matching.py
git commit -m "feat: add project-to-institutions-full endpoint and full-match-stats"
```

---

## Task 6: 前端 API 客户端

**Files:**
- Modify: `frontend/src/api/institutions.ts`
- Modify: `frontend/src/api/matching.ts`

- [ ] **Step 1: 更新 `frontend/src/api/institutions.ts`**

在 `Institution` interface 末尾追加字段：

```typescript
  source: string | null
  preference_profile: string | null
  preference_analyzed_at: string | null
```

在 `institutionsApi` 对象末尾追加方法：

```typescript
  discover: () =>
    apiFetch<{ job_id: string }>('/api/institutions/discover', { method: 'POST' }),
  analyzeAllPreferences: () =>
    apiFetch<{ job_id: string }>('/api/institutions/analyze-preferences', { method: 'POST' }),
  analyzePreference: (id: number) =>
    apiFetch<{ job_id: string }>(`/api/institutions/${id}/analyze-preference`, { method: 'POST' }),
```

- [ ] **Step 2: 更新 `frontend/src/api/matching.ts`**

追加新类型和方法：

```typescript
export interface FullMatchResult {
  id: number
  name: string
  score: number
  reason: string
  preferred_sectors: string
  preferred_stages: string
  recent_active: boolean
  summary: string
}

export interface FullMatchStats {
  total: number
  analyzed: number
  last_analyzed_at: string | null
}

// 在 matchingApi 对象末尾追加：
//  projectToInstitutionsFull: (projectId: number) => ...
//  fullMatchStats: () => ...
```

完整的 `matchingApi` 对象替换为：

```typescript
export const matchingApi = {
  projectToInstitutions: (projectId: number) =>
    apiFetch<MatchResult[]>('/api/matching/project-to-institutions', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId })
    }),
  institutionToProjects: (institutionId: number) =>
    apiFetch<MatchResult[]>('/api/matching/institution-to-projects', {
      method: 'POST',
      body: JSON.stringify({ institution_id: institutionId })
    }),
  projectToInstitutionsFull: (projectId: number) =>
    apiFetch<FullMatchResult[]>('/api/matching/project-to-institutions-full', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId })
    }),
  fullMatchStats: () =>
    apiFetch<FullMatchStats>('/api/matching/full-match-stats'),
}
```

- [ ] **Step 3: 确认 TypeScript 编译无报错**

```bash
cd /Users/cqf/Documents/vibe_coding/fa-matching/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: 无输出（无错误）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/institutions.ts frontend/src/api/matching.ts
git commit -m "feat: add discover/analyze/full-match API client methods and types"
```

---

## Task 7: 前端 — 机构管理页

**Files:**
- Modify: `frontend/src/pages/Institutions.tsx`

- [ ] **Step 1: 引入新 API 方法，添加状态变量**

在文件顶部 `useState` 导入处已有，在组件内现有状态变量末尾追加：

```typescript
const [discovering, setDiscovering] = useState(false)
const [analyzingAll, setAnalyzingAll] = useState(false)
```

- [ ] **Step 2: 添加 discover 和 analyzeAll 处理函数**

在 `scrapeAll` 函数之后追加：

```typescript
function discover() {
  setDiscovering(true)
  institutionsApi.discover().then(({ job_id }) =>
    pollJob(job_id,
      () => { setDiscovering(false); reload() },
      () => setDiscovering(false)
    )
  )
}

function analyzeAll() {
  setAnalyzingAll(true)
  institutionsApi.analyzeAllPreferences().then(({ job_id }) =>
    pollJob(job_id,
      () => { setAnalyzingAll(false); reload() },
      () => setAnalyzingAll(false)
    )
  )
}
```

- [ ] **Step 3: 工具栏新增两个按钮**

找到工具栏 `<div style={{ display: 'flex', gap: 10 ...` 中 `🔄 全量刷新` 按钮之后，追加：

```tsx
<button onClick={discover} disabled={discovering} style={{ ...ghostBtn, display: 'flex', alignItems: 'center', gap: 6 }}>
  {discovering ? <><Spinner size={12} /> 发现中…</> : '🌐 发现机构'}
</button>
<button onClick={analyzeAll} disabled={analyzingAll} style={{ ...ghostBtn, display: 'flex', alignItems: 'center', gap: 6 }}>
  {analyzingAll ? <><Spinner size={12} /> 分析中…</> : '🧠 分析偏好'}
</button>
```

- [ ] **Step 4: 表头新增"偏好"列**

在 `['机构名称', '基本信息', '关注赛道', '偏好阶段', '联系人', '最后更新', '操作']` 中，在 `'最后更新'` 前插入 `'偏好'`：

```tsx
{['机构名称', '基本信息', '关注赛道', '偏好阶段', '联系人', '偏好', '最后更新', '操作'].map(h => (
```

- [ ] **Step 5: 表格行新增偏好状态单元格**

在现有 `<td>` 最后更新列 之前插入：

```tsx
<td style={{ padding: '11px 12px', minWidth: 70 }}>
  {inst.preference_analyzed_at
    ? <span style={{ fontSize: 11, color: 'var(--success)' }}>✅ {inst.preference_analyzed_at.slice(0, 10)}</span>
    : <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>}
</td>
```

- [ ] **Step 6: 操作列新增"🧠"按钮**

在 DetailPanel 函数参数中追加 `onAnalyzed` 回调，并在操作列按钮组中 `🔄` 按钮之后追加：

```tsx
// 在 table 行的操作单元格中，🔄 按钮之后：
<button
  onClick={() => {
    institutionsApi.analyzePreference(inst.id).then(({ job_id }) =>
      pollJob(job_id, reload, () => {})
    )
  }}
  title="分析近2年投资偏好"
  style={ghostBtn}
>🧠</button>
```

- [ ] **Step 7: 在 DetailPanel 中展示偏好画像**

在 `DetailPanel` 函数的 `detailTab === 'info'` 区块内，`<div style={{ padding: 20 }}>` 开始后、字段网格 `<div style={{ display: 'grid'...` 之前插入：

```tsx
{(() => {
  if (!inst.preference_profile) return null
  try {
    const p = JSON.parse(inst.preference_profile)
    return (
      <div style={{ background: 'var(--bg-elevated)', borderRadius: 6, padding: '12px 14px', marginBottom: 16 }}>
        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 8 }}>
          投资偏好画像（分析时间：{inst.preference_analyzed_at?.slice(0, 10)}）
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
          {(p.investment_themes || []).map((t: string) => <Badge key={t} variant="blue">{t}</Badge>)}
          {(p.preferred_stages || []).map((s: string) => <Badge key={s} variant="amber">{s}</Badge>)}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, margin: 0 }}>{p.summary}</p>
      </div>
    )
  } catch { return null }
})()}
```

- [ ] **Step 8: 确认前端编译无报错**

```bash
cd /Users/cqf/Documents/vibe_coding/fa-matching/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: 无输出

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/Institutions.tsx
git commit -m "feat: institutions page — discover/analyze buttons, preference column and panel"
```

---

## Task 8: 前端 — 匹配推荐页

**Files:**
- Modify: `frontend/src/pages/Matching.tsx`

- [ ] **Step 1: 更新导入，扩展类型**

将文件顶部 import 替换为：

```typescript
import { useState, useEffect } from 'react'
import { projectsApi } from '../api/projects'
import { institutionsApi } from '../api/institutions'
import { matchingApi } from '../api/matching'
import type { Project } from '../api/projects'
import type { Institution } from '../api/institutions'
import type { MatchResult, FullMatchResult, FullMatchStats } from '../api/matching'
import Badge from '../components/Badge'
import Spinner from '../components/Spinner'
import { pollJob } from '../api/jobs'
```

- [ ] **Step 2: 扩展组件状态**

将现有 `type Tab = 'p2i'|'i2p'` 替换为：

```typescript
type Tab = 'p2i' | 'i2p' | 'full'
```

在组件内现有状态末尾追加：

```typescript
const [fullResults, setFullResults] = useState<FullMatchResult[]>([])
const [fullLoading, setFullLoading] = useState(false)
const [fullStats, setFullStats] = useState<FullMatchStats | null>(null)
const [warmingUp, setWarmingUp] = useState(false)
```

- [ ] **Step 3: 加载 fullMatchStats**

在现有 `useEffect` 之后追加：

```typescript
useEffect(() => { matchingApi.fullMatchStats().then(setFullStats) }, [])
```

- [ ] **Step 4: 新增 runFullMatch 和 warmUp 函数**

在现有 `runMatch` 函数之后追加：

```typescript
async function runFullMatch() {
  if (!selectedPid) return
  setFullLoading(true); setFullResults([])
  try {
    setFullResults(await matchingApi.projectToInstitutionsFull(selectedPid))
  } finally { setFullLoading(false) }
}

function warmUp() {
  setWarmingUp(true)
  institutionsApi.discover().then(({ job_id }) =>
    pollJob(job_id,
      () => institutionsApi.analyzeAllPreferences().then(({ job_id: jid }) =>
        pollJob(jid,
          () => { setWarmingUp(false); matchingApi.fullMatchStats().then(setFullStats) },
          () => setWarmingUp(false)
        )
      ),
      () => setWarmingUp(false)
    )
  )
}
```

- [ ] **Step 5: 新增 Tab 按钮**

在现有两个 Tab 按钮 map 之后追加第三个 Tab 按钮：

```tsx
<button onClick={() => { setTab('full'); setFullResults([]) }}
  style={{ padding:'8px 16px', background:'none', border:'none', cursor:'pointer',
    color: tab==='full' ? 'var(--text-primary)' : 'var(--text-secondary)',
    borderBottom: `2px solid ${tab==='full' ? 'var(--accent)' : 'transparent'}`,
    marginBottom: -1, fontSize: 13 }}>
  IT桔子全量
</button>
```

- [ ] **Step 6: 新增"IT桔子全量"Tab 内容**

在现有 `{tab === 'p2i' || tab === 'i2p'` 的布局 div 之后，追加：

```tsx
{tab === 'full' && (
  <div style={{ display: 'flex', gap: 24 }}>
    <div style={{ width: 220, flexShrink: 0 }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: .5, marginBottom: 8 }}>选择项目</div>
      {projects.map(p => {
        const isSel = selectedPid === p.id
        return (
          <div key={p.id} onClick={() => setSelectedPid(p.id)}
            style={{ background: isSel ? 'var(--bg-elevated)' : 'var(--bg-surface)', border: `1px solid ${isSel ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 6, padding: '10px 12px', marginBottom: 6, cursor: 'pointer' }}>
            <div style={{ color: isSel ? '#fff' : 'var(--text-secondary)', fontSize: 13 }}>{p.name}</div>
          </div>
        )
      })}
      <button onClick={runFullMatch} disabled={fullLoading || !selectedPid}
        style={{ width: '100%', marginTop: 8, background: 'linear-gradient(135deg,var(--accent),var(--accent-light))', color: '#fff', border: 'none', borderRadius: 6, padding: '9px 16px', fontWeight: 500, fontSize: 13, opacity: !selectedPid ? .5 : 1, cursor: 'pointer' }}>
        {fullLoading ? '匹配中…' : '🚀 开始匹配'}
      </button>
    </div>
    <div style={{ flex: 1 }}>
      {fullStats && (
        <div style={{ background: fullStats.analyzed < fullStats.total ? 'rgba(251,191,36,.08)' : 'var(--bg-elevated)', border: `1px solid ${fullStats.analyzed < fullStats.total ? 'var(--warning,#f59e0b)' : 'var(--border)'}`, borderRadius: 6, padding: '10px 14px', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 12, fontSize: 12 }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            已分析 <strong style={{ color: '#fff' }}>{fullStats.analyzed}</strong> / {fullStats.total} 家机构
            {fullStats.last_analyzed_at && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>· 最后更新 {fullStats.last_analyzed_at.slice(0, 10)}</span>}
          </span>
          <button onClick={warmUp} disabled={warmingUp}
            style={{ marginLeft: 'auto', background: 'none', border: '1px solid var(--border)', borderRadius: 4, padding: '4px 10px', color: 'var(--text-secondary)', fontSize: 11, cursor: 'pointer' }}>
            {warmingUp ? <><Spinner size={10} /> 预热中…</> : '⚡ 一键预热'}
          </button>
        </div>
      )}
      {fullLoading && <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', padding: 16 }}><Spinner /> LLM 分析中，约 20–40 秒…</div>}
      {!fullLoading && fullResults.length === 0 && (
        <div style={{ color: 'var(--text-muted)', padding: 16 }}>{selectedPid ? '点击「开始匹配」获取推荐' : '请先从左侧选择'}</div>
      )}
      {fullResults.map((r, i) => (
        <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 6 }}>
            <span style={{ flex: 1, fontSize: 14, fontWeight: 600, color: '#fff' }}>{r.name}</span>
            {r.recent_active && <Badge variant="green">近期活跃</Badge>}
            <span style={{ background: 'linear-gradient(135deg,var(--accent),var(--accent-light))', color: '#fff', fontWeight: 700, fontSize: 14, borderRadius: 6, padding: '3px 10px', marginLeft: 8 }}>{r.score}</span>
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
            {r.preferred_sectors.split(',').filter(Boolean).slice(0, 4).map(s => <Badge key={s} variant="blue">{s.trim()}</Badge>)}
            {r.preferred_stages.split(',').filter(Boolean).slice(0, 2).map(s => <Badge key={s} variant="amber">{s.trim()}</Badge>)}
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, margin: 0 }}>{r.reason}</p>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 7: 确认 TypeScript 编译无报错**

```bash
cd /Users/cqf/Documents/vibe_coding/fa-matching/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: 无输出

- [ ] **Step 8: 确认 Badge 组件支持 "green" variant**

检查 `frontend/src/components/Badge.tsx`，确认 `variant="green"` 有对应样式。若没有，在 Badge 组件的 variant 映射中追加：

```typescript
green: { background: 'rgba(34,197,94,.15)', color: '#4ade80', border: '1px solid rgba(34,197,94,.3)' },
```

- [ ] **Step 9: 浏览器端到端测试**

1. 重启 API：`python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &`
2. 确认前端热更新已生效（无需重启）
3. 打开 http://localhost:5173/matching
4. 点击"IT桔子全量"Tab，确认状态栏显示"已分析 0 / X 家机构"
5. 不点预热，直接选一个项目点"开始匹配"，预期返回空结果或提示
6. 机构管理页：点"🧠 分析偏好"对一家已有记录的机构手动分析
7. 回到匹配页，再次"开始匹配"，应能看到结果

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/Matching.tsx frontend/src/components/Badge.tsx
git commit -m "feat: matching page — IT桔子全量 tab with two-phase match and warm-up flow"
```

---

## 验收标准

- [ ] `python -m pytest tests/test_preference_analysis.py -v` → 7 tests PASSED
- [ ] `curl -X POST http://127.0.0.1:8000/api/institutions/discover` → 返回 `{"job_id": "..."}`
- [ ] `curl -X POST http://127.0.0.1:8000/api/institutions/analyze-preferences` → 返回 `{"job_id": "..."}`
- [ ] `curl -X POST http://127.0.0.1:8000/api/matching/project-to-institutions-full -d '{"project_id":1}' -H 'Content-Type: application/json'` → 返回 JSON 数组（若有已分析机构）
- [ ] 机构管理页：工具栏有"🌐 发现机构"和"🧠 分析偏好"按钮；详情面板能展示偏好画像
- [ ] 匹配推荐页：有"IT桔子全量"Tab；有状态栏和预热按钮；匹配结果卡片展示活跃标签
