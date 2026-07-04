"""Sequoia Capital portfolio scraper (public WordPress REST API).

The portfolio page is FacetWP-rendered, but the underlying `company` post type
is exposed via the standard WP REST API with pagination headers. The site
returns an empty body to non-browser User-Agents, hence the header.
"""
import html

import httpx

URL = "https://sequoiacap.com/wp-json/wp/v2/company"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


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
                companies.append({
                    "name": name,
                    "url": item.get("link")
                           or f"https://sequoiacap.com/companies/{item['slug']}/",
                    "description": None,  # profile page text is picked up by enrichment
                    "extra": {"slug": item.get("slug")},
                })
            page += 1
    return companies
