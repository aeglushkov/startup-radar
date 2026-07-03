import sqlite3

import pytest

from radar import db


@pytest.fixture
def conn():
    c = db.get_conn(":memory:")
    db.init_db(c)
    return c


def _company(name="Acme", url="https://acme.io"):
    return {
        "name": name,
        "url": url,
        "normalised_url": url.removeprefix("https://"),
        "description": "d",
        "one_liner": None,
        "tags": [],
    }


def test_init_idempotent(conn):
    db.init_db(conn)  # second call must not raise


def test_source_lifecycle(conn):
    db.add_source(conn, "yc", "Y Combinator", "https://yc.com", added_by=1)
    with pytest.raises(sqlite3.IntegrityError):
        db.add_source(conn, "yc", "dup", "https://x.com", added_by=1)
    src = db.get_source(conn, "yc")
    assert src["status"] == "pending"
    db.set_source_status(conn, "yc", "active")
    db.update_source_after_run(conn, "yc", 42)
    src = db.get_source(conn, "yc")
    assert src["status"] == "active" and src["last_count"] == 42
    db.set_source_status(conn, "yc", "removed")
    assert db.list_sources(conn) == []


def test_companies_and_runs(conn):
    db.add_source(conn, "yc", "YC", "https://yc.com", added_by=1)
    sid = db.get_source(conn, "yc")["id"]
    ids = db.insert_companies(conn, sid, [_company()], posted_at="baseline")
    urls, names = db.known_keys(conn, sid)
    assert "acme.io" in urls and "acme" in names
    new_ids = db.insert_companies(conn, sid, [_company("Beta", "https://beta.io")])
    db.mark_posted(conn, new_ids)
    db.record_run(conn, sid, "ok", 2, None)
    row = conn.execute("SELECT outcome, count FROM runs").fetchone()
    assert row["outcome"] == "ok" and row["count"] == 2
