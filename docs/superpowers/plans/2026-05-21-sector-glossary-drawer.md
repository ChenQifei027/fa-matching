# 赛道词条 Drawer 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让项目和机构页表格里的赛道 Badge 可点击，点击后在右侧 Drawer 展示该赛道的 LLM 生成解释(是什么 / 行业发展 / 头部公司 / 同义词候选)，首次生成异步、结果缓存到 SQLite。

**Architecture:** 新建 `sectors` 表存解释;新建 `core/sector_glossary.py` 走和 `core/enricher.py` 相同的 "prompt → call_llm → 解析 JSON → 兜底" 模式;新建 `api/routers/sectors.py` 暴露 `GET` 读缓存、`POST` 触发后台生成,复用 `api/jobs.py`;前端新建 `SectorDrawer.tsx` 组件 + 同文件 export 一个 `ClickableSectorBadge` 复用组件,两个列表页都引用,Badge 接入 onClick 打开 Drawer + 轮询。

**Tech Stack:** Python 3 / FastAPI / SQLite / pytest + pytest-mock;React 19 + TypeScript + Vite;现有 `core/llm.call_llm()` LLM 入口。

---

## File Structure

**New files:**
- `core/sector_glossary.py` — LLM prompt 模板 + `generate_sector_explanation(name)` 函数
- `api/routers/sectors.py` — `/api/sectors/...` endpoints
- `frontend/src/api/sectors.ts` — 前端 API 客户端 + 类型
- `frontend/src/components/SectorDrawer.tsx` — 抽屉组件 + 命名导出 `ClickableSectorBadge`
- `tests/test_sector_glossary.py` — `generate_sector_explanation` 单测
- `tests/api/test_sectors.py` — sectors router 集成测试

**Modified files:**
- `core/database.py` — `CREATE_TABLES_SQL` 加 `sectors` 表 + `get_sector` / `upsert_sector` / `delete_sector` 函数
- `tests/test_database.py` — 加 sectors CRUD 测试
- `api/main.py` — 注册 `sectors.router`
- `frontend/src/styles/globals.css` — 追加 `@keyframes shimmer` 骨架屏动画
- `frontend/src/pages/Institutions.tsx` — 赛道 Badge 改为 `ClickableSectorBadge` + 嵌入 SectorDrawer
- `frontend/src/pages/Projects.tsx` — 同上(覆盖 `sector` 列和 `sub_sector` 列)

---

## Task 1: sectors 表 + CRUD 函数

**Files:**
- Modify: `core/database.py` (add `CREATE_TABLES_SQL` block + 3 functions near other CRUD)
- Test: `tests/test_database.py` (append new tests)

- [ ] **Step 1.1: 在 `tests/test_database.py` 末尾追加测试**

```python
def test_sectors_upsert_and_get(tmp_path):
    from core.database import init_db, upsert_sector, get_sector
    db = tmp_path / "t.db"
    init_db(str(db))

    upsert_sector(str(db), "全主动悬架",
                  description="一种电控悬架。",
                  industry_overview="国内规模化前夜。",
                  top_companies='[{"name":"A","desc":"x"}]',
                  synonyms='["主动悬架"]',
                  generated_by="claude-sonnet-4-6")
    row = get_sector(str(db), "全主动悬架")
    assert row["description"] == "一种电控悬架。"
    assert row["synonyms"] == '["主动悬架"]'
    assert row["generated_at"]  # 非空
    assert row["generated_by"] == "claude-sonnet-4-6"


def test_sectors_upsert_overwrites_existing(tmp_path):
    from core.database import init_db, upsert_sector, get_sector
    db = tmp_path / "t.db"
    init_db(str(db))

    upsert_sector(str(db), "AI芯片", description="老版本")
    upsert_sector(str(db), "AI芯片", description="新版本")
    assert get_sector(str(db), "AI芯片")["description"] == "新版本"


def test_get_sector_missing_returns_none(tmp_path):
    from core.database import init_db, get_sector
    db = tmp_path / "t.db"
    init_db(str(db))
    assert get_sector(str(db), "不存在的赛道") is None


def test_delete_sector(tmp_path):
    from core.database import init_db, upsert_sector, get_sector, delete_sector
    db = tmp_path / "t.db"
    init_db(str(db))
    upsert_sector(str(db), "X", description="d")
    delete_sector(str(db), "X")
    assert get_sector(str(db), "X") is None
```

- [ ] **Step 1.2: 跑测试确认它们失败(函数还不存在)**

Run: `pytest tests/test_database.py -v -k sector`
Expected: FAIL — `ImportError` 或 `AttributeError: ... upsert_sector`

