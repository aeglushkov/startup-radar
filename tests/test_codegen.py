import textwrap
from unittest.mock import patch

from radar import db
from radar.codegen import GenResult, generate_and_enable, render_prompt
from radar.config import Config

GOOD = textwrap.dedent("""
    def scrape():
        return [{"name": "A", "url": "https://a.io", "description": None, "extra": None}]
""")


def make_cfg(tmp_path):
    return Config(bot_token="t", channel_id="@c", admin_ids=frozenset({1}),
                  openai_api_key="sk", openai_model="m",
                  db_path=str(tmp_path / "r.db"),
                  scrapers_dir=str(tmp_path / "scrapers"), timezone="Europe/Berlin")


def seed(cfg, slug="demo"):
    conn = db.get_conn(cfg.db_path)
    db.init_db(conn)
    db.add_source(conn, slug, "Demo", "https://demo.vc", added_by=1)
    return conn


def test_render_prompt_embeds_contract_and_exemplar():
    p = render_prompt("Demo", "https://demo.vc", "demo", "scrapers")
    assert "scrapers/demo.py" in p and "https://demo.vc" in p
    assert "Algolia" in p or "ycombinator" in p  # exemplar embedded


def test_success_path(tmp_path):
    cfg = make_cfg(tmp_path)
    conn = seed(cfg)
    (tmp_path / "scrapers").mkdir()

    def fake_codex(prompt, cfg_):
        (tmp_path / "scrapers" / "demo.py").write_text(GOOD)

    with patch("radar.codegen._invoke_codex", side_effect=fake_codex), \
         patch("radar.codegen._git_commit"):
        res = generate_and_enable(cfg, "demo", "Demo", "https://demo.vc")
    assert res == GenResult(ok=True, count=1, error=None)
    assert db.get_source(conn, "demo")["status"] == "active"
    # baselined, not postable
    row = conn.execute("SELECT posted_at FROM companies").fetchone()
    assert row["posted_at"] == "baseline"


def test_failure_retries_once_then_fails(tmp_path):
    cfg = make_cfg(tmp_path)
    conn = seed(cfg)
    (tmp_path / "scrapers").mkdir()
    calls = []

    def fake_codex(prompt, cfg_):
        calls.append(prompt)
        (tmp_path / "scrapers" / "demo.py").write_text("def scrape():\n    return 'bad'\n")

    with patch("radar.codegen._invoke_codex", side_effect=fake_codex), \
         patch("radar.codegen._git_commit"):
        res = generate_and_enable(cfg, "demo", "Demo", "https://demo.vc")
    assert res.ok is False and len(calls) == 2
    assert "schema" in res.error
    assert calls[1] != calls[0]  # retry prompt includes error feedback
    assert db.get_source(conn, "demo")["status"] == "failed"


EMPTY = "def scrape():\n    return []\n"


def test_zero_companies_first_attempt_gets_retry(tmp_path):
    cfg = make_cfg(tmp_path)
    seed(cfg)
    (tmp_path / "scrapers").mkdir()
    outputs = [EMPTY, GOOD]

    def fake_codex(prompt, cfg_):
        (tmp_path / "scrapers" / "demo.py").write_text(outputs.pop(0))

    with patch("radar.codegen._invoke_codex", side_effect=fake_codex), \
         patch("radar.codegen._git_commit"):
        res = generate_and_enable(cfg, "demo", "Demo", "https://demo.vc")
    assert res.ok is True and res.count == 1  # retry rescued it
    assert not outputs  # both attempts consumed


def test_zero_companies_twice_fails_with_reason(tmp_path):
    cfg = make_cfg(tmp_path)
    conn = seed(cfg)
    (tmp_path / "scrapers").mkdir()

    def fake_codex(prompt, cfg_):
        (tmp_path / "scrapers" / "demo.py").write_text(EMPTY)

    with patch("radar.codegen._invoke_codex", side_effect=fake_codex), \
         patch("radar.codegen._git_commit"):
        res = generate_and_enable(cfg, "demo", "Demo", "https://demo.vc")
    assert res.ok is False and "0 companies" in res.error
    assert db.get_source(conn, "demo")["status"] == "failed"


def test_git_failure_logged_not_raised(tmp_path, caplog):
    import logging
    from radar.codegen import _git_commit
    with patch("radar.codegen.subprocess.run") as run:
        run.return_value.returncode = 1
        run.return_value.stderr = "boom"
        with caplog.at_level(logging.WARNING):
            _git_commit("scrapers/x.py", "x")
    assert "git add failed" in caplog.text or "boom" in caplog.text


def test_existing_working_scraper_used_without_codex(tmp_path):
    cfg = make_cfg(tmp_path)
    conn = seed(cfg)
    (tmp_path / "scrapers").mkdir()
    (tmp_path / "scrapers" / "demo.py").write_text(GOOD)
    with patch("radar.codegen._invoke_codex") as codex, \
         patch("radar.codegen._git_commit"):
        res = generate_and_enable(cfg, "demo", "Demo", "https://demo.vc")
    codex.assert_not_called()
    assert res.ok is True and res.count == 1
    assert db.get_source(conn, "demo")["status"] == "active"


def test_existing_broken_scraper_falls_through_to_codex(tmp_path):
    cfg = make_cfg(tmp_path)
    seed(cfg)
    (tmp_path / "scrapers").mkdir()
    (tmp_path / "scrapers" / "demo.py").write_text("def scrape():\n    return 'bad'\n")

    def fake_codex(prompt, cfg_):
        (tmp_path / "scrapers" / "demo.py").write_text(GOOD)

    with patch("radar.codegen._invoke_codex", side_effect=fake_codex) as codex, \
         patch("radar.codegen._git_commit"):
        res = generate_and_enable(cfg, "demo", "Demo", "https://demo.vc")
    assert codex.called
    assert res.ok is True
