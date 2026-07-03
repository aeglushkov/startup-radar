import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    channel_id: str
    admin_ids: frozenset[int]
    openai_api_key: str
    openai_model: str
    db_path: str
    scrapers_dir: str
    timezone: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
            admin_ids=frozenset(
                int(x) for x in os.environ["ADMIN_USER_IDS"].split(",") if x.strip()
            ),
            openai_api_key=os.environ["OPENAI_API_KEY"],
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
            db_path=os.environ.get("DB_PATH", "/data/radar.db"),
            scrapers_dir=os.environ.get("SCRAPERS_DIR", "scrapers"),
            timezone=os.environ.get("TZ", "Europe/Berlin"),
        )
