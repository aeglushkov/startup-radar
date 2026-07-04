"""Y Combinator company directory scraper (public Algolia index)."""
import httpx

APP_ID = "45BWZJ1SGC"
API_KEY = "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJiMWM4ZTU0ZDlhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"  # public search-only key (from browser XHR)
# Launch-date-sorted index: Algolia caps paginated search at 1000 hits, but newest
# companies always appear first here, so new batches are never missed by the cap.
URL = f"https://{APP_ID.lower()}-dsn.algolia.net/1/indexes/YCCompany_By_Launch_Date_production/query"
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
