"""Index Ventures companies scraper (server-rendered HTML list, single page).

The /companies/ page renders every portfolio company as a `<li class="js-company">`
list item (used by a client-side JS filter over data-backed/-regions/-sectors
attributes), with no pagination — all ~300 companies are present in one
response. Only the firm's profile link is available here (no direct company
website), matching Index's own site.
"""
import html

import httpx
from bs4 import BeautifulSoup

URL = "https://www.indexventures.com/companies/"
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
    for item in soup.select("li.js-company"):
        link = item.find("a")
        if not link or not link.get("href"):
            continue
        name = html.unescape(link.get_text(" ", strip=True))
        # strip trailing "NASDAQ: DIBS"-style ticker badges appended to the name
        ticker = link.find("span", class_="ticker-symbol")
        if ticker:
            name = name.replace(ticker.get_text(strip=True), "").strip()
        if not name:
            continue
        url = str(httpx.URL(URL).join(link["href"]))
        companies.append({
            "name": name,
            "url": url,
            "description": None,
            "extra": None,
        })
    return companies
