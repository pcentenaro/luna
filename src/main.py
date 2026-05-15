import discord
import os # default module
from dotenv import load_dotenv
from storage import ConfigStore, LinkStore
from startgg import StartGGClient, StartGGError

load_dotenv() # load all the variables from the env file
debug_guild_id = os.getenv("DISCORD_GUILD_ID")
debug_guilds = [int(debug_guild_id)] if debug_guild_id else None
bot = discord.Bot(debug_guilds=debug_guilds)
startgg_api_key = os.getenv("STARTGG_API_KEY")
startgg_client = StartGGClient(startgg_api_key) if startgg_api_key else None
link_store = LinkStore()
config_store = ConfigStore()

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
    await ctx.respond(f"Linked your Discord account to start.gg player: {display_name}. // Tu cuenta de Discord ha sido vinculada al siguiente perfil de start.gg: {display_name}", ephemeral=True)

async def find_startgg_player(player_reference: str) -> dict | None:
    player_reference = player_reference.strip()
    if player_reference.isdigit():
        return await startgg_client.get_player(int(player_reference))

    profile_code = player_reference.rstrip("/").split("/")[-1]
    return await startgg_client.get_player_by_profile_slug(f"user/{profile_code}")

@bot.slash_command(name="unlink_startgg", description="Remove your start.gg player link")
async def unlink_startgg(ctx: discord.ApplicationContext):
    deleted = link_store.delete_startgg_link(ctx.author.id)
    if deleted:
        await ctx.respond("Removed your start.gg link. // Vinculo a start.gg eliminado.", ephemeral=True)
        return

    await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)

@bot.slash_command(name="whoami_startgg", description="Show your linked start.gg player")
async def whoami_startgg(ctx: discord.ApplicationContext):
    link = link_store.get_startgg_link(ctx.author.id)
    if link is None:
        await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)
        return

    display_name = format_stored_startgg_player(link)
    await ctx.respond(
        f"Your Discord account is linked to start.gg player {display_name} "
        f"(ID: {link['startgg_player_id']}).",
        ephemeral=True,
    )

@bot.slash_command(name="set_admin_role", description="Set the role that can manage Luna")
async def set_admin_role(ctx: discord.ApplicationContext, role: discord.Role):
    if not can_configure_admin_role(ctx):
        await ctx.respond("You cannot configure Luna admin roles. // No puedes configurar roles admin de Luna.", ephemeral=True)
        return

    config_store.set_admin_role_id(role.id)
    await ctx.respond(f"Luna admin role set to {role.mention}. // Rol admin de Luna definido como {role.mention}.", ephemeral=True)

@bot.slash_command(name="current_admin_role", description="Show the configured Luna admin role")
async def current_admin_role(ctx: discord.ApplicationContext):
    admin_role_id = config_store.get_admin_role_id()
    if admin_role_id is None:
        await ctx.respond("No Luna admin role is configured yet. // Aún no hay rol admin de Luna configurado.", ephemeral=True)
        return

    role = ctx.guild.get_role(admin_role_id) if ctx.guild else None
    role_label = role.mention if role else f"missing role ID {admin_role_id}"
    await ctx.respond(f"Current Luna admin role: {role_label}. // Rol admin actual de Luna: {role_label}.", ephemeral=True)

@bot.slash_command(name="clear_admin_role", description="Clear the configured Luna admin role")
async def clear_admin_role(ctx: discord.ApplicationContext):
    if not is_luna_admin(ctx):
        await ctx.respond("Only Luna admins can clear the admin role. // Solo admins de Luna pueden eliminar el rol admin.", ephemeral=True)
        return

    deleted = config_store.clear_admin_role_id()
    if deleted:
        await ctx.respond("Luna admin role cleared. // Rol admin de Luna eliminado.", ephemeral=True)
        return

    await ctx.respond("No Luna admin role was configured. // No había rol admin de Luna configurado.", ephemeral=True)

