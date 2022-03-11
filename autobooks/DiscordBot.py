import glob
import os
import platform
import sys

import discord
import pandas as pd
from discord.ext import commands

from AutoBooks import web_run, main_run, version, script_dir, parser, csv_path, LOG_FILENAME, logger

# Bot Settings
try:
    token = parser.get("DEFAULT", "discord_bot_token")
except KeyError:
    logger.critical("Bot token field not found in config file, exiting.")
bot = commands.Bot(command_prefix='?')


@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')


@bot.command(name='web')
async def web(ctx):
    # Send starting embed and running web
    embed_start = discord.Embed(title="Running AutoBooks Web. This may take awhile....",
                                description=f"V.{version} \n Logfile: {LOG_FILENAME}", color=0xFFAFCC)
    embed_start.set_image(url="https://raw.githubusercontent.com/ivybowman/AutoBooks/main/img/logo/small_pink.png")
    embed_start.set_footer(text="OS: " + platform.platform() + " Host: " + platform.node())
    await ctx.channel.send(embed=embed_start)
    web_info = ["test-data", "test-data2"]
    web_run()

    # Ending Embed
    embed_end = discord.Embed(title="AutoBooks Web Finished",
                              description="See log info below for details. ErrorCount: " + str(web_info[1]),
                              color=0xFFAFCC)
    embed_end.set_thumbnail(url="https://raw.githubusercontent.com/ivybowman/AutoBooks/main/img/icon_pink.png")
    if web_info[0] != "":
        embed_end.add_field(name="Book List", value=str(web_info[0]), inline=False)
    await ctx.channel.send(embed=embed_end)
    # Logfile fetching
    files = glob.glob(os.path.join(script_dir, "log", "*.log"))
    files2 = sorted(files, key=os.path.getmtime, reverse=True)
    print(files2[0])
    await ctx.channel.send(file=discord.File(files2[0]))


@bot.command(name='main')
async def hello(ctx):
    embed_var = discord.Embed(title="Title", description="Desc", color=0xFFAFCC)
    embed_var.add_field(name="Field1", value="hi", inline=False)
    embed_var.add_field(name="Field2", value="hi2", inline=False)

    await ctx.channel.send(embed=embed_var)
    main_run()


@bot.command(name='log')
async def hello(ctx):
    files = glob.glob(os.path.join(script_dir, "log", "*.log"))
    max_file = max(files, key=os.path.getmtime)
    print(max_file)
    await ctx.channel.send("Fetched latest AutoBooks logfile: \n" + max_file)
    await ctx.channel.send(file=discord.File(max_file))


@bot.command(name='csv')
async def hello(ctx):
    try:
        df = pd.read_csv(csv_path, sep=",")
        embed_var = discord.Embed(title="Autobooks Known Books",
                                  description=df['audiobook_title'].to_string(index=False), color=0xFFAFCC)
        embed_var.set_footer(text="OS: " + platform.platform() + " Host: " + os.uname())
        await ctx.channel.send(embed=embed_var)
    except FileNotFoundError:
        await ctx.channel.send("Known Books CSV not found.")
    # await ctx.channel.send(file=discord.File(max_file))


def discord_run():
    if token == "":
        logger.critical("Bot token not found in config file, exiting.")
    else:
        bot.run(token)


if __name__ == "__main__":
    try:
        discord_run()
    except KeyboardInterrupt:
        sys.exit(1)
