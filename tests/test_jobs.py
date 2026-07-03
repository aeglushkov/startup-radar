from unittest.mock import patch

import pytest

from radar import db
from radar.config import Config
from radar.jobs import run_daily
from radar.runner import ScraperError

CFG = Config(bot_token="t", channel_id="@c", admin_ids=frozenset({1}),
             openai_api_key="sk", openai_model="m", db_path=":memory:",
             scrapers_dir="scrapers", timezone="Europe/Berlin")


@pytest.fixture
def conn():
    c = db.get_conn(":memory:")
    db.init_db(c)
    return c


def _activate(conn, slug, last_count=None):
    db.add_source(conn, slug, slug.upper(), f"https://{slug}.com", added_by=1)
    db.set_source_status(conn, slug, "active")
    if last_count is not None:
        db.update_source_after_run(conn, slug, last_count)


async def _collect(sent):
    async def send(text):
        sent.append(text)
    return send


async def test_new_company_posted_and_marked(conn):
    _activate(conn, "yc", last_count=1)
    sent = []
    scraped = [{"name": "Acme", "url": "https://acme.io", "description": "d", "extra": None}]
    with patch("radar.jobs.run_scraper", return_value=scraped), \
         patch("radar.jobs.enrich_company", side_effect=lambda c, k, m: {**c, "one_liner": "One.", "tags": ["ai"]}):
        await run_daily(conn, CFG, await _collect(sent))
    assert any("Acme" in m for m in sent)
    row = conn.execute("SELECT posted_at FROM companies WHERE name='Acme'").fetchone()
    assert row["posted_at"] not in (None, "baseline")
    assert conn.execute("SELECT outcome FROM runs").fetchone()["outcome"] == "ok"


async def test_suspicious_shrink_skips_diff(conn):
    _activate(conn, "yc", last_count=100)
    sent = []
    scraped = [{"name": "Only", "url": "https://only.io", "description": None, "extra": None}]
    with patch("radar.jobs.run_scraper", return_value=scraped):
        await run_daily(conn, CFG, await _collect(sent))
    assert conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"] == 0
    assert "failures: yc" in sent[-1]
    assert conn.execute("SELECT outcome FROM runs").fetchone()["outcome"] == "suspicious"


async def test_scraper_failure_flagged_but_digest_sent(conn):
    _activate(conn, "yc")
    sent = []
    with patch("radar.jobs.run_scraper", side_effect=ScraperError("exec", "boom")):
        await run_daily(conn, CFG, await _collect(sent))
    assert "Nothing new today." in sent[0]
    assert "failures: yc" in sent[-1]
    assert conn.execute("SELECT outcome FROM runs").fetchone()["outcome"] == "failed"


async def test_orphaned_unposted_companies_recovered(conn):
    _activate(conn, "yc", last_count=1)
    sid_ = db.get_source(conn, "yc")["id"]
    db.insert_companies(conn, sid_, [{"name": "Orphan", "url": "https://orphan.io",
        "normalised_url": "orphan.io", "description": None, "one_liner": "Lost.", "tags": []}])
    sent = []
    scraped = [{"name": "Orphan", "url": "https://orphan.io", "description": None, "extra": None}]
    with patch("radar.jobs.run_scraper", return_value=scraped):
        await run_daily(conn, CFG, await _collect(sent))
    assert any("Orphan" in m for m in sent)
    row = conn.execute("SELECT posted_at FROM companies WHERE name='Orphan'").fetchone()
    assert row["posted_at"] is not None


async def test_processing_error_flagged_but_digest_sent(conn):
    _activate(conn, "yc", last_count=1)
    sent = []
    scraped = [{"name": "Acme", "url": "https://acme.io", "description": None, "extra": None}]
    with patch("radar.jobs.run_scraper", return_value=scraped), \
         patch("radar.jobs.find_new", side_effect=RuntimeError("db exploded")):
        await run_daily(conn, CFG, await _collect(sent))
    assert sent, "digest must still be sent"
    assert "failures: yc" in sent[-1]
    row = conn.execute("SELECT outcome, error FROM runs").fetchone()
    assert row["outcome"] == "failed" and "db exploded" in row["error"]
