import asyncio
import logging
import re

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from radar import db
from radar.codegen import generate_and_enable
from radar.config import Config
from radar.jobs import run_daily

log = logging.getLogger(__name__)


def slugify(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]", "-", name.strip().lower())).strip("-")


def parse_add_args(text: str) -> tuple[str, str] | None:
    parts = text.split()[1:]  # drop /add
    if len(parts) < 2 or not parts[-1].startswith("http"):
        return None
    return " ".join(parts[:-1]), parts[-1]


def format_source_list(rows) -> str:
    if not rows:
        return "No sources yet. Add one with /add <name> <url>."
    lines = []
    for r in rows:
        last = r["last_run_at"] or "never"
        count = r["last_count"] if r["last_count"] is not None else "?"
        lines.append(f"{r['slug']} — {r['status']}, last run {last}, {count} companies")
    return "\n".join(lines)


def build_router(conn, cfg: Config) -> Router:
    router = Router()

    def admin(message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in cfg.admin_ids

    async def _generate(message: Message, slug: str, name: str, url: str) -> None:
        await message.reply(f"Generating scraper for {slug}…")
        res = await asyncio.to_thread(generate_and_enable, cfg, slug, name, url)
        if res.ok:
            await message.reply(f"Tracking {name}: {res.count} companies baselined.")
        else:
            await message.reply(f"Scraper for {slug} failed: {res.error}\nUse /retry {slug}.")

    @router.message(Command("add"))
    async def add(message: Message):
        if not admin(message):
            return
        parsed = parse_add_args(message.text or "")
        if not parsed:
            await message.reply("Usage: /add <name> <url>")
            return
        name, url = parsed
        slug = slugify(name)
        if db.get_source(conn, slug):
            await message.reply(f"Source {slug} already exists. /retry {slug} to regenerate.")
            return
        db.add_source(conn, slug, name, url, added_by=message.from_user.id)
        await _generate(message, slug, name, url)

    @router.message(Command("retry"))
    async def retry(message: Message):
        if not admin(message):
            return
        parts = (message.text or "").split()
        src = db.get_source(conn, parts[1]) if len(parts) == 2 else None
        if not src:
            await message.reply("Usage: /retry <slug> (unknown slug)")
            return
        await _generate(message, src["slug"], src["name"], src["url"])

    @router.message(Command("remove"))
    async def remove(message: Message):
        if not admin(message):
            return
        parts = (message.text or "").split()
        if len(parts) != 2 or not db.get_source(conn, parts[1]):
            await message.reply("Usage: /remove <slug> (unknown slug)")
            return
        db.set_source_status(conn, parts[1], "removed")
        await message.reply(f"Removed {parts[1]}.")

    @router.message(Command("list"))
    async def list_cmd(message: Message):
        if not admin(message):
            return
        await message.reply(format_source_list(db.list_sources(conn)))

    @router.message(Command("run"))
    async def run_cmd(message: Message):
        if not admin(message):
            return
        await message.reply("Running digest now…")
        bot: Bot = message.bot
        async def send(text: str) -> None:
            await bot.send_message(cfg.channel_id, text, parse_mode="HTML",
                                   disable_web_page_preview=True)
        await run_daily(conn, cfg, send)
        await message.reply("Done.")

    return router
