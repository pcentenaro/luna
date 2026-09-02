import config
import discord
from cogs.views.admin_panel import AdminPanelView, build_admin_panel_embed, format_role_sync_result
from discord.ext import commands
from participant_role import sync_participant_role
from startgg import StartGGError


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

    @commands.command(name="ref")
    @commands.guild_only()
    async def refresh_participant_roles(self, ctx: commands.Context):
        if not is_luna_admin(ctx):
            await ctx.send("Only Luna admins can refresh participant roles.")
            return

        try:
            result = await sync_participant_role(ctx.guild)
        except StartGGError as error:
            await ctx.send(f"Could not refresh participant roles: {error}")
            return

        if result is None:
            await ctx.send("Configure an active event and participant role first.")
            return

        await ctx.send(f"Participant roles refreshed.{format_role_sync_result(result)}")


def setup(bot):
    bot.add_cog(Admin(bot))


def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(ctx.author.guild_permissions.administrator)
    if ctx.guild and ctx.guild.get_role(admin_role_id) is None:
        return bool(ctx.author.guild_permissions.administrator)
    return any(role.id == admin_role_id for role in ctx.author.roles)
