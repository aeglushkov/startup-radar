import json

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI

PROMPT = (
    "You describe startups for a daily radar digest. Given the data below, reply as JSON: "
    '{{"one_liner": "<factual one sentence, max 20 words, no hype>", '
    '"tags": ["<2-3 lowercase category tags>"]}}\n\n'
    "Name: {name}\nScraped description: {description}\nWebsite text: {snippet}"
)


def fetch_site_snippet(url: str) -> str | None:
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True,
                         headers={"User-Agent": "startups-radar/0.1"})
        text = BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True)
        return text[:1500] or None
    except Exception:
        return None


def enrich_company(company: dict, api_key: str, model: str) -> dict:
    out = {**company, "one_liner": None, "tags": []}
    try:
        snippet = fetch_site_snippet(company["url"]) or ""
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT.format(
                name=company["name"],
                description=company.get("description") or "(none)",
                snippet=snippet or "(unavailable)",
            )}],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        one_liner = data.get("one_liner")
        tags = data.get("tags") or []
        out["one_liner"] = one_liner if isinstance(one_liner, str) else None
        out["tags"] = [t for t in tags if isinstance(t, str)][:3]
    except Exception:
        pass
    return out