- [ ] **Step 1.3: 在 `core/database.py` 的 `CREATE_TABLES_SQL` 字符串末尾追加 `sectors` 表定义**

定位:在 `CREATE TABLE IF NOT EXISTS project_funding_rounds (... );` 之后、`"""` 闭合之前插入:

```sql

CREATE TABLE IF NOT EXISTS sectors (
    name TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    industry_overview TEXT DEFAULT '',
    top_companies TEXT DEFAULT '[]',
    synonyms TEXT DEFAULT '[]',
    generated_at TEXT DEFAULT (datetime('now')),
    generated_by TEXT DEFAULT ''
);
```

- [ ] **Step 1.4: 在 `core/database.py` 末尾追加 3 个函数**

```python
def get_sector(db_path, name: str) -> Optional[dict]:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM sectors WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def upsert_sector(db_path, name: str, **fields):
    """插入或覆盖。fields 允许 description / industry_overview /
    top_companies / synonyms / generated_by;generated_at 自动设为当前时间。"""
    allowed = {"description", "industry_overview", "top_companies",
               "synonyms", "generated_by"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    clean["name"] = name
    clean["generated_at"] = datetime.now().isoformat()
    cols = ", ".join(clean.keys())
    placeholders = ", ".join("?" * len(clean))
    updates = ", ".join(f"{k} = excluded.{k}" for k in clean if k != "name")
    with _conn(db_path) as conn:
        conn.execute(
            f"INSERT INTO sectors ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(name) DO UPDATE SET {updates}",
            list(clean.values())
        )


def delete_sector(db_path, name: str):
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM sectors WHERE name = ?", (name,))
```

- [ ] **Step 1.5: 跑测试确认通过**

Run: `pytest tests/test_database.py -v -k sector`
Expected: 4 passed

- [ ] **Step 1.6: 跑全量 DB 测试确认没破坏旧的**

Run: `pytest tests/test_database.py -v`
Expected: all green

- [ ] **Step 1.7: 提交**

```bash
git add core/database.py tests/test_database.py
git commit -m "feat(db): add sectors table and CRUD for glossary drawer"
```

---

## Task 2: LLM 生成模块 `core/sector_glossary.py`

**Files:**
- Create: `core/sector_glossary.py`
- Test: `tests/test_sector_glossary.py`

- [ ] **Step 2.1: 创建 `tests/test_sector_glossary.py`**

```python
# tests/test_sector_glossary.py
import json
from core.sector_glossary import generate_sector_explanation


def _llm_payload(**overrides) -> str:
    base = {
        "description": "全主动悬架是一种电控悬架。",
        "industry_overview": "国内规模化前夜。",
        "top_companies": [{"name": "A 公司", "desc": "电磁作动器"}],
        "synonyms": ["主动悬架"],
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


def test_generate_parses_clean_json(mocker):
    mocker.patch("core.llm.call_llm", return_value=_llm_payload())
    out = generate_sector_explanation("全主动悬架")
    assert out["description"].startswith("全主动悬架")
    assert out["top_companies"] == [{"name": "A 公司", "desc": "电磁作动器"}]
    assert out["synonyms"] == ["主动悬架"]


def test_generate_strips_markdown_codefence(mocker):
    fenced = "```json\n" + _llm_payload() + "\n```"
    mocker.patch("core.llm.call_llm", return_value=fenced)
    out = generate_sector_explanation("AI芯片")
    assert out["description"]


def test_generate_handles_malformed_returns_defaults(mocker):
    mocker.patch("core.llm.call_llm", return_value="this is not json")
    out = generate_sector_explanation("不存在的词")
    assert out["description"] == ""
    assert out["top_companies"] == []
    assert out["synonyms"] == []


def test_generate_prompt_contains_sector_name(mocker):
    captured = {}
    def fake_call(prompt):
        captured["prompt"] = prompt
        return _llm_payload()
    mocker.patch("core.llm.call_llm", side_effect=fake_call)
    generate_sector_explanation("脑机接口")
    assert "脑机接口" in captured["prompt"]
```

- [ ] **Step 2.2: 跑测试确认失败**

Run: `pytest tests/test_sector_glossary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.sector_glossary'`

- [ ] **Step 2.3: 创建 `core/sector_glossary.py`**

