import config
import discord
from datetime import datetime
from discord.ext import commands
from startgg import StartGGClient, StartGGError


class Startgg(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    startgg = discord.SlashCommandGroup("startgg")


    class AccountCommandUnlinkAccountView(discord.ui.View):
        def __init__(self, user_id, **kwargs):
            super().__init__(**kwargs)
            self.user_id = user_id

        async def on_timeout(self):
            self.disable_all_items()
            await self.message.edit(view=None)

        @discord.ui.button(
            label= "Unlink account",
            style=discord.ButtonStyle.red
        )
        async def button_callback(self, button: discord.Button, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return
            config.link_store.delete_startgg_link(self.user_id)
            await interaction.response.send_message("Account successfully unlinked.")
            await self.on_timeout()


    @startgg.command(
            name="account",
            description="Display and edit your linked smash.gg account"
    )
    async def account(self, ctx: discord.ApplicationContext):
        account_info = config.link_store.get_startgg_link(ctx.user.id)
        if account_info is None:
            interaction = await ctx.respond("You don't have an account linked to smash.gg. To link an account, reply to this message with your [smash.gg](<https://www.start.gg/>) account ID.")
            bot_message = await interaction.original_response()
            same_user_reply = lambda m: m.reference is not None and ctx.user.id == m.author.id and bot_message.id == m.reference.message_id
            try:
                user_reply = await config.bot.wait_for(
                    event="message",
                    check=same_user_reply,
                    timeout=300
                )
                player_id = user_reply.content
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
                    prefix=player.get("prefix")
                )
                account_info = config.link_store.get_startgg_link(ctx.user.id)
            except TimeoutError:
                await bot_message.edit(content="You took too long to reply with your [smash.gg](<https://www.start.gg/>) ID. If you want to link your account, use `/startgg account` again.")
                return
        account_embed = discord.Embed(
                title=f"smash.gg account for {ctx.user.display_name}",
                thumbnail=ctx.user.display_avatar.url,
                fields=[
                    discord.EmbedField("account name", account_info["startgg_gamer_tag"], inline=True),
                    discord.EmbedField("account ID", account_info["startgg_player_id"], inline=True),
                    discord.EmbedField("updated on", str(datetime.fromisoformat(account_info["updated_at"]).date()), inline=True)
                ]
            )
        await ctx.respond(
            embed=account_embed,
            view=self.AccountCommandUnlinkAccountView(ctx.user.id, timeout=30)
        )
        return


    @startgg.command(
            name="event",
            description="Display information about the current start.gg event"
    )
    async def event(self, ctx: discord.ApplicationContext):
        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet.")
            return
        phases = await config.startgg_client.get_event_phases(active_event["event_id"])
        if not phases:
            await ctx.respond(f"No phases found for {active_event['event_name']}.", ephemeral=True)
            return
        embed_fields = []
        for phase in phases:
            phase_groups = await config.startgg_client.get_phase_groups(phase["id"])
            phase_state = min([group["state"] for group in phase_groups])
            fields = [
                discord.EmbedField("phase", f"[{phase["name"]}](https://www.start.gg/{active_event["event_slug"]}/brackets/{phase["id"]})", True),
                discord.EmbedField("brackets", len(phase_groups), True),
                discord.EmbedField("status", phase_states_dict[phase_state], True)
            ]
            embed_fields.extend(fields)
        general_info_embed = discord.Embed(
            title=active_event["event_name"],
            description="**General information**",
            url=f"https://www.start.gg/{active_event["event_slug"]}",
            fields=embed_fields
        )
        await ctx.respond(embed=general_info_embed)

    
    @startgg.command(
            name="current_event",
            description="Show the active start.gg event"
    )
    async def current_event(self, ctx: discord.ApplicationContext):
        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
            return
        await ctx.respond(
            f"Active event: {active_event['event_name']} (`{active_event['event_slug']}`), "
            f"ID: {active_event['event_id']}.",
            ephemeral=True,
        )
    

    @startgg.command(
            name="list_phases",
            description="List phases for the active start.gg event"
    )
    async def list_phases(self, ctx: discord.ApplicationContext):
        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return
        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        try:
            phases = await config.startgg_client.get_event_phases(active_event["event_id"])
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


    @startgg.command(
            name="list_phase_groups",
            description="List pools or brackets for a start.gg phase"
    )
    async def list_phase_groups(self, ctx: discord.ApplicationContext, phase_id: str):
        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return
        try:
            parsed_phase_id = int(phase_id)
        except ValueError:
            await ctx.respond("The phase ID must be a number.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        try:
            phase_groups = await config.startgg_client.get_phase_groups(parsed_phase_id)
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


    @startgg.command(
            name="sets",
            description="List sets by phase group ID, phase name, or your linked player"
    )
    async def sets(
        self,
        ctx: discord.ApplicationContext,
        phase: str = discord.Option(
            str,
            description="Optional phase group ID or phase name",
            required=False,
            default=None,
        ),
    ):
        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        if phase:
            phase = phase.strip()
            await ctx.defer(ephemeral=True)

            if phase.isdigit():
                await respond_with_phase_group_sets(ctx, int(phase))
                return

            active_event = config.config_store.get_active_event()
            if active_event is None:
                await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
                return

            await respond_with_phase_sets(ctx, active_event, phase)
            return

        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
            return
        link = config.link_store.get_startgg_link(ctx.author.id)
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
    

    @startgg.command(
            name="preview_report",
            description="Preview a score report without submitting it"
    )
    async def preview_report(
        ctx: discord.ApplicationContext,
        set_id: str,
        winner: discord.Member,
        score: str,
    ):
        if config.startgg_client is None:
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
        winner_link = config.link_store.get_startgg_link(winner.id)
        if winner_link is None:
            await ctx.respond("The winner does not have a start.gg link yet.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        try:
            set_data = await config.startgg_client.get_set(parsed_set_id)
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
        author_link = config.link_store.get_startgg_link(ctx.author.id)
        if not is_luna_admin(ctx):
            if author_link is None:
                await ctx.respond("You need to link your start.gg profile before previewing reports.", ephemeral=True)
                return

            if not set_has_player(set_data, author_link["startgg_player_id"]):
                await ctx.respond("Only players in this set or Luna admins can preview this report.", ephemeral=True)
                return
        await ctx.respond(report_preview["message"], ephemeral=True)


def setup(bot):
    bot.add_cog(Startgg(bot))


phase_states_dict = {
        1: "created",
        2: "active",
        3: "completed",
        4: "ready",
        5: "invalid",
        6: "called",
        7: "queue"
    }


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


def format_stored_startgg_player(link: dict) -> str:
    gamer_tag = link.get("startgg_gamer_tag") or f"Player {link['startgg_player_id']}"
    prefix = link.get("startgg_prefix")
    return f"{prefix} | {gamer_tag}" if prefix else gamer_tag


def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(ctx.author.guild_permissions.administrator)
    return any(role.id == admin_role_id for role in ctx.author.roles)


async def find_sets_for_player(event_id: int, player_id: int) -> list[dict]:
    matches = []
    phases = await config.startgg_client.get_event_phases(event_id)
    for phase in phases:
        phase_groups = await config.startgg_client.get_phase_groups(int(phase["id"]))
        for phase_group in phase_groups:
            sets = await config.startgg_client.get_phase_group_sets(int(phase_group["id"]))
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


async def respond_with_phase_group_sets(ctx: discord.ApplicationContext, phase_group_id: int):
    try:
        sets = await config.startgg_client.get_phase_group_sets(phase_group_id)
    except StartGGError as error:
        await ctx.respond(f"Could not read start.gg sets: {error}", ephemeral=True)
        return

    if not sets:
        await ctx.respond(f"No sets found for phase group ID {phase_group_id}.", ephemeral=True)
        return

    set_lines = [format_set_summary(set_data) for set_data in sets]
    await ctx.respond(
        format_lines_response(f"Sets for phase group ID {phase_group_id}:", set_lines),
        ephemeral=True,
    )


async def respond_with_phase_sets(ctx: discord.ApplicationContext, active_event: dict, phase_name: str):
    try:
        phases = await config.startgg_client.get_event_phases(active_event["event_id"])
    except StartGGError as error:
        await ctx.respond(f"Could not read start.gg phases: {error}", ephemeral=True)
        return

    matching_phases = find_phases_by_name(phases, phase_name)
    if not matching_phases:
        phase_names = ", ".join(phase["name"] for phase in phases) or "none"
        await ctx.respond(
            f"No phase named `{phase_name}` was found in {active_event['event_name']}. "
            f"Available phases: {phase_names}.",
            ephemeral=True,
        )
        return

    set_lines = []
    for phase in matching_phases:
        try:
            phase_groups = await config.startgg_client.get_phase_groups(int(phase["id"]))
        except StartGGError as error:
            await ctx.respond(f"Could not read start.gg phase groups: {error}", ephemeral=True)
            return

        for phase_group in phase_groups:
            try:
                sets = await config.startgg_client.get_phase_group_sets(int(phase_group["id"]))
            except StartGGError as error:
                await ctx.respond(f"Could not read start.gg sets: {error}", ephemeral=True)
                return

            set_lines.extend(
                format_phase_set_summary(phase, phase_group, set_data)
                for set_data in sets
            )

    if not set_lines:
        await ctx.respond(f"No sets found for phase `{phase_name}`.", ephemeral=True)
        return

    matched_names = ", ".join(phase["name"] for phase in matching_phases)
    await ctx.respond(
        format_lines_response(f"Sets for phase {matched_names}:", set_lines),
        ephemeral=True,
    )


def find_phases_by_name(phases: list[dict], phase_name: str) -> list[dict]:
    normalized_name = normalize_lookup_text(phase_name)
    exact_matches = [
        phase for phase in phases
        if normalize_lookup_text(phase["name"]) == normalized_name
    ]
    if exact_matches:
        return exact_matches

    return [
        phase for phase in phases
        if normalized_name in normalize_lookup_text(phase["name"])
    ]


def normalize_lookup_text(value: str) -> str:
    return " ".join(value.casefold().split())


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

def format_phase_set_summary(phase: dict, phase_group: dict, set_data: dict) -> str:
    phase_group_label = phase_group.get("displayIdentifier") or phase_group["id"]
    return (
        f"{format_set_summary(set_data)} | "
        f"group: {phase_group_label} (ID: {phase_group['id']})"
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

def format_lines_response(title: str, lines: list[str], limit: int = 1900) -> str:
    message_lines = [title]
    for index, line in enumerate(lines):
        candidate = "\n".join([*message_lines, line])
        remaining = len(lines) - index
        if len(candidate) > limit:
            message_lines.append(f"...and {remaining} more.")
            break
        message_lines.append(line)
    return "\n".join(message_lines)

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
