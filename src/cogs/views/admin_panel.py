import discord

import config
from participant_role import remove_participant_roles, sync_participant_role
from startgg import StartGGError, format_user_display_name


LUNA_AVATAR_URL = "https://cdn.discordapp.com/avatars/1501361206106132591/34addba16ae128186eb6c18777e71865.png?size=4096"


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Set event", style=discord.ButtonStyle.primary, row=0)
    async def set_event(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can set the active event.", ephemeral=True)
            return

        await interaction.response.send_modal(SetEventModal())

    @discord.ui.button(label="Clear event", style=discord.ButtonStyle.danger, row=0)
    async def clear_event(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can clear the active event.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            removal_result = await remove_participant_roles(interaction.guild)
        except StartGGError as error:
            await interaction.followup.send(
                f"Could not remove participant roles, so the event was not cleared: {error}",
                ephemeral=True,
            )
            return

        if removal_result and removal_result["failed"]:
            await interaction.followup.send(
                f"Could not remove {removal_result['failed']} participant role(s), so the event was not cleared.",
                ephemeral=True,
            )
            return

        deleted = config.config_store.clear_active_event()
        await refresh_admin_panel(interaction)
        if deleted:
            await interaction.followup.send(
                f"Active start.gg event cleared.{format_role_removal_result(removal_result)}",
                ephemeral=True,
            )
            return

        await interaction.followup.send("No active start.gg event was configured.", ephemeral=True)

    @discord.ui.button(label="Start.gg status", style=discord.ButtonStyle.secondary, row=0)
    async def startgg_status(self, button: discord.ui.Button, interaction: discord.Interaction):
        if config.startgg_client is None:
            await interaction.response.send_message("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            user = await config.startgg_client.get_current_user()
        except StartGGError as error:
            await interaction.followup.send(f"start.gg connection failed: {error}", ephemeral=True)
            return

        if user is None:
            await interaction.followup.send("Connected to start.gg, but no current user was returned.", ephemeral=True)
            return

        display_name = format_user_display_name(user)
        await interaction.followup.send(f"Connected to start.gg as {display_name}.", ephemeral=True)

    @discord.ui.button(label="Set admin role", style=discord.ButtonStyle.primary, row=1)
    async def set_admin_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not can_configure_admin_role(interaction):
            await interaction.response.send_message("You cannot configure Luna admin roles.", ephemeral=True)
            return

        await interaction.response.send_modal(SetAdminRoleModal())

    @discord.ui.button(label="Clear admin role", style=discord.ButtonStyle.danger, row=1)
    async def clear_admin_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can clear the admin role.", ephemeral=True)
            return

        deleted = config.config_store.clear_admin_role_id()
        await refresh_admin_panel_response(interaction)
        if deleted:
            await interaction.followup.send("Luna admin role cleared.", ephemeral=True)
            return

        await interaction.followup.send("No Luna admin role was configured.", ephemeral=True)

    @discord.ui.button(label="Set participant role", style=discord.ButtonStyle.primary, row=1)
    async def set_participant_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can set the participant role.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Choose an existing server role for registered tournament participants.",
            view=ParticipantRoleView(interaction.message),
            ephemeral=True,
        )

    @discord.ui.button(label="Set score targets", style=discord.ButtonStyle.primary, row=2)
    async def set_score_targets(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can set score targets.", ephemeral=True)
            return

        await interaction.response.send_modal(SetScoreTargetsModal())

    @discord.ui.button(label="Linked accounts", style=discord.ButtonStyle.secondary, row=2)
    async def linked_accounts(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message(
                "Only Luna admins can review linked accounts.",
                ephemeral=True,
            )
            return

        if config.startgg_client is None:
            await interaction.response.send_message("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        active_event = config.config_store.get_active_event()
        if active_event is None:
            await interaction.response.send_message("No active start.gg event is configured yet.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral= False)
        try:
            entrants = await config.startgg_client.get_event_entrants(active_event["event_id"])
        except StartGGError as error:
            await interaction.followup.send(
                f"Could not read attendees from start.gg: {error}",
                ephemeral=True,
            )
            return

        embed = build_linked_accounts_embed(active_event, entrants, interaction.guild)
        await interaction.followup.send(
            embed=embed,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @discord.ui.button(label="Channel settings", style=discord.ButtonStyle.secondary, row=2)
    async def channel_settings(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can configure channels.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("This setting is only available in a server.", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=build_channel_settings_embed(interaction.guild),
            view=ChannelSettingsView(),
            ephemeral=True,
        )


class ChannelSettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(LeaderboardChannelSelect())

    @discord.ui.button(label="Clear ranking channel", style=discord.ButtonStyle.danger, row=1)
    async def clear_clues_ranking_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can clear the ranking channel.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("This setting is only available in a server.", ephemeral=True)
            return

        deleted = config.clues_store.clear_leaderboard_channel_id(interaction.guild.id)
        await refresh_channel_settings_response(interaction)
        message = "Guess the Clues ranking channel cleared." if deleted else "No ranking channel was configured."
        await interaction.followup.send(message, ephemeral=True)


class ParticipantRoleView(discord.ui.View):
    def __init__(self, panel_message: discord.Message | None):
        super().__init__(timeout=300)
        self.add_item(ParticipantRoleSelect(panel_message))


class ParticipantRoleSelect(discord.ui.Select):
    def __init__(self, panel_message: discord.Message | None):
        self.panel_message = panel_message
        super().__init__(
            select_type=discord.ComponentType.role_select,
            custom_id="admin:participant_role",
            placeholder="Choose the tournament participant role",
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can set the participant role.", ephemeral=True)
            return

        role = self.values[0]
        bot_member = interaction.guild.me if interaction.guild else None
        if role.is_default() or role.managed or bot_member is None or role >= bot_member.top_role:
            await interaction.response.send_message(
                "Luna cannot assign that role. Move Luna above it and choose a regular server role.",
                ephemeral=True,
            )
            return

        config.config_store.set_participant_role_id(role.id)
        await interaction.response.defer(ephemeral=True)
        try:
            sync_result = await sync_participant_role(interaction.guild)
        except StartGGError as error:
            sync_result = None
            sync_error = f" Could not sync start.gg attendees: {error}"
        else:
            sync_error = ""

        if self.panel_message:
            try:
                await self.panel_message.edit(
                    embed=build_admin_panel_embed(interaction.guild),
                    view=AdminPanelView(),
                )
            except (discord.Forbidden, discord.NotFound):
                pass

        await interaction.followup.send(
            f"Tournament participant role set to {role.mention}.{format_role_sync_result(sync_result)}{sync_error}",
            ephemeral=True,
        )


class LeaderboardChannelSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            select_type=discord.ComponentType.channel_select,
            custom_id="admin:clues_leaderboard_channel",
            placeholder="Choose the Guess the Clues ranking channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_luna_admin(interaction):
            await interaction.response.send_message("Only Luna admins can set the ranking channel.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("This setting is only available in a server.", ephemeral=True)
            return

        channel = self.values[0]
        bot_member = interaction.guild.me
        if bot_member is None or not channel.permissions_for(bot_member).send_messages:
            await interaction.response.send_message("Luna cannot send messages in that channel.", ephemeral=True)
            return

        config.clues_store.set_leaderboard_channel_id(interaction.guild.id, channel.id)
        await refresh_channel_settings_response(interaction)
        await interaction.followup.send(f"Guess the Clues rankings will be posted in {channel.mention}.", ephemeral=True)


def build_channel_settings_embed(guild: discord.Guild) -> discord.Embed:
    leaderboard_channel_id = config.clues_store.get_leaderboard_channel_id(guild.id)
    leaderboard_channel_value = "Not configured"
    if leaderboard_channel_id:
        channel = guild.get_channel(leaderboard_channel_id)
        leaderboard_channel_value = channel.mention if channel else f"Missing channel ID `{leaderboard_channel_id}`"

    embed = discord.Embed(
        title="Channel settings",
        description="Choose where Luna posts automated messages.",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Guess the Clues ranking", value=leaderboard_channel_value)
    return embed


def build_admin_panel_embed(guild: discord.Guild | None) -> discord.Embed:
    active_event = config.config_store.get_active_event()
    admin_role_id = config.config_store.get_admin_role_id()
    participant_role_id = config.config_store.get_participant_role_id()
    score_targets = config.config_store.get_score_targets()

    event_value = "Not configured"
    if active_event:
        event_value = (
            f"{active_event['event_name']}\n"
            f"`{active_event['event_slug']}`\n"
            f"ID: `{active_event['event_id']}`"
        )

    admin_role_value = "Not configured"
    if admin_role_id:
        role = guild.get_role(admin_role_id) if guild else None
        admin_role_value = role.mention if role else f"Missing role ID `{admin_role_id}`"

    participant_role_value = "Not configured"
    if participant_role_id:
        role = guild.get_role(participant_role_id) if guild else None
        participant_role_value = role.mention if role else f"Missing role ID `{participant_role_id}`"

    startgg_value = "Configured" if config.startgg_client else "STARTGG_API_KEY missing"

    embed = discord.Embed(
        title="Luna Admin Panel",
        description="Use the buttons below to manage tournament setup.",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=LUNA_AVATAR_URL)
    embed.add_field(name="Active event", value=event_value, inline=False)
    embed.add_field(name="Admin role", value=admin_role_value, inline=True)
    embed.add_field(name="Participant role", value=participant_role_value, inline=True)
    embed.add_field(name="Start.gg", value=startgg_value, inline=True)
    embed.add_field(
        name="Score targets",
        value=(
            f"Pools/bracket: `{score_targets['default']}`\n"
            f"Winners/Losers Final: `{score_targets['final']}`\n"
            f"Grand Final: `{score_targets['grand_final']}`"
        ),
        inline=False,
    )
    embed.set_footer(text="Copa Luna tournament tools")
    return embed

def build_linked_accounts_embed(
    active_event: dict,
    entrants: list[dict],
    guild: discord.Guild | None,
) -> discord.Embed:
    links_by_player_id = {
        str(link["startgg_player_id"]): link
        for link in config.link_store.get_all_startgg_links()
        if link.get("startgg_player_id") is not None
    }
    attendees = build_attendee_link_statuses(entrants, links_by_player_id)
    linked_attendees = [attendee for attendee in attendees if attendee["link"] is not None]
    unlinked_attendees = [attendee for attendee in attendees if attendee["link"] is None]

    embed = discord.Embed(
        title=f"{active_event['event_name']} linked accounts",
        description=(
            f"**Attendees:** {len(attendees)}\n"
            f"**Linked:** {len(linked_attendees)}\n"
            f"**Not linked:** {len(unlinked_attendees)}"
        ),
        color=discord.Color.gold(),
        url=f"https://www.start.gg/{active_event['event_slug']}",
    )
    add_link_status_fields(
        embed,
        "Linked",
        [
            format_linked_attendee(attendee, guild)
            for attendee in linked_attendees
        ],
    )
    add_link_status_fields(
        embed,
        "Not linked",
        [
            f"Not linked: **{discord.utils.escape_markdown(attendee['name'])}**"
            for attendee in unlinked_attendees
        ],
    )
    embed.set_footer(text="Account links are stored by start.gg player ID.")
    return embed


def build_attendee_link_statuses(entrants: list[dict], links_by_player_id: dict[str, dict]) -> list[dict]:
    attendees = []
    for entrant in entrants:
        participants = entrant.get("participants") or []
        if not participants:
            attendees.append(
                {
                    "name": entrant.get("name") or f"Entrant {entrant.get('id')}",
                    "player_id": None,
                    "link": None,
                }
            )
            continue

        for participant in participants:
            player = participant.get("player") or {}
            player_id = player.get("id")
            gamer_tag = participant.get("gamerTag") or player.get("gamerTag") or entrant.get("name")
            prefix = player.get("prefix")
            display_name = f"{prefix} | {gamer_tag}" if prefix and gamer_tag else gamer_tag
            attendees.append(
                {
                    "name": display_name or f"Participant {participant.get('id')}",
                    "player_id": player_id,
                    "link": links_by_player_id.get(str(player_id)) if player_id is not None else None,
                }
            )

    return sorted(attendees, key=lambda attendee: attendee["name"].casefold())


def format_linked_attendee(attendee: dict, guild: discord.Guild | None) -> str:
    discord_user_id = int(attendee["link"]["discord_user_id"])
    member = guild.get_member(discord_user_id) if guild else None
    discord_profile = member.mention if member else f"<@{discord_user_id}>"
    startgg_name = discord.utils.escape_markdown(attendee["name"])
    return f"Linked: **{startgg_name}** -> {discord_profile}"


def add_link_status_fields(embed: discord.Embed, title: str, lines: list[str]):
    chunks = chunk_embed_lines(lines)
    for index, chunk in enumerate(chunks):
        field_name = title if index == 0 else f"{title} (continued)"
        embed.add_field(name=field_name, value=chunk, inline=False)


def chunk_embed_lines(lines: list[str], limit: int = 900) -> list[str]:
    if not lines:
        return ["None"]

    chunks = []
    current_lines = []
    current_length = 0
    for line in lines:
        added_length = len(line) + (1 if current_lines else 0)
        if current_lines and current_length + added_length > limit:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_length = 0

        current_lines.append(line)
        current_length += len(line) + (1 if len(current_lines) > 1 else 0)

    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


class SetEventModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set active start.gg event")
        self.add_item(
            discord.ui.InputText(
                label="Tournament slug",
                value="copa-luna-xx",
                required=True,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Event slug",
                value="puyo-singles",
                required=True,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        tournament_slug = self.children[0].value
        event_slug = self.children[1].value

        if config.startgg_client is None:
            await interaction.response.send_message("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        full_event_slug = build_event_slug(tournament_slug, event_slug)
        await interaction.response.defer(ephemeral=True)

        try:
            event = await config.startgg_client.get_event_by_slug(full_event_slug)
        except StartGGError as error:
            await interaction.followup.send(f"Could not verify that start.gg event: {error}", ephemeral=True)
            return

        if event is None:
            await interaction.followup.send(f"No start.gg event was found for `{full_event_slug}`.", ephemeral=True)
            return

        config.config_store.set_active_event(
            tournament_slug=tournament_slug,
            event_slug=full_event_slug,
            event_id=int(event["id"]),
            event_name=event["name"],
        )
        try:
            sync_result = await sync_participant_role(interaction.guild)
        except StartGGError as error:
            sync_result = None
            sync_error = f" Could not sync participant roles: {error}"
        else:
            sync_error = ""
        await refresh_admin_panel(interaction)
        await interaction.followup.send(
            f"Active event set to {event['name']} (`{full_event_slug}`).{format_role_sync_result(sync_result)}{sync_error}",
            ephemeral=True,
        )


class SetAdminRoleModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Luna admin role")
        self.add_item(
            discord.ui.InputText(
                label="Role ID or mention",
                placeholder="@Admin, <@&123456789>, or 123456789",
                required=True,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        role = find_role(interaction.guild, self.children[0].value)
        if role is None:
            await interaction.response.send_message("No role found with that ID, mention, or name in this server.", ephemeral=True)
            return

        config.config_store.set_admin_role_id(role.id)
        await refresh_admin_panel(interaction)
        await interaction.response.send_message(f"Luna admin role set to {role.mention}.", ephemeral=True)


class SetScoreTargetsModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set score targets")
        score_targets = config.config_store.get_score_targets()
        self.add_item(
            discord.ui.InputText(
                label="Pools/bracket",
                placeholder="7",
                value=str(score_targets["default"]),
                required=True,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Winners/Losers Final",
                placeholder="9",
                value=str(score_targets["final"]),
                required=True,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Grand Final",
                placeholder="10",
                value=str(score_targets["grand_final"]),
                required=True,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        parsed_scores = []
        for child in self.children:
            score = parse_positive_int(child.value)
            if score is None:
                await interaction.response.send_message(
                    f"`{child.label}` must be a positive whole number.",
                    ephemeral=True,
                )
                return
            parsed_scores.append(score)

        config.config_store.set_score_targets(
            default=parsed_scores[0],
            final=parsed_scores[1],
            grand_final=parsed_scores[2],
        )
        await refresh_admin_panel(interaction)
        await interaction.response.send_message(
            (
                "Score targets updated: "
                f"pools/bracket `{parsed_scores[0]}`, "
                f"Winners/Losers Final `{parsed_scores[1]}`, "
                f"Grand Final `{parsed_scores[2]}`."
            ),
            ephemeral=True,
        )


async def refresh_admin_panel_response(interaction: discord.Interaction):
    if not interaction.message:
        await interaction.response.defer(ephemeral=True)
        return False

    try:
        await interaction.response.edit_message(
            embed=build_admin_panel_embed(interaction.guild),
            view=AdminPanelView(),
        )
    except (discord.Forbidden, discord.NotFound):
        await interaction.response.defer(ephemeral=True)
        return False

    return True


async def refresh_channel_settings_response(interaction: discord.Interaction):
    await interaction.response.edit_message(
        embed=build_channel_settings_embed(interaction.guild),
        view=ChannelSettingsView(),
    )


async def refresh_admin_panel(interaction: discord.Interaction):
    if not interaction.message:
        return False

    try:
        await interaction.message.edit(
            embed=build_admin_panel_embed(interaction.guild),
            view=AdminPanelView(),
        )
    except (discord.Forbidden, discord.NotFound):
        return False

    return True


def is_luna_admin(interaction: discord.Interaction) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(interaction.user.guild_permissions.administrator)

    if interaction.guild and interaction.guild.get_role(admin_role_id) is None:
        return bool(interaction.user.guild_permissions.administrator)

    return any(role.id == admin_role_id for role in interaction.user.roles)


def can_configure_admin_role(interaction: discord.Interaction) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(interaction.user.guild_permissions.administrator)

    if interaction.guild and interaction.guild.get_role(admin_role_id) is None:
        return bool(interaction.user.guild_permissions.administrator)

    return is_luna_admin(interaction)


def find_role(guild: discord.Guild | None, value: str) -> discord.Role | None:
    if guild is None:
        return None

    role_id = parse_role_id(value)
    if role_id is not None:
        role = guild.get_role(role_id)
        if role:
            return role

    role_name = normalize_role_name(value)
    exact_match = discord.utils.get(guild.roles, name=role_name)
    if exact_match:
        return exact_match

    lowercase_matches = [
        role for role in guild.roles
        if role.name.casefold() == role_name.casefold()
    ]
    if len(lowercase_matches) == 1:
        return lowercase_matches[0]

    return None


def parse_role_id(value: str) -> int | None:
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return None

    return int(digits)


def parse_positive_int(value: str) -> int | None:
    try:
        parsed_value = int(value.strip())
    except ValueError:
        return None

    if parsed_value < 1:
        return None

    return parsed_value


def normalize_role_name(value: str) -> str:
    value = value.strip()
    if value.startswith("@"):
        value = value[1:]
    return value.strip()


def format_role_sync_result(result: dict | None) -> str:
    if result is None:
        return ""
    return (
        f" Assigned to {result['assigned']} linked participant(s); "
        f"{result['already']} already had it, {result['removed']} removed, "
        f"{result['missing']} are not in this server, "
        f"and {result['failed']} failed."
    )


def format_role_removal_result(result: dict | None) -> str:
    if result is None:
        return ""
    return (
        f" Removed from {result['removed']} linked participant(s); "
        f"{result['absent']} did not have it, {result['missing']} are not in this server, "
        f"and {result['failed']} failed."
    )


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
