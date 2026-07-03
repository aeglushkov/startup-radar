import textwrap

import pytest

from radar.runner import ScraperError, check_imports, run_scraper


def write(tmp_path, code):
    p = tmp_path / "s.py"
    p.write_text(textwrap.dedent(code))
    return str(p)


def test_happy_path(tmp_path):
    p = write(tmp_path, """
        def scrape():
            return [{"name": "Acme", "url": "https://acme.io", "description": None, "extra": None}]
    """)
    assert run_scraper(p)[0]["name"] == "Acme"


def test_env_is_stripped(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    p = write(tmp_path, """
        import os
        def scrape():
            return [{"name": os.environ.get("TELEGRAM_BOT_TOKEN", "ABSENT"),
                     "url": "https://x.io", "description": None, "extra": None}]
    """)
    assert run_scraper(p)[0]["name"] == "ABSENT"


def test_timeout(tmp_path):
    p = write(tmp_path, """
        import time
        def scrape():
            time.sleep(5)
            return []
    """)
    with pytest.raises(ScraperError) as e:
        run_scraper(p, timeout=1)
    assert e.value.stage == "timeout"


def test_bad_schema(tmp_path):
    p = write(tmp_path, """
        def scrape():
            return [{"url": "https://x.io"}]
    """)
    with pytest.raises(ScraperError) as e:
        run_scraper(p)
    assert e.value.stage == "schema"


def test_import_allowlist(tmp_path):
    p = write(tmp_path, """
        import requests
        import httpx, json
        from bs4 import BeautifulSoup
        def scrape():
            return []
    """)
    assert check_imports(p) == ["requests"]


def test_syntax_error_wrapped(tmp_path):
    p = write(tmp_path, """
        def scrape(:
            return []
    """)
    with pytest.raises(ScraperError) as e:
        run_scraper(p)
    assert e.value.stage == "imports"


def test_dynamic_import_flagged(tmp_path):
    p = write(tmp_path, """
        import importlib
        def scrape():
            mod = importlib.import_module("openai")
            return []
    """)
    assert "importlib" in check_imports(p)


def test_exec_eval_flagged(tmp_path):
    p = write(tmp_path, """
        def scrape():
            exec("import openai")
            eval("1+1")
            __import__("aiogram")
            return []
    """)
    assert check_imports(p) == ["__import__", "eval", "exec"]
