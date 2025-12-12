from __future__ import annotations

import logging
import asyncio
import datetime
from typing import List, Optional

import discord
from discord import Option
from discord.ext import tasks

from .config import settings
from .db import SettingsRepository
from .embeds import giveaway_embed
from .pagination import EmbedPaginator
from .gamerpower import GamerPowerClient, Giveaway

log = logging.getLogger(__name__)

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

repo = SettingsRepository(settings.db_path)
api_client = GamerPowerClient(settings.gamerpower_base_url)

start_time: datetime.datetime | None = None

repo_connected = False
startup_notified = False
skip_initial_notify = False


PLATFORM_CHOICES = [
    "pc",
    "steam",
    "epic-games-store",
    "gog",
    "origin",
    "ubisoft",
    "itchio",
    "drm-free",
    "battlenet",
    "android",
    "ios",
    "ps4",
    "ps5",
    "xbox-one",
    "xbox-series-xs",
    "switch",
]

TYPE_CHOICES = ["game", "loot", "beta"]
SORT_CHOICES = ["date", "value", "popularity"]


@bot.event
async def on_ready() -> None:
    global start_time, repo_connected, startup_notified

    if not repo_connected:
        await repo.connect()
        repo_connected = True

    await bot.sync_commands(force=True)

    if not giveaway_poll.is_running():
        giveaway_poll.start()

    start_time = datetime.datetime.utcnow()
    await bot.change_presence(activity=discord.Game(name="Free Games Tracking!"))

    commands_count = 0
    for command in bot.walk_application_commands():
        commands_count += 1
        log.info("Loaded Command : %s", command.name)

    log.info("Loaded %s Commands | %s Cogs", commands_count, len(bot.cogs))

    if not startup_notified:
        startup_notified = True
        skip_initial_notify = True
        await _startup_confirmation()


@tasks.loop(seconds=settings.poll_interval_seconds)
async def giveaway_poll() -> None:
    await bot.wait_until_ready()
    await _notify_new_giveaways()


async def _notify_new_giveaways() -> None:
    global skip_initial_notify

    if skip_initial_notify:
        skip_initial_notify = False
        log.info("Skipping initial giveaway notification after startup confirmation")
        return
    try:
        giveaways = await api_client.fetch_giveaways(sort_by="date")
    except Exception:
        log.exception("Failed To Fetch Giveaways")
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

    try:
        giveaways = await api_client.fetch_giveaways(sort_by="date")
    except Exception:
        log.exception("Startup Confirmation Fetch Failed")
        return

    if not giveaways:
        return

    latest = giveaways[0]
    for guild_cfg in guilds:
        await _send_startup_latest(guild_cfg.guild_id, guild_cfg.channel_id, latest)


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

    new_items = []
    for giveaway in giveaways:
        if not await repo.already_notified(guild_id, giveaway.id):
            new_items.append(giveaway)

    if not new_items:
        return

    keep_ids = [g.id for g in giveaways][:200]
    await repo.prune_notified(guild_id, keep_ids)

    for giveaway in new_items:
        try:
            await channel.send(embed=giveaway_embed(giveaway))
            await repo.mark_notified(guild_id, giveaway.id)

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
        await channel.send(embed=giveaway_embed(giveaway))
        await repo.mark_notified(guild_id, giveaway.id)

    except discord.HTTPException:
        log.exception(
            "Failed To Send Startup Giveaway %s To Guild %s Channel %s",
            giveaway.id,
            guild_id,
            channel_id,
        )


freegames = discord.SlashCommandGroup("freegames", "Free Games Utilities")


@freegames.command(
    description="Set The Channel Where Giveaways Will Be Posted",
    integration_types={
        discord.IntegrationType.guild_install,
        discord.IntegrationType.user_install,
    },
)
@discord.default_permissions(manage_guild=True)
async def set_channel(
    ctx: discord.ApplicationContext,
    channel: discord.TextChannel = Option(
        discord.TextChannel, "Channel For Giveaway Notifications"
    ),
) -> None:
    assert ctx.guild_id, "Guild-only command"

    await repo.set_guild_channel(ctx.guild_id, channel.id)
    await ctx.respond(
        f"Got It! New Giveaways Will Be Posted In {channel.mention}.", ephemeral=True
    )


