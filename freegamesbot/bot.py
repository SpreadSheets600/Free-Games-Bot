from __future__ import annotations

import asyncio
import logging
import datetime as dt
from typing import Iterable, List

import discord
from discord.ext import tasks

from .config import settings
from .db import GuildSettings, SettingsRepository
from .embeds import GiveawayView, giveaway_embed
from .gamerpower import GamerPowerClient, Giveaway

log = logging.getLogger(__name__)

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = discord.Bot(intents=intents)

api_client = GamerPowerClient(settings.gamerpower_base_url)
repo = SettingsRepository(settings.db_path)

COGS = [
    "freegamesbot.cogs.freegames",
    "freegamesbot.cogs.dev",
]

cogs_loaded = False
repo_connected = False
start_time: dt.datetime | None = None


@bot.event
async def on_ready() -> None:
    global start_time, repo_connected, cogs_loaded

    if not repo_connected:
        await repo.connect()
        bot.repo = repo
        bot.api_client = api_client
        repo_connected = True

    if not cogs_loaded:
        loaded_any = False
        for ext in COGS:
            try:
                module = __import__(ext, fromlist=["setup"])
                setup_fn = getattr(module, "setup", None)
                if setup_fn is None:
                    log.error("No setup function in cog %s", ext)
                    continue
                setup_fn(bot)
                loaded_any = True
                log.info("Loaded cog: %s", ext)
            except Exception:
                log.exception("Failed to load cog: %s", ext)

        if loaded_any:
            await bot.sync_commands(force=True)
            cogs_loaded = True
            log.info("Commands synced; %s cogs loaded", len(bot.cogs))

    if not giveaway_poll.is_running():
        giveaway_poll.start()

    start_time = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    bot.start_time = start_time
    await bot.change_presence(activity=discord.Game(name="Tracking free games"))

    loaded_commands = [cmd.name for cmd in bot.walk_application_commands()]
    log.info("Ready as %s | Commands: %s", bot.user, ", ".join(sorted(loaded_commands)))


@bot.event
async def on_guild_remove(guild: discord.Guild) -> None:
    if repo_connected:
        await repo.clear_guild(guild.id)


@bot.event
async def on_disconnect() -> None:
    log.warning("Discord gateway disconnected")


@tasks.loop(seconds=settings.poll_interval_seconds)
async def giveaway_poll() -> None:
    await bot.wait_until_ready()
    await _poll_and_notify()


@giveaway_poll.before_loop
async def before_giveaway_poll() -> None:
    await bot.wait_until_ready()


async def _poll_and_notify() -> None:
    giveaways = await _fetch_latest_giveaways()
    if not giveaways:
        return

    rss_entries = await api_client.fetch_rss_feeds(settings.rss_feeds)
    entry_keys = [entry.entry_key for entry in rss_entries]
    new_entry_keys = set(await repo.remember_rss_entries(entry_keys))

    bootstrap_complete = await repo.get_bot_state("rss_bootstrap_complete")
    if bootstrap_complete != "1":
        await repo.set_bot_state("rss_bootstrap_complete", "1")
        log.info("Seeded %s RSS entries without sending notifications", len(entry_keys))
        return

    new_entries = [entry for entry in rss_entries if entry.entry_key in new_entry_keys]
    if not new_entries:
        return

    matched_giveaways = api_client.match_feed_entries(new_entries, giveaways)
    if not matched_giveaways:
        log.info("RSS found %s new entries but no API giveaway matches", len(new_entries))
        return

    guilds = await repo.get_all_guilds()
    if not guilds:
        return

    for guild_cfg in guilds:
        await _notify_guild(guild_cfg, matched_giveaways, giveaways)


async def _fetch_latest_giveaways() -> List[Giveaway]:
    try:
        giveaways = await api_client.fetch_giveaways(sort_by="date")
        await repo.archive_giveaways(giveaways)
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()
        await repo.set_bot_state("last_giveaway_check", now)
        log.info("Fetched %s giveaways", len(giveaways))
        return giveaways
    except Exception:
        log.exception("Failed to fetch giveaways")
        return []


async def _notify_guild(
    guild_cfg: GuildSettings,
    giveaways: Iterable[Giveaway],
    active_giveaways: Iterable[Giveaway],
) -> None:
    if guild_cfg.channel_id is None:
        return

    channel = bot.get_channel(guild_cfg.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(guild_cfg.channel_id)
        except discord.HTTPException:
            log.warning(
                "Unable to fetch channel %s for guild %s",
                guild_cfg.channel_id,
                guild_cfg.guild_id,
            )
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        log.warning("Configured channel %s is not text capable", guild_cfg.channel_id)
        return

    filtered = [item for item in giveaways if _matches_filters(item, guild_cfg)]
    if not filtered:
        return

    active_filtered = [item for item in active_giveaways if _matches_filters(item, guild_cfg)]
    keep_ids = [str(item.id) for item in active_filtered][:250]
    if keep_ids:
        await repo.prune_notified(guild_cfg.guild_id, keep_ids)

    mention_text = _build_mention_text(guild_cfg)

    for giveaway in filtered:
        giveaway_id = str(giveaway.id)
        if await repo.already_notified(guild_cfg.guild_id, giveaway_id):
            continue

        try:
            await channel.send(
                content=mention_text or None,
                embed=giveaway_embed(giveaway),
                view=GiveawayView(giveaway.open_giveaway_url),
                allowed_mentions=discord.AllowedMentions(
                    everyone=True, roles=True, users=True
                ),
            )
            await repo.mark_notified(guild_cfg.guild_id, giveaway_id)
        except discord.HTTPException:
            log.exception(
                "Failed to send giveaway %s to guild %s channel %s",
                giveaway.id,
                guild_cfg.guild_id,
                guild_cfg.channel_id,
            )
            break


def _matches_filters(giveaway: Giveaway, guild_cfg: GuildSettings) -> bool:
    if guild_cfg.platform_filter:
        if guild_cfg.platform_filter.lower() not in giveaway.platforms.lower():
            return False

    if guild_cfg.type_filter:
        if guild_cfg.type_filter.lower() != giveaway.type.lower():
            return False

    return True


def _build_mention_text(guild_cfg: GuildSettings) -> str:
    if guild_cfg.ping_mode == "everyone":
        return "@everyone"
    if guild_cfg.ping_mode == "here":
        return "@here"
    if guild_cfg.ping_mode == "role" and guild_cfg.ping_target_id:
        return f"<@&{guild_cfg.ping_target_id}>"
    if guild_cfg.ping_mode == "user" and guild_cfg.ping_target_id:
        return f"<@{guild_cfg.ping_target_id}>"
    return ""
