"""Greylock Partners portfolio scraper.

The /companies/ URL (a common guess) 301s to a Consider.com jobs board, not
the portfolio — the real portfolio lives at /portfolio/. It's plain
server-rendered WordPress HTML: every company has a `div.portfolio-modal-box`
with a description, a website link (identified by the generic "icon link"
globe icon, distinguishing it from the Twitter/LinkedIn social links), and a
logo `<img alt="...">` that yields the display name once the trailing
"Logo"/color-variant suffix is stripped.
"""
import re

import httpx
from bs4 import BeautifulSoup

URL = "https://greylock.com/portfolio/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
SKIP_IDS = {"newsletter_modal_new"}


def _clean_name(alt: str | None, company_id: str) -> str:
    name = re.sub(r"\s*logo.*$", "", alt, flags=re.I).strip() if alt else ""
    if not name:
        name = company_id.replace("-", " ").title()
    if name.islower():
        name = name.title()
    return name


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    companies = []
    for modal in soup.select("div.portfolio-modal-box"):
        company_id = modal.get("id") or ""
        if company_id in SKIP_IDS:
            continue

        img = modal.select_one("div.logo-box img")
        name = _clean_name(img.get("alt") if img else None, company_id)
        if not name:
            continue

        website = None
        for a in modal.select("div.social-link a"):
            if a.select_one('img[alt="icon link"]'):
                website = a.get("href")
                break

        p = modal.select_one("div.left-box p.l") or modal.select_one("div.left-box p")
        description = p.get_text(strip=True) or None if p else None

        companies.append({
            "name": name,
            "url": website or f"{URL}#{company_id}",
            "description": description,
            "extra": {"greylock_id": company_id},
        })
    return companies
