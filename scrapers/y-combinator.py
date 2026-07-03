"""Y Combinator company directory scraper (public Algolia index)."""
import httpx

APP_ID = "45BWZJ1SGC"
API_KEY = "REPLACE_WITH_PUBLIC_SEARCH_KEY"  # copy x-algolia-api-key from browser XHR
URL = f"https://{APP_ID.lower()}-dsn.algolia.net/1/indexes/YCCompany_production/query"
HEADERS = {"x-algolia-application-id": APP_ID, "x-algolia-api-key": API_KEY}


def scrape() -> list[dict]:
    companies, page, nb_pages = [], 0, 1
    with httpx.Client(timeout=30) as client:
        while page < nb_pages:
            resp = client.post(
                URL, headers=HEADERS,
                json={"params": f"hitsPerPage=1000&page={page}"},
            )
            resp.raise_for_status()
            data = resp.json()
            nb_pages = data.get("nbPages", 0)
            for hit in data.get("hits", []):
                website = (hit.get("website") or "").strip()
                companies.append({
                    "name": hit["name"],
                    "url": website or f"https://www.ycombinator.com/companies/{hit['slug']}",
                    "description": hit.get("one_liner"),
                    "extra": {"batch": hit.get("batch")},
                })
            page += 1
    return companies
