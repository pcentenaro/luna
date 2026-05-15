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

@bot.slash_command(name="force_report_result", description="Admin-only: report a set result to start.gg")
async def force_report_result(
    ctx: discord.ApplicationContext,
    set_id: str,
    winner: discord.Member,
    score: str,
):
    if not is_luna_admin(ctx):
        await ctx.respond("Only Luna admins can force report results.", ephemeral=True)
        return

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

    report = build_report_payload(set_data, winner_link["startgg_player_id"], parsed_score)
    if report["error"]:
        await ctx.respond(report["error"], ephemeral=True)
        return

    try:
        result = await startgg_client.report_set(
            set_id=parsed_set_id,
            winner_id=report["winner_entrant_id"],
            game_data=report["game_data"],
        )
    except StartGGError as error:
        await ctx.respond(f"Could not report start.gg set: {error}", ephemeral=True)
        return

    result_id = result.get("id") if isinstance(result, dict) else parsed_set_id
    result_state = result.get("state") if isinstance(result, dict) else "unknown"
    await ctx.respond(
        f"Score reported to start.gg.\n"
        f"Set {result_id}: {report['winner_name']} {report['winner_score']} - {report['loser_score']} {report['loser_name']}\n"
        f"Set state: {result_state}",
        ephemeral=True,
    )

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
    report = build_report_payload(set_data, winner_player_id, score)
    if report["error"]:
        return {"error": report["error"]}

    message = (
        "Report preview only. Nothing was submitted to start.gg.\n"
        f"Set {set_data['id']} | {set_data.get('fullRoundText')}\n"
        f"{report['winner_name']} {report['winner_score']} - {report['loser_score']} {report['loser_name']}\n"
        f"Winner entrant ID: {report['winner_entrant_id']}"
    )
    return {"error": None, "message": message}

def build_report_payload(set_data: dict, winner_player_id: int, score: tuple[int, int]) -> dict:
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
    game_data = build_game_data_for_set_score(
        slots=slots,
        winner_slot=winner_slot,
        loser_slot=loser_slot,
        winner_score=winner_score,
        loser_score=loser_score,
    )
    return {
        "error": None,
        "winner_entrant_id": int(winner_entrant["id"]),
        "winner_name": winner_entrant["name"],
        "winner_score": winner_score,
        "loser_name": loser_entrant["name"],
        "loser_score": loser_score,
        "game_data": game_data,
    }

def build_game_data_for_set_score(
    slots: list[dict],
    winner_slot: dict,
    loser_slot: dict,
    winner_score: int,
    loser_score: int,
) -> list[dict]:
    games = []
    game_num = 1

    for _ in range(winner_score):
        games.append(build_game_data_entry(slots, winner_slot, game_num))
        game_num += 1

    for _ in range(loser_score):
        games.append(build_game_data_entry(slots, loser_slot, game_num))
        game_num += 1

    return games

def build_game_data_entry(slots: list[dict], winning_slot: dict, game_num: int) -> dict:
    return {
        "winnerId": int(winning_slot["entrant"]["id"]),
        "gameNum": game_num,
        "entrant1Score": 1 if slots[0] == winning_slot else 0,
        "entrant2Score": 1 if slots[1] == winning_slot else 0,
    }

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
    config.bot.load_extension("cogs.admin")
    config.bot.load_extension("cogs.startgg")
    bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token