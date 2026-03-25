from __future__ import annotations

import re
import logging
from typing import List, Optional

import discord
from discord import OptionChoice
from discord.ext import commands

from ..db import ArchiveEntry, SettingsRepository
from ..embeds import giveaway_embed
from ..gamerpower import GamerPowerClient, Giveaway
from ..pagination import EmbedPaginator

log = logging.getLogger(__name__)

PLATFORM_CHOICES = [
    OptionChoice("PC", "pc"),
    OptionChoice("Steam", "steam"),
    OptionChoice("GOG", "gog"),
    OptionChoice("Origin", "origin"),
    OptionChoice("Ubisoft", "ubisoft"),
    OptionChoice("Itch.io", "itchio"),
    OptionChoice("DRM-Free", "drm-free"),
    OptionChoice("Epic Games Store", "epic-games-store"),
    OptionChoice("Battle.net", "battlenet"),
    OptionChoice("Android", "android"),
    OptionChoice("iOS", "ios"),
    OptionChoice("PS4", "ps4"),
    OptionChoice("PS5", "ps5"),
    OptionChoice("Xbox One", "xbox-one"),
    OptionChoice("Xbox Series X/S", "xbox-series-xs"),
    OptionChoice("Nintendo Switch", "switch"),
]

TYPE_CHOICES = [
    OptionChoice("Game", "game"),
    OptionChoice("Loot", "loot"),
    OptionChoice("Beta", "beta"),
]

SORT_CHOICES = [
    OptionChoice("Date", "date"),
    OptionChoice("Value", "value"),
    OptionChoice("Popularity", "popularity"),
]

PING_CHOICES = [
    OptionChoice("Off", "off"),
    OptionChoice("Here", "here"),
    OptionChoice("Everyone", "everyone"),
    OptionChoice("Role", "role"),
    OptionChoice("User", "user"),
]

PLAY_STATUS_CHOICES = [
    OptionChoice("Played", "played"),
    OptionChoice("Playing", "playing"),
    OptionChoice("Completed", "completed"),
    OptionChoice("Dropped", "dropped"),
    OptionChoice("Wishlist", "wishlist"),
]


