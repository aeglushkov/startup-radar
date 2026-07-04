"""Felicis portfolio scraper.

The /companies page embeds the full portfolio as a schema.org CollectionPage
JSON-LD block (<script type="application/ld+json">, the second such script on
the page) — an ItemList of Organization records with name/url/description.
No pagination needed; all ~274 companies are in the one list.
"""
import json
import re

import httpx

URL = "https://www.felicis.com/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        text = resp.text

    scripts = re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S
    )
    item_list = None
    for raw in scripts:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        main_entity = data.get("mainEntity") if isinstance(data, dict) else None
        if isinstance(main_entity, dict) and main_entity.get("@type") == "ItemList":
            item_list = main_entity
            break
    if item_list is None:
        raise RuntimeError("portfolio ItemList JSON-LD block not found")

    companies = []
    for entry in item_list.get("itemListElement", []):
        item = entry.get("item") or {}
        name = (item.get("name") or "").strip()
        url = (item.get("url") or "").strip()
        if not name or not url:
            continue
        description = (item.get("description") or "").strip() or None
        founders = [f.get("name") for f in item.get("founder", []) if f.get("name")]
        companies.append({
            "name": name,
            "url": url,
            "description": description,
            "extra": {"founders": founders} if founders else None,
        })
    return companies