@bot.slash_command(name="set_event", description="Set the active start.gg event")
async def set_event(ctx: discord.ApplicationContext, tournament_slug: str, event_slug: str):
    if not is_luna_admin(ctx):
        await ctx.respond("Only Luna admins can set the active event. // Solo admins de Luna pueden definir el evento activo.", ephemeral=True)
        return

    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    full_event_slug = build_event_slug(tournament_slug, event_slug)
    await ctx.defer(ephemeral=True)

    try:
        event = await startgg_client.get_event_by_slug(full_event_slug)
    except StartGGError as error:
        await ctx.respond(f"Could not verify that start.gg event: {error}", ephemeral=True)
        return

    if event is None:
        await ctx.respond(f"No start.gg event was found for `{full_event_slug}`.", ephemeral=True)
        return

    config_store.set_active_event(
        tournament_slug=tournament_slug,
        event_slug=full_event_slug,
        event_id=int(event["id"]),
        event_name=event["name"],
    )
    await ctx.respond(
        f"Active event set to {event['name']} (`{full_event_slug}`). // Evento activo definido como {event['name']}.",
        ephemeral=True,
    )

@bot.slash_command(name="current_event", description="Show the active start.gg event")
async def current_event(ctx: discord.ApplicationContext):
    active_event = config_store.get_active_event()
    if active_event is None:
        await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
        return

    await ctx.respond(
        f"Active event: {active_event['event_name']} (`{active_event['event_slug']}`), "
        f"ID: {active_event['event_id']}.",
        ephemeral=True,
    )

@bot.slash_command(name="clear_event", description="Clear the active start.gg event")
async def clear_event(ctx: discord.ApplicationContext):
    if not is_luna_admin(ctx):
        await ctx.respond("Only Luna admins can clear the active event. // Solo admins de Luna pueden eliminar el evento activo.", ephemeral=True)
        return

    deleted = config_store.clear_active_event()
    if deleted:
        await ctx.respond("Active start.gg event cleared. // Evento activo eliminado.", ephemeral=True)
        return

    await ctx.respond("No active start.gg event was configured. // No había evento activo configurado.", ephemeral=True)

@bot.slash_command(name="list_phases", description="List phases for the active start.gg event")
async def list_phases(ctx: discord.ApplicationContext):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    active_event = config_store.get_active_event()
    if active_event is None:
        await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        phases = await startgg_client.get_event_phases(active_event["event_id"])
    except StartGGError as error:
        await ctx.respond(f"Could not read start.gg phases: {error}", ephemeral=True)
        return

    if not phases:
        await ctx.respond(f"No phases found for {active_event['event_name']}.", ephemeral=True)
        return

    phase_lines = [
        f"- {phase['name']} (ID: {phase['id']}, seeds: {phase.get('numSeeds') or 0})"
        for phase in phases
    ]
    await ctx.respond(
        f"Phases for {active_event['event_name']}:\n" + "\n".join(phase_lines),
        ephemeral=True,
    )

