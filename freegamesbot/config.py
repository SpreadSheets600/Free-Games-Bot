from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


DEFAULT_RSS_FEEDS = [
    "https://www.gamerpower.com/rss/giveaways",
    "https://www.gamerpower.com/rss/pc",
    "https://www.gamerpower.com/rss/steam",
    "https://www.gamerpower.com/rss/xbox",
    "https://www.gamerpower.com/rss/playstation",
    "https://www.gamerpower.com/rss/nintendo",
    "https://www.gamerpower.com/rss/mobile",
    "https://www.gamerpower.com/rss/games",
    "https://www.gamerpower.com/rss/loot",
]


@dataclass
class Settings:
    discord_token: str
    db_path: str = "data/freegames.db"
    poll_interval_seconds: int = 900

    gamerpower_base_url: str = "https://www.gamerpower.com/api"
    max_items_per_page: int = 6

    rss_feeds: List[str] = field(default_factory=list)
    developer_user_id: Optional[int] = None

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        db_path = os.getenv("DATABASE_PATH", "data/freegames.db").strip()
        poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))

        base_url = os.getenv(
            "GAMERPOWER_BASE_URL", "https://www.gamerpower.com/api"
        ).strip()

        page_size = int(os.getenv("MAX_ITEMS_PER_PAGE", "6"))
        feeds_raw = os.getenv("RSS_FEEDS", "").strip()

        feeds = [
            item.strip() for item in feeds_raw.split(",") if item.strip()
        ] or DEFAULT_RSS_FEEDS

        developer_id_raw = os.getenv("DEVELOPER_USER_ID", "").strip()
        developer_id = int(developer_id_raw) if developer_id_raw.isdigit() else None

        return cls(
            discord_token=token,
            db_path=db_path,
            poll_interval_seconds=poll_interval,
            gamerpower_base_url=base_url,
            max_items_per_page=page_size,
            rss_feeds=feeds,
            developer_user_id=developer_id,
        )


settings: Optional[Settings] = Settings.from_env()
