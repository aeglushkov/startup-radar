"""Alchemist Accelerator portfolio scraper (public JSON:API on vault.alchemistaccelerator.com).

The public portfolio page renders a small curated showcase in static HTML, but
its "load more" grid pulls the full company list from a public JSON:API
backend (no auth required) that the page's own JS calls directly. The API
does not expose each company's real website, only its vault profile slug, so
we link to the public vault profile page instead.
"""
import httpx

URL = "https://vault.alchemistaccelerator.com/api/v1/alchemist_companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}
PARAMS = {
    "include": "aclass",
    "fields[alchemist_classes]": "number",
    "filter[aclass.class_type:eq]": "alchemist",
    "page[size]": 112,
}


def scrape() -> list[dict]:
    companies, page, total = [], 1, None
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        while total is None or len(companies) < total:
            params = dict(PARAMS, **{"page[number]": page})
            resp = client.get(URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            total = data.get("meta", {}).get("results", {}).get("available", 0)
            records = data.get("data", [])
            if not records:
                break
            for rec in records:
                attrs = rec.get("attributes", {})
                meta = rec.get("meta", {})
                name = (attrs.get("name") or "").strip()
                if not name:
                    continue
                slug = meta.get("slug") or attrs.get("source_id")
                url = f"https://vault.alchemistaccelerator.com/companies/public/{slug}" if slug else None
                if not url:
                    continue
                description = (meta.get("oneliner") or meta.get("description") or "").strip()
                if description in ("", "-"):
                    description = None
                companies.append({
                    "name": name,
                    "url": url,
                    "description": description,
                    "extra": {"status": meta.get("status"), "aclass_id": meta.get("aclass_id")},
                })
            page += 1
    return companies