```python
# core/sector_glossary.py
import json
import re

SECTOR_PROMPT = """你是投资行业研究助手。请对以下"细分赛道"做结构化解释,便于早期项目投融资工作者快速理解。

赛道名:{name}

请严格返回 JSON(不要任何前后缀、不要 markdown 代码块),字段如下:

{{
  "description": "1-2 段话说明这个赛道是什么,不超过 150 字",
  "industry_overview": "3-5 句话说明行业发展阶段、市场规模、核心驱动力,不超过 200 字",
  "top_companies": [
    {{"name": "公司名", "desc": "一句话简介"}}
  ],
  "synonyms": ["近义/同义词1", "近义/同义词2"]
}}

要求:
- top_companies 给 3-8 家行业知名公司,每家一句话简介
- synonyms 给 0-5 个业内常用的近义或同义说法(按通用度排序)
- 任何字段无法可靠回答时,给出空字符串或空数组,不要编造
- 如果"{name}"看起来不是真实存在的赛道(疑似拼写错误或表述过宽),在 description 里说明,其他字段留空

只返回 JSON 本体,不要其他内容。"""


def generate_sector_explanation(name: str) -> dict:
    """调用 LLM 生成赛道解释。返回 dict,键固定为 description /
    industry_overview / top_companies / synonyms。LLM 失败或返回非 JSON
    时返回全默认值(空字符串/空数组),不抛异常。"""
    from core.llm import call_llm
    raw = call_llm(SECTOR_PROMPT.format(name=name)).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    defaults = {
        "description": "",
        "industry_overview": "",
        "top_companies": [],
        "synonyms": [],
    }
    return {**defaults, **(data if isinstance(data, dict) else {})}
```

- [ ] **Step 2.4: 跑测试确认通过**

Run: `pytest tests/test_sector_glossary.py -v`
Expected: 4 passed

- [ ] **Step 2.5: 提交**

```bash
git add core/sector_glossary.py tests/test_sector_glossary.py
git commit -m "feat: add sector_glossary LLM module with JSON prompt + parser"
```

---

## Task 3: sectors API endpoints

**Files:**
- Create: `api/routers/sectors.py`
- Modify: `api/main.py` (register router)
- Test: `tests/api/test_sectors.py`

- [ ] **Step 3.1: 创建 `tests/api/test_sectors.py`**

```python
# tests/api/test_sectors.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(db))
    # 重新 import 让 module 内的 DB_PATH 模块级变量读到新值
    import importlib, api.main as main_mod, api.routers.sectors as sectors_mod
    importlib.reload(sectors_mod)
    importlib.reload(main_mod)
    return TestClient(main_mod.app), str(db)


def test_get_missing_sector_returns_404(client):
    c, _ = client
    assert c.get("/api/sectors/未生成的赛道").status_code == 404


def test_get_existing_sector_returns_data(client):
    c, db = client
    from core.database import upsert_sector
    upsert_sector(db, "AI芯片",
                  description="d", industry_overview="i",
                  top_companies='[{"name":"X","desc":"y"}]',
                  synonyms='["AI 加速器"]')
    r = c.get("/api/sectors/AI芯片")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "AI芯片"
    assert body["description"] == "d"
    assert body["top_companies"] == [{"name": "X", "desc": "y"}]
    assert body["synonyms"] == ["AI 加速器"]


def test_post_triggers_generation_and_stores(client, mocker):
    c, _ = client
    mocker.patch("core.sector_glossary.generate_sector_explanation",
                 return_value={"description": "gen-desc",
                               "industry_overview": "ov",
                               "top_companies": [{"name": "A", "desc": "x"}],
                               "synonyms": ["近义"]})
    r = c.post("/api/sectors/新赛道")
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    from api.jobs import get_job
    for _ in range(50):
        if get_job(job_id)["status"] in ("completed", "failed"):
            break
    assert get_job(job_id)["status"] == "completed"
    g = c.get("/api/sectors/新赛道")
    assert g.status_code == 200
    assert g.json()["description"] == "gen-desc"


def test_post_existing_without_force_is_409(client):
    c, db = client
    from core.database import upsert_sector
    upsert_sector(db, "已存在", description="old")
    r = c.post("/api/sectors/已存在")
    assert r.status_code == 409


def test_post_existing_with_force_regenerates(client, mocker):
    c, db = client
    from core.database import upsert_sector
    upsert_sector(db, "已存在", description="old")
    mocker.patch("core.sector_glossary.generate_sector_explanation",
                 return_value={"description": "new", "industry_overview": "",
                               "top_companies": [], "synonyms": []})
    r = c.post("/api/sectors/已存在?force=true")
    assert r.status_code == 202
    from api.jobs import get_job
    job_id = r.json()["job_id"]
    for _ in range(50):
        if get_job(job_id)["status"] in ("completed", "failed"):
            break
    assert c.get("/api/sectors/已存在").json()["description"] == "new"
```

- [ ] **Step 3.2: 跑测试确认失败**

Run: `pytest tests/api/test_sectors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.routers.sectors'`

- [ ] **Step 3.3: 创建 `api/routers/sectors.py`**

