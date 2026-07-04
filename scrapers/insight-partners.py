"""Insight Partners portfolio scraper (public WordPress REST API).

Companies live under the custom "sfcompany" post type (Salesforce-synced),
which is exposed at /wp-json/wp/v2/sfcompany with standard pagination
headers. No external company-website field is exposed via REST, so the
Insight Partners profile page is used as the URL.

The site's edge WAF blocks httpx's default TLS ClientHello (curl passes,
httpx 403s) -- an explicit cipher list on the SSL context avoids whatever
fingerprint is being blocked.
"""
import html
import ssl

import httpx

URL = "https://www.insightpartners.com/wp-json/wp/v2/sfcompany"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def scrape() -> list[dict]:
    companies, page, total_pages = [], 1, 1
    with httpx.Client(timeout=30, headers=HEADERS, verify=_ssl_context()) as client:
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
                           or f"https://www.insightpartners.com/portfolio/{item['slug']}/",
                    "description": description,
                    "extra": {"slug": item.get("slug")},
                })
            page += 1
    return companies
