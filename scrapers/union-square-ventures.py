"""Union Square Ventures portfolio scraper (Next.js RSC payload on /portfolio).

In September 2026 usv.com moved from WordPress/Pantheon to a Next.js App Router
site on Railway behind Cloudflare, with content in Sanity. /companies/ now
redirects to /portfolio, which server-renders every company (~260) as a logo
card linking to a USV profile page; the name only appears in the logo's alt
text and there is no website link or description in the markup. The page's
server component hands the full company list to the client-side grid as a
`companies` prop, which arrives inline in the React Server Components stream
(`self.__next_f.push([1, "..."])` scripts). The chunks are decoded and joined
and that JSON array is read directly, so the scraper sees exactly what the
page shows (name, websites, description, stage) without depending on
Tailwind class names. Sanity's public GROQ API serves the same documents, but
it would bypass any filtering the site applies and has no profile URLs.

URL choice keeps diffing stable against rows stored from the WordPress site:
`legacyUrl` is the old WordPress `url` field carried over in the migration and
matches the previously scraped href for almost every company, whereas the new
`website` field often differs (acquirers, rebrands). New additions have only
`website`. Companies with neither fall back to their USV profile page, taken
from the card whose DOM id is the record's Sanity `_id`.

Cloudflare serves plain httpx fine, so the TLS cipher workaround that the old
Pantheon WAF required is gone.
"""
import json
import re

import httpx
from bs4 import BeautifulSoup

URL = "https://www.usv.com/portfolio"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
FLIGHT_CHUNK = re.compile(r"self\.__next_f\.push\((\[1,.*?\])\)</script>", re.S)
COMPANIES_KEY = '"companies":'


def _flight_stream(page: str) -> str:
    return "".join(json.loads(m.group(1))[1] for m in FLIGHT_CHUNK.finditer(page))


def _records(stream: str) -> list[dict]:
    start = stream.find(COMPANIES_KEY + '[{"_id"')
    if start < 0:
        raise RuntimeError("companies array not found in /portfolio RSC payload")
    records, _ = json.JSONDecoder().raw_decode(stream, start + len(COMPANIES_KEY))
    return records


def _profile_paths(page: str) -> dict[str, str]:
    soup = BeautifulSoup(page, "html.parser")
    return {a["id"]: a["href"] for a in soup.select('a[id][href^="/portfolio/company/"]')}


def _text(value) -> str | None:
    """Undo RSC string encoding: "$undefined" means null and a literal leading "$" arrives as "$$"."""
    if not isinstance(value, str) or value == "$undefined":
        return None
    if value.startswith("$$"):
        value = value[1:]
    return value.strip() or None


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
    page = resp.text
    profiles = _profile_paths(page)

    companies = []
    for r in _records(_flight_stream(page)):
        name = _text(r.get("name"))
        if not name:
            continue
        website = _text(r.get("website"))
        url = _text(r.get("legacyUrl")) or website
        if not url:
            path = profiles.get(r.get("_id")) or "/portfolio/company/" + re.sub(r"[^a-z0-9]", "", name.lower())
            url = str(httpx.URL(URL).join(path))
        companies.append({
            "name": name,
            "url": url,
            "description": _text(r.get("description")),
            "extra": {
                "stage": _text(r.get("currentStage")),
                "round": _text(r.get("investmentRound")),
                "year": r.get("investmentYear"),
                "status": _text(r.get("statusNote")),
                "website": website,
            },
        })
    return companies