```python
# api/routers/sectors.py
import json
import os
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fa_matching.db")

from core.database import init_db, get_sector, upsert_sector
from core.sector_glossary import generate_sector_explanation
from api.jobs import create_job, set_running, set_done, set_failed

init_db(DB_PATH)
router = APIRouter(prefix="/api/sectors")


def _serialize(row: dict) -> dict:
    """把存库的 JSON 字符串字段解出来再返给前端。"""
    return {
        "name": row["name"],
        "description": row.get("description", "") or "",
        "industry_overview": row.get("industry_overview", "") or "",
        "top_companies": json.loads(row.get("top_companies") or "[]"),
        "synonyms": json.loads(row.get("synonyms") or "[]"),
        "generated_at": row.get("generated_at", ""),
        "generated_by": row.get("generated_by", ""),
    }


def _run_generate(job_id: str, name: str):
    set_running(job_id)
    try:
        data = generate_sector_explanation(name)
        upsert_sector(
            DB_PATH, name,
            description=data["description"],
            industry_overview=data["industry_overview"],
            top_companies=json.dumps(data["top_companies"], ensure_ascii=False),
            synonyms=json.dumps(data["synonyms"], ensure_ascii=False),
            generated_by=os.getenv("LLM_MODEL", ""),
        )
        set_done(job_id, {"name": name})
    except Exception as e:
        set_failed(job_id, str(e))


@router.get("/{name}")
def read_sector(name: str):
    row = get_sector(DB_PATH, name)
    if not row:
        raise HTTPException(status_code=404, detail="Sector not generated yet")
    return _serialize(row)


@router.post("/{name}", status_code=202)
def create_sector(name: str, background_tasks: BackgroundTasks,
                  force: bool = Query(False)):
    existing = get_sector(DB_PATH, name)
    if existing and not force:
        raise HTTPException(
            status_code=409,
            detail="Sector already generated; pass ?force=true to regenerate"
        )
    job_id = create_job()
    background_tasks.add_task(_run_generate, job_id, name)
    return {"job_id": job_id, "name": name}
```

- [ ] **Step 3.4: 在 `api/main.py` 注册 router**

把这一行
```python
from api.routers import jobs, projects, institutions, matching, settings
```
改成
```python
from api.routers import jobs, projects, institutions, matching, settings, sectors
```
并把
```python
for router in [jobs.router, projects.router, institutions.router,
               matching.router, settings.router]:
```
改成
```python
for router in [jobs.router, projects.router, institutions.router,
               matching.router, settings.router, sectors.router]:
```

- [ ] **Step 3.5: 跑测试确认通过**

Run: `pytest tests/api/test_sectors.py -v`
Expected: 5 passed

- [ ] **Step 3.6: 跑全量后端测试确认没破坏旧的**

Run: `pytest tests/ -v`
Expected: all green

- [ ] **Step 3.7: 提交**

```bash
git add api/routers/sectors.py api/main.py tests/api/test_sectors.py
git commit -m "feat(api): add /api/sectors GET/POST with async generation"
```

---

## Task 4: 前端 API 客户端 `frontend/src/api/sectors.ts`

**Files:**
- Create: `frontend/src/api/sectors.ts`

- [ ] **Step 4.1: 创建 `frontend/src/api/sectors.ts`**

```typescript
import { apiFetch, ApiError } from './client'

export interface SectorCompany {
  name: string
  desc: string
}

export interface SectorExplanation {
  name: string
  description: string
  industry_overview: string
  top_companies: SectorCompany[]
  synonyms: string[]
  generated_at: string
  generated_by: string
}

export const sectorsApi = {
  /** 拿缓存。命中返完整数据;未命中返 null(不抛错)。 */
  async get(name: string): Promise<SectorExplanation | null> {
    try {
      return await apiFetch<SectorExplanation>(`/api/sectors/${encodeURIComponent(name)}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }
  },

  /** 触发后台生成。返回 job_id。如果已存在且未 force,会抛 409。 */
  async generate(name: string, force = false): Promise<{ job_id: string }> {
    const qs = force ? '?force=true' : ''
    return apiFetch(`/api/sectors/${encodeURIComponent(name)}${qs}`, { method: 'POST' })
  },
}
```

- [ ] **Step 4.2: 跑 tsc 确认类型通过**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出(通过)

- [ ] **Step 4.3: 提交**

```bash
git add frontend/src/api/sectors.ts
git commit -m "feat(fe): add sectors API client"
```

---

## Task 5: SectorDrawer 组件 + 骨架屏样式 + ClickableSectorBadge 复用组件

**Files:**
- Modify: `frontend/src/styles/globals.css` (append @keyframes shimmer)
- Create: `frontend/src/components/SectorDrawer.tsx` (含 default export `SectorDrawer` + named export `ClickableSectorBadge`)

- [ ] **Step 5.1: 在 `frontend/src/styles/globals.css` 末尾追加骨架屏动画**

```css

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

