"""NEA portfolio scraper (Next.js RSC payload + Statamic GraphQL for websites).

www.nea.com is a Next.js app (OpenNext behind CloudFront) whose content lives
in a Statamic CMS. The /portfolio page is CDN-cached and its React Server
Components payload (`self.__next_f.push` chunks) embeds the entire grid as one
`allCompanies` array (~920 records: title, short_description,
/portfolio/<slug> url, stage, status); the client-side grid only filters that
array. One request therefore yields every company name.

The company website is only rendered on the per-company detail pages, from
Statamic's `external_url` field. Crawling ~920 detail pages (the previous
approach) was flaky: pages missing from the CloudFront cache are rendered at
the origin against a slow Statamic backend, and at concurrency 60 almost half
of them hung past 30 s, so runs either timed out or silently lost companies.
Instead, websites come from the public Statamic GraphQL endpoint that the
Next.js server itself queries (the payload carries its `__typename`s, e.g.
`Set_FeaturedCategories_CategoryGroup`), fetched as parallel 100-entry pages
sorted by slug because single large queries regularly stall for 60 s+.

Everything runs under one overall deadline with retries on transient errors.
Names never depend on GraphQL: a page that still fails leaves its companies on
the NEA profile url (the same fallback used for companies without a website).
The scrape only fails if the grid cannot be read, GraphQL reports a schema
error, or no GraphQL page succeeds at all.
"""
import asyncio
import json
import random
import re
import time
import urllib.parse

import httpx

SITE_URL = "https://www.nea.com"
PORTFOLIO_URL = f"{SITE_URL}/portfolio"
GRAPHQL_URL = "https://statamic.nea.com/graphql"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
DEADLINE = 75
ATTEMPT_TIMEOUT = 30
ATTEMPTS = 4
PAGE_SIZE = 100
CONCURRENCY = 10
TRANSIENT_STATUS = {429, 500, 502, 503, 504}
RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
ALL_COMPANIES_RE = re.compile(r'"allCompanies":\s*')
WEBSITES_QUERY = """
query ($page: Int!, $limit: Int!) {
  entries(collection: "portfolio", limit: $limit, page: $page, sort: "slug") {
    last_page
    data { slug ... on Entry_Portfolio_Portfolio { external_url } }
  }
}
"""


class TransientError(Exception):
    pass


async def _request(client: httpx.AsyncClient, method: str, url: str,
                   deadline: float, **kwargs) -> httpx.Response:
    error = None
    for attempt in range(ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining < 1:
            break
        try:
            resp = await client.request(method, url, timeout=min(ATTEMPT_TIMEOUT, remaining), **kwargs)
        except httpx.TransportError as e:
            error = repr(e)
            delay = 2 ** attempt
        else:
            if resp.status_code not in TRANSIENT_STATUS:
                resp.raise_for_status()
                return resp
            error = f"HTTP {resp.status_code}"
            retry_after = resp.headers.get("retry-after", "")
            delay = int(retry_after) if retry_after.isdigit() else 2 ** attempt
        await asyncio.sleep(min(delay + random.random(), max(0, deadline - time.monotonic() - 1)))
    raise TransientError(f"{method} {url} failed before deadline: {error}")


def _all_companies(html: str) -> list[dict]:
    payload = "".join(json.loads(f'"{chunk}"') for chunk in RSC_CHUNK_RE.findall(html))
    match = ALL_COMPANIES_RE.search(payload)
    if not match:
        raise RuntimeError("allCompanies array not found in /portfolio RSC payload")
    records, _ = json.JSONDecoder().raw_decode(payload, match.end())
    return [r for r in records if isinstance(r, dict)]


async def _website_page(client: httpx.AsyncClient, page: int,
                        deadline: float) -> tuple[dict[str, str], int] | None:
    body = {"query": WEBSITES_QUERY, "variables": {"page": page, "limit": PAGE_SIZE}}
    try:
        resp = await _request(client, "POST", GRAPHQL_URL, deadline, json=body)
    except TransientError:
        return None
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Statamic GraphQL error: {data['errors']}")
    entries = data["data"]["entries"]
    websites = {
        e["slug"]: e["external_url"].strip()
        for e in entries["data"] if (e.get("external_url") or "").strip()
    }
    return websites, entries["last_page"]


async def _websites(client: httpx.AsyncClient, total: int, deadline: float) -> dict[str, str]:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def fetch(page: int):
        async with sem:
            return await _website_page(client, page, deadline)

    n_pages = -(-total // PAGE_SIZE)
    results = await asyncio.gather(*map(fetch, range(1, n_pages + 1)))
    last_page = max((r[1] for r in results if r), default=n_pages)
    if last_page > n_pages:
        results += await asyncio.gather(*map(fetch, range(n_pages + 1, last_page + 1)))
    if not any(results):
        raise RuntimeError("no Statamic GraphQL page succeeded before the deadline")

    websites = {}
    for r in results:
        if r:
            websites.update(r[0])
    return websites


async def _scrape() -> list[dict]:
    deadline = time.monotonic() + DEADLINE
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        resp = await _request(client, "GET", PORTFOLIO_URL, deadline)
        records = _all_companies(resp.text)
        if not records:
            raise RuntimeError("allCompanies array on /portfolio is empty")
        websites = await _websites(client, len(records), deadline)

    companies = []
    for r in records:
        name = (r.get("title") or "").strip()
        path = (r.get("url") or "").rstrip("/")
        if not name or not path:
            continue
        slug = path.rsplit("/", 1)[-1]
        profile_url = urllib.parse.urljoin(SITE_URL, path)
        companies.append({
            "name": name,
            "url": websites.get(slug) or profile_url,
            "description": (r.get("short_description") or "").strip() or None,
            "extra": {
                "nea_profile_url": profile_url,
                "status": (r.get("company_status_value") or {}).get("value"),
                "stage": (r.get("company_stage") or {}).get("value"),
            },
        })
    return companies


def scrape() -> list[dict]:
    return asyncio.run(_scrape())