@freegames.command(
    description="Show Where Giveaways Will Be Posted",
    integration_types={
        discord.IntegrationType.guild_install,
        discord.IntegrationType.user_install,
    },
)
async def status(ctx: discord.ApplicationContext) -> None:
    if ctx.guild_id is None:
        await ctx.respond("This Command Can Only Be Used In Servers.", ephemeral=True)
        return
    channel_id = await repo.get_guild_channel(ctx.guild_id)

    if not channel_id:
        await ctx.respond(
            "No Channel Configured. Use /freegames set-channel First.", ephemeral=True
        )
        return

    channel = ctx.guild.get_channel(channel_id) if ctx.guild else None
    mention = channel.mention if channel else f"`{channel_id}`"
    guilds, notified = await repo.dump_state()

    await ctx.respond(
        f"Posting Giveaways To {mention}. Tracked Guilds : {guilds}, Sent Items : {notified}.",
        ephemeral=True,
    )


@freegames.command(
    description="List Current Giveaways With Optional Filters",
    integration_types={
        discord.IntegrationType.guild_install,
        discord.IntegrationType.user_install,
    },
)
async def list(
    ctx: discord.ApplicationContext,
    platform: str = Option(
        str, "Filter By Platform", choices=PLATFORM_CHOICES, default=None
    ),
    type_: str = Option(str, "Filter By Type", choices=TYPE_CHOICES, default=None),
    sort_by: str = Option(str, "Sort Results", choices=SORT_CHOICES, default="date"),
) -> None:
    await ctx.defer()

    giveaways = await _fetch_giveaways(ctx, platform, type_, sort_by)

    if not giveaways:
        await ctx.respond("No Giveaways Found Right Now. Try Again Later.")
        return

    embeds = _chunked_embeds(giveaways)
    if len(embeds) == 1:
        await ctx.respond(embed=embeds[0])
        return

    view = EmbedPaginator(embeds, user_id=ctx.user.id)
    await ctx.respond(embed=embeds[0], view=view)

    view.message = await ctx.interaction.original_response()


@freegames.command(
    description="Lookup A Specific Giveaway By Id",
    integration_types={
        discord.IntegrationType.guild_install,
        discord.IntegrationType.user_install,
    },
)
async def lookup(
    ctx: discord.ApplicationContext,
    giveaway_id: int = Option(int, "Giveaway Id", min_value=1),
) -> None:
    await ctx.defer()
    giveaway = await api_client.fetch_giveaway(giveaway_id)

    if not giveaway:
        await ctx.respond(f"No Giveaway Found For Id {giveaway_id}.")
        return

    await ctx.respond(embed=giveaway_embed(giveaway))


@freegames.command(
    description="Total Live Giveaways And Estimated Worth",
    integration_types={
        discord.IntegrationType.guild_install,
        discord.IntegrationType.user_install,
    },
)
async def worth(
    ctx: discord.ApplicationContext,
    platform: str = Option(
        str, "Filter By Platform", choices=PLATFORM_CHOICES, default=None
    ),
    type_: str = Option(str, "Filter By Type", choices=TYPE_CHOICES, default=None),
) -> None:
    await ctx.defer()
    data = await api_client.fetch_worth(platform=platform, type_=type_)

    if not data:
        await ctx.respond("Worth Endpoint Returned Nothing.")
        return

    embed = discord.Embed(
        title="Live Giveaways Summary",
        color=discord.Color.blurple(),
        description=data.get("description", ""),
    )
    embed.add_field(name="Total", value=str(data.get("total", "?")), inline=True)
    embed.add_field(name="Worth (USD)", value=str(data.get("worth", "?")), inline=True)

    if platform:
        embed.add_field(name="Platform", value=platform, inline=True)

    if type_:
        embed.add_field(name="Type", value=type_, inline=True)

    await ctx.respond(embed=embed)


bot.add_application_command(freegames)


async def _fetch_giveaways(
    ctx: discord.ApplicationContext,
    platform: Optional[str],
    type_: Optional[str],
    sort_by: Optional[str],
) -> List[Giveaway]:
    try:
        return await api_client.fetch_giveaways(
            platform=platform, type_=type_, sort_by=sort_by
        )
    except Exception:
        log.exception("Failed To Fetch Giveaways")
        await ctx.respond("Could Not Reach GamerPower Right Now.", ephemeral=True)
        return []


def _chunked_embeds(giveaways: List[Giveaway]) -> List[discord.Embed]:
    embeds: List[discord.Embed] = []
    page_size = settings.max_items_per_page

    for i in range(0, len(giveaways), page_size):
        batch = giveaways[i : i + page_size]
        description_parts = []

        for g in batch:
            description_parts.append(
                f"**{g.title}** (ID `{g.id}`)\n"
                f"Platforms: {g.platforms}\n"
                f"Type: {g.type} | Worth: {g.worth}\n"
                f"[Claim here]({g.open_giveaway_url})"
            )
        embed = discord.Embed(
            title="Live Giveaways",
            description="\n\n".join(description_parts),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Page {len(embeds) + 1}")
        embeds.append(embed)

    return embeds
