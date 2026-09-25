"""Sequoia Capital portfolio scraper (Framer site-search index).

Since mid-August 2026 sequoiacap.com is a Framer site; the WordPress REST API
(/wp-json/wp/v2/company) the previous version used is gone (404). /our-companies
server-renders only ~20 featured companies and pulls the rest client-side from
Framer's CMS chunks (`*.framercms`), an undocumented binary format keyed by
opaque field ids, so neither is a good source.

Framer also publishes a site-search index for every site: one public JSON file
on framerusercontent.com (~12 MB via CloudFront, ~1 s) with a record per page,
keyed by path. Its URL is content-hashed and changes on every publish, so it is
discovered from the `framer-search-index` meta tag (plus a `-fallback` copy) on
/our-companies. Every /companies/<slug> page is in it (same set as sitemap.xml).

The company name is the page title minus " | Sequoia Capital". Slugs and titles
carried over unchanged from WordPress, so urls keep the old permalink format
(https://sequoiacap.com/companies/<slug>/) and names match those already stored.

A record's `p` list is the page's paragraph text in document order: site nav,
the description paragraph(s), the company's bare domain, then "#tag" /
"Founded YYYY" / "Partnered YYYY" / people. Description and website are read
from that order on a best-effort basis and left empty if the layout shifts.
"""
import re

import httpx

PAGE_URL = "https://sequoiacap.com/our-companies"
PROFILE_URL = "https://sequoiacap.com/companies/{slug}/"
TITLE_SUFFIX = " | Sequoia Capital"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
INDEX_META = re.compile(r'<meta name="framer-search-index(?:-fallback)?" content="([^"]+)"')
COMPANY_PATH = re.compile(r"^/companies/([^/]+)/?$")
DOMAIN = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?", re.I)
MIN_PROSE_WORDS = 4


def _load_index(client: httpx.Client) -> dict:
    resp = client.get(PAGE_URL)
    resp.raise_for_status()
    index_urls = INDEX_META.findall(resp.text)
    if not index_urls:
        raise RuntimeError("framer-search-index meta tag not found on /our-companies")
    error = None
    for url in index_urls:
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            error = exc
    raise error


def _profile_fields(paragraphs: list[str]) -> tuple[str | None, str | None]:
    site_idx = next((i for i, s in enumerate(paragraphs) if DOMAIN.fullmatch(s.strip())), None)
    if site_idx is None:
        return None, None
    prose = []
    for text in reversed(paragraphs[:site_idx]):
        if len(text.split()) < MIN_PROSE_WORDS:
            break
        prose.insert(0, text.strip())
    site = paragraphs[site_idx].strip()
    return " ".join(prose) or None, site if "://" in site else f"https://{site}"


def scrape() -> list[dict]:
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        index = _load_index(client)

    companies = []
    for path, record in index.items():
        match = COMPANY_PATH.match(path)
        if not match:
            continue
        name = (record.get("title") or "").removesuffix(TITLE_SUFFIX).strip()
        if not name:
            continue
        slug = match.group(1)
        description, website = _profile_fields(record.get("p") or [])
        companies.append({
            "name": name,
            "url": PROFILE_URL.format(slug=slug),
            "description": description,
            "extra": {"slug": slug, "website": website},
        })
    if not companies:
        raise RuntimeError("no /companies/ pages in the Framer search index")
    return companies
