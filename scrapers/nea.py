"""NEA portfolio scraper.

The /portfolio page only server-renders a small "featured" carousel (~30
companies); the full grid is client-side and no bulk API is exposed. But
every portfolio company has its own server-rendered detail page at
/portfolio/<slug>, and the sitemap lists all of them (~900). We fetch the
sitemap for the full URL list, then fetch each detail page concurrently
(asyncio) and parse name (from <title>, formatted "NEA Portfolio: <name>"),
description, and website link (falls back to the detail page URL if the
company has no live "Website" field, e.g. old/acquired companies).
"""
import asyncio
import re

import httpx
from bs4 import BeautifulSoup

SITEMAP_URL = "https://www.nea.com/sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
CONCURRENCY = 60
TITLE_PREFIX = "NEA Portfolio: "


def _parse_detail(url: str, html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    name = title[len(TITLE_PREFIX):].strip() if title.startswith(TITLE_PREFIX) else title.strip()
    if not name:
        return None

    website = None
    for header in soup.select("div.portfolioDetailPage_headerItem__UPra6"):
        if header.get_text(strip=True) == "Website":
            link = header.find_next_sibling("a")
            if link:
                website = link.get("href")
            break

    desc_p = soup.select_one("div.portfolioDetailPage_content__Hc_AK p")
    description = desc_p.get_text(strip=True) if desc_p else None

    return {
        "name": name,
        "url": website or url,
        "description": description,
        "extra": {"nea_profile_url": url},
    }


async def _fetch_all(urls: list[str]) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)
    companies = []

    async def fetch_one(client: httpx.AsyncClient, url: str):
        async with sem:
            try:
                resp = await client.get(url, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError:
                return None
        return _parse_detail(url, resp.text)

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
    async with httpx.AsyncClient(headers=HEADERS, limits=limits, follow_redirects=True) as client:
        results = await asyncio.gather(*[fetch_one(client, u) for u in urls])
    for r in results:
        if r:
            companies.append(r)
    return companies


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        resp = client.get(SITEMAP_URL)
        resp.raise_for_status()
    urls = sorted(set(re.findall(r"<loc>(https://www\.nea\.com/portfolio/[a-z0-9-]+)</loc>", resp.text)))
    return asyncio.run(_fetch_all(urls))