class FreeGamesCog(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.repo: SettingsRepository = bot.repo
        self.api: GamerPowerClient = bot.api_client

    freegames = discord.SlashCommandGroup("freegames", "Free games utilities")
    settings = freegames.create_subgroup("settings", "Server settings")
    played = freegames.create_subgroup("played", "Track played games per server")

    @settings.command(name="channel", description="Set the channel for giveaway notifications")
    @discord.default_permissions(manage_guild=True)
    @discord.option("channel", description="Channel for giveaway notifications", type=discord.TextChannel)
    async def set_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
    ) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        await self.repo.set_guild_channel(guild_id, channel.id)
        await ctx.respond(
            f"Notifications will be sent to {channel.mention}.",
            ephemeral=True,
        )

    @settings.command(name="ping", description="Configure ping behavior for new giveaway posts")
    @discord.default_permissions(manage_guild=True)
    @discord.option("mode", input_type=str, description="Ping mode", choices=PING_CHOICES)
    @discord.option("role", description="Role to ping when mode is role", required=False, type=discord.Role)
    @discord.option("user", description="User to ping when mode is user", required=False, type=discord.Member)
    async def set_ping(
        self,
        ctx: discord.ApplicationContext,
        mode: str,
        role: Optional[discord.Role] = None,
        user: Optional[discord.Member] = None,
    ) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        target_id: Optional[int] = None
        if mode == "role":
            if role is None:
                await ctx.respond("Pick a role when using `role` ping mode.", ephemeral=True)
                return
            target_id = role.id
        elif mode == "user":
            if user is None:
                await ctx.respond("Pick a user when using `user` ping mode.", ephemeral=True)
                return
            target_id = user.id

        await self.repo.set_ping_settings(guild_id, mode, target_id)
        await ctx.respond("Ping settings updated.", ephemeral=True)

    @settings.command(name="filters", description="Optional server filters for automatic giveaway posts")
    @discord.default_permissions(manage_guild=True)
    @discord.option("platform", input_type=str, description="Only post for a platform", choices=PLATFORM_CHOICES, required=False)
    @discord.option("type_", input_type=str, description="Only post a giveaway type", choices=TYPE_CHOICES, required=False)
    async def set_filters(
        self,
        ctx: discord.ApplicationContext,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
    ) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        await self.repo.set_filters(guild_id, platform, type_)
        await ctx.respond("Server filters updated.", ephemeral=True)

    @settings.command(name="status", description="Show the current server configuration")
    async def settings_status(self, ctx: discord.ApplicationContext) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        guild_settings = await self.repo.get_guild_settings(guild_id)
        if guild_settings is None:
            await ctx.respond("This server is not configured yet.", ephemeral=True)
            return

        channel = ctx.guild.get_channel(guild_settings.channel_id) if ctx.guild and guild_settings.channel_id else None
        channel_value = channel.mention if channel else (f"`{guild_settings.channel_id}`" if guild_settings.channel_id else "Not set")

        if guild_settings.ping_mode in {"role", "user"} and guild_settings.ping_target_id:
            target_prefix = "@&" if guild_settings.ping_mode == "role" else "@"
            ping_value = f"{guild_settings.ping_mode} (<{target_prefix}{guild_settings.ping_target_id}>)"
        else:
            ping_value = guild_settings.ping_mode

        guilds, notified, archived, played = await self.repo.dump_state()

        embed = discord.Embed(
            title="FreeGames Settings",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Channel", value=channel_value, inline=False)
        embed.add_field(name="Ping", value=ping_value, inline=True)
        embed.add_field(name="Platform Filter", value=guild_settings.platform_filter or "Any", inline=True)
        embed.add_field(name="Type Filter", value=guild_settings.type_filter or "Any", inline=True)
        embed.add_field(name="Tracked Servers", value=str(guilds), inline=True)
        embed.add_field(name="Sent Notifications", value=str(notified), inline=True)
        embed.add_field(name="Archived Giveaways", value=str(archived), inline=True)
        embed.add_field(name="Played Entries", value=str(played), inline=True)
        await ctx.respond(embed=embed, ephemeral=True)

    @freegames.command(description="List current giveaways with optional filters")
    @discord.option("platform", input_type=str, description="Filter by platform", choices=PLATFORM_CHOICES, required=False)
    @discord.option("type_", input_type=str, description="Filter by type", choices=TYPE_CHOICES, required=False)
    @discord.option("sort_by", input_type=str, description="Sort results", choices=SORT_CHOICES, default="date", required=False)
    async def list(
        self,
        ctx: discord.ApplicationContext,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
        sort_by: str = "date",
    ) -> None:
        await ctx.defer()
        giveaways = await self._fetch_giveaways(platform, type_, sort_by)
        if not giveaways:
            await ctx.followup.send("No giveaways found right now.")
            return

        await self._respond_with_giveaway_pages(ctx, giveaways)

    @freegames.command(description="Lookup a specific giveaway by id")
    @discord.option("giveaway_id", input_type=int, description="Giveaway ID", min_value=1)
    async def lookup(self, ctx: discord.ApplicationContext, giveaway_id: int) -> None:
        await ctx.defer()
        giveaway = await self.api.fetch_giveaway(giveaway_id)
        if not giveaway:
            await ctx.followup.send(f"No giveaway found for ID `{giveaway_id}`.")
            return

        await self.repo.archive_giveaways([giveaway])
        await ctx.followup.send(embed=giveaway_embed(giveaway))

    @freegames.command(description="Total live giveaways and estimated worth")
    @discord.option("platform", input_type=str, description="Filter by platform", choices=PLATFORM_CHOICES, required=False)
    @discord.option("type_", input_type=str, description="Filter by type", choices=TYPE_CHOICES, required=False)
    async def worth(
        self,
        ctx: discord.ApplicationContext,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
    ) -> None:
        await ctx.defer()
        data = await self.api.fetch_worth(platform=platform, type_=type_)
        if not data:
            await ctx.followup.send("Worth endpoint returned no data.")
            return

        total = (
            data.get("active_giveaways_number")
            or data.get("total")
            or data.get("active_giveaways")
            or 0
        )
        worth_value = (
            data.get("worth_estimation_usd")
            or data.get("worth")
            or data.get("estimated_worth")
            or "$0"
        )

        embed = discord.Embed(
            title="Live Giveaways Summary",
            color=discord.Color.blurple(),
            description=data.get("description", ""),
        )
        embed.add_field(name="Total", value=str(total), inline=True)
        embed.add_field(name="Worth (USD)", value=str(worth_value), inline=True)
        embed.add_field(name="Platform", value=platform or "Any", inline=True)
        embed.add_field(name="Type", value=type_ or "Any", inline=True)
        await ctx.followup.send(embed=embed)

    @freegames.command(description="Search the archived game database")
    @discord.option("query", description="Title, platform, or keyword to search for")
    async def search(self, ctx: discord.ApplicationContext, query: str) -> None:
        await ctx.defer()
        results = await self.repo.search_archive(query, limit=10)
        if not results:
            giveaways = await self._fetch_giveaways(sort_by="date")
            await self.repo.archive_giveaways(giveaways)
            results = await self.repo.search_archive(query, limit=10)

        if not results:
            await ctx.followup.send(f"No archived games matched `{query}`.")
            return

        embeds = [self._archive_embed(entry) for entry in results]
        urls = [entry.open_giveaway_url for entry in results]
        view = EmbedPaginator(embeds, user_id=ctx.user.id, urls=urls)
        await ctx.followup.send(embed=embeds[0], view=view)

    @freegames.command(description="Show recent game and giveaway feed entries")
    @discord.option("platform", input_type=str, description="Filter by platform", choices=PLATFORM_CHOICES, required=False)
    @discord.option("type_", input_type=str, description="Filter by type", choices=TYPE_CHOICES, required=False)
    async def news(
        self,
        ctx: discord.ApplicationContext,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
    ) -> None:
        await ctx.defer()
        entries = await self.repo.recent_archive(limit=10, platform=platform, type_=type_)
        if not entries:
            giveaways = await self._fetch_giveaways(platform=platform, type_=type_, sort_by="date")
            await self.repo.archive_giveaways(giveaways)
            entries = await self.repo.recent_archive(limit=10, platform=platform, type_=type_)

        if not entries:
            await ctx.followup.send("No recent archive entries are available yet.")
            return

        embeds = [self._archive_embed(entry, include_summary=True) for entry in entries]
        urls = [entry.open_giveaway_url for entry in entries]
        view = EmbedPaginator(embeds, user_id=ctx.user.id, urls=urls)
        await ctx.followup.send(embed=embeds[0], view=view)

    @played.command(name="add", description="Track a game you played or want to track")
    @discord.option("title", description="Game title")
    @discord.option("platform", input_type=str, description="Platform", choices=PLATFORM_CHOICES, required=False)
    @discord.option("status", input_type=str, description="Play status", choices=PLAY_STATUS_CHOICES, default="played")
    @discord.option("notes", description="Short note", required=False)
    async def played_add(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        platform: Optional[str] = None,
        status: str = "played",
        notes: str = "",
    ) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        game_key = self._slugify(title)
        await self.repo.upsert_played_game(
            guild_id=guild_id,
            user_id=ctx.user.id,
            game_key=game_key,
            game_title=title.strip(),
            platform=platform or "",
            status=status,
            notes=notes.strip(),
        )
        await ctx.respond(f"Saved `{title}` to your played list.", ephemeral=True)

    @played.command(name="remove", description="Remove a tracked game from your list")
    @discord.option("title", description="Game title")
    async def played_remove(self, ctx: discord.ApplicationContext, title: str) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        removed = await self.repo.remove_played_game(
            guild_id=guild_id,
            user_id=ctx.user.id,
            game_key=self._slugify(title),
        )
        if not removed:
            await ctx.respond(f"`{title}` was not in your played list.", ephemeral=True)
            return

        await ctx.respond(f"Removed `{title}` from your played list.", ephemeral=True)

    @played.command(name="list", description="Show a user's tracked games")
    @discord.option("member", description="Whose tracked games to show", required=False, type=discord.Member)
    async def played_list(
        self,
        ctx: discord.ApplicationContext,
        member: Optional[discord.Member] = None,
    ) -> None:
        guild_id = await self._require_guild(ctx)
        if guild_id is None:
            return

        target = member or ctx.user
        entries = await self.repo.list_played_games(guild_id, target.id, limit=25)
        if not entries:
            await ctx.respond(f"{target.mention} has no tracked games yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{target.display_name}'s Played Games",
            color=discord.Color.green(),
        )
        for entry in entries[:10]:
            details = f"Status: {entry.status}"
            if entry.platform:
                details += f"\nPlatform: {entry.platform}"
            if entry.notes:
                details += f"\nNotes: {entry.notes[:120]}"
            embed.add_field(name=entry.game_title, value=details, inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

    @freegames.command(description="Show help for the bot")
    async def help(self, ctx: discord.ApplicationContext) -> None:
        embed = discord.Embed(
            title="FreeGames Bot Help",
            description="GamerPower-powered giveaway alerts, archive search, and player tracking.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="/freegames settings channel",
            value="Set the server channel for automatic giveaway notifications.",
            inline=False,
        )
        embed.add_field(
            name="/freegames settings ping",
            value="Choose whether automatic posts ping nobody, here, everyone, a role, or one user.",
            inline=False,
        )
        embed.add_field(
            name="/freegames settings filters",
            value="Restrict automatic posts to one platform and/or one giveaway type.",
            inline=False,
        )
        embed.add_field(
            name="/freegames list | lookup | worth",
            value="Inspect GamerPower live data on demand.",
            inline=False,
        )
        embed.add_field(
            name="/freegames search | news",
            value="Search the archived game database or browse recent entries like a news feed.",
            inline=False,
        )
        embed.add_field(
            name="/freegames played add | list | remove",
            value="Track games you played, completed, dropped, or want to revisit.",
            inline=False,
        )
        embed.set_footer(text="Powered by GamerPower")
        await ctx.respond(embed=embed, ephemeral=True)

    async def _fetch_giveaways(
        self,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> List[Giveaway]:
        try:
            giveaways = await self.api.fetch_giveaways(
                platform=platform,
                type_=type_,
                sort_by=sort_by,
            )
            await self.repo.archive_giveaways(giveaways)
            return giveaways
        except Exception:
            log.exception("Failed to fetch giveaways")
            return []

    async def _respond_with_giveaway_pages(
        self,
        ctx: discord.ApplicationContext,
        giveaways: List[Giveaway],
    ) -> None:
        embeds = [giveaway_embed(giveaway) for giveaway in giveaways]
        urls = [giveaway.open_giveaway_url for giveaway in giveaways]
        view = EmbedPaginator(embeds, user_id=ctx.user.id, urls=urls)
        await ctx.followup.send(embed=embeds[0], view=view)

    def _archive_embed(
        self,
        entry: ArchiveEntry,
        include_summary: bool = False,
    ) -> discord.Embed:
        description = entry.description[:900] if include_summary else None
        embed = discord.Embed(
            title=entry.title,
            url=entry.open_giveaway_url,
            description=description,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Platforms", value=entry.platforms or "Unknown", inline=True)
        embed.add_field(name="Type", value=entry.type or "Unknown", inline=True)
        embed.add_field(name="Worth", value=entry.worth or "N/A", inline=True)
        embed.add_field(name="Status", value=entry.status or "Unknown", inline=True)
        embed.add_field(name="Published", value=entry.published_date or "Unknown", inline=True)
        embed.add_field(name="Ends", value=entry.end_date or "Unknown", inline=True)
        embed.set_footer(text=f"Archive ID: {entry.giveaway_id}")
        return embed

    async def _require_guild(self, ctx: discord.ApplicationContext) -> Optional[int]:
        if ctx.guild_id is None:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return None
        return ctx.guild_id

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]


def setup(bot: commands.Bot) -> None:
    bot.add_cog(FreeGamesCog(bot))
