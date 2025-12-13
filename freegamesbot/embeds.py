from __future__ import annotations

import datetime as dt

import discord

from .gamerpower import Giveaway


def _format_discord_time(value: str | None) -> str:
    if not value or value.lower() == "n/a":
        return "Unknown"

    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return f"<t:{int(parsed.timestamp())}:R>"

    except Exception:
        return value or "Unknown"


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

    embed.add_field(
        name="Status", value=str(getattr(giveaway, "status", "?")), inline=True
    )
    embed.add_field(
        name="Ends In", value=_format_discord_time(giveaway.end_date), inline=True
    )
    embed.add_field(
        name="Started",
        value=_format_discord_time(giveaway.published_date),
        inline=True,
    )
    embed.add_field(
        name="How To Claim",
        value=giveaway.instructions[:512] or "See Link",
        inline=False,
    )

    if giveaway.image:
        embed.set_image(url=giveaway.image)

    elif getattr(giveaway, "thumbnail", None):
        embed.set_thumbnail(url=giveaway.thumbnail)

    embed.set_footer(text=f"ID: {giveaway.id}")
    return embed


class GiveawayView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        open_url = url
        if url.startswith("https://www.gamerpower.com/") and "/open/" not in url:
            open_url = url.replace(
                "https://www.gamerpower.com/", "https://www.gamerpower.com/open/", 1
            )
        self.add_item(
            discord.ui.Button(
                label="Claim Giveaway",
                style=discord.ButtonStyle.link,
                url=open_url,
            )
        )


class RssView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        if url.startswith("https://www.gamerpower.com/"):
            open_url = url.replace(
                "https://www.gamerpower.com/", "https://www.gamerpower.com/open/", 1
            )
        else:
            open_url = url
        self.add_item(
            discord.ui.Button(
                label="Claim Giveaway",
                style=discord.ButtonStyle.link,
                url=open_url,
            )
        )
