"""Earlybird portfolio scraper.

The site is built with Framer. The /companies grid server-renders every
portfolio card (name, status, stage, location) with a link to an internal
`/companies/<slug>` profile page, but the external company website and the
long description only live on that profile page, so each is fetched
(concurrently) after the index page gives us the full company list.
"""
import asyncio

import httpx
from bs4 import BeautifulSoup

BASE = "https://earlybird.com"
LIST_URL = f"{BASE}/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
CONCURRENCY = 12
NAV_LABELS = {"ABOUT US", "PORTFOLIO", "APPROACH", "PERSPECTIVES", "JOBS"}
EXCLUDE_HOST_HINTS = ("earlybird", "linkedin", "twitter", "x.com", "framerusercontent")


def _abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE + "/" + href.lstrip("./")


async def _fetch_detail(client: httpx.AsyncClient, path: str) -> tuple[str | None, str | None]:
    """Returns (website_url, description) scraped from a company profile page."""
    try:
        resp = await client.get(path)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None, None
    soup = BeautifulSoup(resp.text, "html.parser")

    website = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and not any(h in href for h in EXCLUDE_HOST_HINTS):
            website = href
            break

    description = None
    name_h1 = None
    for h1 in soup.find_all("h1"):
        text = h1.get_text(strip=True)
        if text and text.upper() not in NAV_LABELS:
            name_h1 = h1
            break
    if name_h1 is not None:
        ancestor = name_h1
        for _ in range(2):
            if ancestor.find_parent() is None:
                break
            ancestor = ancestor.find_parent()
        block_text = ancestor.get_text(" ", strip=True)
        name_text = name_h1.get_text(strip=True)
        if block_text.startswith(name_text):
            rest = block_text[len(name_text):].strip()
            description = rest or None

    return website, description


async def _scrape_async() -> list[dict]:
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(LIST_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen: dict[str, dict] = {}
        for link in soup.select('a[href*="/companies/"]'):
            href = link.get("href") or ""
            if not href or href in seen:
                continue
            logo = link.find(attrs={"data-framer-name": "Logo"})
            name = logo.get_text(strip=True) if logo else ""
            if not name:
                continue
            extra = {}
            for field in ("Status", "Stage", "Location"):
                el = link.find(attrs={"data-framer-name": field})
                if el:
                    text = el.get_text(strip=True)
                    if text:
                        extra[field.lower()] = text
            seen[href] = {"name": name, "extra": extra or None}

        sem = asyncio.Semaphore(CONCURRENCY)

        async def resolve(path: str):
            async with sem:
                return await _fetch_detail(client, _abs_url(path))

        paths = list(seen.keys())
        details = await asyncio.gather(*(resolve(p) for p in paths))

    companies = []
    for path, (website, description) in zip(paths, details):
        info = seen[path]
        profile_url = _abs_url(path)
        companies.append({
            "name": info["name"],
            "url": website or profile_url,
            "description": description,
            "extra": info["extra"],
        })
    return companies


def scrape() -> list[dict]:
    return asyncio.run(_scrape_async())
