from configparser import ConfigParser
from unittest.mock import patch
from datetime import datetime
from discord.ext import commands
from pathlib import Path
import os
import discord
import logging
import glob
import sys
import shutil

from numpy import column_stack
from AutoBooks import web_run, main_run, scriptdir, parser, csv_path, fh, discord_logger
import pandas as pd

# Log Settings
# DISCORD_LOGFILE = os.path.join(AutoBooks.scriptdir,'log','AutoBooks-{:%H-%M-%S_%m-%d-%Y}-Discord.log'.format(datetime.now()))
# formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s', datefmt='%I:%M:%S %p',)
# discord_fh = logging.FileHandler(DISCORD_LOGFILE)
# discord_fh.setFormatter(formatter)
# AutoBooks.discord_logger.removeHandler(AutoBooks.fh)
# AutoBooks.discord_logger.addHandler(discord_fh)
logger = logging.getLogger('discord')
logger.removeHandler(fh)
# logger.addHandler(discord_fh)
# Bot Settings
try:
    token = parser.get("DEFAULT", "discord_bot_token")
except KeyError:
    discord_logger.critical("Bot token not found in config file, exiting.")
bot = commands.Bot(command_prefix='?')


@bot.event
async def on_ready():
    discord_logger.info(f'{bot.user} has connected to Discord!')


@bot.command(name='web')
async def hello(ctx):
    await ctx.channel.send("Starting AutoBooks Web. This may take awhile.")
    web_run()
    embedVar = discord.Embed(title="Title", description="Desc", color=0x00ff00)
    embedVar.add_field(name="Field1", value="hi", inline=False)
    embedVar.add_field(name="Field2", value="hi2", inline=False)
    await ctx.channel.send(embed=embedVar)


@bot.command(name='main')
async def hello(ctx):
    embedVar = discord.Embed(title="Title", description="Desc", color=0x00ff00)
    embedVar.add_field(name="Field1", value="hi", inline=False)
    embedVar.add_field(name="Field2", value="hi2", inline=False)
    await ctx.channel.send(embed=embedVar)
    main_run()


@bot.command(name='log')
async def hello(ctx):
    files = glob.glob(os.path.join(scriptdir, "log", "*-Main.log"))

    files2 = sorted(files, key=os.path.getmtime, reverse=True)
    print(files2[0])

    max_file = max(files, key=os.path.getmtime)
    print(max_file)
    await ctx.channel.send("Fetched latest AutoBooks logfile: \n" + max_file)
    await ctx.channel.send(file=discord.File(max_file))


@bot.command(name='csv')
async def hello(ctx):
    df = pd.read_csv(csv_path, sep=",")

    print(df)
    await ctx.channel.send("Fetched AutoBooks Known Books Database")
    embedVar = discord.Embed(title="Title", description="Desc", color=0x00ff00)
    embedVar.add_field(name="Field1", value=df['audiobook_info'], inline=False)
    embedVar.add_field(name="Field2", value="hi2", inline=False)
    await ctx.channel.send(embed=embedVar)

    # await ctx.channel.send(file=discord.File(max_file))


def discord_run():
    if token == "":
        pass
        #AutoBooks.discord_logger.critical("Bot token not found in config file, exiting.")
    else:
        bot.run(token)


if __name__ == "__main__":
    try:
        discord_run()
    except KeyboardInterrupt:
        sys.exit(1)
