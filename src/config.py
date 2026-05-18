import discord
import os
from dotenv import load_dotenv
from startgg import StartGGClient
from storage import ConfigStore, LinkStore

load_dotenv()

bot = discord.Bot(debug_guilds=[os.getenv("DISCORD_GUILD_ID")])

startgg_api_key = os.getenv("STARTGG_API_KEY")
startgg_client = StartGGClient(startgg_api_key) if startgg_api_key else None
link_store = LinkStore()
config_store = ConfigStore()