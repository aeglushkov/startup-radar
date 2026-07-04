"""Redpoint portfolio scraper (Gatsby page-data JSON, Sanity-backed).

The /companies/ page is a Gatsby site; its build-time GraphQL query result is
published as a static JSON file at /page-data/companies/page-data.json,
containing the full companies list (~230 records, no pagination needed) with
title, external link, and a rich-text excerpt.
"""
import httpx

URL = "https://www.redpoint.com/page-data/companies/page-data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _plain_text(blocks) -> str | None:
    if not blocks:
        return None
    parts = []
    for block in blocks:
        for child in block.get("children", []):
            text = child.get("text")
            if text:
                parts.append(text)
    text = " ".join(parts).strip()
    return text or None


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        data = resp.json()

    edges = data["result"]["data"]["companies"]["edges"]
    companies = []
    for edge in edges:
        node = edge["node"]
        name = (node.get("title") or "").strip()
        slug = (node.get("slug") or {}).get("current")
        url = (node.get("link") or "").strip() or (
            f"https://www.redpoint.com/companies/{slug}/" if slug else None
        )
        if not name or not url:
            continue
        companies.append({
            "name": name,
            "url": url,
            "description": _plain_text(node.get("_rawExcerpt")),
            "extra": {"stage": [s.get("title") for s in (node.get("stage") or [])]},
        })
    return companies
