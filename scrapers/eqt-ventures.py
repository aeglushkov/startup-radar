"""EQT Ventures portfolio scraper.

eqtventures.com redirects to eqtgroup.com's firm-wide "Current Portfolio"
page (Next.js App Router). The full company list (all EQT strategies, not
just Ventures) is embedded server-side as a React Server Components (RSC)
streaming payload: a series of `self.__next_f.push([id, "<escaped JSON>"])`
calls whose decoded strings contain `id:<json>` lines. One such line holds
the full portfolio tree (each company has `title`, `slug`, and `keyFacts`
including `sector`/`country`, plus `formatedFunds` naming which EQT fund(s)
back it). We keep only companies tagged with an `eqt_ventures_*` fund, per
the acceptance note that a filtered "current portfolio" view for the
Ventures fund is fine. No direct company websites are exposed, so we link
to the company's page on eqtgroup.com.
"""
import json
import re

import httpx

URL = "https://eqtgroup.com/about/current-portfolio"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
PUSH_RE = re.compile(r"self\.__next_f\.push\(")


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


def _find_companies(payload_text: str) -> dict[str, dict]:
    found: dict[str, dict] = {}

    def walk(node):
        if isinstance(node, dict):
            slug = node.get("slug")
            if (
                "keyFacts" in node
                and isinstance(node.get("title"), str)
                and isinstance(slug, dict)
                and slug.get("current")
            ):
                found[slug["current"]] = node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for line in payload_text.split("\n"):
        _, sep, rest = line.partition(":")
        if not sep or not rest:
            continue
        try:
            data = json.loads(rest)
        except json.JSONDecodeError:
            continue
        walk(data)
    return found


def scrape() -> list[dict]:
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()

    payload_text = _rsc_payload_text(resp.text)
    companies_by_slug = _find_companies(payload_text)

    companies = []
    for slug, rec in companies_by_slug.items():
        funds = rec.get("formatedFunds") or []
        if not any(f.startswith("eqt_ventures_") for f in funds):
            continue
        name = (rec.get("title") or "").strip()
        if not name:
            continue
        key_facts = rec.get("keyFacts") or {}
        companies.append({
            "name": name,
            "url": f"https://eqtgroup.com/about/current-portfolio/{slug}",
            "description": key_facts.get("sector"),
            "extra": {
                "country": key_facts.get("country"),
                "launch_year": key_facts.get("launchYear"),
                "funds": funds,
            },
        })
    return companies
