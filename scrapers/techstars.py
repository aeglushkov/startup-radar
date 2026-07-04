"""Techstars portfolio scraper (public Typesense search index).

The /portfolio page (a Next.js catch-all route) embeds its Typesense search
credentials in `__NEXT_DATA__.runtimeConfig` (TYPESENSE_SEARCH_URL /
TYPESENSE_SEARCH_TOKEN) — a public, search-scoped key used by the client-side
company directory widget. Querying the `companies` collection directly
returns the full ~5,600-company network (accelerator + fund portfolio),
far more than what ever paints in the page's initial HTML.
"""
import httpx

SEARCH_URL = "https://8gbms7c94riane0lp-1.a1.typesense.net/collections/companies/documents/search"
SEARCH_TOKEN = "0QKFSu4mIDX9UalfCNQN4qjg2xmukDE0"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "X-TYPESENSE-API-KEY": SEARCH_TOKEN,
}
PER_PAGE = 250


def _normalize_url(website: str) -> str:
    website = website.strip()
    if not website:
        return ""
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website


def scrape() -> list[dict]:
    companies = []
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        page, found = 1, None
        while found is None or len(companies) < found:
            resp = client.get(SEARCH_URL, params={
                "q": "*",
                "query_by": "company_name",
                "per_page": PER_PAGE,
                "page": page,
            })
            resp.raise_for_status()
            data = resp.json()
            found = data.get("found", 0)
            hits = data.get("hits", [])
            if not hits:
                break
            for hit in hits:
                doc = hit.get("document", {})
                name = (doc.get("company_name") or "").strip()
                url = _normalize_url(doc.get("website") or "")
                if not name or not url:
                    continue
                companies.append({
                    "name": name,
                    "url": url,
                    "description": None,
                    "extra": {
                        "industry_vertical": doc.get("industry_vertical"),
                        "program_names": doc.get("program_names"),
                        "is_exit": doc.get("is_exit"),
                    },
                })
            page += 1
    return companies
