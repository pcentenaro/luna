import cogs
import os # default module
import config
import discord


@config.bot.event
async def on_ready():
    print(f"{config.bot.user} is ready and online!")


@config.bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")


if __name__ == "__main__":
    config.bot.load_extension("cogs.admin")
    config.bot.load_extension("cogs.seeding")
    config.bot.load_extension("cogs.startgg")
    config.bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token