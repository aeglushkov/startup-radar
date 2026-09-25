"""Greylock Partners portfolio scraper.

In mid-July 2026 greylock.com moved from WordPress to a Next.js App Router
site on Vercel backed by Sanity CMS, so the old `div.portfolio-modal-box`
markup is gone. /portfolio/ (not /companies/, which 301s to a jobs board)
still server-renders every company, and the same records are streamed in the
React Server Components payload (`self.__next_f.push([1, "..."])` scripts) as
`{"company": {...}}` objects carrying name, slug, tagline, status, sector
and first-partnered stage. That is the company list. The first few companies
are inlined in the list markup and the rest are separate `$L` rows, so the
whole payload is searched for those objects rather than parsed line by line.

The list no longer includes the company's website, which the stored history
is keyed on, so each profile page (/portfolio/<slug>/) is fetched too: it
embeds a schema.org Organization JSON-LD block whose `url` is the website and
whose `description` is the long blurb the old modals showed. ~160 small pages
fetched concurrently take a few seconds. A company without a website falls
back to its profile page URL. If most profile pages fail to load, the scrape
raises rather than returning profile URLs that would diff as "new".

Sanity's GROQ API is not publicly readable for this project (queries return
nothing), so the rendered pages are the only public source.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx

URL = "https://greylock.com/portfolio/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
PUSH_RE = re.compile(r"self\.__next_f\.push\(")
COMPANY_RE = re.compile(r'\{"company":\{')
LD_JSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _rsc_payload_text(html: str) -> str:
    decoder = json.JSONDecoder()
    full = []
    for m in PUSH_RE.finditer(html):
        try:
            obj, _ = decoder.raw_decode(html, m.end())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list) and len(obj) > 1 and isinstance(obj[1], str):
            full.append(obj[1])
    return "".join(full)


def _find_companies(payload: str) -> list[dict]:
    decoder = json.JSONDecoder()
    found: dict[str, dict] = {}
    for m in COMPANY_RE.finditer(payload):
        try:
            obj, _ = decoder.raw_decode(payload, m.start())
        except json.JSONDecodeError:
            continue
        company = obj.get("company") or {}
        if company.get("slug") and (company.get("name") or "").strip():
            found.setdefault(company["slug"], company)
    return list(found.values())


def _profile_org(html: str) -> dict:
    for block in LD_JSON_RE.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict) or node.get("@type") != "Organization":
                continue
            if "/portfolio/" in (node.get("@id") or ""):
                return node
    return {}


def _fetch_profile(client: httpx.Client, slug: str) -> dict | None:
    try:
        resp = client.get(f"{URL}{slug}/")
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    return _profile_org(resp.text)


def _website(org: dict) -> str | None:
    url = (org.get("url") or "").strip()
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return url if url.startswith("http") and host != "greylock.com" else None


def scrape() -> list[dict]:
    limits = httpx.Limits(max_connections=10)
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True, limits=limits) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        records = _find_companies(_rsc_payload_text(resp.text))
        if not records:
            raise RuntimeError("no company records found in portfolio RSC payload")

        slugs = [r["slug"] for r in records]
        with ThreadPoolExecutor(max_workers=10) as pool:
            profiles = dict(zip(slugs, pool.map(lambda s: _fetch_profile(client, s), slugs)))

    failed = sum(1 for p in profiles.values() if p is None)
    if failed > len(slugs) // 2:
        raise RuntimeError(f"{failed}/{len(slugs)} Greylock profile pages failed to load")

    companies = []
    for r in records:
        slug = r["slug"]
        org = profiles.get(slug) or {}
        description = (org.get("description") or r.get("tagline") or "").strip() or None
        companies.append({
            "name": r["name"].strip(),
            "url": _website(org) or f"{URL}{slug}/",
            "description": description,
            "extra": {
                "greylock_slug": slug,
                "status": r.get("status"),
                "sector": r.get("domain"),
                "first_partnered": r.get("firstPartnered"),
            },
        })
    return companies
