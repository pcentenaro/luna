import config
import discord
from discord.ext import commands
from startgg import StartGGError

class Startgg(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    startgg = discord.SlashCommandGroup("startgg")


    @startgg.command(
            name="link_startgg",
            description="Link your Discord account to a start.gg profile"
    )
    async def link_startgg(self, ctx: discord.ApplicationContext, player_id: str):
        if config.startgg_client is None:
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
        config.link_store.set_startgg_link(
            discord_user_id=ctx.author.id,
            startgg_player_id=int(player["id"]),
            gamer_tag=player.get("gamerTag"),
            prefix=player.get("prefix"),
        )
        display_name = format_startgg_player(player)
        await ctx.respond(f"Linked your Discord account to start.gg player: {display_name}. // Tu cuenta de Discord ha sido vinculada al siguiente perfil de start.gg: {display_name}", ephemeral=True)


    @startgg.command(
            name="unlink_startgg",
            description="Remove your start.gg player link"
    )
    async def unlink_startgg(self, ctx: discord.ApplicationContext):
        deleted = config.link_store.delete_startgg_link(ctx.author.id)
        if deleted:
            await ctx.respond("Removed your start.gg link. // Vinculo a start.gg eliminado.", ephemeral=True)
            return
        await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)
    

    @startgg.command(
            name="whoami_startgg",
            description="Show your linked start.gg player")
    async def whoami_startgg(self, ctx: discord.ApplicationContext):
        link = config.link_store.get_startgg_link(ctx.author.id)
        if link is None:
            await ctx.respond("You do not have a start.gg link yet. // No estás vinculado a start.gg aún.", ephemeral=True)
            return
        display_name = format_stored_startgg_player(link)
        await ctx.respond(
            f"Your Discord account is linked to start.gg player {display_name} "
            f"(ID: {link['startgg_player_id']}).",
            ephemeral=True,
        )
    
    
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
    

    @startgg.command(name="list_phases", description="List phases for the active start.gg event")
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


    @startgg.command(name="list_phase_groups", description="List pools or brackets for a start.gg phase")
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


def setup(bot):
    bot.add_cog(Startgg(bot))


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