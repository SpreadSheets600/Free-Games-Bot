from __future__ import annotations

import os
import psutil
import platform
import datetime as dt

import discord
from discord.ext import commands

from ..config import settings


def _format_timedelta(delta: dt.timedelta) -> str:
    total_seconds = int(delta.total_seconds())

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    parts = []

    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")

    parts.append(f"{seconds}s")
    return " ".join(parts)


def _format_iso(ts: str | None) -> str:
    if not ts:
        return "Never"

    try:
        parsed = dt.datetime.fromisoformat(ts)
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts


class DevCog(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.repo = bot.repo

    dev = discord.SlashCommandGroup("dev", "Developer utilities")

    @dev.command(description="Developer-only bot status snapshot")
    async def status(self, ctx: discord.ApplicationContext) -> None:
        allowed_ids = {settings.developer_user_id, getattr(self.bot, "owner_id", None)}
        allowed_ids.discard(None)

        if allowed_ids and ctx.user.id not in allowed_ids:
            await ctx.respond(
                "You Are not Allowed To Use This Command.", ephemeral=True
            )
            return

        process = psutil.Process(os.getpid())
        cpu = psutil.cpu_percent(interval=None)

        mem_bytes = process.memory_info().rss
        mem_mb = mem_bytes / (1024 * 1024)

        uptime = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc) - getattr(
            self.bot, "start_time", dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        )

        last_rss_check = await self.repo.get_bot_state("last_giveaway_check")
        last_status_link = await self.repo.get_bot_state("last_status_message_url")

        embed = discord.Embed(
            title="Bot Health",
            description="Resource Usage And RSS Status Information",
            color=discord.Color.brand_green(),
        )

        embed.add_field(name="CPU load", value=f"{cpu:.1f}%", inline=False)
        embed.add_field(name="Memory", value=f"{mem_mb:.1f} MB", inline=True)
        embed.add_field(name="Uptime", value=_format_timedelta(uptime), inline=True)
        embed.add_field(
            name="Configured Feeds", value=str(len(getattr(settings, "rss_feeds", []))), inline=False
        )
        embed.add_field(
            name="Last API Check", value=_format_iso(last_rss_check), inline=False
        )
        embed.add_field(
            name="Last Status Message",
            value=last_status_link or "Not Saved Yet",
            inline=False,
        )
        embed.set_footer(text=f"Host : {platform.node()} • PID {os.getpid()}")

        await ctx.respond(embed=embed)
        message = await ctx.interaction.original_response()
        await self.repo.set_bot_state("last_status_message_url", message.jump_url)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(DevCog(bot))