@bot.slash_command(name="list_phase_groups", description="List pools or brackets for a start.gg phase")
async def list_phase_groups(ctx: discord.ApplicationContext, phase_id: str):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    try:
        parsed_phase_id = int(phase_id)
    except ValueError:
        await ctx.respond("The phase ID must be a number.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        phase_groups = await startgg_client.get_phase_groups(parsed_phase_id)
    except StartGGError as error:
        await ctx.respond(f"Could not read start.gg phase groups: {error}", ephemeral=True)
        return

    if not phase_groups:
        await ctx.respond(f"No phase groups found for phase ID {parsed_phase_id}.", ephemeral=True)
        return

    phase_group_lines = []
    for phase_group in phase_groups:
        label = phase_group.get("displayIdentifier") or "Unnamed"
        wave = phase_group.get("wave") or {}
        wave_label = f", wave: {wave['identifier']}" if wave.get("identifier") else ""
        phase_group_lines.append(
            f"- {label} (ID: {phase_group['id']}, state: {phase_group.get('state')}{wave_label})"
        )

    await ctx.respond(
        f"Phase groups for phase ID {parsed_phase_id}:\n" + "\n".join(phase_group_lines),
        ephemeral=True,
    )

@bot.slash_command(name="list_sets", description="List sets for a start.gg phase group")
async def list_sets(ctx: discord.ApplicationContext, phase_group_id: str):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    try:
        parsed_phase_group_id = int(phase_group_id)
    except ValueError:
        await ctx.respond("The phase group ID must be a number.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        sets = await startgg_client.get_phase_group_sets(parsed_phase_group_id)
    except StartGGError as error:
        await ctx.respond(f"Could not read start.gg sets: {error}", ephemeral=True)
        return

    if not sets:
        await ctx.respond(f"No sets found for phase group ID {parsed_phase_group_id}.", ephemeral=True)
        return

    set_lines = [format_set_summary(set_data) for set_data in sets]
    await ctx.respond(
        f"Sets for phase group ID {parsed_phase_group_id}:\n" + "\n".join(set_lines),
        ephemeral=True,
    )

@bot.slash_command(name="my_sets", description="List your sets in the active start.gg event")
async def my_sets(ctx: discord.ApplicationContext):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    active_event = config_store.get_active_event()
    if active_event is None:
        await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
        return

    link = link_store.get_startgg_link(ctx.author.id)
    if link is None:
        await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        matching_sets = await find_sets_for_player(
            event_id=active_event["event_id"],
            player_id=link["startgg_player_id"],
        )
    except StartGGError as error:
        await ctx.respond(f"Could not read your start.gg sets: {error}", ephemeral=True)
        return

    if not matching_sets:
        await ctx.respond(f"No sets found for you in {active_event['event_name']}.", ephemeral=True)
        return

    set_lines = [
        format_my_set_summary(match["phase"], match["phase_group"], match["set"])
        for match in matching_sets
    ]
    await ctx.respond(
        f"Your sets in {active_event['event_name']}:\n" + "\n".join(set_lines),
        ephemeral=True,
    )

@bot.slash_command(name="preview_report", description="Preview a score report without submitting it")
async def preview_report(
    ctx: discord.ApplicationContext,
    set_id: str,
    winner: discord.Member,
    score: str,
):
    if startgg_client is None:
        await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
        return

    try:
        parsed_set_id = int(set_id)
    except ValueError:
        await ctx.respond("The set ID must be a number.", ephemeral=True)
        return

    parsed_score = parse_score(score)
    if parsed_score is None:
        await ctx.respond("Score must use the format `7-5`.", ephemeral=True)
        return

    winner_link = link_store.get_startgg_link(winner.id)
    if winner_link is None:
        await ctx.respond("The winner does not have a start.gg link yet.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    try:
        set_data = await startgg_client.get_set(parsed_set_id)
    except StartGGError as error:
        await ctx.respond(f"Could not read start.gg set: {error}", ephemeral=True)
        return

    if set_data is None:
        await ctx.respond(f"No start.gg set was found with ID {parsed_set_id}.", ephemeral=True)
        return

    report_preview = build_report_preview(set_data, winner_link["startgg_player_id"], parsed_score)
    if report_preview["error"]:
        await ctx.respond(report_preview["error"], ephemeral=True)
        return

    author_link = link_store.get_startgg_link(ctx.author.id)
    if not is_luna_admin(ctx):
        if author_link is None:
            await ctx.respond("You need to link your start.gg profile before previewing reports.", ephemeral=True)
            return

        if not set_has_player(set_data, author_link["startgg_player_id"]):
            await ctx.respond("Only players in this set or Luna admins can preview this report.", ephemeral=True)
            return

    await ctx.respond(report_preview["message"], ephemeral=True)

async def find_sets_for_player(event_id: int, player_id: int) -> list[dict]:
    matches = []
    phases = await startgg_client.get_event_phases(event_id)
    for phase in phases:
        phase_groups = await startgg_client.get_phase_groups(int(phase["id"]))
        for phase_group in phase_groups:
            sets = await startgg_client.get_phase_group_sets(int(phase_group["id"]))
            for set_data in sets:
                if set_has_player(set_data, player_id):
                    matches.append(
                        {
                            "phase": phase,
                            "phase_group": phase_group,
                            "set": set_data,
                        }
                    )

    return matches

def set_has_player(set_data: dict, player_id: int) -> bool:
    for slot in set_data.get("slots") or []:
        entrant = slot.get("entrant") or {}
        for participant in entrant.get("participants") or []:
            player = participant.get("player") or {}
            if str(player.get("id")) == str(player_id):
                return True

    return False

def parse_score(score: str) -> tuple[int, int] | None:
    parts = score.strip().split("-")
    if len(parts) != 2:
        return None

    try:
        left_score = int(parts[0].strip())
        right_score = int(parts[1].strip())
    except ValueError:
        return None

    if left_score < 0 or right_score < 0 or left_score == right_score:
        return None

    return left_score, right_score

def build_report_preview(set_data: dict, winner_player_id: int, score: tuple[int, int]) -> dict:
    slots = [slot for slot in set_data.get("slots") or [] if slot.get("entrant")]
    if len(slots) != 2:
        return {"error": "This set does not have exactly two entrants yet."}

    winner_slot = find_slot_by_player_id(slots, winner_player_id)
    if winner_slot is None:
        return {"error": "The selected winner is not part of this set."}

    loser_slot = slots[0] if slots[1] == winner_slot else slots[1]
    winner_score, loser_score = sorted(score, reverse=True)
    if winner_score != 7:
        return {"error": "Puyo scores must have the winner at 7 points."}

    winner_entrant = winner_slot["entrant"]
    loser_entrant = loser_slot["entrant"]
    message = (
        "Report preview only. Nothing was submitted to start.gg.\n"
        f"Set {set_data['id']} | {set_data.get('fullRoundText')}\n"
        f"{winner_entrant['name']} {winner_score} - {loser_score} {loser_entrant['name']}\n"
        f"Winner entrant ID: {winner_entrant['id']}"
    )
    return {"error": None, "message": message}

def find_slot_by_player_id(slots: list[dict], player_id: int) -> dict | None:
    for slot in slots:
        entrant = slot.get("entrant") or {}
        for participant in entrant.get("participants") or []:
            player = participant.get("player") or {}
            if str(player.get("id")) == str(player_id):
                return slot

    return None

def format_startgg_player(player: dict) -> str:
    gamer_tag = player.get("gamerTag") or f"Player {player['id']}"
    prefix = player.get("prefix")
    return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

def format_stored_startgg_player(link: dict) -> str:
    gamer_tag = link.get("startgg_gamer_tag") or f"Player {link['startgg_player_id']}"
    prefix = link.get("startgg_prefix")
    return f"{prefix} | {gamer_tag}" if prefix else gamer_tag

def format_set_summary(set_data: dict) -> str:
    slots = set_data.get("slots") or []
    entrants = [format_slot_summary(slot) for slot in slots]

    while len(entrants) < 2:
        entrants.append("TBD")

    round_text = set_data.get("fullRoundText") or f"Round {set_data.get('round')}"
    return (
        f"- Set {set_data['id']} | {round_text} | state: {set_data.get('state')} | "
        f"{entrants[0]} vs {entrants[1]}"
    )

def format_my_set_summary(phase: dict, phase_group: dict, set_data: dict) -> str:
    phase_group_label = phase_group.get("displayIdentifier") or phase_group["id"]
    return (
        f"{format_set_summary(set_data)} | "
        f"phase: {phase['name']} | group: {phase_group_label}"
    )

def format_slot_summary(slot: dict) -> str:
    entrant = slot.get("entrant")
    if entrant is None:
        return "TBD"

    score = get_slot_score(slot)
    score_text = f" [{score}]" if score is not None else ""
    return f"{entrant.get('name') or 'Unnamed'} (entrant ID: {entrant['id']}){score_text}"

def get_slot_score(slot: dict) -> int | float | None:
    standing = slot.get("standing") or {}
    stats = standing.get("stats") or {}
    score = stats.get("score") or {}
    return score.get("value")

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

def can_configure_admin_role(ctx: discord.ApplicationContext) -> bool:
    if config_store.get_admin_role_id() is None:
        return bool(ctx.author.guild_permissions.administrator)

    return is_luna_admin(ctx)

def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
    admin_role_id = config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(ctx.author.guild_permissions.administrator)

    return any(role.id == admin_role_id for role in ctx.author.roles)

if __name__ == "__main__":
    bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token
