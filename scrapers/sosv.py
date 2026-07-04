"""SOSV portfolio scraper (public WordPress REST API).

The portfolio page is rendered client-side, but the underlying `company` post
type is exposed via the standard WP REST API with pagination headers, same
pattern as Sequoia. Real company website/tagline live in ACF fields.
"""
import html
import re

import httpx

URL = "https://sosv.com/wp-json/wp/v2/company"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).strip()
    return text or None


def scrape() -> list[dict]:
    companies, page, total_pages = [], 1, 1
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        while page <= total_pages:
            resp = client.get(URL, params={"per_page": 100, "page": page})
            resp.raise_for_status()
            total_pages = int(resp.headers.get("x-wp-totalpages", "0"))
            for item in resp.json():
                name = html.unescape(item.get("title", {}).get("rendered", "")).strip()
                if not name:
                    continue
                acf = item.get("acf") or {}
                url = (acf.get("website") or "").strip() or item.get("link")
                description = (acf.get("tagline") or "").strip() or None
                if not description:
                    description = _clean(item.get("excerpt", {}).get("rendered"))
                companies.append({
                    "name": name,
                    "url": url,
                    "description": description,
                    "extra": {
                        "slug": item.get("slug"),
                        "total_capital_raised": acf.get("total_capital_raised"),
                    },
                })
            page += 1
    return companies
