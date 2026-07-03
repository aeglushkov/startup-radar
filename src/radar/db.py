import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    added_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    last_run_at TEXT,
    last_count INTEGER
);
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    normalised_url TEXT NOT NULL,
    description TEXT,
    one_liner TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    first_seen TEXT NOT NULL,
    posted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_companies_source ON companies(source_id);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    started_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    count INTEGER NOT NULL,
    error TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def add_source(conn, slug: str, name: str, url: str, added_by: int) -> None:
    conn.execute(
        "INSERT INTO sources (slug, name, url, added_by, created_at) VALUES (?,?,?,?,?)",
        (slug, name, url, added_by, _now()),
    )


def get_source(conn, slug: str):
    return conn.execute("SELECT * FROM sources WHERE slug=?", (slug,)).fetchone()


def list_sources(conn) -> list:
    return conn.execute(
        "SELECT * FROM sources WHERE status != 'removed' ORDER BY slug"
    ).fetchall()


def set_source_status(conn, slug: str, status: str) -> None:
    conn.execute("UPDATE sources SET status=? WHERE slug=?", (status, slug))


def update_source_after_run(conn, slug: str, count: int) -> None:
    conn.execute(
        "UPDATE sources SET last_run_at=?, last_count=? WHERE slug=?",
        (_now(), count, slug),
    )


def insert_companies(conn, source_id: int, companies: list[dict],
                     posted_at: str | None = None) -> list[int]:
    ids = []
    for c in companies:
        cur = conn.execute(
            "INSERT INTO companies (source_id, name, url, normalised_url, description,"
            " one_liner, tags, first_seen, posted_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (source_id, c["name"], c["url"], c["normalised_url"], c.get("description"),
             c.get("one_liner"), json.dumps(c.get("tags", [])), _now(), posted_at),
        )
        ids.append(cur.lastrowid)
    return ids


def known_keys(conn, source_id: int) -> tuple[set[str], set[str]]:
    rows = conn.execute(
        "SELECT normalised_url, name FROM companies WHERE source_id=?", (source_id,)
    ).fetchall()
    return ({r["normalised_url"] for r in rows},
            {r["name"].strip().lower() for r in rows})


def mark_posted(conn, company_ids: list[int]) -> None:
    now = _now()
    conn.executemany(
        "UPDATE companies SET posted_at=? WHERE id=?", [(now, i) for i in company_ids]
    )


def record_run(conn, source_id: int, outcome: str, count: int,
               error: str | None) -> None:
    conn.execute(
        "INSERT INTO runs (source_id, started_at, outcome, count, error)"
        " VALUES (?,?,?,?,?)",
        (source_id, _now(), outcome, count, error),
    )
