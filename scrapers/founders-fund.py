"""Founders Fund portfolio scraper (public WordPress REST API).

The rendered /portfolio/ page and per-company /company/<slug>/ pages both
share one client-side-hydrated overlay template that server-renders
identical (always "SpaceX") markup regardless of route — so scraping the
HTML directly returns the wrong company for every entry. The underlying
`company` custom post type is exposed via the standard WP REST API instead,
with real per-company `content` (description) and a `profiles` field
containing the "Website" link HTML. Some website hrefs have a template bug
producing a broken scheme (e.g. "http:///www.spacex.com/"), normalized here.
"""
import html
import re

import httpx
from bs4 import BeautifulSoup

URL = "https://foundersfund.com/wp-json/wp/v2/company"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _fix_scheme(url: str) -> str:
    return re.sub(r"^(https?:)/+", r"\1//", url.strip())


def scrape() -> list[dict]:
    companies, page, total_pages = [], 1, 1
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        while page <= total_pages:
            resp = client.get(URL, params={"per_page": 100, "page": page})
            resp.raise_for_status()
            total_pages = int(resp.headers.get("x-wp-totalpages", "0"))
            for item in resp.json():
                name = html.unescape(item["title"]["rendered"]).strip()
                if not name:
                    continue

                website = None
                profiles_html = item.get("profiles") or ""
                soup = BeautifulSoup(profiles_html, "html.parser")
                for a in soup.find_all("a"):
                    if a.get_text(strip=True) == "Website" and a.get("href"):
                        website = _fix_scheme(a["href"])
                        break

                desc_soup = BeautifulSoup(item.get("content", {}).get("rendered", ""), "html.parser")
                description = desc_soup.get_text(strip=True) or None

                industry = item.get("industry")
                companies.append({
                    "name": name,
                    "url": website or item.get("link") or URL,
                    "description": description,
                    "extra": {"slug": item.get("slug"), "industry": html.unescape(industry) if industry else None},
                })
            page += 1
    return companies
