import discord
from discord.ext import commands
import asyncio, os, datetime
from config import Config
from emojis import Emojis
from utils.components import (
    MatrixContainer, text, make_separator, error_view, send_v2
)

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=Config.PREFIX,
    intents=intents,
    help_command=None,
    case_insensitive=True
)
bot.start_time = None


@bot.event
async def on_ready():
    bot.start_time = datetime.datetime.utcnow()
    print(f"✅ Logged in as {bot.user} | Servers: {len(bot.guilds)} | Powered by FX DEVELOPMENT & MATRIX AND GACKY STUDIOS")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{Config.PREFIX}help | FX DEVELOPMENT"
        ),
        status=discord.Status.online
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Mention reply ("Hello! I'm " + Config.BOT_NAME)
    if bot.user.mentioned_in(message) and not message.mention_everyone and not message.reference:
        content = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        if not content:
            view = discord.ui.LayoutView()
            section = discord.ui.Section(
                text(f"### Hello! I'm {Config.BOT_NAME}"),
                text(
                    f"Hey {message.author.mention}, thanks for the mention!\n"
                    f"Here's some quick info to get you started."
                ),
                accessory=discord.ui.Thumbnail(media=message.author.display_avatar.url)
            )
            container = MatrixContainer(
                section,
                make_separator(),
                text(
                    f"**Prefix Information**\n"
                    f"My Prefix here is `{Config.PREFIX}`. Use it to access all available commands.\n\n"
                    f"**Need Help?**\n"
                    f"Use `{Config.PREFIX}help` to view the list of available commands."
                ),
                make_separator(),
                text(f"-# {Config.FOOTER_TEXT}"),
                discord.ui.ActionRow(
                    discord.ui.Button(label="Invite Me",      style=discord.ButtonStyle.link, url=Config.INVITE_URL),
                    discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url=Config.SUPPORT_SERVER),
                    discord.ui.Button(label="Vote",           style=discord.ButtonStyle.link, url=Config.VOTE_URL),
                )
            )
            view.add_item(container)
            await message.reply(view=view, mention_author=False)
            return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        usage = f"{Config.PREFIX}{ctx.command.name} {ctx.command.signature}"
        return await send_v2(ctx, error_view("You didn't used the command correctly.", usage))
    if isinstance(error, commands.MissingPermissions):
        return await send_v2(ctx, error_view("You don't have permission to use this command."))
    if isinstance(error, commands.BotMissingPermissions):
        return await send_v2(ctx, error_view("I don't have required permissions."))
    if isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
        return await send_v2(ctx, error_view("Please provide a valid user ID or mention a member."))
    if isinstance(error, commands.RoleNotFound):
        return await send_v2(ctx, error_view("Please provide a valid role."))
    if isinstance(error, commands.ChannelNotFound):
        return await send_v2(ctx, error_view("Please provide a valid channel."))
    if isinstance(error, commands.BadArgument):
        return await send_v2(ctx, error_view(str(error)))
    print(f"Error: {error}")


async def load_cogs():
    for folder in ['cogs']:
        for file in os.listdir(folder):
            if file.endswith('.py') and not file.startswith('_'):
                try:
                    await bot.load_extension(f"{folder}.{file[:-3]}")
                    print(f"✅ Loaded {file}")
                except Exception as e:
                    print(f"❌ Failed {file}: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(Config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())