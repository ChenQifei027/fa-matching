# core/database.py
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT,
    sector TEXT,
    sub_sector TEXT,
    stage TEXT,
    location TEXT,
    description TEXT,
    highlights TEXT,
    financing_need TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS institutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website TEXT,
    founded_year TEXT,
    location TEXT,
    aum TEXT,
    current_fund TEXT,
    preferred_sectors TEXT,
    preferred_stages TEXT,
    ticket_size_min TEXT,
    ticket_size_max TEXT,
    preferred_locations TEXT,
    key_partners TEXT,
    notable_portfolio TEXT,
    contact_name TEXT,
    contact_wechat TEXT,
    fa_fee_note TEXT,
    response_style TEXT,
    known_preferences TEXT,
    itjuzi_url TEXT,
    track_updates INTEGER DEFAULT 0,
    last_scraped_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS investment_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    sector TEXT,
    stage TEXT,
    amount TEXT,
    invested_date TEXT,
    event_url TEXT,
    company_desc TEXT,
    source TEXT DEFAULT 'itjuzi',
    FOREIGN KEY (institution_id) REFERENCES institutions(id),
    UNIQUE(institution_id, company_name, invested_date)
);

CREATE TABLE IF NOT EXISTS project_funding_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    round_date TEXT,
    round_type TEXT,
    amount TEXT,
    investors TEXT,
    source TEXT DEFAULT 'itjuzi',
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(project_id, round_date, round_type)
);

CREATE TABLE IF NOT EXISTS sectors (
    name TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    industry_overview TEXT DEFAULT '',
    top_companies TEXT DEFAULT '[]',
    synonyms TEXT DEFAULT '[]',
    generated_at TEXT DEFAULT (datetime('now')),
    generated_by TEXT DEFAULT ''
);
"""

@contextmanager
def _conn(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _migrate(conn):
    for ddl in [
        "ALTER TABLE investment_records ADD COLUMN event_url TEXT",
        "ALTER TABLE investment_records ADD COLUMN company_desc TEXT",
        "ALTER TABLE projects ADD COLUMN report_json TEXT",
        "ALTER TABLE projects ADD COLUMN report_generated_at TEXT",
        "ALTER TABLE projects ADD COLUMN research_json TEXT",
        "ALTER TABLE projects ADD COLUMN research_generated_at TEXT",
        "ALTER TABLE institutions ADD COLUMN source TEXT DEFAULT 'manual'",
        "ALTER TABLE institutions ADD COLUMN preference_profile TEXT",
        "ALTER TABLE institutions ADD COLUMN preference_analyzed_at TEXT",
    ]:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e) and "already exists" not in str(e):
                raise


def init_db(db_path):
    with _conn(db_path) as conn:
        conn.executescript(CREATE_TABLES_SQL)
        _migrate(conn)

def insert_project(db_path, **kwargs) -> int:
    fields = {k: v for k, v in kwargs.items()}
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    with _conn(db_path) as conn:
        cur = conn.execute(
            f"INSERT INTO projects ({cols}) VALUES ({placeholders})",
            list(fields.values())
        )
        return cur.lastrowid

def get_project(db_path, project_id) -> Optional[dict]:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

def list_projects(db_path) -> list:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def update_project(db_path, project_id, **kwargs):
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    sets += ", updated_at = ?"
    values.append(datetime.now().isoformat())
    with _conn(db_path) as conn:
        conn.execute(
            f"UPDATE projects SET {sets} WHERE id = ?",
            values + [project_id]
        )

def delete_project(db_path, project_id):
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM project_funding_rounds WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

def insert_institution(db_path, **kwargs) -> int:
    fields = {k: v for k, v in kwargs.items()}
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    with _conn(db_path) as conn:
        cur = conn.execute(
            f"INSERT INTO institutions ({cols}) VALUES ({placeholders})",
            list(fields.values())
        )
        return cur.lastrowid

def get_institution(db_path, institution_id) -> Optional[dict]:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM institutions WHERE id = ?", (institution_id,)).fetchone()
        return dict(row) if row else None

def list_institutions(db_path) -> list:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM institutions ORDER BY name").fetchall()
        return [dict(r) for r in rows]

def update_institution(db_path, institution_id, **kwargs):
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    sets += ", updated_at = ?"
    values.append(datetime.now().isoformat())
    with _conn(db_path) as conn:
        conn.execute(
            f"UPDATE institutions SET {sets} WHERE id = ?",
            values + [institution_id]
        )

def delete_institution(db_path, institution_id):
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM investment_records WHERE institution_id = ?", (institution_id,))
        conn.execute("DELETE FROM institutions WHERE id = ?", (institution_id,))

def insert_investment_record(db_path, **kwargs):
    fields = {k: v for k, v in kwargs.items()}
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    with _conn(db_path) as conn:
        conn.execute(
            f"INSERT OR IGNORE INTO investment_records ({cols}) VALUES ({placeholders})",
            list(fields.values())
        )

def list_investment_records(db_path, institution_id) -> list:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM investment_records WHERE institution_id = ? ORDER BY invested_date DESC",
            (institution_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_records_missing_desc(db_path, institution_id) -> list:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM investment_records WHERE institution_id = ? "
            "AND (company_desc IS NULL OR company_desc = '') "
            "AND (event_url IS NOT NULL AND event_url != '') "
            "ORDER BY invested_date DESC",
            (institution_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_investment_record_desc(db_path, record_id: int, company_desc: str):
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE investment_records SET company_desc = ? WHERE id = ?",
            (company_desc, record_id)
        )


def upsert_project_report(db_path, project_id: int, report_json: str):
    now = datetime.now().isoformat()
    with _conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE projects SET report_json = ?, report_generated_at = ?, updated_at = ? WHERE id = ?",
            (report_json, now, now, project_id)
        )
        if cur.rowcount == 0:
            raise ValueError(f"project {project_id} not found")


def upsert_project_research(db_path, project_id: int, research_json: str):
    now = datetime.now().isoformat()
    with _conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE projects SET research_json = ?, research_generated_at = ?, updated_at = ? WHERE id = ?",
            (research_json, now, now, project_id)
        )
        if cur.rowcount == 0:
            raise ValueError(f"project {project_id} not found")


def insert_funding_round(db_path, **kwargs):
    fields = {k: v for k, v in kwargs.items()}
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    with _conn(db_path) as conn:
        conn.execute(
            f"INSERT OR IGNORE INTO project_funding_rounds ({cols}) VALUES ({placeholders})",
            list(fields.values())
        )


def list_funding_rounds(db_path, project_id: int) -> list:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM project_funding_rounds WHERE project_id = ? ORDER BY round_date DESC",
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_project_funding_rounds(db_path, project_id: int):
    with _conn(db_path) as conn:
        conn.execute(
            "DELETE FROM project_funding_rounds WHERE project_id = ?",
            (project_id,)
        )


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


def get_sector(db_path, name: str) -> Optional[dict]:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM sectors WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def upsert_sector(db_path, name: str, **fields):
    """插入或更新。只覆盖 fields 中明确传入的列(未传入的列保持原值);
    generated_at 每次调用都自动刷新为当前时间。
    fields 允许: description / industry_overview / top_companies /
    synonyms / generated_by。"""
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
