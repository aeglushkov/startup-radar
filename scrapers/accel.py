"""Accel portfolio scraper (public Sanity CMS API).

/relationships is a Next.js app backed by Sanity. The page inlines a
"projectId"/"dataset" pair (458oembh / production) for a public dataset, so
the full `company` document set can be queried directly via Sanity's GROQ
HTTP API instead of scraping the rendered carousel (which only shows a
featured subset). `shortDescription` is Portable Text, flattened with the
built-in `pt::text()` GROQ function.
"""
import urllib.parse

import httpx

PROJECT_ID = "458oembh"
DATASET = "production"
API_VERSION = "2025-10-30"
BASE_URL = f"https://{PROJECT_ID}.api.sanity.io/v{API_VERSION}/data/query/{DATASET}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
QUERY = (
    '*[_type=="company"]{'
    'name, "slug": slug.current, websiteUrl, '
    '"description": pt::text(shortDescription)'
    '}'
)


def scrape() -> list[dict]:
    params = {"query": QUERY}
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
    records = resp.json().get("result", [])

    companies = []
    for r in records:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        slug = r.get("slug")
        website = (r.get("websiteUrl") or "").strip()
        url = website or (f"https://www.accel.com/relationships/{slug}" if slug else None)
        if not url:
            continue
        companies.append({
            "name": name,
            "url": url,
            "description": (r.get("description") or "").strip() or None,
            "extra": {"slug": slug},
        })
    return companies
