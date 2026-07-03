import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from radar import db
from radar.bot import build_router
from radar.config import Config
from radar.jobs import run_daily

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def build_scheduler(cfg: Config, job) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=cfg.timezone)
    scheduler.add_job(job, CronTrigger(hour=8, minute=0, timezone=cfg.timezone))
    return scheduler


async def main() -> None:
    cfg = Config.from_env()
    conn = db.get_conn(cfg.db_path)
    db.init_db(conn)
    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher()
    dp.include_router(build_router(conn, cfg))

    async def send(text: str) -> None:
        await bot.send_message(cfg.channel_id, text, parse_mode="HTML",
                               disable_web_page_preview=True)

    async def daily() -> None:
        try:
            await run_daily(conn, cfg, send)
        except Exception:
            log.exception("daily job crashed")

    scheduler = build_scheduler(cfg, daily)
    scheduler.start()
    log.info("startups-radar started; polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
