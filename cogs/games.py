import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

GAME_FILE = "games_config.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(GAME_FILE, dict)

def load_games():
    return _cache.load()

def save_games(d):
    _cache.save(d)


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── COUNTING SETUP ───
    @commands.group(name="counting", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def counting(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.COUNTING}  Counting Game"),
            make_separator(),
            text(
                "A fun counting game for your server!\n\n"
                f"**Available Commands:**\n"
                f"`{Config.PREFIX}counting setup` — Set counting channel\n"
                f"`{Config.PREFIX}counting reset` — Reset count to 0\n"
                f"`{Config.PREFIX}counting stats` — View counting stats\n"
                f"`{Config.PREFIX}counting config` — View current config\n"
                f"`{Config.PREFIX}counting disable` — Disable counting\n\n"
                "**Rules:**\n"
                "• Count one number at a time\n"
                "• No same person twice in a row\n"
                "• Wrong number = count resets"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @counting.command(name="setup")
    async def counting_setup(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        data = load_games()
        gid = str(ctx.guild.id)
        data[gid] = {
            "channel": str(channel.id),
            "count": 0,
            "last_user": None,
            "highest": 0,
            "total_counts": 0,
            "enabled": True
        }
        save_games(data)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Counting Game Setup"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                f"{Emojis.ARROW} **Starting Count:** `1`\n"
                f"{Emojis.ON} **Status:** Enabled"
            ),
            make_separator(),
            text(f"-# Start counting from 1 in {channel.mention}!")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @counting.command(name="reset")
    async def counting_reset(self, ctx):
        data = load_games()
        gid = str(ctx.guild.id)
        if gid not in data:
            return await send_v2(ctx, error_view("Counting not set up. Use `&counting setup` first."))
        data[gid]["count"] = 0
        data[gid]["last_user"] = None
        save_games(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Count reset to `0`")))
        await send_v2(ctx, view)

    @counting.command(name="stats")
    async def counting_stats(self, ctx):
        data = load_games()
        gid = str(ctx.guild.id)
        if gid not in data:
            return await send_v2(ctx, error_view("Counting not set up."))
        g = data[gid]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.COUNTING}  Counting Stats"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Current Count:** `{g['count']}`\n"
                f"{Emojis.TROPHY} **Highest Count:** `{g['highest']}`\n"
                f"{Emojis.ARROW} **Total Counts:** `{g['total_counts']}`\n"
                f"{Emojis.CHANNEL} **Channel:** <#{g['channel']}>"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @counting.command(name="config")
    async def counting_config(self, ctx):
        data = load_games()
        gid = str(ctx.guild.id)
        if gid not in data:
            return await send_v2(ctx, error_view("Counting not set up."))
        g = data[gid]
        status = f"{Emojis.ON} Enabled" if g.get("enabled") else f"{Emojis.OFF} Disabled"
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.COUNTING}  Counting Config"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** <#{g['channel']}>\n"
                f"{Emojis.ARROW} **Current Count:** `{g['count']}`\n"
                f"{Emojis.ARROW} **Status:** {status}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @counting.command(name="disable")
    async def counting_disable(self, ctx):
        data = load_games()
        gid = str(ctx.guild.id)
        if gid not in data:
            return await send_v2(ctx, error_view("Counting not set up."))
        data[gid]["enabled"] = False
        save_games(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Counting disabled.")))
        await send_v2(ctx, view)

    # ─── COUNTING LISTENER ───
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        data = load_games()
        gid = str(message.guild.id)
        if gid not in data:
            return
        g = data[gid]
        if not g.get("enabled"):
            return
        if str(message.channel.id) != g["channel"]:
            return

        content = message.content.strip()
        if not content.isdigit():
            return

        number = int(content)
        expected = g["count"] + 1

        if str(message.author.id) == g.get("last_user"):
            await message.add_reaction(Emojis.WRONG)
            data[gid]["count"] = 0
            data[gid]["last_user"] = None
            save_games(data)
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(
                text(f"### {Emojis.WRONG}  Wrong!"),
                make_separator(),
                text(f"{message.author.mention} you can't count twice in a row!\nCount reset to `0`. Next number: `1`")
            ))
            await message.channel.send(view=view)
            return

        if number == expected:
            await message.add_reaction(Emojis.CORRECT)
            data[gid]["count"] = number
            data[gid]["last_user"] = str(message.author.id)
            data[gid]["total_counts"] = g.get("total_counts", 0) + 1
            if number > g.get("highest", 0):
                data[gid]["highest"] = number
            save_games(data)
        else:
            await message.add_reaction(Emojis.WRONG)
            data[gid]["count"] = 0
            data[gid]["last_user"] = None
            save_games(data)
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(
                text(f"### {Emojis.WRONG}  Wrong Number!"),
                make_separator(),
                text(f"{message.author.mention} expected `{expected}`, got `{number}`.\nCount reset to `0`. Next: `1`")
            ))
            await message.channel.send(view=view)


async def setup(bot):
    await bot.add_cog(Games(bot))