import discord
import os # default module
from dotenv import load_dotenv
from storage import LinkStore
from startgg import StartGGClient, StartGGError

load_dotenv() # load all the variables from the env file
debug_guild_id = os.getenv("DISCORD_GUILD_ID")
debug_guilds = [int(debug_guild_id)] if debug_guild_id else None
bot = discord.Bot(debug_guilds=debug_guilds)
startgg_api_key = os.getenv("STARTGG_API_KEY")
startgg_client = StartGGClient(startgg_api_key) if startgg_api_key else None
link_store = LinkStore()

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

@bot.slash_command(name="link_startgg", description="Link your Discord account to a start.gg profile")
async def link_startgg(ctx: discord.ApplicationContext, player_id: str):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        player = await find_startgg_player(player_id)
    except StartGGError as error:
        await ctx.respond(f"Could not verify that start.gg profile: {error}", ephemeral=True)
        return

    if player is None:
        await ctx.respond("No start.gg player was found with that ID or profile code.", ephemeral=True)
        return

    link_store.set_startgg_link(
        discord_user_id=ctx.author.id,
        startgg_player_id=int(player["id"]),
        gamer_tag=player.get("gamerTag"),
        prefix=player.get("prefix"),
    )

    display_name = format_startgg_player(player)
    await ctx.respond(f"Linked your Discord account to start.gg player: {display_name}. // Tu cuenta de Discord ha sido ligada al siguiente perfil de start.gg: {display_name}", ephemeral=True)

async def find_startgg_player(player_reference: str) -> dict | None:
    player_reference = player_reference.strip()
    if player_reference.isdigit():
        return await startgg_client.get_player(int(player_reference))

    profile_code = player_reference.rstrip("/").split("/")[-1]
    return await startgg_client.get_player_by_profile_slug(f"user/{profile_code}")

@bot.slash_command(name="unlink_startgg", description="Remove your start.gg player link // Elimina el enlace de tu perfil de start.gg")
async def unlink_startgg(ctx: discord.ApplicationContext):
    deleted = link_store.delete_startgg_link(ctx.author.id)
    if deleted:
        await ctx.respond("Removed your start.gg link.", ephemeral=True)
        return

    await ctx.respond("You do not have a start.gg link yet. // No tienes un enlace a start.gg aún.", ephemeral=True)

@bot.slash_command(name="whoami_startgg", description="Show your linked start.gg player")
async def whoami_startgg(ctx: discord.ApplicationContext):
    link = link_store.get_startgg_link(ctx.author.id)
    if link is None:
        await ctx.respond("You do not have a start.gg link yet. // No tienes un enlace a start.gg aún.", ephemeral=True)
        return

    display_name = format_stored_startgg_player(link)
    await ctx.respond(
        f"Your Discord account is linked to start.gg player {display_name} "
        f"(ID: {link['startgg_player_id']}).",
        ephemeral=True,
    )

def format_startgg_player(player: dict) -> str:
    gamer_tag = player.get("gamerTag") or f"Player {player['id']}"
    prefix = player.get("prefix")
    return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

def format_stored_startgg_player(link: dict) -> str:
    gamer_tag = link.get("startgg_gamer_tag") or f"Player {link['startgg_player_id']}"
    prefix = link.get("startgg_prefix")
    return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token
