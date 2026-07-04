"""Cherry Ventures portfolio scraper.

The /founders page server-renders a Webflow CMS list of all current portfolio
companies (name + description) as `a.founders-list_item` elements linking to
per-company profile pages under /founder-companies/<slug>. The index page
doesn't carry the external company website, so each profile page is fetched
(concurrently) to pull the "text-style-link" out-link; if a profile has no
external link, the profile page URL itself is used as a fallback.
"""
import asyncio

import httpx
from bs4 import BeautifulSoup

BASE = "https://cherry.vc"
LIST_URL = f"{BASE}/founders"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
CONCURRENCY = 10


async def _fetch_website(client: httpx.AsyncClient, path: str) -> str | None:
    try:
        resp = await client.get(f"{BASE}{path}")
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    link = soup.select_one("a.text-style-link")
    href = link.get("href") if link else None
    return href if href and href.startswith("http") else None


async def _scrape_async() -> list[dict]:
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = await client.get(LIST_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen: dict[str, dict] = {}
        for item in soup.select("a.founders-list_item"):
            href = item.get("href") or ""
            if not href or href in seen:
                continue
            name_el = item.select_one("h3")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue
            desc_el = item.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else None
            seen[href] = {"name": name, "description": description or None}

        sem = asyncio.Semaphore(CONCURRENCY)

        async def resolve(path: str) -> str | None:
            async with sem:
                return await _fetch_website(client, path)

        paths = list(seen.keys())
        websites = await asyncio.gather(*(resolve(p) for p in paths))

    companies = []
    for path, website in zip(paths, websites):
        info = seen[path]
        profile_url = f"{BASE}{path}"
        companies.append({
            "name": info["name"],
            "url": website or profile_url,
            "description": info["description"],
            "extra": {"profile_url": profile_url},
        })
    return companies


def scrape() -> list[dict]:
    return asyncio.run(_scrape_async())
