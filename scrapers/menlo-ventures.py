"""Menlo Ventures portfolio scraper (public WordPress REST API).

Companies live under the custom "portfolios" post type, exposed at
/wp-json/wp/v2/portfolios with standard pagination headers. No external
company-website field is exposed via REST, so the Menlo profile page is used
as the URL; the Yoast meta description usually holds a real company blurb.
"""
import html

import httpx

URL = "https://menlovc.com/wp-json/wp/v2/portfolios"
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
                description = (
                    item.get("yoast_head_json", {}).get("og_description") or None
                )
                companies.append({
                    "name": name,
                    "url": item.get("link")
                           or f"https://menlovc.com/portfolio/{item['slug']}/",
                    "description": description,
                    "extra": {"slug": item.get("slug")},
                })
            page += 1
    return companies