- [ ] **Step 5.2: 创建 `frontend/src/components/SectorDrawer.tsx`**

```tsx
import { useState, useEffect, useRef } from 'react'
import { sectorsApi } from '../api/sectors'
import type { SectorExplanation } from '../api/sectors'
import { pollJob } from '../api/jobs'

interface DrawerProps {
  sectorName: string
  onClose: () => void
  onJumpTo: (name: string) => void
}

type State =
  | { kind: 'loading' }
  | { kind: 'data', data: SectorExplanation }
  | { kind: 'error', message: string }

export default function SectorDrawer({ sectorName, onClose, onJumpTo }: DrawerProps) {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [regenerating, setRegenerating] = useState(false)
  const cancelPoll = useRef<(() => void) | null>(null)

  useEffect(() => {
    let cancelled = false
    setState({ kind: 'loading' })
    cancelPoll.current?.()

    sectorsApi.get(sectorName).then(hit => {
      if (cancelled) return
      if (hit) {
        setState({ kind: 'data', data: hit })
      } else {
        sectorsApi.generate(sectorName).then(({ job_id }) => {
          if (cancelled) return
          cancelPoll.current = pollJob(
            job_id,
            async () => {
              const fresh = await sectorsApi.get(sectorName)
              if (cancelled) return
              if (fresh) setState({ kind: 'data', data: fresh })
              else setState({ kind: 'error', message: '生成完成但未读到结果' })
            },
            (j) => !cancelled && setState({ kind: 'error', message: j.error || '生成失败' })
          )
        }).catch(e => !cancelled && setState({ kind: 'error', message: String(e) }))
      }
    }).catch(e => !cancelled && setState({ kind: 'error', message: String(e) }))

    return () => { cancelled = true; cancelPoll.current?.() }
  }, [sectorName])

  async function regenerate() {
    setRegenerating(true)
    setState({ kind: 'loading' })
    try {
      const { job_id } = await sectorsApi.generate(sectorName, true)
      cancelPoll.current = pollJob(
        job_id,
        async () => {
          const fresh = await sectorsApi.get(sectorName)
          if (fresh) setState({ kind: 'data', data: fresh })
          setRegenerating(false)
        },
        (j) => { setState({ kind: 'error', message: j.error || '重新生成失败' }); setRegenerating(false) }
      )
    } catch (e) {
      setState({ kind: 'error', message: String(e) })
      setRegenerating(false)
    }
  }

  return (
    <aside style={{
      width: 520, flexShrink: 0, alignSelf: 'flex-start',
      position: 'sticky', top: 0,
      border: '1px solid var(--border)', borderRadius: 8,
      background: 'var(--bg-surface)', overflow: 'hidden'
    }}>
      <div style={{
        padding: '14px 16px 14px 20px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10
      }}>
        <span style={{
          fontWeight: 600, fontSize: 15, color: '#fff', flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
        }}>{sectorName}</span>
        <button onClick={onClose} aria-label="关闭" title="关闭" style={{
          background: 'transparent', border: 'none', color: 'var(--text-muted)',
          fontSize: 20, padding: '0 4px', lineHeight: 1, cursor: 'pointer'
        }}>×</button>
      </div>

      <div style={{
        padding: '8px 20px', borderBottom: '1px solid var(--border)',
        background: 'rgba(245,158,11,0.06)',
        display: 'flex', alignItems: 'center', gap: 12,
        fontSize: 11, color: 'var(--text-secondary)'
      }}>
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--warning)' }} />
        <span>AI 生成,仅供参考</span>
        {state.kind === 'data' && state.data.generated_at && (
          <>
            <span>·</span>
            <span>上次生成 {state.data.generated_at.slice(0, 10)}</span>
          </>
        )}
        <button onClick={regenerate} disabled={regenerating} style={{
          marginLeft: 'auto',
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--text-secondary)', fontSize: 11,
          padding: '3px 10px', borderRadius: 4, cursor: 'pointer'
        }}>↻ 重新生成</button>
      </div>

      <div style={{ padding: 20, maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
        {state.kind === 'loading' && <SkeletonView />}

        {state.kind === 'error' && (
          <div style={{ color: 'var(--danger)', fontSize: 13 }}>
            {state.message}
            <div style={{ marginTop: 8 }}>
              <button onClick={regenerate} style={{
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text-secondary)', padding: '4px 12px',
                borderRadius: 4, fontSize: 12, cursor: 'pointer'
              }}>重试</button>
            </div>
          </div>
        )}

        {state.kind === 'data' && <DataView data={state.data} onJumpTo={onJumpTo} />}
      </div>
    </aside>
  )
}

const SKEL_BASE: React.CSSProperties = {
  background: 'linear-gradient(90deg, var(--bg-elevated) 0%, rgba(91,91,214,0.12) 50%, var(--bg-elevated) 100%)',
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.4s linear infinite',
  borderRadius: 4,
}

function SkelLine({ w = '100%', h = 14 }: { w?: string; h?: number }) {
  return <div style={{ ...SKEL_BASE, width: w, height: h, marginBottom: 8 }} />
}

function SkeletonView() {
  const h3: React.CSSProperties = {
    fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '.5px', fontWeight: 500, marginBottom: 8
  }
  return (
    <>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 16 }}>
        AI 生成中…首次生成可能需要十几秒
      </p>
      <div style={{ marginBottom: 20 }}>
        <div style={h3}>是什么</div>
        <SkelLine /><SkelLine /><SkelLine w="60%" />
      </div>
      <div style={{ marginBottom: 20 }}>
        <div style={h3}>行业发展</div>
        <SkelLine /><SkelLine w="80%" /><SkelLine />
      </div>
      <div>
        <div style={h3}>头部公司</div>
        <div style={{ ...SKEL_BASE, height: 40, marginBottom: 8 }} />
        <div style={{ ...SKEL_BASE, height: 40 }} />
      </div>
    </>
  )
}

function DataView({ data, onJumpTo }: { data: SectorExplanation; onJumpTo: (name: string) => void }) {
  const h3: React.CSSProperties = {
    fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '.5px', fontWeight: 500, marginBottom: 8
  }
  const section: React.CSSProperties = { marginBottom: 20 }
  return (
    <>
      <div style={section}>
        <div style={h3}>是什么</div>
        <p style={{ fontSize: 13, lineHeight: 1.65 }}>{data.description || '—'}</p>
      </div>
      <div style={section}>
        <div style={h3}>行业发展</div>
        <p style={{ fontSize: 13, lineHeight: 1.65 }}>{data.industry_overview || '—'}</p>
      </div>
      <div style={section}>
        <div style={h3}>头部公司</div>
        {data.top_companies.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.top_companies.map(c => (
              <div key={c.name} style={{
                padding: '8px 10px', borderRadius: 6,
                background: 'var(--bg-elevated)', border: '1px solid var(--bg-elevated)'
              }}>
                <div style={{ color: '#fff', fontWeight: 500, fontSize: 13 }}>{c.name}</div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{c.desc}</div>
              </div>
            ))}
          </div>
        )}
      </div>
      {data.synonyms.length > 0 && (
        <div style={section}>
          <div style={h3}>同义词候选(LLM 给出,可点跳转)</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.synonyms.map(s => (
              <span key={s} onClick={() => onJumpTo(s)} style={{
                fontSize: 12, padding: '3px 10px', borderRadius: 4,
                background: 'rgba(139,92,246,0.12)', color: 'var(--accent-light)',
                border: '1px solid rgba(139,92,246,0.3)', cursor: 'pointer'
              }}>{s}</span>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

interface BadgeProps {
  name: string
  onClick: (name: string) => void
}

export function ClickableSectorBadge({ name, onClick }: BadgeProps) {
  return (
    <span onClick={() => onClick(name)} style={{
      fontSize: 11, padding: '2px 8px', borderRadius: 3,
      background: 'rgba(91,91,214,0.18)', color: '#a8a4ff',
      border: '1px dashed transparent',
      cursor: 'pointer', userSelect: 'none', lineHeight: 1.6,
      display: 'inline-block',
      transition: 'all .12s ease',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.background = 'rgba(91,91,214,0.32)'
      e.currentTarget.style.borderColor = 'rgba(139,92,246,0.6)'
      e.currentTarget.style.color = '#fff'
    }}
    onMouseLeave={e => {
      e.currentTarget.style.background = 'rgba(91,91,214,0.18)'
      e.currentTarget.style.borderColor = 'transparent'
      e.currentTarget.style.color = '#a8a4ff'
    }}
    >{name}</span>
  )
}
```

