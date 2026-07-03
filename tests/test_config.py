import pytest

from radar.config import Config

ENV = {
    "TELEGRAM_BOT_TOKEN": "tok",
    "TELEGRAM_CHANNEL_ID": "@chan",
    "ADMIN_USER_IDS": "1, 2",
    "OPENAI_API_KEY": "sk-x",
}


def test_from_env_required_and_defaults(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg.bot_token == "tok"
    assert cfg.admin_ids == frozenset({1, 2})
    assert cfg.openai_model == "gpt-5-mini"
    assert cfg.db_path == "/data/radar.db"
    assert cfg.timezone == "Europe/Berlin"


def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(KeyError):
        Config.from_env()
