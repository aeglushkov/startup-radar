from unittest.mock import AsyncMock, MagicMock

from radar.notify import make_sender


async def test_retries_then_succeeds():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[RuntimeError("net"), RuntimeError("net"), None])
    send = make_sender(bot, "@c", delays=(0.01, 0.01, 0.01))
    await send("hi")
    assert bot.send_message.await_count == 3


async def test_raises_after_exhausted():
    import pytest
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("down"))
    send = make_sender(bot, "@c", delays=(0.01,))
    with pytest.raises(RuntimeError):
        await send("hi")
