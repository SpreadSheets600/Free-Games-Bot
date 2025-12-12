# FreeGames Discord Bot

A modular Discord bot (py-cord) that posts new GamerPower giveaways to per-server channels, with slash commands, pagination, and SQLite persistence.

## Features

- Slash commands under `/freegames` (set channel, list giveaways with filters, lookup by id, worth summary).
- Background loop polls GamerPower and posts new giveaways to the configured channel per guild.
- Pagination for long lists using buttons.
- SQLite storage for guild channel mapping and per-guild notified giveaway ids.

## Quick start

1. **Install deps** (Python 3.10+ recommended):

   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure env**: copy `.env.example` to `.env` and fill `DISCORD_TOKEN` (bot token). Optionally tweak `POLL_INTERVAL_SECONDS`, `DATABASE_PATH`, `MAX_ITEMS_PER_PAGE`.
3. **Run**:

   ```sh
   python bot.py
   ```

## Slash commands

- `/freegames set-channel <#text-channel>`: set where the bot will post new giveaways (manage server permission required).
- `/freegames status`: show current channel and counters.
- `/freegames list [platform] [type] [sort_by]`: fetch live giveaways with pagination.
- `/freegames lookup <id>`: detailed embed for a specific giveaway.
- `/freegames worth [platform] [type]`: summary count and USD worth.

## Notes

- Polls GamerPower every `POLL_INTERVAL_SECONDS` (default 900s). API rate limit is 4 req/sec; this bot stays well below it.
- First poll after configuring a channel will post all currently live giveaways (they are tracked to prevent repeats afterward).
- Data is stored in `DATABASE_PATH` (defaults to `data/freegames.db`).
