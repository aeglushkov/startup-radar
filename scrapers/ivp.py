"""IVP portfolio scraper (Nuxt 3 site, no public GraphQL host exposed).

The /portfolio page is Nuxt-rendered and inlines its data as a Nuxt
`devalue`-encoded payload, reachable directly as static JSON at
`/portfolio/_payload.json` (no need to render the HTML). That payload's
`paginatedItems` gives every company (name, slug, headline) in one page
(totalPages=1), but not the external website. Each company's own detail
page exposes a `websiteUrl` field via the same payload mechanism at
`/portfolio/<slug>/_payload.json`, so we fan out one small JSON request per
company (~5-10KB each) to fill it in.
"""
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "https://www.ivp.com"
LIST_PAYLOAD_URL = f"{BASE}/portfolio/_payload.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}

# Reactivity/collection tags used by Nuxt's `devalue` payload format that just
# wrap an inner value (or, for Set/Map, a flat run of index references).
_REACTIVE_TAGS = {"ShallowReactive", "Reactive", "Ref", "ShallowRef"}


def _unflatten(values: list):
    """Decode a Nuxt `devalue`-style flattened payload array into plain data."""
    hydrated: dict[int, object] = {}

    def hydrate(index):
        if index in hydrated:
            return hydrated[index]
        value = values[index]
        if value is None or not isinstance(value, (list, dict)):
            hydrated[index] = value
            return value
        if isinstance(value, list):
            if value and isinstance(value[0], str) and value[0] in _REACTIVE_TAGS:
                result = hydrate(value[1])
                hydrated[index] = result
                return result
            if value and value[0] == "Set":
                result = set()
                hydrated[index] = result
                for i in value[1:]:
                    result.add(hydrate(i))
                return result
            if value and value[0] == "Map":
                result = {}
                hydrated[index] = result
                it = iter(value[1:])
                for k, v in zip(it, it):
                    result[hydrate(k)] = hydrate(v)
                return result
            if value and value[0] == "Date":
                result = value[1]
                hydrated[index] = result
                return result
            result = []
            hydrated[index] = result
            for v in value:
                result.append(hydrate(v))
            return result
        result = {}
        hydrated[index] = result
        for k, v in value.items():
            result[k] = hydrate(v)
        return result

    return hydrate(0)


def _fetch_payload(client: httpx.Client, url: str) -> dict:
    resp = client.get(url)
    resp.raise_for_status()
    return _unflatten(resp.json())


def _find_gql_value(data: dict, key_contains: str):
    for k, v in data.items():
        if k.startswith("gql:data:") and isinstance(v, dict) and key_contains in v:
            return v[key_contains]
    return None


def _fetch_website(slug: str) -> tuple[str, str | None]:
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        try:
            root = _fetch_payload(client, f"{BASE}/portfolio/{slug}/_payload.json")
        except httpx.HTTPError:
            return slug, None
    company = _find_gql_value(root.get("data", {}), "company") or {}
    return slug, (company.get("websiteUrl") or "").strip() or None


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        root = _fetch_payload(client, LIST_PAYLOAD_URL)
    paginated = _find_gql_value(root.get("data", {}), "paginatedItems") or {}
    items = paginated.get("items", [])

    slugs = [it.get("slug") for it in items if it.get("slug")]
    websites: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=15) as pool:
        for slug, website in pool.map(_fetch_website, slugs):
            websites[slug] = website

    companies = []
    for item in items:
        name = (item.get("name") or "").strip()
        slug = item.get("slug")
        if not name or not slug:
            continue
        url = websites.get(slug) or f"{BASE}/portfolio/{slug}"
        description = (item.get("headline") or item.get("description") or "").strip() or None
        sectors = [s.get("name") for s in (item.get("sectors") or []) if s.get("name")]
        status = (item.get("status") or {}).get("name")
        companies.append({
            "name": name,
            "url": url,
            "description": description,
            "extra": {"sectors": sectors, "status": status} if (sectors or status) else None,
        })
    return companies
