import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='f.', intents=intents, help_command=None)

TAC_GUILD_ID = 946060638231359588


@bot.hybrid_command(name="link", description="Link command")
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def link(ctx: commands.Context):
    print("Command executed!")
    await ctx.send("new `link` slash command jumpscare")


@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=TAC_GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f'Successfully synced {len(synced)} commands.')

    except Exception as e:
        print(f'Error syncing: {e}')

    print('Logged in.\nv3 test')

load_dotenv()
bot.run(os.getenv("TOKEN"))
