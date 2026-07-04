"""Northzone portfolio scraper (Webflow CMS collection list, server-rendered).

The /portfolio page renders the full company collection server-side via
Finsweet CMS filter/pagination attributes (`filters5_company-list-item`).
Webflow caps a rendered collection list at 100 items per page and exposes
extra pages via a `?<hash>_page=N` query var found in the page's own
pagination link, which we reuse. No direct company website is listed, only
Northzone's own portfolio profile page.
"""
import re

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://northzone.com/portfolio"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _parse(html: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for item in soup.select("div.filters5_company-list-item"):
        link = item.select_one("a.filters5_company-link")
        name_el = item.select_one("[fs-cmsfilter-field=name]")
        if not link or not link.get("href") or not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue
        status = item.select_one("[fs-cmsfilter-field=status]")
        stage = item.select_one("[fs-cmsfilter-field=stage]")
        industries = [el.get_text(strip=True) for el in item.select("[fs-cmsfilter-field=industry]")]
        companies.append({
            "name": name,
            "url": str(httpx.URL(BASE_URL).join(link["href"])),
            "description": None,
            "extra": {
                "status": status.get_text(strip=True) if status else None,
                "stage": stage.get_text(strip=True) if stage else None,
                "industries": industries or None,
            },
        })

    next_link = soup.select_one("a.w-pagination-next")
    next_href = next_link["href"] if next_link and next_link.get("href") else None
    return companies, next_href


def scrape() -> list[dict]:
    companies = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(BASE_URL)
        resp.raise_for_status()
        batch, next_href = _parse(resp.text)
        companies.extend(batch)

        seen_pages = {""}
        while next_href:
            match = re.search(r"_page=(\d+)", next_href)
            page_key = match.group(1) if match else next_href
            if page_key in seen_pages:
                break
            seen_pages.add(page_key)

            resp = client.get(str(httpx.URL(BASE_URL).join(next_href)))
            resp.raise_for_status()
            batch, next_href = _parse(resp.text)
            if not batch:
                break
            companies.extend(batch)

    return companies
