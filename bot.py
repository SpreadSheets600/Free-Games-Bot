from __future__ import annotations

import sys
import asyncio
import logging
from typing import Final

from freegamesbot.config import settings
from freegamesbot import bot as bot_module


LOG_FORMAT: Final = "[%(asctime)s] %(levelname).1s %(name)s | %(message)s"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if not settings.discord_token:
        sys.exit("DISCORD TOKEN Is Not Set. Update Your .env File Or Environment.")

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    bot_module.bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
