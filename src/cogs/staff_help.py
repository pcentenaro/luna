import discord
from discord.ext import commands


LUNA_AVATAR_URL = "https://cdn.discordapp.com/avatars/1501361206106132591/34addba16ae128186eb6c18777e71865.png?size=4096"


class StaffHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    @commands.guild_only()
    async def staff_help(self, ctx: commands.Context):
        await ctx.send(embeds=build_staff_help_embeds())


def build_staff_help_embeds() -> list[discord.Embed]:
    overview = discord.Embed(
        title="Luna Staff Guide",
        description=(
            "Quick reference for preparing and running a Copa Luna tournament. "
            "The controls below are available from Luna's administration panel."
        ),
        color=discord.Color.gold(),
    )
    overview.set_thumbnail(url=LUNA_AVATAR_URL)
    overview.add_field(
        name="Open the panel",
        value="Use `!admin` in the staff channel.",
        inline=False,
    )
    overview.set_footer(text="Copa Luna staff reference")

    event_configuration = discord.Embed(
        title="Event configuration",
        description="Controls for connecting Luna to the correct start.gg event.",
        color=discord.Color.blue(),
    )
    event_configuration.add_field(
        name="Set event",
        value=(
            "Opens a form requesting the tournament and event slugs. Both values "
            "come from the start.gg URL.\n\n"
            "**Example URL**\n"
            "`https://www.start.gg/tournament/copa-luna-16/event/puyo-singles/overview`\n"
            "**Tournament:** `copa-luna-16`\n"
            "**Event:** `puyo-singles`"
        ),
        inline=False,
    )
    event_configuration.add_field(
        name="Clear event",
        value=(
            "Removes the active event from Luna. Use this after a tournament or "
            "before switching to a different event."
        ),
        inline=False,
    )
    event_configuration.add_field(
        name="Start.gg status",
        value=(
            "Checks whether Luna can communicate with the start.gg API and shows "
            "which start.gg account owns the configured token."
        ),
        inline=False,
    )

    tournament_settings = discord.Embed(
        title="Permissions and match settings",
        description="Controls for staff access, set lengths, and account verification.",
        color=discord.Color.blue(),
    )
    tournament_settings.add_field(
        name="Set admin role",
        value=(
            "Selects the Discord role allowed to use Luna's administrative tools.\n"
            "**Important:** Assign the role carefully. Server administrators can "
            "recover access if the configured role is missing."
        ),
        inline=False,
    )
    tournament_settings.add_field(
        name="Clear admin role",
        value=(
            "Removes the configured Luna role. Until another role is selected, "
            "Discord server administrators can manage Luna."
        ),
        inline=False,
    )
    tournament_settings.add_field(
        name="Set score targets",
        value=(
            "Sets the wins required for each type of set:\n"
            "- Pools and regular bracket rounds\n"
            "- Winners Final and Losers Final\n"
            "- Grand Final"
        ),
        inline=False,
    )
    tournament_settings.add_field(
        name="Linked accounts",
        value=(
            "Compares event attendees with Luna's saved links. It shows which "
            "start.gg players are connected to Discord profiles and who still "
            "needs to use `/link`."
        ),
        inline=False,
    )
    miscellaneous = discord.Embed(
        title="Miscellaneous",
        description="Other useful commands for staff.",
        color=discord.Color.green(),
    )
    miscellaneous.add_field(
        name="!refresh",
        value="This command obtains the event's data defined in the admin panel. " \
        "It also gets the next matches when the final brackets are made" \
        "Use it after making changes to the event.",
        inline=False,
    )

    return [overview, event_configuration, tournament_settings, miscellaneous]


def setup(bot):
    bot.add_cog(StaffHelp(bot))

