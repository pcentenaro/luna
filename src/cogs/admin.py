import config
import discord
from cogs.views.admin_panel import AdminPanelView, build_admin_panel_embed
from discord.ext import commands


class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    admin = discord.SlashCommandGroup("admin")

    @admin.command(
        name="panel",
        description="Send the Luna admin panel",
    )
    async def panel(self, ctx: discord.ApplicationContext):
        if not is_luna_admin(ctx):
            await ctx.respond("Only Luna admins can send the admin panel.", ephemeral=True)
            return

        await ctx.respond(
            embed=build_admin_panel_embed(ctx.guild),
            view=AdminPanelView(),
        )


def setup(bot):
    bot.add_cog(Admin(bot))


def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(ctx.author.guild_permissions.administrator)
    if ctx.guild and ctx.guild.get_role(admin_role_id) is None:
        return bool(ctx.author.guild_permissions.administrator)
    return any(role.id == admin_role_id for role in ctx.author.roles)
