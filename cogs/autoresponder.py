import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

AR_FILE = "autoresponder.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(AR_FILE, dict)

def load_ar():
    return _cache.load()

def save_ar(d):
    _cache.save(d)


class Autoresponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── BASE HELP ───
    @commands.group(name="autoresponder", aliases=["ar"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autoresponder(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTORESPONDER}  Autoresponder Command Help"),
            make_separator(),
            text("Manage automatic responses to specific trigger words or phrases."),
            make_separator(),
            text(
                f"`{Config.PREFIX}ar add <trigger> <reply>`\n"
                f"Adds a new autoresponder.\n\n"
                f"`{Config.PREFIX}ar edit <trigger> <new_reply>`\n"
                f"Edits an existing autoresponder.\n\n"
                f"`{Config.PREFIX}ar delete <trigger>`\n"
                f"Deletes a specific autoresponder.\n\n"
                f"`{Config.PREFIX}ar clear`\n"
                f"Removes all autoresponders from this server.\n\n"
                f"`{Config.PREFIX}ar list`\n"
                f"Shows all autoresponders on the server.\n\n"
                f"`{Config.PREFIX}ar info <trigger>`\n"
                f"Shows detailed information about a specific autoresponder."
            ),
            make_separator(),
            text(
                f"**Examples**\n"
                f"`{Config.PREFIX}ar add hello Hello there! Welcome to our server!`\n"
                f"`{Config.PREFIX}ar list`\n"
                f"`{Config.PREFIX}ar delete hello`"
            ),
            make_separator(),
            text("-# Tip: Triggers are case-insensitive and match exact words only.")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoresponder.command(name="add")
    async def ar_add(self, ctx, trigger: str, *, reply: str):
        data = load_ar()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {})[trigger.lower()] = {"reply": reply, "creator": ctx.author.id}
        save_ar(data)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Autoresponder Added"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Trigger:** `{trigger}`\n"
                f"{Emojis.ARROW} **Reply:** {reply}\n"
                f"{Emojis.MOD} **Created by:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoresponder.command(name="edit")
    async def ar_edit(self, ctx, trigger: str, *, new_reply: str):
        data = load_ar()
        gid = str(ctx.guild.id)
        if trigger.lower() not in data.get(gid, {}):
            return await send_v2(ctx, error_view(f"No autoresponder found for `{trigger}`."))
        data[gid][trigger.lower()]["reply"] = new_reply
        save_ar(data)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Autoresponder Updated"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Trigger:** `{trigger}`\n"
                f"{Emojis.ARROW} **New Reply:** {new_reply}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoresponder.command(name="delete")
    async def ar_delete(self, ctx, trigger: str):
        data = load_ar()
        gid = str(ctx.guild.id)
        if trigger.lower() not in data.get(gid, {}):
            return await send_v2(ctx, error_view(f"No autoresponder found for `{trigger}`."))
        del data[gid][trigger.lower()]
        save_ar(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Deleted autoresponder: `{trigger}`")))
        await send_v2(ctx, view)

    @autoresponder.command(name="clear")
    async def ar_clear(self, ctx):
        data = load_ar()
        data[str(ctx.guild.id)] = {}
        save_ar(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  All autoresponders cleared.")))
        await send_v2(ctx, view)

    @autoresponder.command(name="list")
    async def ar_list(self, ctx):
        data = load_ar()
        triggers = data.get(str(ctx.guild.id), {})
        if not triggers:
            return await send_v2(ctx, error_view("No autoresponders set up."))
        lines = "\n".join([f"`{t}` → {v['reply'][:50]}" for t, v in triggers.items()])
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTORESPONDER}  Autoresponders [{len(triggers)}]"),
            make_separator(),
            text(lines)
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autoresponder.command(name="info")
    async def ar_info(self, ctx, trigger: str):
        data = load_ar()
        gid = str(ctx.guild.id)
        entry = data.get(gid, {}).get(trigger.lower())
        if not entry:
            return await send_v2(ctx, error_view(f"No autoresponder found for `{trigger}`."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTORESPONDER}  Autoresponder Info"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Trigger:** `{trigger}`\n"
                f"{Emojis.ARROW} **Reply:** {entry['reply']}\n"
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
        data = load_ar()
        triggers = data.get(str(message.guild.id), {})
        content = message.content.lower().strip()
        if content in triggers:
            await message.channel.send(triggers[content]["reply"])


async def setup(bot):
    await bot.add_cog(Autoresponder(bot))