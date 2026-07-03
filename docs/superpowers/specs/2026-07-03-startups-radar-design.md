# startups-radar — design spec

Date: 2026-07-03
Status: approved design (brainstorm complete); next step: implementation plan.
Owners: Aleksandr + friend (both Telegram admins).

## 1. Purpose & success criteria

A two-person market radar. Track chosen VCs'/accelerators' portfolio pages, post an
LLM-enriched digest to a Telegram channel every morning at 08:00 Europe/Berlin (also on
empty days), and manage the source list from Telegram, with scrapers for new sources
generated on demand by a coding-agent CLI.

Success criteria:
- Y Combinator tracked end-to-end on the user's remote server.
- Adding a plausible new source requires nothing but `/add <name> <url>` in Telegram.
- Daily digest arrives at 08:00 CET every day, with a health footer.

## 2. Architecture decisions (settled during brainstorm)

- **Signal definition:** portfolio/batch-page diffs per source. No news monitoring in v1.
- **Overall shape (approach A):** one Python monolith — bot + scheduler + SQLite — in
  Docker Compose. Rejected: LLM-as-parser (daily token cost, non-determinism, expensive on
  large directories); hybrid scraper+LLM-fallback (clean v2 upgrade, not v1 scope).
- **Agent CLI:** OpenAI Codex CLI (`codex exec`, non-interactive) — one vendor/key for
  both codegen and enrichment, since the server carries an OpenAI API key. Wrapped behind
  a thin `generate_scraper(source) -> path` interface so switching to Claude Code headless
  (`claude -p`, officially supported with an API key or `claude setup-token` token; a
  regular interactive Pro/Max OAuth login must not be reused for server automation) is a
  config change, not a rewrite.
- **Autonomy:** generated scrapers go live automatically after passing a self-test;
  failures are reported to Telegram.
- **Post format:** LLM-enriched (one-liner + tags) via OpenAI cheap model.
- **Cadence:** daily 08:00 Europe/Berlin, always post (empty days say "nothing new").
- **Telegram model:** bot posts digests to a channel; source management via bot commands
  from authorised admin user IDs.
- **Deployment:** Docker Compose on the user's remote server.

## 3. Stack

Python 3.12 · aiogram (bot) · APScheduler (daily job) · SQLite (named Docker volume) ·
httpx + beautifulsoup4 (scraper allowlist deps) · OpenAI API (enrichment) · Codex CLI
(scraper codegen) · Docker Compose · pytest.

## 4. Scraper contract (core abstraction)

Each source is a file `scrapers/<slug>.py` exposing:

```python
def scrape() -> list[dict]:
    # each dict: {"name": str, "url": str, "description": str|None, "extra": dict|None}
```

Execution rules:
- Scrapers run as a **sandboxed subprocess with a stripped environment** — no bot token,
  no API keys — and print a JSON array to stdout. Hard timeout (default 120 s).
- Rationale: generated code must never see secrets. A hostile page could prompt-inject
  the codegen step; the blast radius is limited to a process that can only fetch and print.
- Allowed third-party imports: `httpx`, `beautifulsoup4` only. Enforced by the self-test
  (import scan) and stated in the codegen prompt.

## 5. Add-source flow

1. Admin sends `/add <name> <url>`; source row created with `status=pending`.
2. Harness invokes `codex exec` with a prompt template containing: the scraper contract,
   the source URL, the dependency allowlist, guidance to prefer underlying JSON/API
   endpoints over HTML parsing, and the hand-written YC scraper as exemplar.
3. Output written to `scrapers/<slug>.py`.
4. **Self-test:** run the scraper via the sandboxed runner; validate JSON schema; require
   ≥1 company; scan imports against the allowlist.
5. On pass: **baseline** all returned companies as already-seen (`posted_at` set to a
   sentinel so they are never posted — adding YC must not flood the channel with 5,000
   historical entries), set `status=active`, `git commit` the scraper, reply
   "Tracking <name>: N companies baselined."
6. On fail: one retry with the error output fed back into the prompt; second failure sets
   `status=failed` and reports the error to Telegram (`/retry <slug>` re-runs the flow).

**YC in v1** ships as a hand-written reference scraper (the YC directory is JS-rendered
but backed by a public Algolia search API; the scraper uses that endpoint directly). It
doubles as the exemplar in the codegen prompt and the fixture basis for tests.

## 6. Daily job (08:00 Europe/Berlin)

For each `active` source:
1. Run scraper via sandboxed runner.
2. Diff against `companies` on `(source_id, normalised url)`; fallback key: normalised
   name. New rows inserted with `first_seen`.
3. **Sanity guard:** if the scraper fails or returns <50% of the source's `last_count`,
   skip diffing for that source and flag it in the health footer (protects against
   posting garbage after a site redesign).

Then:
4. Enrich each new company via OpenAI (one cheap-model call per company: one-line
   description + 2–3 category tags, using the scraped description plus a best-effort
   fetch of the company site; enrichment failure degrades to the raw scraped description,
   never blocks the digest).
5. Compose one digest post grouped by source: name + one-liner + tags + link. Split into
   multiple messages if over Telegram's 4096-char limit.
6. Post to the channel. Empty day → "Nothing new today." Always append a health footer:
   "N sources checked · M new · failures: <slugs or none>".
7. Mark posted companies with `posted_at`; log the run per source in `runs`.

## 7. Data model (SQLite; schema created on start, no migrations framework)

- `sources` — id, slug (unique), name, url, status (pending|active|failed|removed),
  added_by (telegram user id), created_at, last_run_at, last_count.
- `companies` — id, source_id, name, url, normalised_url, description, one_liner, tags
  (JSON), first_seen, posted_at (nullable; sentinel value for baselined rows).
- `runs` — id, source_id, started_at, outcome (ok|failed|suspicious), count, error.

## 8. Bot commands (admin user IDs only; others ignored)

- `/add <name> <url>` — add source, trigger scraper generation.
- `/remove <slug>` — set source `status=removed` (data retained).
- `/list` — sources with status, last run, last count.
- `/run` — trigger the digest job now (testing).
- `/retry <slug>` — re-run scraper generation for a failed source.

## 9. Deployment & config

Docker Compose on the remote server: one `app` service; named volume holding the SQLite
DB; `scrapers/` lives in the repo working tree (bind mount) so generated scrapers are
git-committed on the server and shared via push/pull. Codex CLI available inside the app
image (installed at build; authenticated via the OpenAI API key).

`.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `ADMIN_USER_IDS` (comma-separated),
`OPENAI_API_KEY`, `TZ=Europe/Berlin`. Secrets never passed into scraper subprocesses.

## 10. Error handling summary

- Scraper generation failure → retry once with error feedback → report to Telegram.
- Scraper runtime failure / suspicious count → skip source, flag in health footer.
- Enrichment failure → degrade to raw description.
- Telegram post failure → retry with backoff; log.
- Every failure path is visible in the daily health footer — silence never means "broken".

## 11. Testing

Pytest, no live network in CI: diff + baseline logic, digest composition, scraper-contract
schema validation, sandbox runner (env stripping, timeout, import allowlist), self-test
harness, YC scraper against recorded fixture responses. OpenAI and Telegram mocked.
Acceptance: one manual end-to-end run on the server posting to the real channel.

## 12. Out of scope for v1

Funding-news monitoring · cross-source dedup of the same startup · LLM-fallback
extraction (approach C; designed as a clean v2 upgrade) · web dashboard · multiple
channels/subscribers beyond the one channel.
