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


    @admin.command(
            name="set_admin_role",
            description="Set the role that can manage Luna"
    )
    async def set_admin_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        if not can_configure_admin_role(ctx):
            await ctx.respond("You cannot configure Luna admin roles. // No puedes configurar roles admin de Luna.", ephemeral=True)
            return
        config.config_store.set_admin_role_id(role.id)
        await ctx.respond(f"Luna admin role set to {role.mention}. // Rol admin de Luna definido como {role.mention}.", ephemeral=True)
    

    @admin.command(
            name="current_admin_role",
            description="Show the configured Luna admin role"
    )
    async def current_admin_role(self, ctx: discord.ApplicationContext):
        admin_role_id = config.config_store.get_admin_role_id()
        if admin_role_id is None:
            await ctx.respond("No Luna admin role is configured yet. // Aún no hay rol admin de Luna configurado.", ephemeral=True)
            return
        role = ctx.guild.get_role(admin_role_id) if ctx.guild else None
        role_label = role.mention if role else f"missing role ID {admin_role_id}"
        await ctx.respond(f"Current Luna admin role: {role_label}. // Rol admin actual de Luna: {role_label}.", ephemeral=True)
    

    @admin.command(
        name="clear_admin_role",
        description="Clear the configured Luna admin role"
    )
    async def clear_admin_role(self, ctx: discord.ApplicationContext):
        if not is_luna_admin(ctx):
            await ctx.respond("Only Luna admins can clear the admin role. // Solo admins de Luna pueden eliminar el rol admin.", ephemeral=True)
            return
        deleted = config.config_store.clear_admin_role_id()
        if deleted:
            await ctx.respond("Luna admin role cleared. // Rol admin de Luna eliminado.", ephemeral=True)
            return
        await ctx.respond("No Luna admin role was configured. // No había rol admin de Luna configurado.", ephemeral=True)
    

    @admin.command(
            name="set_event",
            description="Set the active start.gg event"
    )
    async def set_event(self, ctx: discord.ApplicationContext, tournament_slug: str, event_slug: str):
        if not is_luna_admin(ctx):
            await ctx.respond("Only Luna admins can set the active event. // Solo admins de Luna pueden definir el evento activo.", ephemeral=True)
            return
        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return
        full_event_slug = build_event_slug(tournament_slug, event_slug)
        await ctx.defer(ephemeral=True)
        try:
            event = await config.startgg_client.get_event_by_slug(full_event_slug)
        except StartGGError as error:
            await ctx.respond(f"Could not verify that start.gg event: {error}", ephemeral=True)
            return
        if event is None:
            await ctx.respond(f"No start.gg event was found for `{full_event_slug}`.", ephemeral=True)
            return
        config.config_store.set_active_event(
            tournament_slug=tournament_slug,
            event_slug=full_event_slug,
            event_id=int(event["id"]),
            event_name=event["name"],
        )
        await ctx.respond(
            f"Active event set to {event['name']} (`{full_event_slug}`). // Evento activo definido como {event['name']}.",
            ephemeral=True,
        )
    

    @admin.command(
            name="clear_event",
            description="Clear the active start.gg event"
    )
    async def clear_event(self, ctx: discord.ApplicationContext):
        if not is_luna_admin(ctx):
            await ctx.respond("Only Luna admins can clear the active event. // Solo admins de Luna pueden eliminar el evento activo.", ephemeral=True)
            return
        deleted = config.config_store.clear_active_event()
        if deleted:
            await ctx.respond("Active start.gg event cleared. // Evento activo eliminado.", ephemeral=True)
            return
        await ctx.respond("No active start.gg event was configured. // No había evento activo configurado.", ephemeral=True)


def setup(bot):
    bot.add_cog(Admin(bot))
    

def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(ctx.author.guild_permissions.administrator)
    return any(role.id == admin_role_id for role in ctx.author.roles)


def can_configure_admin_role(ctx: discord.ApplicationContext) -> bool:
    if config.config_store.get_admin_role_id() is None:
        return bool(ctx.author.guild_permissions.administrator)
    return is_luna_admin(ctx)


def build_event_slug(tournament_slug: str, event_slug: str) -> str:
    event_slug = event_slug.strip().strip("/")
    if event_slug.startswith("tournament/"):
        return event_slug
    tournament_slug = tournament_slug.strip().strip("/")
    if tournament_slug.startswith("tournament/"):
        tournament_slug = tournament_slug.split("/")[1]
    if event_slug.startswith("event/"):
        event_slug = event_slug.split("/", 1)[1]
    return f"tournament/{tournament_slug}/event/{event_slug}"