- [ ] **Step 5.3: 跑 tsc**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出

- [ ] **Step 5.4: 提交**

```bash
git add frontend/src/components/SectorDrawer.tsx frontend/src/styles/globals.css
git commit -m "feat(fe): add SectorDrawer + ClickableSectorBadge + shimmer keyframes"
```

---

## Task 6: Institutions 页接入 Drawer

**Files:**
- Modify: `frontend/src/pages/Institutions.tsx`

- [ ] **Step 6.1: 在 imports 区追加**

定位:`import Spinner from '../components/Spinner'` 行之后插入:

```tsx
import SectorDrawer, { ClickableSectorBadge } from '../components/SectorDrawer'
```

- [ ] **Step 6.2: 在 `Institutions` 组件状态声明区追加**

定位:`const [selectedId, setSelectedId] = useState<number | null>(null)` 之后:

```tsx
const [openSector, setOpenSector] = useState<string | null>(null)
```

- [ ] **Step 6.3: 替换关注赛道列里的渲染**

定位:文件里这一段(关注赛道列 td,Badge variant="blue" 那段):

```tsx
<td style={{ padding: '11px 12px', maxWidth: 200 }}>
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
    {(inst.preferred_sectors || '').split(',').filter(Boolean).slice(0, 5).map(s => (
      <Badge key={s} variant="blue">{s.trim()}</Badge>
    ))}
    {(inst.preferred_sectors || '').split(',').filter(Boolean).length > 5 && (
      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>+{(inst.preferred_sectors || '').split(',').filter(Boolean).length - 5}</span>
    )}
  </div>
</td>
```

