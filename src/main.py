import cogs
import os # default module
import config
import discord

@config.bot.event
async def on_ready():
    print(f"{config.bot.user} is ready and online!")

@config.bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")









# @bot.slash_command(name="whoami_startgg", description="Show your linked start.gg player")
# async def whoami_startgg(ctx: discord.ApplicationContext):
#     link = link_store.get_startgg_link(ctx.author.id)
#     if link is None:
#         await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)
#         return

#     display_name = format_stored_startgg_player(link)
#     await ctx.respond(
#         f"Your Discord account is linked to start.gg player {display_name} "
#         f"(ID: {link['startgg_player_id']}).",
#         ephemeral=True,
#     )

# @bot.slash_command(name="set_admin_role", description="Set the role that can manage Luna")
# async def set_admin_role(ctx: discord.ApplicationContext, role: discord.Role):
#     if not can_configure_admin_role(ctx):
#         await ctx.respond("You cannot configure Luna admin roles. // No puedes configurar roles admin de Luna.", ephemeral=True)
#         return

#     config_store.set_admin_role_id(role.id)
#     await ctx.respond(f"Luna admin role set to {role.mention}. // Rol admin de Luna definido como {role.mention}.", ephemeral=True)

# @bot.slash_command(name="current_admin_role", description="Show the configured Luna admin role")
# async def current_admin_role(ctx: discord.ApplicationContext):
#     admin_role_id = config_store.get_admin_role_id()
#     if admin_role_id is None:
#         await ctx.respond("No Luna admin role is configured yet. // Aún no hay rol admin de Luna configurado.", ephemeral=True)
#         return

#     role = ctx.guild.get_role(admin_role_id) if ctx.guild else None
#     role_label = role.mention if role else f"missing role ID {admin_role_id}"
#     await ctx.respond(f"Current Luna admin role: {role_label}. // Rol admin actual de Luna: {role_label}.", ephemeral=True)

# @bot.slash_command(name="clear_admin_role", description="Clear the configured Luna admin role")
# async def clear_admin_role(ctx: discord.ApplicationContext):
#     if not is_luna_admin(ctx):
#         await ctx.respond("Only Luna admins can clear the admin role. // Solo admins de Luna pueden eliminar el rol admin.", ephemeral=True)
#         return

#     deleted = config_store.clear_admin_role_id()
#     if deleted:
#         await ctx.respond("Luna admin role cleared. // Rol admin de Luna eliminado.", ephemeral=True)
#         return

#     await ctx.respond("No Luna admin role was configured. // No había rol admin de Luna configurado.", ephemeral=True)

# @bot.slash_command(name="set_event", description="Set the active start.gg event")
# async def set_event(ctx: discord.ApplicationContext, tournament_slug: str, event_slug: str):
#     if not is_luna_admin(ctx):
#         await ctx.respond("Only Luna admins can set the active event. // Solo admins de Luna pueden definir el evento activo.", ephemeral=True)
#         return

#     if startgg_client is None:
#         await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
#         return

#     full_event_slug = build_event_slug(tournament_slug, event_slug)
#     await ctx.defer(ephemeral=True)

#     try:
#         event = await startgg_client.get_event_by_slug(full_event_slug)
#     except StartGGError as error:
#         await ctx.respond(f"Could not verify that start.gg event: {error}", ephemeral=True)
#         return

#     if event is None:
#         await ctx.respond(f"No start.gg event was found for `{full_event_slug}`.", ephemeral=True)
#         return

#     config_store.set_active_event(
#         tournament_slug=tournament_slug,
#         event_slug=full_event_slug,
#         event_id=int(event["id"]),
#         event_name=event["name"],
#     )
#     await ctx.respond(
#         f"Active event set to {event['name']} (`{full_event_slug}`). // Evento activo definido como {event['name']}.",
#         ephemeral=True,
#     )

# @bot.slash_command(name="current_event", description="Show the active start.gg event")
# async def current_event(ctx: discord.ApplicationContext):
#     active_event = config_store.get_active_event()
#     if active_event is None:
#         await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
#         return

#     await ctx.respond(
#         f"Active event: {active_event['event_name']} (`{active_event['event_slug']}`), "
#         f"ID: {active_event['event_id']}.",
#         ephemeral=True,
#     )

