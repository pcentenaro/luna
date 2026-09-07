import asyncio

import config
import discord
from discord.ext import commands
from seeding import build_player_standings, rank_players, split_into_brackets
from startgg import StartGGError


class Seeding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="seeding",
        description="Calculate final bracket splits and seeds from completed pools",
    )
    async def seeding(self, ctx: discord.ApplicationContext):
        if not is_luna_admin(ctx):
            await ctx.respond("Only Luna admins can calculate seeding.", ephemeral=True)
            return

        if config.startgg_client is None:
            await ctx.respond("STARTGG_API_KEY is not configured yet.", ephemeral=True)
            return

        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet.", ephemeral=True)
            return

        await ctx.defer()
        try:
            pool_groups = await get_completed_pool_groups(active_event["event_id"])
        except StartGGError as error:
            await ctx.respond(f"Could not read pool data from start.gg: {error}", ephemeral=True)
            return

        if pool_groups["error"]:
            await ctx.respond(pool_groups["error"], ephemeral=True)
            return

        group_results = await asyncio.gather(*[
            load_pool_seeding_data(phase_group)
            for phase_group in pool_groups["groups"]
        ])
        players = [
            player
            for group_players in group_results
            for player in group_players
        ]
        if not players:
            await ctx.respond("No pool standings were found for this event.", ephemeral=True)
            return

        ranked, ranking_warnings = rank_players(players)
        brackets = split_into_brackets(ranked)
        await ctx.respond(
            embeds=build_seeding_embeds(
                active_event=active_event,
                ranked=ranked,
                brackets=brackets,
                ranking_warnings=ranking_warnings,
            ),
        )


def setup(bot):
    bot.add_cog(Seeding(bot))


async def get_completed_pool_groups(event_id: int) -> dict:
    phases = await config.startgg_client.get_event_phases(event_id)
    phase_group_results = await asyncio.gather(*[
        config.startgg_client.get_phase_groups(int(phase["id"]))
        for phase in phases
    ])
    groups = [
        phase_group
        for phase, phase_groups in zip(phases, phase_group_results)
        for phase_group in phase_groups
        if is_pool_group(phase, phase_group)
    ]
    if not groups:
        return {"error": "No Round Robin pool phase was found in the active event.", "groups": []}

    incomplete_groups = [
        phase_group for phase_group in groups
        if str(phase_group.get("state")).casefold() not in {"3", "completed"}
    ]
    if incomplete_groups:
        labels = ", ".join(
            str(group.get("displayIdentifier") or group["id"])
            for group in incomplete_groups
        )
        return {
            "error": f"All pools must be completed before calculating seeding. Incomplete pools: {labels}.",
            "groups": [],
        }

    return {"error": None, "groups": groups}


def is_pool_group(phase: dict, phase_group: dict) -> bool:
    bracket_type = normalize_text(phase_group.get("bracketType") or "")
    if bracket_type:
        return bracket_type == "round_robin"

    return "pool" in normalize_text(phase.get("name") or "")

async def load_pool_seeding_data(phase_group: dict) -> list:
    phase_group_id = int(phase_group["id"])
    standings, sets = await asyncio.gather(
        config.startgg_client.get_phase_group_standings(phase_group_id),
        config.startgg_client.get_phase_group_sets(phase_group_id),
    )
    pool_name = f"Pool {phase_group.get('displayIdentifier') or phase_group_id}"
    return build_player_standings(
        pool_id=phase_group_id,
        pool_name=pool_name,
        standings=standings,
        sets=sets,
    )


def build_seeding_embeds(active_event: dict, ranked: list, brackets: list, ranking_warnings: list[str]):
    summary = discord.Embed(
        title=f"{active_event['event_name']} seeding preview",
        description=(
            f"{len(ranked)} players ranked from completed pools.\n"
            "Tiebreakers: placement, match winrate, point winrate, "
            "point differential/set, points/set, total points."
        ),
        color=discord.Color.gold(),
        url=f"https://www.start.gg/{active_event['event_slug']}",
    )
    summary.add_field(
        name="Bracket split",
        value="\n".join(f"**{bracket.name}:** {len(bracket.players)}" for bracket in brackets),
        inline=False,
    )
    if ranking_warnings:
        summary.add_field(
            name="Manual review",
            value=truncate_lines(ranking_warnings),
            inline=False,
        )

    embeds = [summary]
    for bracket in brackets:
        lines = [
            format_seed_line(seed, player)
            for seed, player in enumerate(bracket.players, start=1)
        ]
        embed = discord.Embed(
            title=bracket.name,
            description=truncate_lines(lines, limit=3900),
            color=discord.Color.blue(),
        )
        if bracket.adjustments:
            embed.add_field(
                name="Rematch adjustments",
                value=truncate_lines([
                    (
                        f"Seeds {adjustment.first_seed}/{adjustment.second_seed}: "
                        f"{adjustment.first_name} ↔ {adjustment.second_name}"
                    )
                    for adjustment in bracket.adjustments
                ]),
                inline=False,
            )
        if bracket.warnings:
            embed.add_field(
                name="Warnings",
                value=truncate_lines(bracket.warnings),
                inline=False,
            )
        embeds.append(embed)

    return embeds


def format_seed_line(seed: int, player) -> str:
    return (
        f"`{seed:>2}.` **{player.name}** — {player.pool_name}, P{player.placement} "
        f"| sets {player.match_wins}-{player.match_losses} "
        f"| points {player.points_for}-{player.points_against}"
    )


def truncate_lines(lines: list[str], limit: int = 1000) -> str:
    output = []
    length = 0
    for line in lines:
        extra_length = len(line) + (1 if output else 0)
        if length + extra_length > limit:
            output.append("...")
            break
        output.append(line)
        length += extra_length
    return "\n".join(output) or "None"


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def is_luna_admin(ctx: discord.ApplicationContext) -> bool:
    admin_role_id = config.config_store.get_admin_role_id()
    if admin_role_id is None:
        return bool(ctx.author.guild_permissions.administrator)
    if ctx.guild and ctx.guild.get_role(admin_role_id) is None:
        return bool(ctx.author.guild_permissions.administrator)
    return any(role.id == admin_role_id for role in ctx.author.roles)
