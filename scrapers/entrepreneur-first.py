"""Entrepreneur First portfolio scraper.

The /portfolio/ page loads its company grid via a WordPress admin-ajax
endpoint (`action=loadmore`) driven by the theme's `main.min.js`; passing
`posts_per_page=-1` in the query payload returns every company in one
request. Each tile carries name/description/slug but not the company's own
website — that only appears in the per-company overlay fragment fetched via
`action=getcompany`, so those are fetched concurrently afterwards.

About 20 entries have no "Website" row in that overlay at all (mostly
inactive/older portfolio companies). A previous version fell back to the
shared /portfolio/?company=<slug> listing URL for those, so they all
collapsed onto one URL key on dedupe. We skip companies with no website of
their own instead — same pattern as scrapers/a16z.py.
"""
import asyncio
import json

import httpx
from bs4 import BeautifulSoup

AJAX_URL = "https://www.joinef.com/wp-admin/admin-ajax.php"
PORTFOLIO_URL = "https://www.joinef.com/portfolio/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
QUERY = json.dumps({
    "post_type": "company",
    "post_status": "publish",
    "orderby": "menu_order",
    "order": "ASC",
    "posts_per_page": -1,
})
CONCURRENCY = 15


async def _fetch_website(client: httpx.AsyncClient, slug: str) -> str | None:
    try:
        resp = await client.post(AJAX_URL, data={
            "action": "getcompany", "company": slug, "index": 0, "featured": "false",
        })
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    for row in soup.select(".meta__row"):
        label = row.select_one(".meta__row__name, .meta__row__role")
        if label and label.get_text(strip=True).lower() == "website":
            link = row.select_one(".meta__row__value a[href]")
            if link:
                return link["href"].strip()
    return None


async def _scrape_async() -> list[dict]:
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.post(AJAX_URL, data={"action": "loadmore", "query": QUERY, "page": 1})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        entries = []
        for tile in soup.select(".tile--company"):
            link_el = tile.select_one(".tile__link")
            if not link_el:
                continue
            slug = link_el.get("data-companyslug")
            name = (link_el.get("data-companyname") or link_el.get_text(strip=True)).strip()
            if not slug or not name:
                continue
            desc_el = tile.select_one(".tile__description")
            description = desc_el.get_text(strip=True) if desc_el else None
            entries.append({"slug": slug, "name": name, "description": description})

        sem = asyncio.Semaphore(CONCURRENCY)

        async def resolve(slug: str):
            async with sem:
                return await _fetch_website(client, slug)

        websites = await asyncio.gather(*(resolve(e["slug"]) for e in entries))

    companies = []
    for entry, website in zip(entries, websites):
        if not website:
            continue  # no website of its own — skip rather than fall back
        profile_url = f"{PORTFOLIO_URL}?company={entry['slug']}"
        companies.append({
            "name": entry["name"],
            "url": website,
            "description": entry["description"],
            "extra": {"profile_url": profile_url},
        })
    return companies


def scrape() -> list[dict]:
    return asyncio.run(_scrape_async())
