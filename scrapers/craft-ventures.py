"""Craft Ventures portfolio scraper (server-rendered Webflow CMS grid).

The /portfolio page renders `.portfolio-card` items server-side (40 per
page) and uses Finsweet CMS Load (infinite mode) for further pages via a
`?<listId>_page=N` query param exposed on the "Next" pagination link.
"""
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.craftventures.com/portfolio"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _description(card) -> str | None:
    for p in card.select("p.text-size-tiny"):
        classes = p.get("class") or []
        if classes == ["text-size-tiny"]:
            text = p.get_text(strip=True)
            if text:
                return text
    return None


def scrape() -> list[dict]:
    companies, seen = [], set()
    url = BASE_URL
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        while url:
            resp = client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for card in soup.select(".portfolio-card"):
                name_el = card.select_one(".portfolio-name-holder")
                link_el = card.select_one("a.card-link-block")
                if name_el is None or link_el is None:
                    continue
                name = name_el.get_text(strip=True)
                website = (link_el.get("href") or "").strip()
                if not name or not website or name in seen:
                    continue
                seen.add(name)
                companies.append({
                    "name": name,
                    "url": website,
                    "description": _description(card),
                    "extra": None,
                })

            next_link = soup.select_one(".w-pagination-next")
            href = next_link.get("href") if next_link else None
            url = httpx.URL(BASE_URL).join(href) if href else None
    return companies
