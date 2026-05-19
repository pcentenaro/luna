import discord

import config


LUNA_AVATAR_URL = "https://cdn.discordapp.com/avatars/1501361206106132591/34addba16ae128186eb6c18777e71865.png?size=4096"


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Set event", style=discord.ButtonStyle.primary, row=0)
    async def set_event(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Set event flow coming next.", ephemeral=True)

    @discord.ui.button(label="Clear event", style=discord.ButtonStyle.danger, row=0)
    async def clear_event(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Clear event flow coming next.", ephemeral=True)

    @discord.ui.button(label="Start.gg status", style=discord.ButtonStyle.secondary, row=0)
    async def startgg_status(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Start.gg status check coming next.", ephemeral=True)

    @discord.ui.button(label="Set admin role", style=discord.ButtonStyle.primary, row=1)
    async def set_admin_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Set admin role flow coming next.", ephemeral=True)

    @discord.ui.button(label="Clear admin role", style=discord.ButtonStyle.danger, row=1)
    async def clear_admin_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Clear admin role flow coming next.", ephemeral=True)


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
