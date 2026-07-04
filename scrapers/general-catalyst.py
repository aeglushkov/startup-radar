"""General Catalyst portfolio scraper (public Algolia index).

The portfolio page (Webflow) loads a site-search widget whose Algolia
credentials are public search-only keys shipped in a Slater-hosted JS bundle
(https://assets.slater.app/slater/20127/60751.js). The underlying "gc_primary"
index mixes several content types (Portfolio, Stories, Investors, News,
Pages); filtering on type:Portfolio isolates the ~580 portfolio companies.
"""
import httpx

APP_ID = "ID4635ZLKJ"
API_KEY = "871677f0423646c1278b67120f5adcc0"
INDEX_NAME = "gc_primary"
URL = f"https://{APP_ID.lower()}-dsn.algolia.net/1/indexes/{INDEX_NAME}/query"
HEADERS = {
    "x-algolia-application-id": APP_ID,
    "x-algolia-api-key": API_KEY,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    companies, page, nb_pages = [], 0, 1
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        while page < nb_pages:
            resp = client.post(
                URL,
                json={"params": f"hitsPerPage=100&page={page}&filters=type:Portfolio"},
            )
            resp.raise_for_status()
            data = resp.json()
            nb_pages = data.get("nbPages", 0)
            for hit in data.get("hits", []):
                name = (hit.get("name") or "").strip()
                slug = hit.get("slug")
                website = (hit.get("website") or "").strip()
                url = website or (f"https://www.generalcatalyst.com/{slug}" if slug else None)
                if not name or not url:
                    continue
                description = (hit.get("description") or "").strip() or None
                companies.append({
                    "name": name,
                    "url": url,
                    "description": description,
                    "extra": {
                        "sectors": hit.get("sectors"),
                        "gc_backed_since": hit.get("gc-backed-since"),
                    },
                })
            page += 1
    return companies
