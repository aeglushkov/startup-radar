import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from radar import db
from radar.config import Config
from radar.diffing import find_new
from radar.digest import compose
from radar.enrich import enrich_company
from radar.runner import ScraperError, run_scraper

log = logging.getLogger(__name__)


async def run_daily(conn, cfg: Config, send: Callable[[str], Awaitable[None]]) -> None:
    sources = [s for s in db.list_sources(conn) if s["status"] == "active"]
    sections, failures, total_new = [], [], 0

    for src in sources:
        path = os.path.join(cfg.scrapers_dir, f"{src['slug']}.py")
        try:
            scraped = await asyncio.to_thread(run_scraper, path)
        except ScraperError as e:
            log.warning("scraper %s failed: %s", src["slug"], e)
            db.record_run(conn, src["id"], "failed", 0, str(e))
            failures.append(src["slug"])
            continue

        last = src["last_count"]
        if last and last > 0 and len(scraped) < 0.5 * last:
            db.record_run(conn, src["id"], "suspicious", len(scraped),
                          f"count {len(scraped)} < 50% of last {last}")
            failures.append(src["slug"])
            continue

        try:
            new = find_new(conn, src["id"], scraped)
            enriched = [
                await asyncio.to_thread(enrich_company, c, cfg.openai_api_key, cfg.openai_model)
                for c in new
            ]
            db.insert_companies(conn, src["id"], enriched)
            db.record_run(conn, src["id"], "ok", len(scraped), None)
            db.update_source_after_run(conn, src["slug"], len(scraped))
        except Exception as e:
            log.exception("processing %s failed", src["slug"])
            db.record_run(conn, src["id"], "failed", len(scraped), str(e))
            failures.append(src["slug"])
            continue

        # includes both the rows just inserted and any orphans from prior failed sends
        pending = db.unposted_companies(conn, src["id"])
        if pending:
            sections.append((src["name"], pending))
            total_new += len(enriched)

    footer = (f"{len(sources)} sources checked · {total_new} new · "
              f"failures: {', '.join(failures) if failures else 'none'}")
    for message in compose(sections, footer):
        await send(message)
    posted_ids = [c["_id"] for _, cs in sections for c in cs]
    if posted_ids:
        db.mark_posted(conn, posted_ids)
