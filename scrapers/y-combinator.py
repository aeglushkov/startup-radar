"""Y Combinator company directory scraper (public Algolia index).

ycombinator.com/companies is an Inertia/React page that queries Algolia from the
browser. The search credentials are inlined in a script tag as
`window.AlgoliaOpts = {"app": ..., "key": ...}`. The key is a secured,
search-only key (HMAC + `restrictIndices=YCCompany_production,
YCCompany_By_Launch_Date_production&tagFilters=["ycdc_public"]`) derived from a
parent key that YC rotates; a hardcoded copy went 403 in September 2026. So the
credentials are read from the live page on every run instead of being pinned.

The directory component builds its index names as `YCCompany_<env>` (default)
and `YCCompany_By_Launch_Date_<env>` (the "Launch Date" sort), with env
"production". Algolia caps paginated results at 1000 hits, so we query the
launch-date index: newest companies come first and new batches are never cut
off by the cap. ~1000 records per run is therefore expected, not a regression.
"""
import json
import re

import httpx

DIRECTORY_URL = "https://www.ycombinator.com/companies"
INDEX = "YCCompany_By_Launch_Date_production"
PROFILE_URL = "https://www.ycombinator.com/companies/{slug}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}

_OPTS_RE = re.compile(r"window\.AlgoliaOpts\s*=\s*(\{.*?\})\s*;", re.S)


def parse_algolia_opts(page: str) -> tuple[str, str]:
    match = _OPTS_RE.search(page)
    if not match:
        raise RuntimeError(
            f"window.AlgoliaOpts not found on {DIRECTORY_URL}; YC changed how the "
            "page embeds its Algolia credentials")
    try:
        opts = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"window.AlgoliaOpts on {DIRECTORY_URL} is not valid JSON: {e}")
    app, key = opts.get("app"), opts.get("key")
    if not app or not key:
        raise RuntimeError(f"window.AlgoliaOpts on {DIRECTORY_URL} lacks app/key: {sorted(opts)}")
    return app, key


def _to_company(hit: dict) -> dict:
    website = (hit.get("website") or "").strip()
    return {
        "name": hit["name"],
        "url": website or PROFILE_URL.format(slug=hit["slug"]),
        "description": hit.get("one_liner"),
        "extra": {"batch": hit.get("batch")},
    }


def scrape() -> list[dict]:
    companies, page, nb_pages = [], 0, 1
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(DIRECTORY_URL)
        resp.raise_for_status()
        app, key = parse_algolia_opts(resp.text)
        url = f"https://{app.lower()}-dsn.algolia.net/1/indexes/{INDEX}/query"
        algolia_headers = {"x-algolia-application-id": app, "x-algolia-api-key": key}
        while page < nb_pages:
            resp = client.post(url, headers=algolia_headers,
                               json={"params": f"hitsPerPage=1000&page={page}"})
            if resp.status_code in (403, 404):
                raise RuntimeError(
                    f"Algolia {resp.status_code} for index {INDEX} with the key from "
                    f"{DIRECTORY_URL}: {resp.text[:200]} (index renamed or key restrictions changed?)")
            resp.raise_for_status()
            data = resp.json()
            nb_pages = data.get("nbPages", 0)
            companies.extend(_to_company(hit) for hit in data.get("hits", []))
            page += 1
    return companies
