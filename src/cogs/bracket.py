import discord
from discord.ext import commands


class Bracket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="bracket",
        description="Privately view the current tournament pools and brackets",
    )
    async def bracket(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bracket images are not available yet.", ephemeral=True)


def setup(bot):
    bot.add_cog(Bracket(bot))
