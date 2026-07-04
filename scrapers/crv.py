"""CRV portfolio scraper (public Sanity content API).

The /companies page is a Next.js/Vercel app; its Content-Security-Policy
header reveals the Sanity project id (58537uhq, dataset production). Sanity's
read API is public by default, so a GROQ query fetches every "company"
document directly -- no pagination needed (~185 docs).
"""
import httpx

PROJECT_ID = "58537uhq"
DATASET = "production"
URL = f"https://{PROJECT_ID}.api.sanity.io/v2021-06-07/data/query/{DATASET}"
QUERY = '*[_type == "company"]{name, website, "slug": slug.current, about}'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _plain_text(blocks) -> str | None:
    if not blocks:
        return None
    parts = []
    for block in blocks:
        for child in block.get("children", []):
            text = child.get("text")
            if text:
                parts.append(text)
    text = "".join(parts).strip()
    return text or None


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS) as client:
        resp = client.get(URL, params={"query": QUERY})
        resp.raise_for_status()
        records = resp.json().get("result", [])

    companies = []
    for r in records:
        name = (r.get("name") or "").strip()
        slug = r.get("slug")
        url = (r.get("website") or "").strip() or (
            f"https://www.crv.com/companies/{slug}" if slug else None
        )
        if not name or not url:
            continue
        companies.append({
            "name": name,
            "url": url,
            "description": _plain_text(r.get("about")),
            "extra": {"slug": slug},
        })
    return companies
