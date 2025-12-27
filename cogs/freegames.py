import discord
from discord.ext import commands
import traceback

import componenets.cog_commands.freegames.giveaway_command

from utilities.gamespowered import (
    get_giveaway,
    get_all_giveaways,
    get_filtered_giveaways,
)


class FreeGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="giveaway", description="Get Details Of A Specific Giveaway"
    )
    async def giveaway(self, ctx, giveaway_id: str):
        await ctx.defer()

        try:
            data = await get_giveaway(giveaway_id)

            if not data:
                data = None

                await ctx.followup.send(
                    view=componenets.cog_commands.freegames.giveaway_command.GiveawayView(
                        giveaway_data=data, giveaway_id=giveaway_id
                    )
                )

            else:
                await ctx.followup.send(
                    view=componenets.cog_commands.freegames.giveaway_command.GiveawayView(
                        giveaway_data=data, giveaway_id=giveaway_id
                    )
                )

        except Exception as e:
            print(traceback.format_exc())
            try:
                await ctx.followup.send(
                    view=componenets.cog_commands.freegames.giveaway_command.GiveawayView(
                        giveaway_data=None, giveaway_id=giveaway_id, error=str(e)
                    )
                )
            except Exception as e2:
                print(f"Error sending error view: {e2}")
                print(traceback.format_exc())
                await ctx.followup.send(f"Error: {e}")

    @discord.slash_command(
        name="giveaways",
        description="Get all live giveaways, optionally filtered",
    )
    async def giveaways(
        self,
        ctx,
        platform: str = discord.Option(
            description="Platform filter (single or comma-separated)",
            required=False,
            default=None,
        ),
        type_: str = discord.Option(
            description="Type filter (single or comma-separated)",
            required=False,
            default=None,
        ),
        sort_by: str = discord.Option(
            description="Sort by",
            choices=["date", "value", "popularity"],
            required=False,
            default=None,
        ),
    ):
        await ctx.defer()
        try:
            # Check if multiple filters (comma-separated)
            plat_list = platform.split(",") if platform and "," in platform else None
            type_list = type_.split(",") if type_ and "," in type_ else None

            if plat_list or type_list:
                # Use filtered API
                data = await get_filtered_giveaways(plat_list, type_list)
            else:
                # Use standard API
                data = await get_all_giveaways(platform, type_, sort_by)

            if not data:
                await ctx.followup.send("No giveaways found.")
                return

            # Limit to first 5 for brevity
            giveaways = data[:5]
            embed = discord.Embed(
                title="Live Giveaways",
                description=f"Showing {len(giveaways)} of {len(data)} giveaways",
                color=discord.Color.green(),
            )
            for gw in giveaways:
                embed.add_field(
                    name=gw.get("title", "Unknown"),
                    value=f"Worth: ${gw.get('worth', 'N/A')} | [Link]({gw.get('open_giveaway_url', '#')})",
                    inline=False,
                )

            await ctx.followup.send(embed=embed)
        except Exception as e:
            print(traceback.format_exc())
            await ctx.followup.send(f"Error fetching giveaways: {e}")


def setup(bot):
    bot.add_cog(FreeGames(bot))
