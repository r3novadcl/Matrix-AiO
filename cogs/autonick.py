import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

NICK_FILE = "autonick.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(NICK_FILE, dict)

def load_nick():
    return _cache.load()

def save_nick(d):
    _cache.save(d)

DEFAULT_TEMPLATE = "!NM乙{displayname}"

def apply_template(template: str, member: discord.Member) -> str:
    return template.replace("{username}", member.name)\
                   .replace("{displayname}", member.display_name)\
                   .replace("{tag}", str(member.discriminator))\
                   .replace("{count}", str(member.guild.member_count))


class Autonick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="autonick", invoke_without_command=True)
    @commands.has_permissions(manage_nicknames=True)
    async def autonick(self, ctx):
        data = load_nick()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, {"enabled": False, "template": DEFAULT_TEMPLATE})
        status = f"{Emojis.ON} Enabled" if gcfg.get("enabled") else f"{Emojis.OFF} Disabled"

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {ctx.guild.name}'s server"),
            text(f"### {Emojis.AUTONICK}  AutoNick Configuration"),
            make_separator(),
            text(
                f"**AUTO-SETUP:** The bot automatically creates `{DEFAULT_TEMPLATE}` template on member join!\n\n"
                f"**Available Commands:**\n"
                f"`{Config.PREFIX}autonick enable` - Enable autonick system\n"
                f"`{Config.PREFIX}autonick disable` - Disable autonick system\n"
                f"`{Config.PREFIX}autonick set <template>` - Set custom nickname template\n"
                f"`{Config.PREFIX}autonick reset` - Reset autonick configuration\n"
                f"`{Config.PREFIX}autonick config` - View current configuration\n"
                f"`{Config.PREFIX}bulkautonick` - Apply to all existing members"
            ),
            make_separator(),
            text(
                f"**Template Variables:**\n"
                f"`{{username}}` - User's original username\n"
                f"`{{displayname}}` - User's display name (fallback to username)\n"
                f"`{{tag}}` - User's discriminator (if any)\n"
                f"`{{count}}` - Member count"
            ),
            make_separator(),
            text(
                f"**Examples:**\n"
                f"• `{DEFAULT_TEMPLATE}` ← Default auto-created\n"
                f"• `[{{count}}] {{username}}`\n"
                f"• `★ {{displayname}} ★`"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autonick.command(name="enable")
    async def nick_enable(self, ctx):
        data = load_nick()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"template": DEFAULT_TEMPLATE})["enabled"] = True
        save_nick(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Autonick Enabled"),
            make_separator(),
            text(f"{Emojis.ARROW} Template: `{data[gid].get('template', DEFAULT_TEMPLATE)}`")
        ))
        await send_v2(ctx, view)

    @autonick.command(name="disable")
    async def nick_disable(self, ctx):
        data = load_nick()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"template": DEFAULT_TEMPLATE})["enabled"] = False
        save_nick(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Autonick Disabled")))
        await send_v2(ctx, view)

    @autonick.command(name="set")
    async def nick_set(self, ctx, *, template: str):
        data = load_nick()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"enabled": False})["template"] = template
        save_nick(data)
        preview = apply_template(template, ctx.author)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Template Updated"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Template:** `{template}`\n"
                f"{Emojis.ARROW} **Preview:** `{preview}`"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @autonick.command(name="reset")
    async def nick_reset(self, ctx):
        data = load_nick()
        data[str(ctx.guild.id)] = {"enabled": False, "template": DEFAULT_TEMPLATE}
        save_nick(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Autonick configuration reset.")))
        await send_v2(ctx, view)

    @autonick.command(name="config")
    async def nick_config(self, ctx):
        data = load_nick()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, {"enabled": False, "template": DEFAULT_TEMPLATE})
        status = f"{Emojis.ON} Enabled" if gcfg.get("enabled") else f"{Emojis.OFF} Disabled"
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTONICK}  Autonick Config"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Status:** {status}\n"
                f"{Emojis.ARROW} **Template:** `{gcfg.get('template', DEFAULT_TEMPLATE)}`\n"
                f"{Emojis.ARROW} **Preview:** `{apply_template(gcfg.get('template', DEFAULT_TEMPLATE), ctx.author)}`"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BULK APPLY ───
    @commands.command(name="bulkautonick")
    @commands.has_permissions(manage_nicknames=True)
    async def bulkautonick(self, ctx):
        data = load_nick()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, {})
        template = gcfg.get("template", DEFAULT_TEMPLATE)
        count = 0

        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.LOADING}  Applying nicknames to all members...")))
        msg = await ctx.send(view=view)

        for member in ctx.guild.members:
            if member.bot or member == ctx.guild.owner:
                continue
            try:
                new_nick = apply_template(template, member)
                await member.edit(nick=new_nick)
                count += 1
            except:
                pass

        done_view = discord.ui.LayoutView()
        done_view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Bulk Autonick Complete"),
            make_separator(),
            text(f"{Emojis.ARROW} **Applied to:** {count} members\n{Emojis.ARROW} **Template:** `{template}`")
        ))
        await msg.edit(view=done_view)

    # ─── FIXAUTONICK ───
    @commands.command(name="fixautonick")
    @commands.has_permissions(manage_nicknames=True)
    async def fixautonick(self, ctx, member: discord.Member):
        data = load_nick()
        gcfg = data.get(str(ctx.guild.id), {})
        template = gcfg.get("template", DEFAULT_TEMPLATE)
        new_nick = apply_template(template, member)
        await member.edit(nick=new_nick)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Fixed nickname for {member.mention}"),
            make_separator(),
            text(f"{Emojis.ARROW} **New Nick:** `{new_nick}`")
        ))
        await send_v2(ctx, view)

    # ─── RESETNICKS ───
    @commands.command(name="resetnicks")
    @commands.has_permissions(manage_nicknames=True)
    async def resetnicks(self, ctx):
        count = 0
        for member in ctx.guild.members:
            if member.nick and not member.bot and member != ctx.guild.owner:
                try:
                    await member.edit(nick=None)
                    count += 1
                except:
                    pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Reset nicknames for {count} members.")))
        await send_v2(ctx, view)

    # ─── AUTONICKLOG ───
    @commands.command(name="autonicklog")
    @commands.has_permissions(manage_nicknames=True)
    async def autonicklog(self, ctx):
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.AUTONICK}  Autonick Log"),
            make_separator(),
            text("Autonick logs will be sent to the logging channel if configured.")
        ))
        await send_v2(ctx, view)

    # ─── ON MEMBER JOIN (AUTO APPLY) ───
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        data = load_nick()
        gcfg = data.get(str(member.guild.id), {})
        if not gcfg.get("enabled"):
            return
        template = gcfg.get("template", DEFAULT_TEMPLATE)
        new_nick = apply_template(template, member)
        try:
            await member.edit(nick=new_nick)
        except:
            pass


async def setup(bot):
    await bot.add_cog(Autonick(bot))