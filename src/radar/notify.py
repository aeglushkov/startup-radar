import asyncio
import logging

log = logging.getLogger(__name__)


def make_sender(bot, channel_id: str, delays: tuple[float, ...] = (1.0, 3.0, 9.0)):
    """Channel sender with retry/backoff and light pacing between messages."""
    async def send(text: str) -> None:
        last_error = None
        for attempt, delay in enumerate((0.0,) + delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                await bot.send_message(channel_id, text, parse_mode="HTML",
                                       disable_web_page_preview=True)
                await asyncio.sleep(0.5)  # pace multi-message digests
                return
            except Exception as e:
                last_error = e
                log.warning("send attempt %d failed: %s", attempt + 1, e)
        raise last_error
    return send
