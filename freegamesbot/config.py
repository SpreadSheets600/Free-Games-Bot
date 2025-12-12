from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    discord_token: str
    db_path: str = "data/freegames.db"
    poll_interval_seconds: int = 900
    gamerpower_base_url: str = "https://www.gamerpower.com/api"
    max_items_per_page: int = 6

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        db_path = os.getenv("DATABASE_PATH", "data/freegames.db").strip()
        poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))
        base_url = os.getenv(
            "GAMERPOWER_BASE_URL", "https://www.gamerpower.com/api"
        ).strip()
        page_size = int(os.getenv("MAX_ITEMS_PER_PAGE", "6"))

        return cls(
            discord_token=token,
            db_path=db_path,
            poll_interval_seconds=poll_interval,
            gamerpower_base_url=base_url,
            max_items_per_page=page_size,
        )


settings: Optional[Settings] = Settings.from_env()
