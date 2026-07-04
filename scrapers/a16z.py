"""Andreessen Horowitz portfolio scraper.

The portfolio page inlines the full company list as one entity-encoded JSON
array in a `data-companies` attribute (~3.5 MB page, ~850 records) — no
pagination needed. Rich per-company fields include the actual website URL,
description, status, and first-funded date.
"""
import html
import json
import re

import httpx

URL = "https://a16z.com/portfolio/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        text = resp.text
    match = re.search(r'data-companies="(.*?)"', text, re.S)
    if not match:
        raise RuntimeError("data-companies attribute not found on portfolio page")
    records = json.loads(html.unescape(match.group(1)))

    companies = []
    for r in records:
        name = (r.get("name") or r.get("post_title") or "").strip()
        url = r.get("url") or r.get("external_url") or r.get("permalink")
        if not name or not url:
            continue
        description = (r.get("website_description") or "").strip() or None
        companies.append({
            "name": name,
            "url": url,
            "description": description,
            "extra": {
                "status": r.get("status"),
                "first_funded": r.get("initial_a16z_date_funded"),
            },
        })
    return companies
