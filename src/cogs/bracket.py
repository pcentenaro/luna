import config
import discord
from cogs.startgg import event_cache
from discord.ext import commands


class Bracket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="bracket",
        description="Privately view the current tournament pools and brackets",
    )
    async def bracket(self, ctx: discord.ApplicationContext):
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
        await ctx.respond(
            f"Loaded {cached_event.get('event_name') or active_event['event_name']}. "
            "Bracket images are not available yet.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


def setup(bot):
    bot.add_cog(Bracket(bot))
