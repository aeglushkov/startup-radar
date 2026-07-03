import json
from unittest.mock import MagicMock, patch

from radar.enrich import enrich_company

COMPANY = {"name": "Acme", "url": "https://acme.io", "description": "AI acme", "extra": None}


def _openai_returning(payload: str):
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=payload))]
    )
    return client


def test_enrich_happy():
    payload = json.dumps({"one_liner": "Makes acme with AI.", "tags": ["ai", "tools", "x", "y"]})
    with patch("radar.enrich.OpenAI", return_value=_openai_returning(payload)), \
         patch("radar.enrich.fetch_site_snippet", return_value=None):
        out = enrich_company(COMPANY, "sk", "gpt-5-mini")
    assert out["one_liner"] == "Makes acme with AI."
    assert out["tags"] == ["ai", "tools", "x"]  # capped at 3
    assert out["name"] == "Acme"


def test_enrich_failure_degrades():
    with patch("radar.enrich.OpenAI", side_effect=RuntimeError("down")):
        out = enrich_company(COMPANY, "sk", "gpt-5-mini")
    assert out["one_liner"] is None and out["tags"] == []
