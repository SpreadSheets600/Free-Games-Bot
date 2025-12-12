from __future__ import annotations

import discord

from .gamerpower import Giveaway


def giveaway_embed(giveaway: Giveaway) -> discord.Embed:
    embed = discord.Embed(
        title=giveaway.title,
        url=giveaway.open_giveaway_url,
        description=giveaway.description[:1000],
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Platforms", value=giveaway.platforms or "Unknown", inline=True
    )
    embed.add_field(name="Type", value=giveaway.type or "?", inline=True)
    embed.add_field(name="Worth", value=giveaway.worth or "N/A", inline=True)
    embed.add_field(name="Ends", value=giveaway.end_date or "Unknown", inline=True)
    embed.add_field(
        name="Published", value=giveaway.published_date or "Unknown", inline=True
    )
    embed.add_field(
        name="How To Claim",
        value=giveaway.instructions[:512] or "See Link",
        inline=False,
    )
    if giveaway.image:
        embed.set_image(url=giveaway.image)

    embed.set_footer(text=f"ID: {giveaway.id}")
    return embed
