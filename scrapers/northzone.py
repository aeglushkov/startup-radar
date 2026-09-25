"""Northzone portfolio scraper (Webflow CMS collection list, server-rendered).

/portfolio is a Webflow page (behind Cloudflare, but plain requests get the
full HTML) whose company table is a native collection list
(`.w-dyn-items > .w-dyn-item`) enhanced client-side by Finsweet attributes
(CMS Load `render-all`, CMS Filter, CMS Nest). Webflow caps a rendered
collection list at 100 items, so the rest sits behind a `?<hash>_page=N`
link in the (hidden) `a.w-pagination-next`; CMS Load follows those same
links in the browser, and so do we. There is no public JSON/CMS endpoint.

The 2026-09-02 redesign turned `.filters5_company-link` into a plain `div`
wrapping the name and moved the profile href onto a separate
`a.filters5_company-link-absolute` overlay, so we key off the functional
pieces instead: the CMS Load list wrapper, each item's `/portfolio/<slug>`
anchor and the `fs-cmsfilter-field` values. Location entries are also tagged
`fs-cmsfilter-field="industry"` on the site, so industries and locations are
told apart by their nested list wrappers. Acquired companies carry the
acquirer after a "by" in the status cell. No company website is listed, only
Northzone's own profile page, which is used as the url.
"""
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://northzone.com/portfolio"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
MAX_PAGES = 20


def _texts(item, selector: str) -> list[str]:
    return [t for t in (el.get_text(strip=True) for el in item.select(selector)) if t]


def _parse_item(item) -> dict | None:
    link = item.select_one('a[href*="/portfolio/"]')
    names = _texts(item, "[fs-cmsfilter-field=name]")
    if not link or not names:
        return None

    status_el = item.select_one("[fs-cmsfilter-field=status]")
    status, acquirer = None, None
    if status_el:
        status = status_el.get_text(strip=True) or None
        rest = [el.get_text(strip=True) for el in status_el.find_next_siblings()]
        if rest[:1] == ["by"]:
            acquirer = " ".join(t for t in rest[1:] if t) or None
    stages = _texts(item, ".filters5_company-link [fs-cmsfilter-field=stage]")

    return {
        "name": names[0],
        "url": str(httpx.URL(BASE_URL).join(link["href"])),
        "description": None,
        "extra": {
            "status": status,
            "acquirer": acquirer,
            "stage": stages[0] if stages else None,
            "industries": _texts(item, ".filters5_industry-list [fs-cmsfilter-field]") or None,
            "locations": _texts(item, ".filters5_location-list [fs-cmsfilter-field]") or None,
        },
    }


def _parse_page(html: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    wrapper = soup.select_one("[fs-cmsload-element=list]")
    items = wrapper.select(":scope > .w-dyn-items > .w-dyn-item") if wrapper else []
    companies = [c for c in map(_parse_item, items) if c]

    next_link = soup.select_one("a.w-pagination-next[href]")
    return companies, next_link["href"] if next_link else None


def scrape() -> list[dict]:
    companies: dict[str, dict] = {}
    url, seen_urls = BASE_URL, set()
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        while url and url not in seen_urls and len(seen_urls) < MAX_PAGES:
            seen_urls.add(url)
            resp = client.get(url)
            resp.raise_for_status()
            batch, next_href = _parse_page(resp.text)
            if not batch:
                break
            for c in batch:
                companies.setdefault(c["url"], c)
            url = str(httpx.URL(BASE_URL).join(next_href)) if next_href else None

    if not companies:
        raise RuntimeError("no companies found in the portfolio collection list")
    return list(companies.values())
