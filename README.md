# FreeGames Discord Bot

A Discord bot built on `py-cord` that watches GamerPower RSS feeds, enriches entries with the GamerPower API, and posts new free game drops to the right channel in each server.

## What It Does

- Polls GamerPower RSS feeds and only announces newly seen entries.
- Enriches RSS hits with the GamerPower API so posts include full embeds, claim buttons, worth, platform, and timing data.
- Stores per-server settings in SQLite:
  - notification channel
  - ping mode (`off`, `here`, `everyone`, `role`, `user`)
  - optional platform filter
  - optional giveaway type filter
- Maintains an archive of giveaways for search and recent-news browsing.
- Lets users track games they have played, are playing, completed, dropped, or added to a wishlist.

## Commands

### Server Setup

- `/freegames settings channel <#channel>`
- `/freegames settings ping <mode> [role] [user]`
- `/freegames settings filters [platform] [type]`
- `/freegames settings status`

### Giveaway Commands

- `/freegames list [platform] [type] [sort_by]`
- `/freegames lookup <giveaway_id>`
- `/freegames worth [platform] [type]`
- `/freegames search <query>`
- `/freegames news [platform] [type]`
- `/freegames help`

### Played Game Tracking

- `/freegames played add <title> [platform] [status] [notes]`
- `/freegames played list [member]`
- `/freegames played remove <title>`

## Setup

1. Create a virtual environment and install dependencies:

   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set at least `DISCORD_TOKEN`.

3. Start the bot:

   ```sh
   python bot.py
   ```

## Environment Variables

- `DISCORD_TOKEN`: required Discord bot token
- `DATABASE_PATH`: SQLite file path, default `data/freegames.db`
- `POLL_INTERVAL_SECONDS`: polling interval, default `900`
- `GAMERPOWER_BASE_URL`: GamerPower API base URL
- `RSS_FEEDS`: comma-separated GamerPower RSS feeds to poll
- `DEVELOPER_USER_ID`: optional user id allowed to use `/dev status`

## Notes

- On first startup, the bot seeds the current RSS entries and does not back-post old giveaways.
- New giveaway notifications are deduplicated per server.
- Giveaway archive data is refreshed from GamerPower whenever the bot polls or a user runs live lookup/list commands.
- GamerPower asks clients to stay below 4 requests per second. This bot stays well under that limit.
