"""Startup Wise Guys portfolio scraper.

The /portfolio/ page server-renders every company as a `.portfolio-item` div
with a `data-details` attribute holding the full record (title, description,
country, status, and a links array including the company website) as
HTML-escaped JSON — sourced from an Airtable base but fully inlined, no
pagination needed.
"""
import json

import httpx
from bs4 import BeautifulSoup

URL = "https://startupwiseguys.com/portfolio/"
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
    for item in soup.select(".portfolio-item"):
        raw = item.get("data-details")
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = (d.get("title") or "").strip()
        if not name:
            continue

        website = None
        for link in d.get("links", []):
            if link.get("title") == "Website" and (link.get("value") or "").strip():
                website = link["value"].strip()
                break

        description = BeautifulSoup(d.get("description") or "", "html.parser").get_text(strip=True) or None

        info = {i.get("slug"): i.get("value") for i in d.get("info-items", []) if i.get("slug")}
        country_html = info.get("country") or ""
        country = BeautifulSoup(country_html, "html.parser").get_text(strip=True) or None

        companies.append({
            "name": name,
            "url": website or URL,
            "description": description,
            "extra": {
                "status": info.get("status") or None,
                "country": country,
                "batch": d.get("batch") or None,
            },
        })
    return companies
