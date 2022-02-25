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
import AutoBooks 


#Log Settings
DISCORD_LOGFILE = os.path.join(AutoBooks.scriptdir,'log','AutoBooks-{:%H-%M-%S_%m-%d-%Y}-Discord.log'.format(datetime.now()))
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s', datefmt='%I:%M:%S %p',)
discord_fh = logging.FileHandler(DISCORD_LOGFILE)
discord_fh.setFormatter(formatter)
AutoBooks.discord_logger.removeHandler(AutoBooks.fh)
AutoBooks.discord_logger.addHandler(discord_fh)
logger = logging.getLogger('discord')
logger.removeHandler(AutoBooks.fh)
logger.addHandler(discord_fh)
#Bot Settings
try:
   token = AutoBooks.parser.get("DEFAULT", "discord_bot_token")
except KeyError:
   AutoBooks.discord_logger.critical("Bot token not found in config file, exiting.")
bot = commands.Bot(command_prefix='?')

@bot.event
async def on_ready():
   AutoBooks.discord_logger.info(f'{bot.user} has connected to Discord!')

@bot.command(name='web')
async def hello(ctx):
   embedVar = discord.Embed(title="Title", description="Desc", color=0x00ff00)
   embedVar.add_field(name="Field1", value="hi", inline=False)
   embedVar.add_field(name="Field2", value="hi2", inline=False)
   await ctx.channel.send(embed=embedVar)
   AutoBooks.web_run()

@bot.command(name='dl')
async def hello(ctx):
   embedVar = discord.Embed(title="Title", description="Desc", color=0x00ff00)
   embedVar.add_field(name="Field1", value="hi", inline=False)
   embedVar.add_field(name="Field2", value="hi2", inline=False)
   await ctx.channel.send(embed=embedVar)
   AutoBooks.dl_run()

@bot.command(name='log')
async def hello(ctx):
   files = glob.glob(os.path.join(AutoBooks.scriptdir, "log","*-Main.log"))
   max_file = max(files, key=os.path.getctime)
   print(max_file)
   await ctx.channel.send("Fetched latest AutoBooks logfile: \n"+ max_file)
   await ctx.channel.send(file=discord.File(max_file))
def discord_run():
   if token == "":
      AutoBooks.discord_logger.critical("Bot token not found in config file, exiting.")
   else:
      bot.run(token)

if __name__ == "__main__":
    try:
      discord_run()
    except KeyboardInterrupt:
        sys.exit(1)