"""Point Nine portfolio scraper.

The /companies page is a Webflow CMS collection list paginated by a Finsweet
"Load More" widget. Each page is plain server-rendered HTML reachable via the
query param `?<key>_page=N` (key discovered from the pagination widget's own
"Next Page" link); the widget reports the total page count directly.
"""
import re

import httpx
from bs4 import BeautifulSoup

URL = "https://www.pointnine.com/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _parse_page(html: str) -> tuple[list[dict], str | None, int]:
    soup = BeautifulSoup(html, "html.parser")
    companies = []
    for item in soup.select(".cms_ci.is-companies"):
        link = item.select_one("a.company_card-inline")
        name_el = item.select_one("[sort=name]")
        if not link or not name_el:
            continue
        name = name_el.get_text(strip=True)
        url = (link.get("href") or "").strip()
        if not name or not url:
            continue
        desc_el = item.select_one('p[tooltip="paragraph"]')
        description = desc_el.get_text(strip=True) if desc_el else None
        companies.append({"name": name, "url": url, "description": description, "extra": None})

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
