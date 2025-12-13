from __future__ import annotations

import logging
from typing import List, Optional

import discord
from discord import OptionChoice
from discord.ext import commands

from ..db import SettingsRepository
from ..embeds import giveaway_embed
from ..pagination import EmbedPaginator
from ..gamerpower import GamerPowerClient, Giveaway

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


class FreeGamesCog(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

        self.repo: SettingsRepository = bot.repo
        self.api: GamerPowerClient = bot.api_client

    freegames = discord.SlashCommandGroup("freegames", "Free games utilities")

    @freegames.command(
        description="Set The Channel For Giveaway Notifications",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    @discord.default_permissions(manage_guild=True)
    @discord.option(
        "channel",
        description="Channel For Giveaway Notifications",
        type=discord.TextChannel,
    )
    async def set_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
    ) -> None:
        assert ctx.guild_id, "Guild-only Command"
        await self.repo.set_guild_channel(ctx.guild_id, channel.id)
        await ctx.respond(
            f"Got It! New Giveaways Will Be Posted In {channel.mention}.",
            ephemeral=True,
        )

    @freegames.command(
        description="Show Where Giveaways Will Be Posted",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def status(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild_id is None:
            await ctx.respond(
                "This Command Can Only Be Used In Servers.", ephemeral=True
            )
            return
        channel_id = await self.repo.get_guild_channel(ctx.guild_id)

        if not channel_id:
            await ctx.respond(
                "No Channel Configured. Use /freegames set-channel First.",
                ephemeral=True,
            )
            return

        channel = ctx.guild.get_channel(channel_id) if ctx.guild else None
        mention = channel.mention if channel else f"`{channel_id}`"
        guilds, notified = await self.repo.dump_state()

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
    @discord.option(
        "platform",
        input_type=str,
        description="Filter by platform",
        choices=PLATFORM_CHOICES,
        required=False,
    )
    @discord.option(
        "type_",
        input_type=str,
        description="Filter by type",
        choices=TYPE_CHOICES,
        required=False,
    )
    @discord.option(
        "sort_by",
        input_type=str,
        description="Sort results",
        choices=SORT_CHOICES,
        default="date",
        required=False,
    )
    async def list(
        self,
        ctx: discord.ApplicationContext,
        platform: str = None,
        type_: str = None,
        sort_by: str = "date",
    ) -> None:
        await ctx.defer()

        giveaways = await self._fetch_giveaways(ctx, platform, type_, sort_by)
        if not giveaways:
            await ctx.respond("No Giveaways Found Right Now. Try Again Later.")
            return

        embeds = self._chunked_embeds(giveaways)
        urls = [g.open_giveaway_url or None for g in giveaways]

        view = EmbedPaginator(embeds, user_id=ctx.user.id, urls=urls)
        await ctx.respond(embed=embeds[0], view=view)
        view.message = await ctx.interaction.original_response()

    @freegames.command(
        description="Lookup A Specific Giveaway By Id",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    @discord.option(
        "giveaway_id", input_type=int, description="Giveaway ID", min_value=1
    )
    async def lookup(
        self,
        ctx: discord.ApplicationContext,
        giveaway_id: int,
    ) -> None:
        await ctx.defer()
        giveaway = await self.api.fetch_giveaway(giveaway_id)
        if not giveaway:
            await ctx.respond(f"No Giveaway Found For ID {giveaway_id}.")
            return
        await ctx.respond(embed=giveaway_embed(giveaway))

    @freegames.command(
        description="Total Live Giveaways And Estimated Worth",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    @discord.option(
        "platform",
        input_type=str,
        description="Filter by platform",
        choices=PLATFORM_CHOICES,
        required=False,
    )
    @discord.option(
        "type_",
        input_type=str,
        description="Filter by type",
        choices=TYPE_CHOICES,
        required=False,
    )
    async def worth(
        self,
        ctx: discord.ApplicationContext,
        platform: str = None,
        type_: str = None,
    ) -> None:
        await ctx.defer()

        data = await self.api.fetch_worth(platform=platform, type_=type_)

        if not data:
            await ctx.respond("Worth Endpoint Returned Nothing.")
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
        if platform:
            embed.add_field(name="Platform", value=platform, inline=True)
        if type_:
            embed.add_field(name="Type", value=type_, inline=True)
        await ctx.respond(embed=embed)

    @freegames.command(
        description="Show Help For FreeGames Commands",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def help(self, ctx: discord.ApplicationContext) -> None:
        embed = discord.Embed(
            title="FreeGames Bot Help",
            description="Discover free games and loot with GamerPower API commands.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="/freegames set-channel <channel>",
            value="Set the channel where giveaway notifications will be posted. Requires manage guild permission.",
            inline=False,
        )
        embed.add_field(
            name="/freegames status",
            value="Show the configured notification channel and stats.",
            inline=False,
        )
        embed.add_field(
            name="/freegames list [platform] [type] [sort-by]",
            value="List current giveaways with optional filters. Platforms: pc, steam, etc. Types: game, loot, beta. Sort: date, value, popularity.",
            inline=False,
        )
        embed.add_field(
            name="/freegames lookup <giveaway_id>",
            value="Get details for a specific giveaway by ID.",
            inline=False,
        )
        embed.add_field(
            name="/freegames worth [platform] [type]",
            value="Show total live giveaways and estimated worth in USD.",
            inline=False,
        )
        embed.set_footer(text="Powered by GamerPower API")
        await ctx.respond(embed=embed)

    async def _fetch_giveaways(
        self,
        ctx: discord.ApplicationContext,
        platform: Optional[str],
        type_: Optional[str],
        sort_by: Optional[str],
    ) -> List[Giveaway]:
        try:
            return await self.api.fetch_giveaways(
                platform=platform, type_=type_, sort_by=sort_by
            )
        except Exception:
            log.exception("Failed To Fetch Giveaways")
            await ctx.respond("Could Not Reach GamerPower Right Now.", ephemeral=True)

            return []

    def _chunked_embeds(self, giveaways: List[Giveaway]) -> List[discord.Embed]:
        embeds = []
        for g in giveaways:
            embed = discord.Embed(
                title=g.title,
                description=f"Platforms: {g.platforms}\nType: {g.type} | Worth: {g.worth}",
                color=discord.Color.blurple(),
            )
            if g.image:
                embed.set_image(url=g.image)
            embed.set_footer(text=f"ID: {g.id}")
            embeds.append(embed)
        return embeds


def setup(bot: commands.Bot) -> None:
    bot.add_cog(FreeGamesCog(bot))
