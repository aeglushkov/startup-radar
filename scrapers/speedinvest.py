"""Speedinvest portfolio scraper.

The /portfolio page is a Webflow CMS collection list paginated by a Finsweet
"Load More" widget (query param `?<key>_page=N`, total pages reported by the
widget). Each card server-renders the company name, a short one-liner, a
longer rich-text description, sector tags and year invested. The site never
links out to the company's own website from this list (only an internal
"View Full Profile" link back into the same portfolio page), so the profile
URL is used as the company URL.
"""
import re

import httpx
from bs4 import BeautifulSoup

BASE = "https://www.speedinvest.com"
URL = f"{BASE}/portfolio"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _parse_page(html: str) -> tuple[list[dict], str | None, int]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for item in soup.select(".portfolio-list_item"):
        name_el = item.select_one("h6.portfolio-list-title") or item.select_one("h4")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue
        profile_link = item.select_one('a[href^="/portfolio/"]')
        profile_url = BASE + profile_link["href"] if profile_link else None

        desc_el = item.select_one(".portfolio-list_full-descript-rtf")
        description = desc_el.get_text(" ", strip=True) if desc_el else None
        if not description:
            short_el = item.select_one(".portfolio-list_short-descript")
            description = short_el.get_text(strip=True) if short_el else None

        sectors = [t.get_text(strip=True) for t in item.select('[fs-list-field="portfolio"]')
                   if t.get_text(strip=True)]
        year_el = item.select_one(".portfolio-date-company")

        companies.append({
            "name": name,
            "url": profile_url or URL,
            "description": description or None,
            "extra": {
                "sectors": sectors or None,
                "year_invested": year_el.get_text(strip=True) if year_el else None,
            },
        })

    next_link = soup.select_one("a.w-pagination-next")
    pagination_key = None
    if next_link and next_link.get("href"):
        m = re.search(r"([a-f0-9]+)_page=", next_link["href"])
        if m:
            pagination_key = m.group(1)

    total_pages = 1
    page_count_el = soup.select_one(".w-page-count")
    if page_count_el:
        m = re.search(r"(\d+)\s*/\s*(\d+)", page_count_el.get_text())
        if m:
            total_pages = int(m.group(2))

    return companies, pagination_key, total_pages


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        companies, key, total_pages = _parse_page(resp.text)

        page = 2
        while key and page <= total_pages:
            resp = client.get(URL, params={f"{key}_page": page})
            resp.raise_for_status()
            more, _, _ = _parse_page(resp.text)
            if not more:
                break
            companies.extend(more)
            page += 1

    return companies
