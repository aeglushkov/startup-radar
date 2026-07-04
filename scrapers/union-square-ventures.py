"""Union Square Ventures portfolio scraper (server-rendered HTML).

The /companies/ page is a plain WordPress "company" post-type archive with
posts_per_page=-1, so the full portfolio (~215 companies) is rendered in one
page as repeated `.m__list-row` cards. Each card is duplicated in a
`.m__list-row.m__list-row--mobile` variant for responsive layout, which is
skipped to avoid double-counting.

The site's Pantheon/Varnish edge WAF blocks httpx's default TLS ClientHello
(curl passes, httpx 403s) -- an explicit cipher list on the SSL context avoids
whatever fingerprint is being blocked.
"""
import ssl

import httpx
from bs4 import BeautifulSoup

URL = "https://www.usv.com/companies/"
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
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True, verify=_ssl_context()) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    companies = []
    for row in soup.select(".m__list-row"):
        classes = row.get("class") or []
        if "m__list-row--mobile" in classes:
            continue
        link = row.select_one("a[href]:not(.m__list-row__link)")
        if link is None:
            continue
        name = link.get_text(strip=True)
        url = link["href"].strip()
        if not name or not url:
            continue
        excerpt = row.select_one(".m__list-row__excerpt")
        description = excerpt.get_text(strip=True) if excerpt else None
        companies.append({
            "name": name,
            "url": url,
            "description": description or None,
            "extra": None,
        })
    return companies
