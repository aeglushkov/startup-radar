import importlib.util
import json
import pathlib
from unittest.mock import MagicMock, patch

FIX = pathlib.Path(__file__).parent / "fixtures"


def load_scraper():
    spec = importlib.util.spec_from_file_location(
        "yc", pathlib.Path(__file__).parents[1] / "scrapers" / "ycombinator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scrape_paginates_and_maps():
    pages = [json.loads((FIX / f"yc_page{i}.json").read_text()) for i in (0, 1)]
    responses = [MagicMock(json=MagicMock(return_value=p)) for p in pages]
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post = MagicMock(side_effect=responses)
    mod = load_scraper()
    with patch.object(mod.httpx, "Client", return_value=client):
        out = mod.scrape()
    assert [c["name"] for c in out] == ["Acme AI", "Beta Labs"]
    assert out[0]["url"] == "https://acme.ai"
    # empty website falls back to the YC profile page
    assert out[1]["url"] == "https://www.ycombinator.com/companies/beta-labs"
    assert out[0]["extra"]["batch"] == "S26"
