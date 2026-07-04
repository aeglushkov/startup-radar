"""Notable Capital companies scraper (Webflow site, Finsweet CMS-load tabs).

The /companies page renders company cards inside several category tabs
(Featured, All, AI, Cybersecurity, ...); Webflow server-renders every tab
pane's first page into the static HTML (inactive tabs are only CSS-hidden),
so a plain GET already yields a broad, de-duplicated set of companies with
name/website/description. Further pages within a tab ("Load More") are
fetched client-side via Finsweet and are not reachable without JS, so this
scraper is capped at what ships in the initial HTML.
"""
import httpx
from bs4 import BeautifulSoup

URL = "https://www.notablecap.com/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    seen: dict[str, dict] = {}
    for anchor in soup.select("a.c-logo_list_wrap"):
        href = (anchor.get("href") or "").strip()
        img = anchor.find("img")
        name = (img.get("alt") or "").strip() if img else ""
        if not name or not href or href == "#" or name in seen:
            continue
        description = None
        box = anchor.find_parent("div", class_="c-logo-box")
        if box:
            p = box.select_one('p[fs-cmsfilter-field="description"]')
            if p:
                description = p.get_text(strip=True) or None
        seen[name] = {"name": name, "url": href, "description": description, "extra": None}

    return list(seen.values())
