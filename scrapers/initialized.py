"""Initialized Capital companies scraper.

The /companies page is Next.js; the full portfolio (backed by a Strapi CMS)
is inlined in the __NEXT_DATA__ script as `props.pageProps.startups.data` —
no separate API call or pagination needed (no `meta`/cursor present, and the
count matches the visible directory).
"""
import json
import re

import httpx

URL = "https://initialized.com/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        text = resp.text

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S
    )
    if not match:
        raise RuntimeError("__NEXT_DATA__ script not found")
    data = json.loads(match.group(1))
    startups = data["props"]["pageProps"]["startups"]["data"]

    companies = []
    for entry in startups:
        attrs = entry.get("attributes", {})
        name = (attrs.get("name") or "").strip()
        url = (attrs.get("websiteUrl") or "").strip()
        if not name or not url:
            continue
        description = (attrs.get("description") or "").strip() or None
        tags = [
            t.get("attributes", {}).get("name")
            for t in (attrs.get("tags", {}).get("data") or [])
            if t.get("attributes", {}).get("name")
        ]
        companies.append({
            "name": name,
            "url": url,
            "description": description,
            "extra": {"tags": tags, "is_unicorn": attrs.get("isUnicorn")} if tags else None,
        })
    return companies
