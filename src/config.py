import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from startgg import StartGGClient
from storage import CluesStore, ConfigStore, LinkStore

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
rae_api_key = os.getenv("RAE_API_KEY")
clues_leaderboard_channel_id = int(os.getenv("CLUES_LEADERBOARD_CHANNEL_ID", "0")) or None
link_store = LinkStore()
config_store = ConfigStore()
clues_store = CluesStore()
