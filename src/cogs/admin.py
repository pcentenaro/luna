import config
import discord
from discord.ext import commands
from startgg import StartGGError

class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    admin = discord.SlashCommandGroup("admin")

    @admin.command(
            description="Check the start.gg API connection",
            description_localizations={
                "es-419": "Comprueba la conexión con la API de start.gg",
                "pt-BR": "Checa a conexão com a API do start.GG"
            })
    async def startgg_status(self, ctx: discord.ApplicationContext):
        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.")
            return

        await ctx.defer()

        try:
            user = await config.startgg_client.get_current_user()
        except StartGGError as error:
            await ctx.respond(f"start.gg connection failed: {error}")
            return

        if user is None:
            await ctx.respond("Connected to start.gg, but no current user was returned.")
            return

        display_name = user.get("name") or user.get("slug") or user.get("id")
        await ctx.respond(f"Connected to start.gg as {display_name}.")

def setup(bot):
    bot.add_cog(Admin(bot))