# @bot.slash_command(name="clear_event", description="Clear the active start.gg event")
# async def clear_event(ctx: discord.ApplicationContext):
#     if not is_luna_admin(ctx):
#         await ctx.respond("Only Luna admins can clear the active event. // Solo admins de Luna pueden eliminar el evento activo.", ephemeral=True)
#         return

#     deleted = config_store.clear_active_event()
#     if deleted:
#         await ctx.respond("Active start.gg event cleared. // Evento activo eliminado.", ephemeral=True)
#         return

#     await ctx.respond("No active start.gg event was configured. // No había evento activo configurado.", ephemeral=True)

# @bot.slash_command(name="list_phases", description="List phases for the active start.gg event")
# async def list_phases(ctx: discord.ApplicationContext):
#     if startgg_client is None:
#         await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
#         return

#     active_event = config_store.get_active_event()
#     if active_event is None:
#         await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
#         return

#     await ctx.defer(ephemeral=True)

#     try:
#         phases = await startgg_client.get_event_phases(active_event["event_id"])
#     except StartGGError as error:
#         await ctx.respond(f"Could not read start.gg phases: {error}", ephemeral=True)
#         return

#     if not phases:
#         await ctx.respond(f"No phases found for {active_event['event_name']}.", ephemeral=True)
#         return

#     phase_lines = [
#         f"- {phase['name']} (ID: {phase['id']}, seeds: {phase.get('numSeeds') or 0})"
#         for phase in phases
#     ]
#     await ctx.respond(
#         f"Phases for {active_event['event_name']}:\n" + "\n".join(phase_lines),
#         ephemeral=True,
#     )

# @bot.slash_command(name="list_phase_groups", description="List pools or brackets for a start.gg phase")
# async def list_phase_groups(ctx: discord.ApplicationContext, phase_id: str):
#     if startgg_client is None:
#         await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
#         return

#     try:
#         parsed_phase_id = int(phase_id)
#     except ValueError:
#         await ctx.respond("The phase ID must be a number.", ephemeral=True)
#         return

#     await ctx.defer(ephemeral=True)

#     try:
#         phase_groups = await startgg_client.get_phase_groups(parsed_phase_id)
#     except StartGGError as error:
#         await ctx.respond(f"Could not read start.gg phase groups: {error}", ephemeral=True)
#         return

#     if not phase_groups:
#         await ctx.respond(f"No phase groups found for phase ID {parsed_phase_id}.", ephemeral=True)
#         return

#     phase_group_lines = []
#     for phase_group in phase_groups:
#         label = phase_group.get("displayIdentifier") or "Unnamed"
#         wave = phase_group.get("wave") or {}
#         wave_label = f", wave: {wave['identifier']}" if wave.get("identifier") else ""
#         phase_group_lines.append(
#             f"- {label} (ID: {phase_group['id']}, state: {phase_group.get('state')}{wave_label})"
#         )

#     await ctx.respond(
#         f"Phase groups for phase ID {parsed_phase_id}:\n" + "\n".join(phase_group_lines),
#         ephemeral=True,
#     )

# def format_startgg_player(player: dict) -> str:
#     gamer_tag = player.get("gamerTag") or f"Player {player['id']}"
#     prefix = player.get("prefix")
#     return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

# def format_stored_startgg_player(link: dict) -> str:
#     gamer_tag = link.get("startgg_gamer_tag") or f"Player {link['startgg_player_id']}"
#     prefix = link.get("startgg_prefix")
#     return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

# def build_event_slug(tournament_slug: str, event_slug: str) -> str:
#     event_slug = event_slug.strip().strip("/")
#     if event_slug.startswith("tournament/"):
#         return event_slug

#     tournament_slug = tournament_slug.strip().strip("/")
#     if tournament_slug.startswith("tournament/"):
#         tournament_slug = tournament_slug.split("/")[1]

#     if event_slug.startswith("event/"):
#         event_slug = event_slug.split("/", 1)[1]

#     return f"tournament/{tournament_slug}/event/{event_slug}"

# def can_configure_admin_role(ctx: discord.ApplicationContext) -> bool:
#     if config_store.get_admin_role_id() is None:
#         return bool(ctx.author.guild_permissions.administrator)

#     return is_luna_admin(ctx)

# def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
#     admin_role_id = config_store.get_admin_role_id()
#     if admin_role_id is None:
#         return bool(ctx.author.guild_permissions.administrator)

#     return any(role.id == admin_role_id for role in ctx.author.roles)

config.bot.load_extension("cogs.admin")
config.bot.load_extension("cogs.startgg")
config.bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token