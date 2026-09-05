import discord
from discord.ext import commands
from datetime import datetime, timedelta
import json, os, asyncio
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2


# Simple JSON Storage for warns / ignore / prefix
DATA_FILE = "data.json"
# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(DATA_FILE, (lambda: {"warns": {}, "ignore_users": [], "ignore_channels": [], "ignore_commands": [], "prefixes": {}, "snipes": {}}))

def load_data():
    return _cache.load()

def save_data(d):
    _cache.save(d)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipes = {}  # channel_id -> deleted msg

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        self.snipes[message.channel.id] = (message.author, message.content, datetime.utcnow())

    # ───────── BAN ─────────
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        if not member:
            return await send_v2(ctx, error_view("Please provide a valid user ID or mention a member."))
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await send_v2(ctx, error_view("You can't ban this member."))
        await member.ban(reason=reason)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Banned {member}"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.WARNING} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── UNBAN ─────────
    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int = None):
        if not user_id:
            return await send_v2(ctx, error_view("Please provide a valid user ID."))
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user)
        except:
            return await send_v2(ctx, error_view("User not found or not banned."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Unbanned {user}"),
            make_separator(),
            text(f"{Emojis.MOD} **Moderator:** {ctx.author.mention}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── UNBANALL ─────────
    @commands.command(name="unbanall")
    @commands.has_permissions(administrator=True)
    async def unbanall(self, ctx):
        count = 0
        async for entry in ctx.guild.bans():
            try:
                await ctx.guild.unban(entry.user); count += 1
            except: pass
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Mass Unban Complete"),
            make_separator(),
            text(f"{Emojis.ARROW} **Total Unbanned:** {count}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── KICK ─────────
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        if not member:
            return await send_v2(ctx, error_view("Please provide a valid user ID or mention a member."))
        await member.kick(reason=reason)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Kicked {member}"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.WARNING} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── MUTE ─────────
    @commands.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member = None, duration: int = 10, *, reason="No reason provided"):
        if not member:
            return await send_v2(ctx, error_view("Please provide a valid user ID or mention a member."))
        until = datetime.utcnow() + timedelta(minutes=duration)
        await member.timeout(until, reason=reason)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Muted {member}"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.ARROW} **Duration:** {duration} mins\n"
                f"{Emojis.WARNING} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── UNMUTE ─────────
    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member = None):
        if not member:
            return await send_v2(ctx, error_view("Please provide a valid user ID or mention a member."))
        await member.timeout(None)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Unmuted {member}"),
            make_separator(),
            text(f"{Emojis.MOD} **Moderator:** {ctx.author.mention}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── HIDE ─────────
    @commands.command(name="hide")
    @commands.has_permissions(manage_channels=True)
    async def hide(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, view_channel=False)

        view = discord.ui.LayoutView()

        async def unhide_cb(interaction: discord.Interaction):
            await channel.set_permissions(ctx.guild.default_role, view_channel=None)
            new_view = discord.ui.LayoutView()
            new_container = MatrixContainer(
                text(f"### {Emojis.SUCCESS}   Successfully Unhidden {channel.name}"),
                make_separator(),
                text(
                    f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                    f"{Emojis.WARNING} **Status:** Unhidden\n"
                    f"{Emojis.MOD} **Moderator:** {interaction.user.mention}"
                )
            )
            new_view.add_item(new_container)
            await interaction.response.edit_message(view=new_view)

        async def delete_cb(interaction: discord.Interaction):
            await interaction.message.delete()

        unhide_btn = discord.ui.Button(label="Unhide", style=discord.ButtonStyle.success)
        delete_btn = discord.ui.Button(emoji="🗑️", style=discord.ButtonStyle.danger)
        unhide_btn.callback = unhide_cb
        delete_btn.callback = delete_cb

        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Hidden {channel.name}"),
            text(f"-# Requested by {ctx.author.name}"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                f"{Emojis.WARNING} **Status:** Hidden\n"
                f"{Emojis.WARNING} **Reason:** Hide request by {ctx.author.name}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            ),
            discord.ui.ActionRow(unhide_btn, delete_btn)
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── UNHIDE ─────────
    @commands.command(name="unhide")
    @commands.has_permissions(manage_channels=True)
    async def unhide(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, view_channel=None)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Unhidden {channel.name}"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                f"{Emojis.WARNING} **Status:** Unhidden\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── HIDEALL ─────────
    @commands.command(name="hideall")
    @commands.has_permissions(administrator=True)
    async def hideall(self, ctx):
        for ch in ctx.guild.text_channels:
            try: await ch.set_permissions(ctx.guild.default_role, view_channel=False)
            except: pass
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   All Channels Hidden"),
            make_separator(),
            text(f"{Emojis.MOD} **Moderator:** {ctx.author.mention}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── UNHIDEALL ─────────
    @commands.command(name="unhideall")
    @commands.has_permissions(administrator=True)
    async def unhideall(self, ctx):
        for ch in ctx.guild.text_channels:
            try: await ch.set_permissions(ctx.guild.default_role, view_channel=None)
            except: pass
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   All Channels Unhidden"),
            make_separator(),
            text(f"{Emojis.MOD} **Moderator:** {ctx.author.mention}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── LOCK ─────────
    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Locked {channel.name}"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                f"{Emojis.LOCK} **Status:** Locked\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── UNLOCK ─────────
    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Unlocked {channel.name}"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                f"{Emojis.UNLOCK} **Status:** Unlocked\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── LOCKALL / UNLOCKALL ─────────
    @commands.command(name="lockall")
    @commands.has_permissions(administrator=True)
    async def lockall(self, ctx):
        for ch in ctx.guild.text_channels:
            try: await ch.set_permissions(ctx.guild.default_role, send_messages=False)
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   All Channels Locked")))
        await send_v2(ctx, view)

    @commands.command(name="unlockall")
    @commands.has_permissions(administrator=True)
    async def unlockall(self, ctx):
        for ch in ctx.guild.text_channels:
            try: await ch.set_permissions(ctx.guild.default_role, send_messages=None)
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   All Channels Unlocked")))
        await send_v2(ctx, view)

    # ───────── PURGE ─────────
    @commands.command(name="purge", aliases=["clear"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 10):
        if amount < 1 or amount > 100:
            return await send_v2(ctx, error_view("Amount must be between 1-100."))
        deleted = await ctx.channel.purge(limit=amount + 1)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Successfully Purged {len(deleted)-1} messages")
        ))
        msg = await ctx.send(view=view)
        await asyncio.sleep(5)
        try: await msg.delete()
        except: pass

    # ───────── PURGEBOT ─────────
    @commands.command(name="purgebot")
    @commands.has_permissions(manage_messages=True)
    async def purgebot(self, ctx, amount: int = 50):
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.bot)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Purged {len(deleted)} bot messages")))
        await send_v2(ctx, view)

    # ───────── NICK ─────────
    @commands.command(name="nick")
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname=None):
        await member.edit(nick=nickname)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Nickname Changed"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.ARROW} **New Nick:** {nickname or 'Reset'}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── ROLE ─────────
    @commands.command(name="role")
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx, member: discord.Member = None, *, role: discord.Role = None):
        if not member or not role:
            return await send_v2(ctx, error_view("You didn't used the command correctly.", "&role <user> <role>"))
        action = "Removed" if role in member.roles else "Added"
        if role in member.roles: await member.remove_roles(role)
        else: await member.add_roles(role)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Role {action}"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.ROLE} **Role:** {role.mention}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── MASSROLE ─────────
    @commands.command(name="massrole")
    @commands.has_permissions(manage_roles=True)
    async def massrole(self, ctx, role: discord.Role):
        count = 0
        for m in ctx.guild.members:
            if role not in m.roles:
                try: await m.add_roles(role); count += 1
                except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Massrole Complete"),
            make_separator(),
            text(f"Added {role.mention} to **{count}** members.")
        ))
        await send_v2(ctx, view)

    # ───────── CHANNEL CREATE/DELETE ─────────
    @commands.command(name="channel")
    @commands.has_permissions(manage_channels=True)
    async def channel_cmd(self, ctx, action: str, *, name: str):
        if action == "create":
            ch = await ctx.guild.create_text_channel(name)
            msg = f"Created {ch.mention}"
        elif action == "delete":
            ch = discord.utils.get(ctx.guild.channels, name=name)
            if not ch: return await send_v2(ctx, error_view("Channel not found."))
            await ch.delete()
            msg = f"Deleted `{name}`"
        else:
            return await send_v2(ctx, error_view("Use `create` or `delete`."))
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   {msg}")))
        await send_v2(ctx, view)

    # ───────── CATEGORY CREATE ─────────
    @commands.command(name="category")
    @commands.has_permissions(manage_channels=True)
    async def category(self, ctx, action: str, *, name: str):
        if action == "create":
            cat = await ctx.guild.create_category(name)
            msg = f"Created category `{cat.name}`"
        elif action == "delete":
            cat = discord.utils.get(ctx.guild.categories, name=name)
            if not cat: return await send_v2(ctx, error_view("Category not found."))
            await cat.delete()
            msg = f"Deleted category `{name}`"
        else:
            return await send_v2(ctx, error_view("Use `create` or `delete`."))
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   {msg}")))
        await send_v2(ctx, view)

    # ───────── RENAME ─────────
    @commands.command(name="rename")
    @commands.has_permissions(manage_channels=True)
    async def rename(self, ctx, *, new_name: str):
        await ctx.channel.edit(name=new_name)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Channel renamed to `{new_name}`")))
        await send_v2(ctx, view)

    # ───────── SLOWMODE ─────────
    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Slowmode set to `{seconds}s`")))
        await send_v2(ctx, view)

    # ───────── SNIPE ─────────
    @commands.command(name="snipe")
    async def snipe(self, ctx):
        data = self.snipes.get(ctx.channel.id)
        if not data: return await send_v2(ctx, error_view("Nothing to snipe."))
        author, content, ts = data
        view = discord.ui.LayoutView()
        section = discord.ui.Section(
            text(f"### {Emojis.SNIPE}   Sniped Message"),
            text(f"**Author:** {author.mention}\n**Sent:** <t:{int(ts.timestamp())}:R>"),
            accessory=discord.ui.Thumbnail(media=author.display_avatar.url)
        )
        container = MatrixContainer(
            section,
            make_separator(),
            text(content or "*[Empty content]*")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── STEAL EMOJI ─────────
    @commands.command(name="steal")
    @commands.has_permissions(manage_emojis=True)
    async def steal(self, ctx, emoji: discord.PartialEmoji, *, name: str = None):
        name = name or emoji.name
        data = await emoji.read()
        new_emoji = await ctx.guild.create_custom_emoji(name=name, image=data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Stolen Emoji {new_emoji} as `{name}`")))
        await send_v2(ctx, view)

    # ───────── WARN ─────────
    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="No reason"):
        data = load_data()
        gid, uid = str(ctx.guild.id), str(member.id)
        data["warns"].setdefault(gid, {}).setdefault(uid, []).append({"reason": reason, "by": ctx.author.id})
        save_data(data)
        count = len(data["warns"][gid][uid])
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Warned {member}"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.WARN} **Warns:** {count}\n"
                f"{Emojis.ARROW} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── WARNLIST ─────────
    @commands.command(name="warnlist", aliases=["warns"])
    async def warnlist(self, ctx, member: discord.Member):
        data = load_data()
        warns = data["warns"].get(str(ctx.guild.id), {}).get(str(member.id), [])
        view = discord.ui.LayoutView()
        if not warns:
            container = MatrixContainer(text(f"### {Emojis.WARN}   {member} has no warnings."))
        else:
            lines = "\n".join([f"`{i+1}.` {w['reason']}" for i, w in enumerate(warns)])
            container = MatrixContainer(
                text(f"### {Emojis.WARN}   Warnings for {member}"),
                make_separator(),
                text(lines)
            )
        view.add_item(container)
        await send_v2(ctx, view)

    # ───────── WARNREMOVE ─────────
    @commands.command(name="warnremove")
    @commands.has_permissions(moderate_members=True)
    async def warnremove(self, ctx, member: discord.Member, index: int):
        data = load_data()
        warns = data["warns"].get(str(ctx.guild.id), {}).get(str(member.id), [])
        if index < 1 or index > len(warns):
            return await send_v2(ctx, error_view("Invalid warning index."))
        warns.pop(index - 1)
        save_data(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Warning #{index} removed for {member}")))
        await send_v2(ctx, view)

    # ───────── PREFIX ─────────
    @commands.command(name="prefix")
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx, new_prefix: str):
        data = load_data()
        data["prefixes"][str(ctx.guild.id)] = new_prefix
        save_data(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Prefix changed to `{new_prefix}`")))
        await send_v2(ctx, view)

    # ───────── IGNORE / IGNORECOMMAND ─────────
    @commands.command(name="ignore")
    @commands.has_permissions(administrator=True)
    async def ignore(self, ctx, target: str):
        data = load_data()
        data["ignore_channels"].append(target)
        save_data(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Added to ignore list: `{target}`")))
        await send_v2(ctx, view)

    @commands.command(name="ignorecommand")
    @commands.has_permissions(administrator=True)
    async def ignorecommand(self, ctx, command_name: str):
        data = load_data()
        data["ignore_commands"].append(command_name)
        save_data(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Command `{command_name}` ignored.")))
        await send_v2(ctx, view)

    # ───────── EMBED ─────────
    @commands.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    async def embed_cmd(self, ctx, *, content: str):
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(content)))
        await send_v2(ctx, view)

    # ───────── ESNIPE ─────────
    @commands.command(name="esnipe")
    async def esnipe(self, ctx):
        await send_v2(ctx, error_view("Edit snipe is not enabled yet."))

    # ───────── BOTNICK ─────────
    @commands.command(name="botnick")
    @commands.has_permissions(administrator=True)
    async def botnick(self, ctx, *, name=None):
        await ctx.guild.me.edit(nick=name)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Bot nickname set to `{name or 'Reset'}`")))
        await send_v2(ctx, view)

    # ───────── CHATBAN (channel-level mute) ─────────
    @commands.command(name="chatban")
    @commands.has_permissions(manage_channels=True)
    async def chatban(self, ctx, member: discord.Member):
        await ctx.channel.set_permissions(member, send_messages=False)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   {member.mention} chat-banned in this channel.")))
        await send_v2(ctx, view)

    # ───────── MEDIACHANNEL ─────────
    @commands.command(name="mediachannel")
    @commands.has_permissions(manage_channels=True)
    async def mediachannel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   {channel.mention} marked as media-only channel.")))
        await send_v2(ctx, view)

    # ───────── NUKE ─────────
    @commands.command(name="nuke")
    @commands.has_permissions(administrator=True)
    async def nuke(self, ctx):
        ch = ctx.channel
        new_ch = await ch.clone()
        await new_ch.edit(position=ch.position)
        await ch.delete()
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.NUKE}   Channel nuked by {ctx.author.mention}")))
        await new_ch.send(view=view)

    # ───────── REMINDME ─────────
    @commands.command(name="remindme")
    async def remindme(self, ctx, minutes: int, *, reminder: str):
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   I'll remind you in `{minutes}m`")))
        await send_v2(ctx, view)
        await asyncio.sleep(minutes * 60)
        rview = discord.ui.LayoutView()
        rview.add_item(MatrixContainer(
            text(f"### {Emojis.WARNING}   Reminder for {ctx.author.mention}"),
            make_separator(),
            text(reminder)
        ))
        await ctx.send(view=rview)

    # ───────── VOICEBAN ─────────
    @commands.command(name="voiceban")
    @commands.has_permissions(moderate_members=True)
    async def voiceban(self, ctx, member: discord.Member):
        if member.voice:
            await member.move_to(None)
        for vc in ctx.guild.voice_channels:
            await vc.set_permissions(member, connect=False)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   {member.mention} voice-banned.")))
        await send_v2(ctx, view)

    # ───────── WEBHOOK ─────────
    @commands.command(name="webhook")
    @commands.has_permissions(manage_webhooks=True)
    async def webhook(self, ctx, name: str = f"{Config.BOT_NAME} Webhook"):
        wh = await ctx.channel.create_webhook(name=name)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Webhook Created"),
            make_separator(),
            text(f"**Name:** {wh.name}\n**URL:** ||{wh.url}||")
        ))
        await ctx.author.send(view=view)
        await ctx.reply("📩 Webhook sent in DMs.")


async def setup(bot):
    await bot.add_cog(Moderation(bot))