"""Bessemer Venture Partners portfolio scraper.

/companies is plain server-rendered WordPress HTML: every company is an
`article.box.investment` element containing both a summary (name, link to
its BVP profile page) and an expandable "details" panel with the
description and a "Visit Website" external link. No API/pagination needed
— all ~500 companies render in the initial page load.

The "Visit Website" link and the roadmap/category links further down the
same details panel (e.g. "/cybersecurity", "/atlas?filter=...") all share
the `cta button white` classes, so a selector that isn't scoped to the
`.ctas` wrapper picks up whichever of them comes first in the DOM — for
companies with no website link, that's a category page, and dozens of
unrelated companies end up sharing e.g. "/cybersecurity" as their url. We
scope the selector to `div.ctas` (where only "Visit Website" ever lives),
resolve any relative href against the site root, and fall back to the
company's own (always-absolute, always-unique) BVP profile url — never to
a category page.
"""
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

URL = "https://www.bvp.com/companies"
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
    for art in soup.select("article.box.investment"):
        name_a = art.select_one("div.company h3.name a")
        name = name_a.get_text(strip=True) if name_a else None
        if not name:
            continue
        profile_url = name_a.get("href")
        if profile_url:
            profile_url = urljoin(URL, profile_url.strip())

        website = art.select_one("div.details div.ctas a.cta.button.white")
        website_url = website.get("href", "").strip() if website else None
        if website_url:
            website_url = urljoin(URL, website_url)

        url = website_url or profile_url
        if not url:
            continue  # no website and no profile link — nothing of its own to key on

        p = art.select_one("div.details div.intro p")
        description = p.get_text(strip=True) if p else None

        companies.append({
            "name": name,
            "url": url,
            "description": description,
            "extra": {"bvp_profile_url": profile_url},
        })
    return companies
