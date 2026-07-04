"""Spark Capital companies scraper (Webflow CMS, server-rendered).

The /companies page renders every company as a Webflow collection-list item
in one static HTML response (modal card with name/description/website link
plus a visible logo tile) — no pagination, no JS execution needed.

Each company's modal fragment is repeated once per category tab it belongs
to (e.g. "Anthropic" appears 4 times, once under each tag it carries), all
with identical name/description/website. A previous regex-based version
extracted names/descriptions/urls as three flat, page-wide lists and zipped
them positionally; that broke down whenever the counts drifted, silently
pairing companies with the wrong website. We instead scope extraction to
each individual collection-item element (so a name is always paired with
the url that's actually inside its own card) and dedupe on name, since the
repeats are exact duplicates, not distinct companies.
"""
import httpx
from bs4 import BeautifulSoup

URL = "https://www.sparkcapital.com/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    seen_names = set()
    companies = []
    for item in soup.select("div.collection-item.w-dyn-item"):
        h3 = item.select_one("h3.h3")
        name = h3.get_text(strip=True) if h3 else None
        if not name:
            continue

        link = item.select_one("div.website-link a.company-link")
        url = link.get("href", "").strip() if link else ""
        if not url or url == "#":
            continue  # no website of its own — skip rather than mis-pair

        if name in seen_names:
            continue  # same company repeated under another category tab
        seen_names.add(name)

        desc_el = item.select_one("div.company-specs")
        description = desc_el.get_text(strip=True) if desc_el else None

        companies.append({
            "name": name,
            "url": url,
            "description": description or None,
            "extra": None,
        })
    return companies
