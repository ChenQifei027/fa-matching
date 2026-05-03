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
    source TEXT DEFAULT 'itjuzi',
    FOREIGN KEY (institution_id) REFERENCES institutions(id),
    UNIQUE(institution_id, company_name, invested_date)
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

def init_db(db_path):
    with _conn(db_path) as conn:
        conn.executescript(CREATE_TABLES_SQL)

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
