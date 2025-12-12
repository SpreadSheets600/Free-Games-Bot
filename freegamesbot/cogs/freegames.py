"""Cog providing slash commands for the FreeGames bot."""
from __future__ import annotations

import logging
from typing import List, Optional

import discord
from discord import Option
from discord.ext import commands

from ..config import settings
from ..db import SettingsRepository
from ..embeds import giveaway_embed
from ..gamerpower import GamerPowerClient, Giveaway
from ..pagination import EmbedPaginator

log = logging.getLogger(__name__)

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


class FreeGamesCog(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        # These are injected by the bot during setup
        self.repo: SettingsRepository = bot.repo  # type: ignore[attr-defined]
        self.api: GamerPowerClient = bot.api_client  # type: ignore[attr-defined]

    freegames = discord.SlashCommandGroup("freegames", "Free games utilities")

    @freegames.command(
        description="Set the channel where new giveaways will be posted",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    @discord.default_permissions(manage_guild=True)
    async def set_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: Option(discord.TextChannel, "Channel for giveaway notifications"),
    ) -> None:
        assert ctx.guild_id, "Guild-only command"
        await self.repo.set_guild_channel(ctx.guild_id, channel.id)
        await ctx.respond(
            f"Got it! New giveaways will be posted in {channel.mention}.", ephemeral=True
        )

    @freegames.command(
        description="Show where giveaways will be posted",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def status(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild_id is None:
            await ctx.respond("This command can only be used in servers.", ephemeral=True)
            return
        channel_id = await self.repo.get_guild_channel(ctx.guild_id)
        if not channel_id:
            await ctx.respond(
                "No channel configured. Use /freegames set-channel first.", ephemeral=True
            )
            return
        channel = ctx.guild.get_channel(channel_id) if ctx.guild else None
        mention = channel.mention if channel else f"`{channel_id}`"
        guilds, notified = await self.repo.dump_state()
        await ctx.respond(
            f"Posting giveaways to {mention}. Tracked guilds: {guilds}, sent items: {notified}.",
            ephemeral=True,
        )

    @freegames.command(
        description="List current giveaways with optional filters",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def list(
        self,
        ctx: discord.ApplicationContext,
        platform: Option(str, "Filter by platform", choices=PLATFORM_CHOICES, default=None),
        type_: Option(str, "Filter by type", choices=TYPE_CHOICES, default=None),
        sort_by: Option(str, "Sort results", choices=SORT_CHOICES, default="date"),
    ) -> None:
        await ctx.defer()
        giveaways = await self._fetch_giveaways(ctx, platform, type_, sort_by)
        if not giveaways:
            await ctx.respond("No giveaways found right now. Try again later.")
            return

        embeds = self._chunked_embeds(giveaways)
        if len(embeds) == 1:
            await ctx.respond(embed=embeds[0])
            return

        view = EmbedPaginator(embeds, user_id=ctx.user.id)
        await ctx.respond(embed=embeds[0], view=view)
        view.message = await ctx.interaction.original_response()

    @freegames.command(
        description="Lookup a specific giveaway by id",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def lookup(
        self,
        ctx: discord.ApplicationContext,
        giveaway_id: Option(int, "Giveaway id", min_value=1),
    ) -> None:
        await ctx.defer()
        giveaway = await self.api.fetch_giveaway(giveaway_id)
        if not giveaway:
            await ctx.respond(f"No giveaway found for id {giveaway_id}.")
            return
        await ctx.respond(embed=giveaway_embed(giveaway))

    @freegames.command(
        description="Total live giveaways and estimated worth",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def worth(
        self,
        ctx: discord.ApplicationContext,
        platform: Option(str, "Filter by platform", choices=PLATFORM_CHOICES, default=None),
        type_: Option(str, "Filter by type", choices=TYPE_CHOICES, default=None),
    ) -> None:
        await ctx.defer()
        data = await self.api.fetch_worth(platform=platform, type_=type_)
        if not data:
            await ctx.respond("Worth endpoint returned nothing.")
            return
        embed = discord.Embed(
            title="Live giveaways summary",
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

    async def _fetch_giveaways(
        self,
        ctx: discord.ApplicationContext,
        platform: Optional[str],
        type_: Optional[str],
        sort_by: Optional[str],
    ) -> List[Giveaway]:
        try:
            return await self.api.fetch_giveaways(platform=platform, type_=type_, sort_by=sort_by)
        except Exception:
            log.exception("Failed to fetch giveaways")
            await ctx.respond("Could not reach GamerPower right now.", ephemeral=True)
            return []

    def _chunked_embeds(self, giveaways: List[Giveaway]) -> List[discord.Embed]:
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
                title="Live giveaways",
                description="\n\n".join(description_parts),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"Page {len(embeds) + 1}")
            embeds.append(embed)
        return embeds


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - Discord entrypoint
    await bot.add_cog(FreeGamesCog(bot))
