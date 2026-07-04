"""Partech portfolio scraper (Next.js `__NEXT_DATA__` payload).

The /companies page inlines the full company list (name, description,
external website, sector, HQ, status) as JSON in the standard Next.js
`__NEXT_DATA__` script tag — no pagination needed.
"""
import json

import httpx
from bs4 import BeautifulSoup

BASE = "https://partechpartners.com"
URL = f"{BASE}/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        raise RuntimeError("__NEXT_DATA__ script not found on companies page")
    data = json.loads(tag.string)
    records = data["props"]["pageProps"]["companies"]

    companies = []
    for r in records:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        website = (r.get("external_link") or "").strip()
        internal_link = r.get("internal_link")
        profile_url = f"{BASE}{internal_link}" if internal_link else None
        description = (r.get("description") or r.get("short_text") or "").strip() or None
        companies.append({
            "name": name,
            "url": website or profile_url or URL,
            "description": description,
            "extra": {
                "status": (r.get("status") or {}).get("status"),
                "sectors": [s.get("sector") for s in (r.get("sectors") or [])] or None,
                "hq": [h.get("location") for h in (r.get("hq_locations") or [])] or None,
            },
        })
    return companies
