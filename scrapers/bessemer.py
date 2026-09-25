"""Bessemer Venture Partners portfolio scraper (public Sanity CMS API).

In September 2026 bvp.com moved from WordPress to a Next.js app on Netlify
backed by Sanity (project 2e9xvz8g, dataset production). The old /companies
page and the /companies/<slug> profiles are gone (500 / 404); the portfolio
now lives at /portfolio with profiles at /portfolio/<slug>.

/portfolio server-renders every company into its RSC payload, but only the
fields its grid needs (name, slug, logo, sectors) -- the website and
description appear only on each profile page, which would mean ~530 extra
requests. The same `company` documents are world-readable through Sanity's
GROQ HTTP API, so one query returns every field the site renders. The
/portfolio page shows exactly the full `company` set, so no filter is needed.

URLs keep the previous scraper's convention: the company's own website
(the profile's "Visit Website" link, stored as `website`), falling back to
its BVP profile page. The site itself lists one company twice (two documents
with the same name), so names are de-duplicated.
"""
import httpx

PROJECT_ID = "2e9xvz8g"
DATASET = "production"
API_VERSION = "2025-02-19"
BASE_URL = f"https://{PROJECT_ID}.apicdn.sanity.io/v{API_VERSION}/data/query/{DATASET}"
PROFILE_URL = "https://www.bvp.com/portfolio/{slug}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
QUERY = (
    '*[_type == "company" && defined(name)] | order(name asc) {'
    'name, "slug": slug.current, website, shortDescription, status, '
    'partneredYear, "sectors": sectors[]->label'
    '}'
)


def _website(raw: str | None) -> str | None:
    url = (raw or "").strip()
    if not url:
        return None
    return url if url.lower().startswith(("http://", "https://")) else f"https://{url}"


def scrape() -> list[dict]:
    params = {"query": QUERY, "perspective": "published"}
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
    records = resp.json()["result"]
    if not records:
        raise RuntimeError("Sanity returned no company documents")

    companies, seen = [], set()
    for r in records:
        name = (r.get("name") or "").strip()
        slug = r.get("slug")
        if not name or not slug or name.lower() in seen:
            continue
        seen.add(name.lower())
        profile_url = PROFILE_URL.format(slug=slug)
        companies.append({
            "name": name,
            "url": _website(r.get("website")) or profile_url,
            "description": (r.get("shortDescription") or "").strip() or None,
            "extra": {
                "bvp_profile_url": profile_url,
                "status": r.get("status"),
                "partnered_year": r.get("partneredYear"),
                "sectors": [s for s in r.get("sectors") or [] if s],
            },
        })
    return companies
