import discord
import os # default module
from dotenv import load_dotenv
from startgg import StartGGClient, StartGGError

load_dotenv() # load all the variables from the env file
bot = discord.Bot()
startgg_api_key = os.getenv("STARTGG_API_KEY")
startgg_client = StartGGClient(startgg_api_key) if startgg_api_key else None

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")

@bot.slash_command(name="startgg_status", description="Check the start.gg API connection")
async def startgg_status(ctx: discord.ApplicationContext):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.")
        return

    await ctx.defer()

    try:
        user = await startgg_client.get_current_user()
    except StartGGError as error:
        await ctx.respond(f"start.gg connection failed: {error}")
        return

    if user is None:
        await ctx.respond("Connected to start.gg, but no current user was returned.")
        return

    display_name = user.get("name") or user.get("slug") or user.get("id")
    await ctx.respond(f"Connected to start.gg as {display_name}.")

bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token
