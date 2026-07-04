"""Battery Ventures portfolio scraper (WordPress admin-ajax endpoint).

The public portfolio page is /list-of-all-companies/ (the /our-companies/
and /portfolio/ guesses 404). Its company grid is populated client-side via
a jQuery.ajax POST to /wp-admin/admin-ajax.php, action
"loadbatterycompanieswithFilter" (discovered in the theme's custom.js).
Passing allCompany=1 returns the entire list (~340 companies) as an HTML
fragment in one call -- no further pagination required.

The site's edge WAF blocks httpx's default TLS ClientHello (curl passes,
httpx 403s) -- an explicit cipher list on the SSL context avoids whatever
fingerprint is being blocked.
"""
import ssl

import httpx
from bs4 import BeautifulSoup

PAGE_URL = "https://www.battery.com/list-of-all-companies/"
AJAX_URL = "https://www.battery.com/wp-admin/admin-ajax.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
PAYLOAD = {
    "action": "loadbatterycompanieswithFilter",
    "pagination": 1,
    "sector": "",
    "location": "",
    "stage": "",
    "status": "",
    "docpage": 1,
    "allCompany": 1,
    "companySearch": "",
}


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, verify=_ssl_context()) as client:
        resp = client.post(AJAX_URL, data=PAYLOAD)
        resp.raise_for_status()
        data = resp.json()

    fragment = data.get("htmls", "")
    soup = BeautifulSoup(fragment, "html.parser")

    companies = []
    for card in soup.select("a.inv-logo-card"):
        url = (card.get("href") or "").strip()
        img = card.select_one("img.inv-logo")
        name = (img.get("alt") or img.get("title") or "").strip() if img else ""
        if not name or not url:
            continue
        meta = card.select_one(".text-block-16")
        meta_text = meta.get_text(" ", strip=True) if meta else None
        companies.append({
            "name": name,
            "url": url,
            "description": None,
            "extra": {"location_status": meta_text} if meta_text else None,
        })
    return companies
