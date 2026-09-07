import config
import discord
from cogs.views.admin_panel import (
    AdminPanelView,
    build_admin_panel_embed,
    build_attendee_link_statuses,
    build_pgrs_link_statuses,
    chunk_embed_lines,
    format_role_sync_result,
)
from discord.ext import commands
from participant_role import sync_participant_role
from pgrs import PGRSError, fetch_pgrs_entries
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
        except (StartGGError, PGRSError) as error:
            await ctx.send(f"Could not refresh participant roles: {error}")
            return

        if result is None:
            await ctx.send("Configure an active event and participant role first.")
            return

        await ctx.send(f"Participant roles refreshed.{format_role_sync_result(result)}")

    @commands.command(name="notif")
    @commands.guild_only()
    async def notify_incomplete_registrations(self, ctx: commands.Context):
        if not is_luna_admin(ctx):
            await ctx.send("Only Luna admins can send registration reminders.")
            return

        active_event = config.config_store.get_active_event()
        if active_event is None or not active_event.get("pgrs_competition_id"):
            await ctx.send("Configure an active event with a PGRS competition first.")
            return
        if config.startgg_client is None:
            await ctx.send("STARTGG_API_KEY is not configured yet.")
            return

        try:
            entrants = await config.startgg_client.get_event_entrants(active_event["event_id"])
            pgrs_entries = await fetch_pgrs_entries(active_event["pgrs_competition_id"])
        except (StartGGError, PGRSError) as error:
            await ctx.send(f"Could not check tournament registrations: {error}")
            return

        links = config.link_store.get_all_startgg_links()
        links_by_player_id = {
            str(link["startgg_player_id"]): link
            for link in links
            if link.get("startgg_player_id") is not None
        }
        attendees = build_attendee_link_statuses(entrants, links_by_player_id)
        statuses = build_pgrs_link_statuses(attendees, links, pgrs_entries)
        notifications = statuses["notifications"]
        unlinked = statuses["unlinked"]
        if not notifications and not unlinked:
            await ctx.send("All linked participants are registered on both start.gg and PGRS.")
            return

        for chunk in (chunk_embed_lines(notifications, limit=1800) if notifications else []):
            await ctx.send(
                f"**Tournament registration reminder**\n{chunk}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )

        for chunk in (chunk_embed_lines(unlinked, limit=1600) if unlinked else []):
            await ctx.send(
                "**PGRS players without a linked Discord account**\n"
                f"{chunk}\n\nIf one of these profiles is yours, use `/link`.",
                allowed_mentions=discord.AllowedMentions.none(),
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
