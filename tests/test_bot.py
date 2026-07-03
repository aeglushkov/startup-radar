from radar.bot import format_source_list, parse_add_args, slugify


def test_slugify():
    assert slugify("Y Combinator!") == "y-combinator"
    assert slugify("  A16Z  crypto ") == "a16z-crypto"


def test_parse_add_args():
    assert parse_add_args("/add Y Combinator https://www.ycombinator.com/companies") == (
        "Y Combinator", "https://www.ycombinator.com/companies")
    assert parse_add_args("/add onlyname") is None
    assert parse_add_args("/add Name not-a-url") is None


class Row(dict):
    def __getitem__(self, k):
        return dict.__getitem__(self, k)


def test_format_source_list():
    rows = [Row(slug="yc", status="active", last_run_at="2026-07-03T06:00:00+00:00",
                last_count=5000)]
    out = format_source_list(rows)
    assert "yc" in out and "active" in out and "5000" in out
    assert format_source_list([]) == "No sources yet. Add one with /add <name> <url>."
