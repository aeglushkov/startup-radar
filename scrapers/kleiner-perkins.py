"""Kleiner Perkins portfolio scraper.

The /partnerships page is a Framer site, but it's server-rendered: each
company has a hidden `<div class="js-companies" data-id="...">` modal with
name, one-line description, website link, and "Partnered Since"/"Stage"
metadata. No pagination or JS execution needed.

Most historical companies (~60, mostly acquired/defunct) have no "Website"
link in their modal at all. A previous version fell back to the shared
/partnerships listing URL for those, which not only dropped them on
dedupe but poisoned the URL key for every other company sharing that
fallback. We skip companies with no website of their own instead — same
pattern as scrapers/a16z.py — since a forward-looking radar only needs
companies with a real, individually-keyable url.
"""
import httpx
from bs4 import BeautifulSoup

URL = "https://www.kleinerperkins.com/partnerships"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def scrape() -> list[dict]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    companies = []
    for modal in soup.select("div.js-companies"):
        h2 = modal.find("h2")
        name = h2.get_text(strip=True) if h2 else None
        if not name:
            continue
        website = None
        for a in modal.find_all("a"):
            if a.get_text(strip=True) == "Website":
                website = a.get("href")
                break
        if not website:
            continue  # no website of its own — skip rather than fall back
        desc_div = modal.select_one("div.text-12")
        description = desc_div.get_text(strip=True) if desc_div else None

        since, stage = None, None
        for li in modal.select("ul li"):
            h3 = li.find("h3")
            label = h3.get_text(strip=True) if h3 else None
            spans = [s.get_text(strip=True) for s in li.select("span")]
            if label == "Partnered Since" and spans:
                since = spans[0]
            elif label == "Stage" and spans:
                stage = spans[0]

        companies.append({
            "name": name,
            "url": website,
            "description": description,
            "extra": {"since": since, "stage": stage},
        })
    return companies