替换为:

```tsx
<td style={{ padding: '11px 12px', maxWidth: 200 }}>
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
    {(inst.preferred_sectors || '').split(',').filter(Boolean).slice(0, 5).map(s => (
      <ClickableSectorBadge key={s.trim()} name={s.trim()} onClick={setOpenSector} />
    ))}
    {(inst.preferred_sectors || '').split(',').filter(Boolean).length > 5 && (
      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>+{(inst.preferred_sectors || '').split(',').filter(Boolean).length - 5}</span>
    )}
  </div>
</td>
```

- [ ] **Step 6.4: 把 list tab 包成 flex 布局**

定位:文件里这一段(list tab 开头):

```tsx
      {tab === 'list' && <>
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center' }}>
```

替换为:

```tsx
      {tab === 'list' && (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0, overflowX: 'auto' }}>
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center' }}>
```

- [ ] **Step 6.5: 把 list tab 闭合处替换为 flex 容器闭合 + SectorDrawer**

定位:文件里这一段(list tab 结尾):

```tsx
        {selected && (
          <DetailPanel
            inst={selected}
            onUpdated={reload}
            onDeleted={() => { setSelectedId(null); reload() }}
          />
        )}
      </>}
```

替换为:

```tsx
        {selected && (
          <DetailPanel
            inst={selected}
            onUpdated={reload}
            onDeleted={() => { setSelectedId(null); reload() }}
          />
        )}
          </div>
          {openSector && (
            <SectorDrawer
              key={openSector}
              sectorName={openSector}
              onClose={() => setOpenSector(null)}
              onJumpTo={(n) => setOpenSector(n)}
            />
          )}
        </div>
      )}
```

- [ ] **Step 6.6: 跑 tsc + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 无 error

- [ ] **Step 6.7: 手工验证**

Run: `./start.sh`
浏览器打开 http://localhost:5173 → 机构管理页 → 逐项验证:

- [ ] 关注赛道列里的标签鼠标悬停时背景变深、紫色虚线描边、光标变手
- [ ] 点击赛道标签 → 右侧 Drawer 出现,标题是该赛道名
- [ ] Drawer 顶部黄色提示条显示 "AI 生成,仅供参考"
- [ ] 首次点击显示骨架屏(shimmer 动画扫过的灰条)
- [ ] 生成完成后展示「是什么 / 行业发展 / 头部公司 / 同义词候选」
- [ ] 同义词标签可点击,Drawer 切换到该词条
- [ ] 点击其他赛道标签 → Drawer 内容直接切换、不需要先关
- [ ] Drawer 右上 × 关闭后,列表恢复全宽
- [ ] "↻ 重新生成"按钮能再触发一次生成

把 ./start.sh 跑出的两个进程 Ctrl+C 关掉再继续。

- [ ] **Step 6.8: 提交**

```bash
git add frontend/src/pages/Institutions.tsx
git commit -m "feat(fe): clickable sector badges + SectorDrawer on Institutions page"
```

---

## Task 7: Projects 页接入 Drawer

**Files:**
- Modify: `frontend/src/pages/Projects.tsx`

- [ ] **Step 7.1: 在 imports 区追加**

定位:文件第 1 行 `import { useState, useEffect, useCallback } from 'react'` 之后(具体位置参考现有 import 段尾):

```tsx
import SectorDrawer, { ClickableSectorBadge } from '../components/SectorDrawer'
```

- [ ] **Step 7.2: 在 `Projects` 组件状态区追加**

定位:跟其他 `useState` 放在一起,在 `const filtered = ...` 上方:

