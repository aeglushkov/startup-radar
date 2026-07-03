import pytest

from radar import db
from radar.diffing import baseline, find_new, normalise_url


@pytest.fixture
def conn():
    c = db.get_conn(":memory:")
    db.init_db(c)
    db.add_source(c, "s", "S", "https://s.com", added_by=1)
    return c


def sid(conn):
    return db.get_source(conn, "s")["id"]


def test_normalise_url():
    assert normalise_url("HTTPS://WWW.Acme.io/") == "acme.io"
    assert normalise_url("http://acme.io/x?utm=1#top") == "acme.io/x"


def test_baseline_then_find_new(conn):
    scraped = [{"name": "Acme", "url": "https://acme.io", "description": None, "extra": None}]
    assert baseline(conn, sid(conn), scraped) == 1
    # same company, cosmetic url change -> not new
    again = [{"name": "ACME", "url": "https://www.acme.io/", "description": None, "extra": None}]
    assert find_new(conn, sid(conn), again) == []
    new = find_new(conn, sid(conn), [
        {"name": "Beta", "url": "https://beta.io", "description": "d", "extra": None},
        {"name": "Beta", "url": "https://beta.io", "description": "d", "extra": None},  # in-batch dup
    ])
    assert len(new) == 1 and new[0]["normalised_url"] == "beta.io"


def test_known_name_blocks_new_url(conn):
    baseline(conn, sid(conn), [{"name": "Acme", "url": "https://acme.io", "description": None, "extra": None}])
    moved = [{"name": "acme", "url": "https://acme.com", "description": None, "extra": None}]
    assert find_new(conn, sid(conn), moved) == []


def test_normalise_url_schemeless():
    assert normalise_url("acme.io:8080") == "acme.io:8080"
    assert normalise_url("www.acme.io/x/") == "acme.io/x"


def test_in_batch_same_name_different_urls(conn):
    new = find_new(conn, sid(conn), [
        {"name": "Gamma", "url": "https://gamma.io", "description": None, "extra": None},
        {"name": "Gamma", "url": "https://gamma.ai", "description": None, "extra": None},
    ])
    assert len(new) == 1
