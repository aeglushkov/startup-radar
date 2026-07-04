"""Seedcamp portfolio scraper.

The /our-companies/ page server-renders every portfolio company as a
`.company__item` block with a direct external website link, name, investment
year, and a short description — all in one page, no pagination.
"""
import httpx
from bs4 import BeautifulSoup

URL = "https://seedcamp.com/our-companies/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    companies = []
    for item in soup.select(".company__item"):
        link = item.select_one("a.company__item__link")
        name_el = item.select_one(".company__item__name")
        if not link or not name_el:
            continue
        url = (link.get("href") or "").strip()
        name = name_el.get_text(strip=True)
        if not name or not url:
            continue
        desc_el = item.select_one(".company__item__description__content")
        description = desc_el.get_text(strip=True) if desc_el else None
        year_el = item.select_one(".company__item__year")
        companies.append({
            "name": name,
            "url": url,
            "description": description,
            "extra": {"year_invested": year_el.get_text(strip=True) if year_el else None},
        })
    return companies
