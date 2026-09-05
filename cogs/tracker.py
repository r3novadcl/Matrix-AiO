"""
Matrix Bot - Tracker (Message & Invite tracking)
Components V2 with red accent + JSON storage
"""

import discord
from discord.ext import commands
import json, os
from datetime import datetime, timezone
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

TRACK_FILE = "tracker.json"


# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(TRACK_FILE, lambda: {"messages": {}, "daily": {}, "invites": {}, "invite_cache": {}, "blacklist": {}})

def load_track():
    return _cache.load()

def save_track(d):
    _cache.save(d)

def utcnow():
    return datetime.now(timezone.utc)


# ─── View Builders ───

def message_view(member, total, today, avg):
    view = discord.ui.LayoutView()
    section = discord.ui.Section(
        text(f"### {Emojis.MSG_TRACK}  Message Tracker"),
        text(
            f"{Emojis.USER_TRK} **User:** {member.mention}\n"
            f"{Emojis.ARROW} **Total Messages:** `{total}`\n"
            f"{Emojis.ARROW} **Today's Messages:** `{today}`\n"
            f"{Emojis.ARROW} **Avg. Daily:** `{avg:.2f}`"
        ),
        accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
    )
    container = MatrixContainer(section)
    view.add_item(container)
    return view


def invites_view(member, total, fake, today_inv, invited_users):
    view = discord.ui.LayoutView()
    section = discord.ui.Section(
        text(f"### {Emojis.INVITE_TRK}  Invite Tracker"),
        text(
            f"{Emojis.USER_TRK} **User:** {member.mention}\n"
            f"{Emojis.ARROW} **Total Invites:** `{total}`\n"
            f"{Emojis.ARROW} **Fake Invites:** `{fake}`\n"
            f"{Emojis.ARROW} **Today's Invites:** `{today_inv}`"
        ),
        accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
    )
    container = MatrixContainer(section)
    if invited_users:
        container.add_item(make_separator(visible=False))
        container.add_item(text(f"-# Recently invited: {invited_users}"))
    view.add_item(container)
    return view


def blacklist_view(channels):
    view = discord.ui.LayoutView()
    lines = [f"{Emojis.ARROW} <#{c}>" for c in channels] if channels else ["-# No channels are blacklisted."]
    container = MatrixContainer(
        text(f"### {Emojis.BLOCK}  Blacklisted Channels"),
        make_separator(),
        text("\n".join(lines)),
        make_separator(),
        text(f"-# Total: {len(channels)}")
    )
    view.add_item(container)
    return view


def overview_view(bot, total_users, total_msgs, today_total, bl_count):
    view = discord.ui.LayoutView()
    section = discord.ui.Section(
        text(f"### {Emojis.STATS_TRK}  Tracker Overview"),
        text(
            f"{Emojis.USER_TRK} **Tracked Users:** `{total_users}`\n"
            f"{Emojis.MSG_TRACK} **Total Messages:** `{total_msgs}`\n"
            f"{Emojis.ARROW} **Today's Messages:** `{today_total}`\n"
            f"{Emojis.BLOCK} **Blacklisted Channels:** `{bl_count}`"
        ),
        accessory=discord.ui.Thumbnail(media=bot.user.display_avatar.url)
    )
    container = MatrixContainer(section)
    view.add_item(container)
    return view