```tsx
const [openSector, setOpenSector] = useState<string | null>(null)
```

- [ ] **Step 7.3: 把 `p.sector` 列里的 Badge 改为可点**

定位:文件里这一行(目前约第 62 行):

```tsx
<td style={{ padding:'11px 12px' }}>{p.sector && <Badge variant="purple">{p.sector}</Badge>}</td>
```

替换为:

```tsx
<td style={{ padding:'11px 12px' }}>{p.sector && (
  <ClickableSectorBadge name={p.sector} onClick={setOpenSector} />
)}</td>
```

- [ ] **Step 7.4: 把 `p.sub_sector` 列从纯文本改为可点 Badge(支持逗号分隔多值)**

定位:文件里这一行(目前约第 63 行):

```tsx
<td style={{ padding:'11px 12px', color:'var(--text-secondary)' }}>{p.sub_sector||'—'}</td>
```

替换为:

```tsx
<td style={{ padding:'11px 12px' }}>
  {p.sub_sector ? (
    <div style={{ display:'flex', flexWrap:'wrap', gap:3 }}>
      {p.sub_sector.split(',').filter(Boolean).map(s => (
        <ClickableSectorBadge key={s.trim()} name={s.trim()} onClick={setOpenSector} />
      ))}
    </div>
  ) : <span style={{ color:'var(--text-secondary)' }}>—</span>}
</td>
```

- [ ] **Step 7.5: 把主返回结构包成 flex 容器,右侧挂 SectorDrawer**

定位:文件里 `Projects` 组件的 return 起始:

```tsx
  return (
    <div>
      <div style={{ display:'flex', gap:10, marginBottom:16, alignItems:'center' }}>
```

替换为:

```tsx
  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
      <div style={{ flex: 1, minWidth: 0, overflowX: 'auto' }}>
      <div style={{ display:'flex', gap:10, marginBottom:16, alignItems:'center' }}>
```

定位:文件里 `Projects` 组件 return 的结尾(`{showUpload && ...}` 之后、最外层 `</div>` 之前):

```tsx
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSaved={() => { setShowUpload(false); reload() }} />}
    </div>
  )
}
```

替换为:

```tsx
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSaved={() => { setShowUpload(false); reload() }} />}
      </div>
      {openSector && (
        <SectorDrawer
          key={openSector}
          sectorName={openSector}
          onClose={() => setOpenSector(null)}
          onJumpTo={(n) => setOpenSector(n)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 7.6: 跑 tsc + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 无 error

- [ ] **Step 7.7: 手工验证**

Run: `./start.sh`
浏览器 http://localhost:5173 → 项目页 → 验证:

- [ ] 「赛道」列的紫色 Badge 替换为蓝紫可点 Badge,悬停描边、光标变手
- [ ] 「细分」列从纯文本变为可点 Badge(若 sub_sector 是逗号分隔的,逐个拆分)
- [ ] 点击 → 右侧 Drawer 弹出该词条解释
- [ ] 同义词跳转正常
- [ ] 与机构页 Drawer 行为完全一致(因为复用同组件)

- [ ] **Step 7.8: 提交**

```bash
git add frontend/src/pages/Projects.tsx
git commit -m "feat(fe): clickable sector badges + SectorDrawer on Projects page"
```

---

## Self-Review

- ✅ **Spec 覆盖**:DB schema(Task 1)/ LLM 模块(Task 2)/ API endpoints(Task 3)/ 前端 client(Task 4)/ Drawer 组件 + 骨架屏 + 复用 Badge(Task 5)/ 机构页接入(Task 6)/ 项目页接入(Task 7)— 七个任务对应到位
- ✅ **类型一致**:`SectorExplanation`(字段 name / description / industry_overview / top_companies(SectorCompany[]) / synonyms(string[]) / generated_at / generated_by)在 sectors.ts 定义,SectorDrawer 引用,router `_serialize` 返回字段名匹配
- ✅ **TDD 严格度**:后端 Task 1/2/3 严格走 "写测试 → 跑失败 → 实现 → 跑通过 → commit";前端 Task 4-7 用 `tsc` + lint + 手工验证替代(项目前端无测试框架)
- ✅ **无占位符**:所有代码块完整可用,无 "TBD / 添加合适的错误处理" 等模糊指令;Task 7 的位置定位精确到具体行级 before/after
- ✅ **复用与 DRY**:可点 Badge 抽成 `ClickableSectorBadge` 命名导出,Institutions / Projects 两页都引用,无重复 inline 样式
- ⚠️ **已知后置项**(约定不在本次实施):同义词归一去重(库膨胀时再做)、LLM 头部公司外挂搜索校验、词条增删管理 UI、批量预生成
