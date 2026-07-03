Write a single Python file at {scrapers_dir}/{slug}.py that scrapes the current
portfolio/companies list of "{name}" from {url}.

Contract (must hold exactly):
- Define `scrape() -> list[dict]`. Each dict has keys: "name" (non-empty str),
  "url" (non-empty str), "description" (str or None), "extra" (dict or None).
- Return ALL companies currently listed by the source, paginating until exhausted.
- Imports: Python stdlib plus `httpx` and `bs4` ONLY. No other third-party packages.
- No environment variable access, no file writes, no printing. Request timeout 30s.
- Prefer the site's underlying JSON/API endpoints (inspect XHR traffic) over HTML
  parsing; fall back to HTML parsing with bs4 if there is no API.

Example of a good scraper following this contract:

```python
{exemplar}
```

Write only that one file. Verify it compiles (`python -m py_compile`).
{feedback}