class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_cache = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                invs = await guild.invites()
                self.invite_cache[guild.id] = {i.code: i.uses for i in invs}
            except:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        data = load_track()
        gid = str(message.guild.id)
        uid = str(message.author.id)

        # Blacklist check
        bl = data.get("blacklist", {}).get(gid, [])
        if str(message.channel.id) in bl:
            return

        # Total
        data.setdefault("messages", {}).setdefault(gid, {}).setdefault(uid, 0)
        data["messages"][gid][uid] += 1

        # Daily
        today = utcnow().date().isoformat()
        data.setdefault("daily", {}).setdefault(gid, {}).setdefault(today, {}).setdefault(uid, 0)
        data["daily"][gid][today][uid] += 1

        save_track(data)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        try:
            new_invs = await member.guild.invites()
        except:
            return

        old = self.invite_cache.get(member.guild.id, {})
        inviter = None
        for inv in new_invs:
            if inv.uses > old.get(inv.code, 0):
                inviter = inv.inviter
                break
        self.invite_cache[member.guild.id] = {i.code: i.uses for i in new_invs}

        if not inviter:
            return

        fake = (utcnow() - member.created_at).days < 7

        data = load_track()
        gid = str(member.guild.id)
        data.setdefault("invites", {}).setdefault(gid, {})
        data["invites"][gid][str(member.id)] = {
            "inviter_id": str(inviter.id),
            "joined_at": utcnow().isoformat(),
            "fake": fake,
            "left": False
        }
        save_track(data)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        data = load_track()
        gid = str(member.guild.id)
        if str(member.id) in data.get("invites", {}).get(gid, {}):
            data["invites"][gid][str(member.id)]["left"] = True
            save_track(data)

    # ─── COMMANDS ───

    @commands.command(name="messages", aliases=["msg", "msgs"])
    async def messages(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load_track()
        gid = str(ctx.guild.id); uid = str(member.id)

        total = data.get("messages", {}).get(gid, {}).get(uid, 0)
        today = utcnow().date().isoformat()
        today_count = data.get("daily", {}).get(gid, {}).get(today, {}).get(uid, 0)

        days = max(1, (utcnow().date() - member.joined_at.date()).days) if member.joined_at else 1
        avg = total / days

        await send_v2(ctx, message_view(member, total, today_count, avg))

    @commands.command(name="addmessages", aliases=["addmsg"])
    @commands.has_permissions(manage_guild=True)
    async def addmessages(self, ctx, member: discord.Member, count: int):
        data = load_track()
        gid = str(ctx.guild.id); uid = str(member.id)
        data.setdefault("messages", {}).setdefault(gid, {}).setdefault(uid, 0)
        data["messages"][gid][uid] += count
        save_track(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Added `{count}` messages to {member.mention}")))
        await send_v2(ctx, view)

    @commands.command(name="removemessages", aliases=["rmmsg"])
    @commands.has_permissions(manage_guild=True)
    async def removemessages(self, ctx, member: discord.Member, count: int):
        data = load_track()
        gid = str(ctx.guild.id); uid = str(member.id)
        current = data.get("messages", {}).get(gid, {}).get(uid, 0)
        data.setdefault("messages", {}).setdefault(gid, {})[uid] = max(0, current - count)
        save_track(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Removed `{count}` messages from {member.mention}")))
        await send_v2(ctx, view)

    @commands.command(name="resetmessages", aliases=["clearmsg"])
    @commands.has_permissions(administrator=True)
    async def resetmessages(self, ctx, member: discord.Member = None):
        data = load_track()
        gid = str(ctx.guild.id)
        if member is None:
            data.get("messages", {}).pop(gid, None)
            data.get("daily", {}).pop(gid, None)
            msg = "All messages reset for this server."
        else:
            data.get("messages", {}).get(gid, {}).pop(str(member.id), None)
            for d in data.get("daily", {}).get(gid, {}).values():
                d.pop(str(member.id), None)
            msg = f"Reset messages for {member.mention}"
        save_track(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  {msg}")))
        await send_v2(ctx, view)

    @commands.command(name="blacklistchannel", aliases=["blch"])
    @commands.has_permissions(manage_channels=True)
    async def blacklistchannel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        data = load_track()
        gid = str(ctx.guild.id)
        bl = data.setdefault("blacklist", {}).setdefault(gid, [])
        if str(channel.id) not in bl:
            bl.append(str(channel.id))
            save_track(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  {channel.mention} blacklisted from tracking.")))
        await send_v2(ctx, view)

    @commands.command(name="unblacklistchannel", aliases=["ublch"])
    @commands.has_permissions(manage_channels=True)
    async def unblacklistchannel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        data = load_track()
        gid = str(ctx.guild.id)
        bl = data.get("blacklist", {}).get(gid, [])
        if str(channel.id) in bl:
            bl.remove(str(channel.id))
            save_track(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  {channel.mention} removed from blacklist.")))
        await send_v2(ctx, view)

    @commands.command(name="blacklistedchannels", aliases=["blchlist"])
    @commands.has_permissions(manage_channels=True)
    async def blacklistedchannels(self, ctx):
        data = load_track()
        bl = data.get("blacklist", {}).get(str(ctx.guild.id), [])
        await send_v2(ctx, blacklist_view(bl))

    @commands.command(name="invites", aliases=["invs"])
    async def invites(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load_track()
        gid = str(ctx.guild.id)
        invites = data.get("invites", {}).get(gid, {})

        # Find all invites by this member
        invited = [(uid, info) for uid, info in invites.items() if info["inviter_id"] == str(member.id)]
        total = len(invited)
        fake = sum(1 for _, i in invited if i.get("fake"))

        today = utcnow().date()
        today_inv = sum(
            1 for _, i in invited
            if datetime.fromisoformat(i["joined_at"]).date() == today
        )

        recent_names = []
        for uid, _ in invited[-5:]:
            u = ctx.guild.get_member(int(uid))
            if u: recent_names.append(u.name)
        invited_str = ", ".join(recent_names) if recent_names else None

        await send_v2(ctx, invites_view(member, total, fake, today_inv, invited_str))

    @commands.command(name="tracker")
    async def tracker(self, ctx):
        data = load_track()
        gid = str(ctx.guild.id)

        msgs = data.get("messages", {}).get(gid, {})
        users = len(msgs)
        total = sum(msgs.values())

        today = utcnow().date().isoformat()
        today_data = data.get("daily", {}).get(gid, {}).get(today, {})
        today_total = sum(today_data.values())

        bl = len(data.get("blacklist", {}).get(gid, []))

        await send_v2(ctx, overview_view(self.bot, users, total, today_total, bl))


async def setup(bot):
    await bot.add_cog(Tracker(bot))