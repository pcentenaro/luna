import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from startgg import StartGGClient
from storage import ConfigStore, LinkStore

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    help_command=None,
    intents=intents,
    debug_guilds=[os.getenv("DISCORD_GUILD_ID")],
)

startgg_api_key = os.getenv("STARTGG_API_KEY")
startgg_client = StartGGClient(startgg_api_key) if startgg_api_key else None
link_store = LinkStore()
config_store = ConfigStore()
