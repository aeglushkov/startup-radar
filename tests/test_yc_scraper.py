import importlib.util
import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest

FIX = pathlib.Path(__file__).parent / "fixtures"
PAGE_KEY = (
    "NzJmMWExZWYxYzY5OGYwN2VkYWM5YzRiM2VlNDFlM2I0ODU2YjQ2Yjg0MTFiNWE5NzY0NTMyZGI1OWEwMzVjY2Fu"
    "YWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlf"
    "QnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"
)


def load_scraper():
    spec = importlib.util.spec_from_file_location(
        "yc", pathlib.Path(__file__).parents[1] / "scrapers" / "y-combinator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_algolia_opts_from_page():
    mod = load_scraper()
    app, key = mod.parse_algolia_opts((FIX / "yc_companies_page.html").read_text())
    assert app == "45BWZJ1SGC"
    assert key == PAGE_KEY


@pytest.mark.parametrize("page", [
    "<html><script>window.RAILS_ENV = 'production';</script></html>",
    '<script>window.AlgoliaOpts = {"app":"45BWZJ1SGC"};</script>',
])
def test_parse_algolia_opts_fails_loudly(page):
    mod = load_scraper()
    with pytest.raises(RuntimeError, match="AlgoliaOpts"):
        mod.parse_algolia_opts(page)


def test_scrape_paginates_and_maps():
    pages = [json.loads((FIX / f"yc_page{i}.json").read_text()) for i in (0, 1)]
    responses = [MagicMock(status_code=200, json=MagicMock(return_value=p)) for p in pages]
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get = MagicMock(return_value=MagicMock(text=(FIX / "yc_companies_page.html").read_text()))
    client.post = MagicMock(side_effect=responses)
    mod = load_scraper()
    with patch.object(mod.httpx, "Client", return_value=client):
        out = mod.scrape()
    assert client.post.call_count == 2
    url = client.post.call_args.args[0]
    assert url == "https://45bwzj1sgc-dsn.algolia.net/1/indexes/YCCompany_By_Launch_Date_production/query"
    assert client.post.call_args.kwargs["headers"]["x-algolia-api-key"] == PAGE_KEY
    assert [c["name"] for c in out] == ["Acme AI", "Beta Labs"]
    assert out[0]["url"] == "https://acme.ai"
    assert out[0]["description"] == "AI for acme"
    # empty website falls back to the YC profile page
    assert out[1]["url"] == "https://www.ycombinator.com/companies/beta-labs"
    assert out[0]["extra"]["batch"] == "S26"
