from __future__ import annotations

import asyncio
import logging
import datetime as dt
from typing import List

import discord
from discord.ext import tasks

from .config import settings
from .embeds import giveaway_embed, GiveawayView
from .db import SettingsRepository
from .gamerpower import GamerPowerClient, Giveaway

log = logging.getLogger(__name__)

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

api_client = GamerPowerClient(settings.gamerpower_base_url)
repo = SettingsRepository(settings.db_path)

COGS = [
    "freegamesbot.cogs.freegames",
    "freegamesbot.cogs.dev",
]

cogs_loaded = False
repo_connected = False
startup_notified = False
skip_initial_notify = False
start_time: dt.datetime | None = None


@bot.event
async def on_ready() -> None:
    global \
        start_time, \
        repo_connected, \
        cogs_loaded, \
        startup_notified, \
        skip_initial_notify

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
                if hasattr(module, "setup"):
                    setup_fn = getattr(module, "setup")
                    setup_fn(bot)
                    loaded_any = True
                    log.info("Loaded cog: %s", ext)
                else:
                    log.error("No setup function in cog %s", ext)
            except Exception:
                log.exception("Failed to load cog: %s", ext)

        if loaded_any:
            await bot.sync_commands(force=True)
            cogs_loaded = True
            log.info("Commands synced; %s cogs loaded", len(bot.cogs))
        else:
            log.error("No cogs loaded; commands will not be available")

    if not giveaway_poll.is_running():
        giveaway_poll.start()

    start_time = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    bot.start_time = start_time

    await bot.change_presence(activity=discord.Game(name="Tracking Games"))

    if not startup_notified:
        startup_notified = True
        skip_initial_notify = True
        await _startup_confirmation()

    loaded_commands = [cmd.name for cmd in bot.walk_application_commands()]

    log.info(
        "Ready As %s | Commands : %s", bot.user, ", ".join(sorted(loaded_commands))
    )


@tasks.loop(seconds=settings.poll_interval_seconds)
async def giveaway_poll() -> None:
    await bot.wait_until_ready()
    await _notify_new_giveaways()


async def _notify_new_giveaways() -> None:
    global skip_initial_notify

    if skip_initial_notify:
        skip_initial_notify = False
        log.info("Skipping Initial RSS Notification After Startup Check")

        return

    giveaways = await _fetch_latest_giveaways()
    if not giveaways:
        return

    guilds = await repo.get_all_guilds()
    if not guilds:
        return

    for guild_cfg in guilds:
        await _notify_guild(guild_cfg.guild_id, guild_cfg.channel_id, giveaways)


async def _startup_confirmation() -> None:
    await bot.wait_until_ready()

    guilds = await repo.get_all_guilds()
    if not guilds:
        return

    giveaways = await _fetch_latest_giveaways()
    if not giveaways:
        return

    latest = giveaways[0]
    for guild_cfg in guilds:
        await _send_startup_latest(guild_cfg.guild_id, guild_cfg.channel_id, latest)


async def _fetch_latest_giveaways() -> List[Giveaway]:
    try:
        giveaways = await api_client.fetch_giveaways(sort_by="date")
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()
        await repo.set_bot_state("last_giveaway_check", now)
        log.info("Fetched %s giveaways", len(giveaways))
        return giveaways
    except Exception:
        log.exception("Failed to fetch giveaways")
        return []


async def _notify_guild(
    guild_id: int, channel_id: int, giveaways: List[Giveaway]
) -> None:
    channel = bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            log.warning("Unable To Fetch Channel %s For Guild %s", channel_id, guild_id)
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        log.warning("Configured Channel %s Is Not Text Capable", channel_id)
        return

    new_items: List[Giveaway] = []
    for giveaway in giveaways:
        giveaway_id = str(giveaway.id)
        if not await repo.already_notified(guild_id, giveaway_id):
            new_items.append(giveaway)

    if not new_items:
        return

    keep_ids = [str(item.id) for item in giveaways][:200]
    await repo.prune_notified(guild_id, keep_ids)

    for giveaway in new_items:
        try:
            embed = giveaway_embed(giveaway)
            view = GiveawayView(giveaway.open_giveaway_url)
            await channel.send(embed=embed, view=view)
            await repo.mark_notified(guild_id, str(giveaway.id))

        except discord.HTTPException:
            log.exception(
                "Failed To Send Giveaway %s To Guild %s Channel %s",
                giveaway.id,
                guild_id,
                channel_id,
            )
            break


async def _send_startup_latest(
    guild_id: int, channel_id: int, giveaway: Giveaway
) -> None:
    channel = bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)

        except discord.HTTPException:
            log.warning("Unable To Fetch Channel %s For Guild %s", channel_id, guild_id)
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        log.warning("Configured Channel %s Is Not Text Capable", channel_id)
        return

    try:
        embed = giveaway_embed(giveaway)
        view = GiveawayView(giveaway.open_giveaway_url)
        await channel.send(embed=embed, view=view)
        await repo.mark_notified(guild_id, str(giveaway.id))

    except discord.HTTPException:
        log.exception(
            "Failed To Send Startup Giveaway %s To Guild %s Channel %s",
            giveaway.id,
            guild_id,
            channel_id,
        )
