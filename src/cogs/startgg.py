import config
import discord
from discord.ext import commands
from startgg import StartGGError

class Startgg(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    startgg = discord.SlashCommandGroup("startgg")

    @startgg.command(
            name="link_startgg",
            description="Link your Discord account to a start.gg profile"
    )
    async def link_startgg(self, ctx: discord.ApplicationContext, player_id: str):
        if config.startgg_client is None:
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

        config.link_store.set_startgg_link(
            discord_user_id=ctx.author.id,
            startgg_player_id=int(player["id"]),
            gamer_tag=player.get("gamerTag"),
            prefix=player.get("prefix"),
        )

        display_name = format_startgg_player(player)
        await ctx.respond(f"Linked your Discord account to start.gg player: {display_name}. // Tu cuenta de Discord ha sido vinculada al siguiente perfil de start.gg: {display_name}", ephemeral=True)


    @startgg.command(
            name="unlink_startgg",
            description="Remove your start.gg player link"
    )
    async def unlink_startgg(self, ctx: discord.ApplicationContext):
        deleted = config.link_store.delete_startgg_link(ctx.author.id)
        if deleted:
            await ctx.respond("Removed your start.gg link. // Vinculo a start.gg eliminado.", ephemeral=True)
            return

        await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)


def setup(bot):
    bot.add_cog(Startgg(bot))


def format_startgg_player(player: dict) -> str:
    gamer_tag = player.get("gamerTag") or f"Player {player['id']}"
    prefix = player.get("prefix")
    return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

async def find_startgg_player(player_reference: str) -> dict | None:
    player_reference = player_reference.strip()
    if player_reference.isdigit():
        return await config.startgg_client.get_player(int(player_reference))
    profile_code = player_reference.rstrip("/").split("/")[-1]
    return await config.startgg_client.get_player_by_profile_slug(f"user/{profile_code}")