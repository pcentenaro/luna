import discord

import config
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

        deleted = config.config_store.clear_active_event()
        await refresh_admin_panel_response(interaction)
        if deleted:
            await interaction.followup.send("Active start.gg event cleared.", ephemeral=True)
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


def build_admin_panel_embed(guild: discord.Guild | None) -> discord.Embed:
    active_event = config.config_store.get_active_event()
    admin_role_id = config.config_store.get_admin_role_id()

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

    startgg_value = "Configured" if config.startgg_client else "STARTGG_API_KEY missing"

    embed = discord.Embed(
        title="Luna Admin Panel",
        description="Use the buttons below to manage tournament setup.",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=LUNA_AVATAR_URL)
    embed.add_field(name="Active event", value=event_value, inline=False)
    embed.add_field(name="Admin role", value=admin_role_value, inline=True)
    embed.add_field(name="Start.gg", value=startgg_value, inline=True)
    embed.set_footer(text="Copa Luna tournament tools")
    return embed


class SetEventModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set active start.gg event")
        self.add_item(
            discord.ui.InputText(
                label="Tournament slug",
                placeholder="torneo-pruebas-bot-luna",
                required=True,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Event slug",
                placeholder="puyo-singles",
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
        await refresh_admin_panel(interaction)
        await interaction.followup.send(
            f"Active event set to {event['name']} (`{full_event_slug}`).",
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


async def refresh_admin_panel_response(interaction: discord.Interaction):
    if interaction.message:
        await interaction.response.edit_message(
            embed=build_admin_panel_embed(interaction.guild),
            view=AdminPanelView(),
        )
        return

    await interaction.response.defer(ephemeral=True)


async def refresh_admin_panel(interaction: discord.Interaction):
    if interaction.message:
        await interaction.message.edit(
            embed=build_admin_panel_embed(interaction.guild),
            view=AdminPanelView(),
        )


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


def normalize_role_name(value: str) -> str:
    value = value.strip()
    if value.startswith("@"):
        value = value[1:]
    return value.strip()


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
