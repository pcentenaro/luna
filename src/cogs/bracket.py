import asyncio
import logging
from io import BytesIO
from copy import deepcopy
from time import perf_counter

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


logger = logging.getLogger(__name__)


class PoolPagesView(discord.ui.DesignerView):
    def __init__(self, summary: dict, active_event: dict, user_id: int, first_png: bytes):
        super().__init__(timeout=300)
        self.summary = summary
        # The view owns one fixed snapshot, so rendered pages stay valid until it expires.
        self.page_images = {1: first_png}
        self.active_event = active_event
        self.user_id = user_id
        self.page = 1
        self.page_count = max(1, (len(summary["pools"]) + 1) // 2)
        self.lock = asyncio.Lock()
        self.uploaded_attachments = None
        self.gallery = discord.ui.MediaGallery()
        self.previous = discord.ui.Button(label="Anterior", style=discord.ButtonStyle.secondary)
        self.next_page = discord.ui.Button(label="Siguiente", style=discord.ButtonStyle.primary)
        self.previous.callback = self.previous_page
        self.next_page.callback = self.following_page
        self.add_item(self.gallery)
        self.add_item(discord.ui.ActionRow(self.previous, self.next_page))
        self.update_buttons()

    def update_buttons(self):
        self.gallery.items = [discord.MediaGalleryItem(
            f"attachment://pools-page-{self.page}.png",
            description=f"Pool standings, page {self.page} of {self.page_count}",
        )]
        self.previous.disabled = self.page <= 1
        self.next_page.disabled = self.page >= self.page_count

    async def previous_page(self, interaction):
        await self.change_page(interaction, -1)

    async def following_page(self, interaction):
        await self.change_page(interaction, 1)

    async def change_page(self, interaction: discord.Interaction, direction: int):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who used /bracket can navigate these pages.", ephemeral=True)
            return
        request_started = perf_counter()
        await interaction.response.defer()
        acknowledged = perf_counter()
        async with self.lock:
            logger.info("Pool navigation: acknowledge=%.3fs queue=%.3fs",
                        acknowledged - request_started, perf_counter() - acknowledged)
            if config.config_store.get_active_event() != self.active_event:
                await interaction.followup.send("The active event changed. Run /bracket again.", ephemeral=True)
                return
            page = self.page + direction
            if not 1 <= page <= self.page_count:
                return
            render_started = perf_counter()
            cached = page in self.page_images
            try:
                if not cached:
                    start = (page - 1) * 2
                    svg = await asyncio.to_thread(
                        create_pools_svg, {**self.summary, "pools": self.summary["pools"][start:start + 2]},
                        page=page, page_count=self.page_count,
                    )
                    self.page_images[page] = await svg_to_png(svg)
                png = self.page_images[page]
            except (ValueError, RuntimeError):
                logger.exception("Could not render pool page %s", page)
                await interaction.followup.send("Could not generate this page. Please try again.", ephemeral=True)
                return
            if config.config_store.get_active_event() != self.active_event:
                await interaction.followup.send("The active event changed. Run /bracket again.", ephemeral=True)
                return
            logger.info("Pool page %s: cached=%s render=%.3fs bytes=%s",
                         page, cached, perf_counter() - render_started, len(png))
            previous_page = self.page
            self.page = page
            self.update_buttons()
            if self.uploaded_attachments is None:
                self.uploaded_attachments = list(interaction.message.attachments)
            filename = f"pools-page-{page}.png"
            uploaded = any(item.filename == filename for item in self.uploaded_attachments)
            attachment = None if uploaded else discord.File(BytesIO(png), filename=filename)
            # Discord allows ten attachments; older pages can be uploaded again from the PNG cache.
            retained = self.uploaded_attachments if uploaded else self.uploaded_attachments[-9:]
            try:
                send_started = perf_counter()
                message = await interaction.edit_original_response(
                    attachments=retained, view=self,
                    **({"file": attachment} if attachment is not None else {}),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                self.uploaded_attachments = list(message.attachments)
                logger.info("Pool page %s: uploaded_cached=%s Discord edit=%.3fs total=%.3fs",
                            page, uploaded, perf_counter() - send_started, perf_counter() - request_started)
            except discord.HTTPException:
                self.page = previous_page
                self.update_buttons()
                logger.exception("Could not update pool page")
                await interaction.followup.send("Could not update this page. Please try again.", ephemeral=True)
            finally:
                if attachment is not None:
                    attachment.close()


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
        defer_started = perf_counter()
        await ctx.defer(ephemeral=True)
        logger.info("Bracket image: acknowledge=%.3fs", perf_counter() - defer_started)
        render_started = perf_counter()
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
            logger.exception("Could not render bracket request for group %s", group_id)
            await ctx.respond("Could not generate the bracket image. Please try again later.", ephemeral=True)
            return
        if config.config_store.get_active_event() != active_event:
            await ctx.respond("The active event changed. Run /bracket again.", ephemeral=True)
            return
        logger.info("Bracket image: group=%s render=%.3fs bytes=%s",
                     group_id, perf_counter() - render_started, len(png))
        view = PoolPagesView(summary, active_event.copy(), ctx.author.id, png) if group_id is None else None
        attachment = discord.File(BytesIO(png), filename=filename)
        try:
            send_started = perf_counter()
            await ctx.respond(file=attachment, view=view, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            logger.info("Bracket image: Discord send=%.3fs", perf_counter() - send_started)
        finally:
            attachment.close()



def setup(bot):
    bot.add_cog(Bracket(bot))
