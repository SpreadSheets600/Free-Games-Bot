import os
import asyncio
import discord
import datetime
from dotenv import load_dotenv

from components import general_command

load_dotenv()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

intents = discord.Intents.all()
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    print("+------------------------------+")
    print(f"+ {bot.user} ")
    print("+------------------------------+")

    activity = discord.Activity(type=discord.ActivityType.listening, name="Free Games")

    bot.start_time = datetime.datetime.now()
    bot.create_time = discord.utils.format_dt(bot.user.created_at, "R")

    print("----- + Loading Commands + -----")
    print("+------------------------------+")

    commands = 0

    for command in bot.walk_application_commands():
        commands += 1

        print(f"Loaded Command : {command.name}")

    print("+------------------------------+")
    print("------- + Loading Cogs + -------")
    print("+------------------------------+")

    cogs = list(bot.cogs.keys())

    for cog in cogs:
        print(f"Loaded COG : {cog}")

    print("+------------------------------+")

    await bot.change_presence(activity=activity)


@bot.slash_command(name="ping", description="Check Bot's Latency & Uptime")
async def ping(ctx: discord.ApplicationContext) -> None:
    latency = bot.latency * 1000
    uptime = (datetime.datetime.now() - bot.start_time).total_seconds()

    uptime_str = f"- *Uptime* : {str(datetime.timedelta(seconds=uptime)).split('.')[0]}"
    latency_str = f"- *Latency* : {latency:.2f} ms"

    await ctx.respond(
        view=general_command.PingView(uptime=uptime_str, latency=latency_str)
    )


@bot.slash_command(
    name="info", description="Get Information About The Bot And Its User"
)
async def info(ctx: discord.ApplicationContext) -> None:
    await ctx.respond(view=general_command.InfoView(created_at=bot.create_time))


bot.load_extension("cogs.freegames")

bot.run(str(os.getenv("DISCORD_TOKEN")))
