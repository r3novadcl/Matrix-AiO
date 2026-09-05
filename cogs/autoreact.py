import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

REACT_FILE = "autoreact.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(REACT_FILE, dict)

def load_react():
    return _cache.load()

def save_react(d):
    _cache.save(d)


class Autoreact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="autoreact", aliases=["areact"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autoreact(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTOREACT}  Autoreactor Command Help"),
            make_separator(),
            text("Manage automatic reactions to specific trigger words or phrases."),
            make_separator(),
            text(
                f"`{Config.PREFIX}areact add <trigger> <reactions>`\n"
                f"Adds a new autoreactor.\n\n"
                f"`{Config.PREFIX}areact edit <trigger> <new_reactions>`\n"
                f"Edits an existing autoreactor.\n\n"
                f"`{Config.PREFIX}areact delete <trigger>`\n"
                f"Deletes a specific autoreactor.\n\n"
                f"`{Config.PREFIX}areact clear`\n"
                f"Removes all autoreactors from this server.\n\n"
                f"`{Config.PREFIX}areact list`\n"
                f"Shows all autoreactors on the server.\n\n"
                f"`{Config.PREFIX}areact info <trigger>`\n"
                f"Shows detailed information about a specific autoreactor."
            ),
            make_separator(),
            text(
                f"**Examples**\n"
                f"`{Config.PREFIX}areact add hello 👋 😊 🎉`\n"
                f"`{Config.PREFIX}areact add welcome :custom: 👏`\n"
                f"`{Config.PREFIX}areact list`"
            ),
            make_separator(),
            text("-# Tip: Triggers are case-insensitive and match exact words only.")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoreact.command(name="add")
    async def react_add(self, ctx, trigger: str, *, reactions: str):
        data = load_react()
        gid = str(ctx.guild.id)
        react_list = reactions.strip().split()
        data.setdefault(gid, {})[trigger.lower()] = {"reactions": react_list, "creator": ctx.author.id}
        save_react(data)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Autoreactor Added"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Trigger:** `{trigger}`\n"
                f"{Emojis.ARROW} **Reactions:** {' '.join(react_list)}\n"
                f"{Emojis.MOD} **Created by:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoreact.command(name="edit")
    async def react_edit(self, ctx, trigger: str, *, new_reactions: str):
        data = load_react()
        gid = str(ctx.guild.id)
        if trigger.lower() not in data.get(gid, {}):
            return await send_v2(ctx, error_view(f"No autoreactor found for `{trigger}`."))
        data[gid][trigger.lower()]["reactions"] = new_reactions.strip().split()
        save_react(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Autoreactor updated for `{trigger}`.")))
        await send_v2(ctx, view)

    @autoreact.command(name="delete")
    async def react_delete(self, ctx, trigger: str):
        data = load_react()
        gid = str(ctx.guild.id)
        if trigger.lower() not in data.get(gid, {}):
            return await send_v2(ctx, error_view(f"No autoreactor found for `{trigger}`."))
        del data[gid][trigger.lower()]
        save_react(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Autoreactor deleted: `{trigger}`")))
        await send_v2(ctx, view)

    @autoreact.command(name="clear")
    async def react_clear(self, ctx):
        data = load_react()
        data[str(ctx.guild.id)] = {}
        save_react(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  All autoreactors cleared.")))
        await send_v2(ctx, view)

    @autoreact.command(name="list")
    async def react_list(self, ctx):
        data = load_react()
        triggers = data.get(str(ctx.guild.id), {})
        if not triggers:
            return await send_v2(ctx, error_view("No autoreactors set up."))
        lines = "\n".join([f"`{t}` → {' '.join(v['reactions'])}" for t, v in triggers.items()])
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTOREACT}  Autoreactors [{len(triggers)}]"),
            make_separator(),
            text(lines)
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoreact.command(name="info")
    async def react_info(self, ctx, trigger: str):
        data = load_react()
        entry = data.get(str(ctx.guild.id), {}).get(trigger.lower())
        if not entry:
            return await send_v2(ctx, error_view(f"No autoreactor found for `{trigger}`."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTOREACT}  Autoreactor Info"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Trigger:** `{trigger}`\n"
                f"{Emojis.ARROW} **Reactions:** {' '.join(entry['reactions'])}\n"
                f"{Emojis.ARROW} **Created by:** <@{entry['creator']}>"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── LISTENER ───
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        data = load_react()
        triggers = data.get(str(message.guild.id), {})
        content = message.content.lower().strip()
        if content in triggers:
            for r in triggers[content]["reactions"]:
                try:
                    await message.add_reaction(r)
                except:
                    pass


async def setup(bot):
    await bot.add_cog(Autoreact(bot))