import asyncio
import logging
from io import BytesIO
from copy import deepcopy

import config
import discord
from cogs.startgg import event_cache
from discord.ext import commands
from images.bracket_data import build_bracket_data
from images.bracket_renderer import create_bracket_svg
from images.svg_renderer import svg_to_png
from images.pool_data import build_pools_summary_data
from images.pool_renderer import create_pools_svg
from seeding import is_pool_group


class Bracket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="bracket",
        description="Privately view the current tournament pools and brackets",
    )
    async def bracket(
        self,
        ctx: discord.ApplicationContext,
        group_id: discord.Option(str, "start.gg phase group ID", required=False) = None,
    ):
        active_event = config.config_store.get_active_event()
        if active_event is None:
            await ctx.respond("No active start.gg event is configured yet.", ephemeral=True)
            return
        cached_event = event_cache.copy()
        if cached_event.get("event_id") != active_event["event_id"]:
            await ctx.respond(
                "Event cache is not ready. Ask a Luna admin to use `/refresh_event` first.",
                ephemeral=True,
            )
            return
        if not cached_event.get("phases") or not any(cached_event.get("phase_groups", {}).values()):
            await ctx.respond("No pools or brackets are available in the cached event yet.", ephemeral=True)
            return
        if group_id is None:
            if not any(is_pool_group(phase, group)
                       for phase in cached_event["phases"]
                       for group in cached_event["phase_groups"].get(int(phase["id"]), [])):
                await ctx.respond("No pools are available. Specify a group ID to view its bracket.",
                                  ephemeral=True)
                return
            data = deepcopy(cached_event)
            filename = "pools-page-1.png"
        else:
            try:
                parsed_id = int(group_id)
                if parsed_id <= 0:
                    raise ValueError
            except ValueError:
                await ctx.respond("The group ID must be a positive integer.", ephemeral=True)
                return
            try:
                data = build_bracket_data(cached_event, active_event["event_id"], parsed_id)
            except ValueError:
                await ctx.respond("That group is not in the cached event.", ephemeral=True)
                return
            if is_pool_group(data["phase"], data["phase_group"]):
                await ctx.respond("Use /bracket without a group ID to view the pool standings.",
                                  ephemeral=True)
                return
            if not data["sets"]:
                await ctx.respond("No sets are available for this bracket yet.", ephemeral=True)
                return
            filename = f"bracket-{parsed_id}.png"
        await ctx.defer(ephemeral=True)
        try:
            if group_id is None:
                summary = await asyncio.to_thread(build_pools_summary_data, data, active_event["event_id"])
                page_count = max(1, (len(summary["pools"]) + 1) // 2)
                svg = await asyncio.to_thread(
                    create_pools_svg, {**summary, "pools": summary["pools"][:2]},
                    page=1, page_count=page_count,
                )
            else:
                svg = await asyncio.to_thread(create_bracket_svg, data)
            png = await svg_to_png(svg)
        except (ValueError, RuntimeError):
            logging.exception("Could not render bracket request for group %s", group_id)
            await ctx.respond("Could not generate the bracket image. Please try again later.", ephemeral=True)
            return
        if config.config_store.get_active_event() != active_event:
            await ctx.respond("The active event changed. Run /bracket again.", ephemeral=True)
            return
        attachment = discord.File(BytesIO(png), filename=filename)
        try:
            await ctx.respond(file=attachment, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        finally:
            attachment.close()



def setup(bot):
    bot.add_cog(Bracket(bot))
