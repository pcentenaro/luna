import asyncio
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
        await ctx.defer()
        try:
            phases = await config.startgg_client.get_event_phases(active_event["event_id"])
        except StartGGError as error:
            await ctx.respond(f"Could not read start.gg phases: {error}", ephemeral=True)
            return
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
        await ctx.defer(ephemeral=True)
        try:
            event_matches = await find_sets_for_event(active_event["event_id"])
        except StartGGError as error:
            await ctx.respond(f"Could not read start.gg sets: {error}", ephemeral=True)
            return

        player_matches = []
        if link is not None:
            player_matches = [
                match for match in event_matches
                if set_has_player(match["set"], link["startgg_player_id"])
            ]

        view = SetsInfoView(
            active_event=active_event,
            link=link,
            player_matches=player_matches,
            event_matches=event_matches,
            user_id=ctx.author.id,
        )
        await ctx.respond(
            embed=view.current_embed(),
            view=view,
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

    @startgg.command(
            name="inspect_set",
            description="Inspect a start.gg set for debugging"
    )
    async def inspect_set(self, ctx: discord.ApplicationContext, set_id: str):
        if not is_luna_admin(ctx):
            await ctx.respond("Only Luna admins can inspect sets.", ephemeral=True)
            return

        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        try:
            parsed_set_id = int(set_id)
        except ValueError:
            await ctx.respond("The set ID must be a number.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        try:
            set_data = await config.startgg_client.get_set_inspection(parsed_set_id)
        except StartGGError as error:
            await ctx.respond(f"Could not inspect start.gg set: {error}", ephemeral=True)
            return

        if set_data is None:
            await ctx.respond(f"No start.gg set was found with ID {parsed_set_id}.", ephemeral=True)
            return

        await ctx.respond(format_set_inspection(set_data), ephemeral=True)


    @discord.slash_command(
            name="report",
            description="Report your next pending start.gg set"
    )
    async def report(self, ctx: discord.ApplicationContext, score: str):
        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet. // Aún no hay evento activo configurado.", ephemeral=True)
            return

        link = config.link_store.get_startgg_link(ctx.author.id)
        if link is None:
            await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)
            return

        parsed_score = parse_score(score)
        if parsed_score is None:
            await ctx.respond("Score must use the format `7-5`.", ephemeral=True)
            return

        await ctx.defer()
        try:
            matching_sets = await asyncio.wait_for(
                find_sets_for_player(
                    event_id=active_event["event_id"],
                    player_id=link["startgg_player_id"],
                ),
                timeout=20,
            )
            next_match = find_next_pending_match(matching_sets)
            if next_match is None:
                await ctx.respond(f"No pending sets found for you in {active_event['event_name']}.", ephemeral=True)
                return

            report = build_player_report_payload(
                set_data=next_match["set"],
                player_id=link["startgg_player_id"],
                score=parsed_score,
            )
            if report["error"]:
                await ctx.respond(report["error"], ephemeral=True)
                return

            opponent_link = config.link_store.get_startgg_link_by_player_id(report["opponent_player_id"])
            if opponent_link is None:
                await ctx.respond("Your opponent must link their start.gg profile before this result can be confirmed.", ephemeral=True)
                return

            set_id = int(next_match["set"]["id"])
            player_discord_ids = {
                int(link["discord_user_id"]),
                int(opponent_link["discord_user_id"]),
            }
            pending_report_message = get_pending_report_message(set_id, player_discord_ids)
            if pending_report_message:
                await ctx.respond(pending_report_message)
                return

            register_pending_report(set_id, player_discord_ids)
            view = ReportConfirmationView(
                match=next_match,
                report=report,
                active_event=active_event,
                player_discord_ids=player_discord_ids,
            )
            try:
                await ctx.respond(
                    build_player_report_confirmation_message(next_match, report),
                    view=view,
                )
            except Exception:
                release_pending_report(set_id, player_discord_ids)
                raise
        except asyncio.TimeoutError:
            await ctx.respond("Reading your start.gg sets took too long. Try again in a moment.", ephemeral=True)
        except StartGGError as error:
            await ctx.respond(f"Could not read your start.gg sets: {error}", ephemeral=True)
        except Exception as error:
            await ctx.respond(f"Could not prepare the report panel: {error}", ephemeral=True)
            raise


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


pending_report_user_ids_by_set: dict[int, set[int]] = {}
pending_report_set_id_by_user: dict[int, int] = {}


class SetsInfoView(discord.ui.View):
    def __init__(
        self,
        active_event: dict,
        link: dict | None,
        player_matches: list[dict],
        event_matches: list[dict],
        user_id: int,
    ):
        super().__init__(timeout=300)
        self.active_event = active_event
        self.link = link
        self.player_matches = player_matches
        self.event_matches = event_matches
        self.user_id = user_id
        self.mode = "next" if player_matches else "general"
        self.update_button_states()

    @discord.ui.button(label="Next set", style=discord.ButtonStyle.primary)
    async def next_set(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.can_use_button(interaction):
            return
        self.mode = "next"
        self.update_button_states()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="My sets", style=discord.ButtonStyle.secondary)
    async def my_sets(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.can_use_button(interaction):
            return
        self.mode = "my"
        self.update_button_states()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="General sets", style=discord.ButtonStyle.secondary)
    async def general_sets(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.can_use_button(interaction):
            return
        self.mode = "general"
        self.update_button_states()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def can_use_button(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who used this command can switch this view.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        self.disable_all_items()

    def current_embed(self) -> discord.Embed:
        if self.mode == "next":
            return build_next_set_embed(self.active_event, self.link, self.player_matches)
        if self.mode == "my":
            return build_my_sets_embed(self.active_event, self.link, self.player_matches)
        return build_general_sets_embed(self.active_event, self.event_matches)

    def update_button_states(self):
        for child in self.children:
            if child.label == "Next set":
                child.disabled = not self.player_matches
                child.style = discord.ButtonStyle.primary if self.mode == "next" else discord.ButtonStyle.secondary
            elif child.label == "My sets":
                child.disabled = not self.player_matches
                child.style = discord.ButtonStyle.primary if self.mode == "my" else discord.ButtonStyle.secondary
            elif child.label == "General sets":
                child.style = discord.ButtonStyle.primary if self.mode == "general" else discord.ButtonStyle.secondary


class ReportConfirmationView(discord.ui.View):
    def __init__(
        self,
        match: dict,
        report: dict,
        active_event: dict,
        player_discord_ids: set[int],
    ):
        super().__init__(timeout=600)
        self.match = match
        self.report = report
        self.active_event = active_event
        self.player_discord_ids = player_discord_ids
        self.confirmed_user_ids = set()
        self.finished = False
        self.message = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.can_use_button(interaction):
            return

        self.confirmed_user_ids.add(interaction.user.id)
        if self.confirmed_user_ids != self.player_discord_ids:
            await interaction.response.edit_message(
                content=build_player_report_confirmation_message(
                    self.match,
                    self.report,
                    confirmed_count=len(self.confirmed_user_ids),
                ),
                view=self,
            )
            return

        self.finished = True
        self.disable_all_items()
        await interaction.response.defer()

        try:
            await config.startgg_client.report_set(
                set_id=int(self.match["set"]["id"]),
                winner_id=self.report["winner_entrant_id"],
                game_data=self.report["game_data"],
            )
        except StartGGError as error:
            release_pending_report(int(self.match["set"]["id"]), self.player_discord_ids)
            await interaction.message.edit(
                content=f"Could not report start.gg set: {error}",
                view=self,
            )
            return

        release_pending_report(int(self.match["set"]["id"]), self.player_discord_ids)
        await interaction.message.edit(
            content=build_player_report_success_message(self.match, self.report, self.active_event),
            view=self,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.can_use_button(interaction):
            return

        self.finished = True
        self.disable_all_items()
        release_pending_report(int(self.match["set"]["id"]), self.player_discord_ids)
        await interaction.response.edit_message(
            content="Result report cancelled. Run `/report` again when both players are ready.",
            view=self,
        )

    @discord.ui.button(label="Ping Admin", style=discord.ButtonStyle.secondary)
    async def admin_dq(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.finished:
            await interaction.response.send_message("This report confirmation is already closed.", ephemeral=True)
            return

        if is_luna_admin_interaction(interaction):
            self.message = interaction.message
            await interaction.response.send_modal(DQReportModal(self))
            return

        if interaction.user.id in self.player_discord_ids:
            await interaction.response.send_message(
                build_admin_help_message(self.match),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            return

        await interaction.response.send_message("Only players in this set or Luna admins can use this button.", ephemeral=True)

    async def can_use_button(self, interaction: discord.Interaction) -> bool:
        if self.finished:
            await interaction.response.send_message("This report confirmation is already closed.", ephemeral=True)
            return False

        if interaction.user.id not in self.player_discord_ids:
            await interaction.response.send_message("Only the two players in this set can confirm this result.", ephemeral=True)
            return False

        return True

    async def on_timeout(self):
        self.finished = True
        self.disable_all_items()
        release_pending_report(int(self.match["set"]["id"]), self.player_discord_ids)


class DQReportModal(discord.ui.Modal):
    def __init__(self, report_view: ReportConfirmationView):
        super().__init__(title="Report DQ")
        self.report_view = report_view
        self.add_item(
            discord.ui.InputText(
                label="DQ player",
                placeholder="1, 2, entrant ID, or exact player name",
                required=True,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_luna_admin_interaction(interaction):
            await interaction.response.send_message("Only Luna admins can report DQs.", ephemeral=True)
            return

        dq_slot = find_dq_slot(self.report_view.match["set"], self.children[0].value)
        if dq_slot is None:
            await interaction.response.send_message("Could not find that player in this set.", ephemeral=True)
            return

        dq_report = build_dq_report_payload(self.report_view.match["set"], dq_slot)
        if dq_report["error"]:
            await interaction.response.send_message(dq_report["error"], ephemeral=True)
            return

        self.report_view.finished = True
        self.report_view.disable_all_items()
        await interaction.response.defer(ephemeral=True)

        try:
            await config.startgg_client.report_set(
                set_id=int(self.report_view.match["set"]["id"]),
                winner_id=dq_report["winner_entrant_id"],
                is_dq=True,
                game_data=None,
            )
        except StartGGError as error:
            release_pending_report(int(self.report_view.match["set"]["id"]), self.report_view.player_discord_ids)
            await interaction.followup.send(f"Could not report DQ to start.gg: {error}", ephemeral=True)
            return

        release_pending_report(int(self.report_view.match["set"]["id"]), self.report_view.player_discord_ids)
        message = self.report_view.message
        if message:
            await message.edit(
                content=build_dq_report_success_message(self.report_view.match, dq_report, self.report_view.active_event),
                view=self.report_view,
            )
        await interaction.followup.send("DQ reported.", ephemeral=True)


def get_pending_report_message(set_id: int, player_discord_ids: set[int]) -> str | None:
    if set_id in pending_report_user_ids_by_set:
        return "There is already a pending report confirmation for this set."

    for player_discord_id in player_discord_ids:
        pending_set_id = pending_report_set_id_by_user.get(player_discord_id)
        if pending_set_id is not None:
            return (
                "One of the players already has a pending report confirmation. "
                "Confirm or cancel that report before creating another one."
            )

    return None


def register_pending_report(set_id: int, player_discord_ids: set[int]):
    pending_report_user_ids_by_set[set_id] = set(player_discord_ids)
    for player_discord_id in player_discord_ids:
        pending_report_set_id_by_user[player_discord_id] = set_id


def release_pending_report(set_id: int, player_discord_ids: set[int]):
    pending_report_user_ids_by_set.pop(set_id, None)
    for player_discord_id in player_discord_ids:
        if pending_report_set_id_by_user.get(player_discord_id) == set_id:
            pending_report_set_id_by_user.pop(player_discord_id, None)


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
    return is_luna_admin_user(ctx.guild, ctx.author)


def is_luna_admin_interaction(interaction: discord.Interaction) -> bool:
    return is_luna_admin_user(interaction.guild, interaction.user)


def is_luna_admin_user(guild: discord.Guild | None, user: discord.Member) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(user.guild_permissions.administrator)
    if guild and guild.get_role(admin_role_id) is None:
        return bool(user.guild_permissions.administrator)
    return any(role.id == admin_role_id for role in user.roles)


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


async def find_sets_for_event(event_id: int) -> list[dict]:
    matches = []
    phases = await config.startgg_client.get_event_phases(event_id)
    for phase in phases:
        phase_groups = await config.startgg_client.get_phase_groups(int(phase["id"]))
        for phase_group in phase_groups:
            sets = await config.startgg_client.get_phase_group_sets(int(phase_group["id"]))
            for set_data in sets:
                matches.append(
                    {
                        "phase": phase,
                        "phase_group": phase_group,
                        "set": set_data,
                    }
                )
    return sort_set_matches(matches)


def sort_set_matches(matches: list[dict]) -> list[dict]:
    return sorted(
        matches,
        key=lambda match: (
            str(match["phase"].get("name") or ""),
            str(match["phase_group"].get("displayIdentifier") or ""),
            get_set_round(match["set"]),
            int(match["set"].get("id") or 0),
        ),
    )


def find_next_pending_match(matches: list[dict]) -> dict | None:
    pending_matches = [
        match for match in matches
        if is_pending_set(match["set"]) and has_two_entrants(match["set"])
    ]
    if not pending_matches:
        return None

    return sorted(
        pending_matches,
        key=lambda match: (
            get_set_round(match["set"]),
            str(match["phase"].get("name") or ""),
            str(match["phase_group"].get("displayIdentifier") or ""),
            int(match["set"].get("id") or 0),
        ),
    )[0]


def is_pending_set(set_data: dict) -> bool:
    state = set_data.get("state")
    return str(state).casefold() not in {"3", "completed"}


def has_two_entrants(set_data: dict) -> bool:
    return len([slot for slot in set_data.get("slots") or [] if slot.get("entrant")]) == 2


def get_set_round(set_data: dict) -> int:
    try:
        return int(set_data.get("round"))
    except (TypeError, ValueError):
        return 999999


def build_player_report_payload(set_data: dict, player_id: int, score: tuple[int, int]) -> dict:
    player_slot = find_slot_by_player_id(set_data.get("slots") or [], player_id)
    if player_slot is None:
        return {"error": "You are not part of this set."}

    opponent_slot = find_opponent_slot(set_data, player_slot)
    if opponent_slot is None:
        return {"error": "This set does not have an opponent yet."}

    player_score, opponent_score = score
    if player_score > opponent_score:
        winner_player_id = player_id
    else:
        winner_player_id = get_slot_player_id(opponent_slot)
        if winner_player_id is None:
            return {"error": "Could not find your opponent's start.gg player ID."}

    report = build_report_payload(set_data, winner_player_id, score)
    if report["error"]:
        return report

    report["player_name"] = player_slot["entrant"]["name"]
    report["player_score"] = player_score
    report["player_id"] = player_id
    report["opponent_name"] = opponent_slot["entrant"]["name"]
    report["opponent_score"] = opponent_score
    report["opponent_player_id"] = get_slot_player_id(opponent_slot)
    return report


def find_opponent_slot(set_data: dict, player_slot: dict) -> dict | None:
    for slot in set_data.get("slots") or []:
        if slot.get("entrant") and slot != player_slot:
            return slot
    return None


def get_slot_player_id(slot: dict) -> int | None:
    entrant = slot.get("entrant") or {}
    for participant in entrant.get("participants") or []:
        player = participant.get("player") or {}
        player_id = player.get("id")
        if player_id is not None:
            return int(player_id)
    return None


def build_player_report_success_message(match: dict, report: dict, active_event: dict) -> str:
    set_data = match["set"]
    phase = match["phase"]
    phase_group = match["phase_group"]
    phase_group_label = phase_group.get("displayIdentifier") or phase_group["id"]
    round_text = set_data.get("fullRoundText") or f"Round {set_data.get('round')}"
    return (
        f"Score reported for {active_event['event_name']}.\n"
        f"{phase['name']} - Group {phase_group_label} | {round_text}\n"
        f"Set ID: {set_data['id']}\n"
        f"{report['player_name']} {report['player_score']} - "
        f"{report['opponent_score']} {report['opponent_name']}"
    )


def build_player_report_confirmation_message(match: dict, report: dict, confirmed_count: int = 0) -> str:
    set_data = match["set"]
    phase = match["phase"]
    phase_group = match["phase_group"]
    phase_group_label = phase_group.get("displayIdentifier") or phase_group["id"]
    round_text = set_data.get("fullRoundText") or f"Round {set_data.get('round')}"
    return (
        "Resultado a reportar:\n"
        f"{report['player_name']} ({report['player_score']}) - "
        f"({report['opponent_score']}) {report['opponent_name']}.\n\n"
        f"{phase['name']} - Group {phase_group_label} | {round_text}\n"
        f"Set ID: {set_data['id']}\n\n"
        "Seleccionen ✅ para confirmar o ❌ para cancelar.\n"
        f"Confirmaciones: {confirmed_count}/2"
    )


def build_admin_help_message(match: dict) -> str:
    admin_role_id = config.config_store.get_admin_role_id()
    admin_mention = f"<@&{admin_role_id}>" if admin_role_id else "Luna admins"
    return (
        f"{admin_mention} help requested for this set.\n"
        f"{format_match_card(match)}"
    )


def build_dq_report_payload(set_data: dict, dq_slot: dict) -> dict:
    slots = [slot for slot in set_data.get("slots") or [] if slot.get("entrant")]
    if len(slots) != 2:
        return {"error": "This set does not have exactly two entrants yet."}
    if dq_slot not in slots:
        return {"error": "The selected DQ player is not part of this set."}

    winner_slot = slots[0] if slots[1] == dq_slot else slots[1]
    dq_entrant = dq_slot["entrant"]
    winner_entrant = winner_slot["entrant"]
    return {
        "error": None,
        "winner_entrant_id": int(winner_entrant["id"]),
        "winner_name": winner_entrant["name"],
        "dq_entrant_id": int(dq_entrant["id"]),
        "dq_name": dq_entrant["name"],
    }


def build_dq_report_success_message(match: dict, dq_report: dict, active_event: dict) -> str:
    set_data = match["set"]
    phase = match["phase"]
    phase_group = match["phase_group"]
    phase_group_label = phase_group.get("displayIdentifier") or phase_group["id"]
    round_text = set_data.get("fullRoundText") or f"Round {set_data.get('round')}"
    return (
        f"DQ reported for {active_event['event_name']}.\n"
        f"{phase['name']} - Group {phase_group_label} | {round_text}\n"
        f"Set ID: {set_data['id']}\n"
        f"Winner: {dq_report['winner_name']}\n"
        f"DQ: {dq_report['dq_name']}"
    )


def find_dq_slot(set_data: dict, value: str) -> dict | None:
    value = value.strip()
    slots = [slot for slot in set_data.get("slots") or [] if slot.get("entrant")]
    if value in {"1", "2"}:
        slot_index = int(value) - 1
        return slots[slot_index] if slot_index < len(slots) else None

    normalized_value = normalize_lookup_text(value)
    matches = []
    for slot in slots:
        entrant = slot["entrant"]
        if str(entrant.get("id")) == value:
            matches.append(slot)
            continue
        if normalize_lookup_text(entrant.get("name") or "") == normalized_value:
            matches.append(slot)

    return matches[0] if len(matches) == 1 else None


def format_set_inspection(set_data: dict) -> str:
    lines = [
        f"Set inspection for `{set_data['id']}`",
        f"Round: {get_set_round_label(set_data)}",
        f"State: {set_data.get('state')}",
        f"Winner ID: {set_data.get('winnerId')}",
        "",
        "Slots:",
    ]

    for index, slot in enumerate(set_data.get("slots") or [], start=1):
        entrant = slot.get("entrant") or {}
        standing = slot.get("standing") or {}
        stats = standing.get("stats") or {}
        score = (stats.get("score") or {}).get("value")
        player_ids = [
            str((participant.get("player") or {}).get("id"))
            for participant in entrant.get("participants") or []
            if (participant.get("player") or {}).get("id") is not None
        ]
        lines.append(
            f"- Slot {index}: entrant `{entrant.get('id')}` {entrant.get('name')} | "
            f"score: `{score}` | placement: `{standing.get('placement')}` | "
            f"players: {', '.join(player_ids) or 'none'}"
        )

    games = set_data.get("games") or []
    lines.extend(["", f"Games: {len(games)}"])
    for game in games[:10]:
        selections = game.get("selections") or []
        selection_labels = [
            f"`{(selection.get('entrant') or {}).get('id')}` {(selection.get('entrant') or {}).get('name')}"
            for selection in selections
        ]
        lines.append(
            f"- Game `{game.get('id')}` | state: `{game.get('state')}` | "
            f"winnerId: `{game.get('winnerId')}` | selections: {', '.join(selection_labels) or 'none'}"
        )

    if len(games) > 10:
        lines.append(f"...and {len(games) - 10} more games.")

    return format_lines_response("", lines).lstrip()


def build_next_set_embed(active_event: dict, link: dict | None, player_matches: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"{active_event['event_name']} sets",
        description="Your next pending set",
        color=discord.Color.gold(),
    )
    embed.url = f"https://www.start.gg/{active_event['event_slug']}"

    if link is None:
        embed.description = "No linked start.gg account"
        embed.add_field(
            name="Next set",
            value="Link your account with `/startgg account` to see your next set.",
            inline=False,
        )
        return embed

    next_match = find_next_pending_match(player_matches)
    if next_match is None:
        embed.add_field(
            name="Next set",
            value="No pending sets found for your linked player.",
            inline=False,
        )
        return embed

    embed.add_field(name="Next set", value=format_match_card(next_match), inline=False)
    remaining_pending = [
        match for match in player_matches
        if is_pending_set(match["set"]) and has_two_entrants(match["set"])
    ]
    if len(remaining_pending) > 1:
        embed.set_footer(text=f"{len(remaining_pending) - 1} more pending set(s) after this one")
    return embed


def build_my_sets_embed(active_event: dict, link: dict | None, player_matches: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"{active_event['event_name']} sets",
        description="Your sets",
        color=discord.Color.gold(),
    )
    embed.url = f"https://www.start.gg/{active_event['event_slug']}"

    if link is None:
        embed.description = "No linked start.gg account"
        embed.add_field(
            name="My sets",
            value="Link your account with `/startgg account` to see your sets.",
            inline=False,
        )
        return embed

    if not player_matches:
        embed.add_field(
            name="My sets",
            value="No sets found for your linked player in this event.",
            inline=False,
        )
        return embed

    for match in player_matches[:8]:
        embed.add_field(
            name=format_match_title(match),
            value=format_match_pair(match["set"]),
            inline=False,
        )
    if len(player_matches) > 8:
        embed.set_footer(text=f"{len(player_matches) - 8} more set(s) not shown")
    return embed


def build_general_sets_embed(active_event: dict, event_matches: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"{active_event['event_name']} sets",
        description="General set information",
        color=discord.Color.gold(),
    )
    embed.url = f"https://www.start.gg/{active_event['event_slug']}"

    if not event_matches:
        embed.add_field(name="Sets", value="No sets found for this event.", inline=False)
        return embed

    pending_matches = [
        match for match in event_matches
        if is_pending_set(match["set"]) and has_two_entrants(match["set"])
    ]
    completed_count = len(event_matches) - len(pending_matches)
    embed.add_field(name="Total sets", value=str(len(event_matches)), inline=True)
    embed.add_field(name="Pending", value=str(len(pending_matches)), inline=True)
    embed.add_field(name="Completed", value=str(completed_count), inline=True)

    matches_to_show = pending_matches[:8] if pending_matches else event_matches[:8]
    for match in matches_to_show:
        embed.add_field(
            name=format_match_title(match),
            value=format_match_pair(match["set"]),
            inline=False,
        )
    hidden_count = len(event_matches) - len(matches_to_show)
    if hidden_count > 0:
        embed.set_footer(text=f"{hidden_count} more set(s) not shown")
    return embed


def format_match_card(match: dict) -> str:
    set_data = match["set"]
    return (
        f"{format_match_title(match)}\n"
        f"{format_match_pair(set_data)}\n"
        f"Set ID: `{set_data['id']}`"
    )


def format_match_title(match: dict) -> str:
    phase = match["phase"]
    phase_group = match["phase_group"]
    set_data = match["set"]
    phase_group_label = phase_group.get("displayIdentifier") or phase_group["id"]
    round_text = set_data.get("fullRoundText") or f"Round {set_data.get('round')}"
    return f"{phase['name']} - Group {phase_group_label} | {round_text}"


def format_match_pair(set_data: dict) -> str:
    slots = set_data.get("slots") or []
    entrants = [format_slot_name_with_score(slot) for slot in slots]
    while len(entrants) < 2:
        entrants.append("TBD")
    return f"{entrants[0]} vs {entrants[1]}"


def format_slot_name_with_score(slot: dict) -> str:
    entrant = slot.get("entrant")
    if entrant is None:
        return "TBD"

    score = get_slot_score(slot)
    score_text = f" ({score})" if score is not None else ""
    return f"{entrant.get('name') or 'Unnamed'}{score_text}"


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
    required_winner_score = get_required_winner_score(set_data)
    if winner_score != required_winner_score:
        return {
            "error": (
                "Invalid score for this round. "
                f"{get_set_round_label(set_data)} requires the winner to reach {required_winner_score} points."
            )
        }
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


def get_required_winner_score(set_data: dict) -> int:
    round_text = normalize_lookup_text(get_set_round_label(set_data))
    if "grand final" in round_text:
        return 10
    if round_text in {"winners final", "losers final"}:
        return 9
    return 7


def get_set_round_label(set_data: dict) -> str:
    return set_data.get("fullRoundText") or f"Round {set_data.get('round')}"


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
