"""
Matrix Bot - Giveaway System
Components V2 style with red accent + JSON storage (no sqlite)
"""

import discord
from discord.ext import commands, tasks
import json, os, asyncio, random, re
from datetime import datetime, timedelta, timezone
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

GW_FILE = "giveaways.json"

# Default reaction emoji (uses standard emoji – can replace with custom)
PARTICIPATE_EMOJI = "🎉"


# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(GW_FILE, dict)

def load_gw():
    return _cache.load()

def save_gw(d):
    _cache.save(d)


def utcnow():
    return datetime.now(timezone.utc)


def parse_duration(text_input: str):
    """Parse duration like 1h, 30m, 1d2h."""
    pattern = re.compile(r"(\d+)\s*([smhdw])", re.IGNORECASE)
    matches = pattern.findall(text_input.lower())
    if not matches:
        try:
            return int(text_input) * 60
        except ValueError:
            return None
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    total = sum(int(v) * mult[u.lower()] for v, u in matches)
    return total if total > 0 else None


# ── View Builders ─────────────────────────────────────────────

def giveaway_active_view(prize, winners, ends_at, host):
    view = discord.ui.LayoutView(timeout=None)
    end_ts = int(ends_at.timestamp())
    container = MatrixContainer(
        text(f"### {Emojis.GIFT_NEW}  **{prize}**  {Emojis.GIFT_NEW}"),
        make_separator(),
        text(
            f"{Emojis.ARROW} **Winners:** {winners}\n"
            f"{Emojis.TIMER} **Ends:** <t:{end_ts}:R> (<t:{end_ts}:f>)\n"
            f"{Emojis.HOST} **Hosted by:** {host.mention}"
        ),
        make_separator(),
        text(f"{Emojis.TADA} React with {PARTICIPATE_EMOJI} to participate!"),
        make_separator(),
        text(f"-# Ends at • <t:{end_ts}:t>")
    )
    view.add_item(container)
    return view


def giveaway_ended_view(prize, host, total):
    view = discord.ui.LayoutView(timeout=None)
    container = MatrixContainer(
        text(f"### {Emojis.GIFT_NEW}  **{prize}**  {Emojis.GIFT_NEW}"),
        make_separator(),
        text(
            f"{Emojis.HOST} **Hosted by:** {host.mention}\n"
            f"{Emojis.USERS} **Total participants:** {total}"
        ),
        make_separator(),
        text(f"-# Ended • <t:{int(utcnow().timestamp())}:f>")
    )
    view.add_item(container)
    return view


def winners_view(winners, prize, host, url):
    view = discord.ui.LayoutView(timeout=None)
    mentions = ", ".join(w.mention for w in winners)
    container = MatrixContainer(
        text(f"### {Emojis.TADA}  Giveaway Winner!"),
        make_separator(),
        text(f"Congrats {mentions}! You won **{prize}** hosted by {host.mention} {Emojis.TROPHY}"),
        discord.ui.ActionRow(
            discord.ui.Button(label="Giveaway Link", style=discord.ButtonStyle.link, url=url)
        )
    )
    view.add_item(container)
    return view


def no_winners_view(prize, url):
    view = discord.ui.LayoutView(timeout=None)
    container = MatrixContainer(
        text(f"### {Emojis.ERROR}  No Winners"),
        make_separator(),
        text(f"Could not determine a winner for **{prize}** — not enough participants."),
        discord.ui.ActionRow(
            discord.ui.Button(label="Giveaway Link", style=discord.ButtonStyle.link, url=url)
        )
    )
    view.add_item(container)
    return view


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    # ─── BASE HELP ───
    @commands.group(name="giveaway", aliases=["g"], invoke_without_command=True)
    async def giveaway(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.GIFT_NEW}  Giveaway Commands"),
            make_separator(),
            text(
                f"`{Config.PREFIX}gstart <duration> <winners> <prize>` — Start a giveaway\n"
                f"`{Config.PREFIX}gend <message_id>` — End a giveaway early\n"
                f"`{Config.PREFIX}greroll <message_id>` — Reroll winners\n"
                f"`{Config.PREFIX}glist` — List active giveaways\n"
                f"`{Config.PREFIX}gdelete <message_id>` — Delete a giveaway"
            ),
            make_separator(),
            text("**Duration formats:** `30s`, `5m`, `2h`, `1d`, `1w`"),
            make_separator(),
            text(f"-# © {Config.FOOTER_TEXT}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── GSTART ───
    @commands.command(name="gstart")
    @commands.has_permissions(manage_guild=True)
    async def gstart(self, ctx, duration: str, winners: int, *, prize: str):
        seconds = parse_duration(duration)
        if seconds is None or seconds < 10:
            return await send_v2(ctx, error_view("Invalid duration. Use `30s`, `5m`, `2h`, `1d`. Min 10s."))
        if winners < 1 or winners > 50:
            return await send_v2(ctx, error_view("Winners must be between 1-50."))

        ends_at = utcnow() + timedelta(seconds=seconds)
        view = giveaway_active_view(prize, winners, ends_at, ctx.author)
        msg = await ctx.channel.send(view=view)
        try:
            await msg.add_reaction(PARTICIPATE_EMOJI)
        except:
            pass

        data = load_gw()
        data[str(msg.id)] = {
            "channel_id": str(ctx.channel.id),
            "guild_id": str(ctx.guild.id),
            "host_id": str(ctx.author.id),
            "prize": prize,
            "winners": winners,
            "ends_at": ends_at.isoformat(),
            "ended": False,
            "winner_ids": []
        }
        save_gw(data)

        try: await ctx.message.delete()
        except: pass

    # ─── BACKGROUND CHECK ───
    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        data = load_gw()
        now = utcnow()
        for msg_id, info in list(data.items()):
            if info.get("ended"):
                continue
            try:
                ends_at = datetime.fromisoformat(info["ends_at"])
                if ends_at.tzinfo is None:
                    ends_at = ends_at.replace(tzinfo=timezone.utc)
            except:
                continue
            if ends_at <= now:
                await self._end_giveaway(msg_id, info)

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def _end_giveaway(self, msg_id, info):
        guild = self.bot.get_guild(int(info["guild_id"]))
        if not guild: return
        channel = guild.get_channel(int(info["channel_id"]))
        if not channel: return

        try:
            message = await channel.fetch_message(int(msg_id))
        except:
            data = load_gw(); data[msg_id]["ended"] = True; save_gw(data)
            return

        host = guild.get_member(int(info["host_id"])) or self.bot.get_user(int(info["host_id"]))
        if not host:
            try: host = await self.bot.fetch_user(int(info["host_id"]))
            except: return

        # Collect participants
        participants = []
        for r in message.reactions:
            if str(r.emoji) == PARTICIPATE_EMOJI:
                async for u in r.users():
                    if not u.bot:
                        participants.append(u)
                break

        total = len(participants)
        winners_list = []
        if total > 0:
            winners_list = random.sample(participants, min(info["winners"], total))

        # Edit ended view
        try:
            await message.edit(view=giveaway_ended_view(info["prize"], host, total))
        except: pass

        # Update DB
        data = load_gw()
        data[msg_id]["ended"] = True
        data[msg_id]["winner_ids"] = [str(w.id) for w in winners_list]
        save_gw(data)

        url = f"https://discord.com/channels/{guild.id}/{channel.id}/{msg_id}"
        try:
            if winners_list:
                await channel.send(
                    view=winners_view(winners_list, info["prize"], host, url),
                    allowed_mentions=discord.AllowedMentions(users=winners_list, roles=False, everyone=False)
                )
            else:
                await channel.send(view=no_winners_view(info["prize"], url))
        except: pass

    # ─── GEND ───
    @commands.command(name="gend")
    @commands.has_permissions(manage_guild=True)
    async def gend(self, ctx, message_id: int):
        data = load_gw()
        info = data.get(str(message_id))
        if not info:
            return await send_v2(ctx, error_view(f"No giveaway with ID `{message_id}`."))
        if info.get("ended"):
            return await send_v2(ctx, error_view("That giveaway has already ended."))
        await self._end_giveaway(str(message_id), info)
        try: await ctx.message.delete()
        except: pass

    # ─── GREROLL ───
    @commands.command(name="greroll")
    @commands.has_permissions(manage_guild=True)
    async def greroll(self, ctx, message_id: int):
        data = load_gw()
        info = data.get(str(message_id))
        if not info:
            return await send_v2(ctx, error_view(f"No giveaway with ID `{message_id}`."))
        if not info.get("ended"):
            return await send_v2(ctx, error_view("Giveaway hasn't ended yet."))

        guild = self.bot.get_guild(int(info["guild_id"]))
        channel = guild.get_channel(int(info["channel_id"]))
        try:
            message = await channel.fetch_message(int(message_id))
        except:
            return await send_v2(ctx, error_view("Original message gone."))

        host = guild.get_member(int(info["host_id"])) or ctx.author

        participants = []
        for r in message.reactions:
            if str(r.emoji) == PARTICIPATE_EMOJI:
                async for u in r.users():
                    if not u.bot: participants.append(u)
                break

        url = message.jump_url
        if not participants:
            return await channel.send(view=no_winners_view(info["prize"], url))

        winners_list = random.sample(participants, min(info["winners"], len(participants)))
        data[str(message_id)]["winner_ids"] = [str(w.id) for w in winners_list]
        save_gw(data)

        await channel.send(
            view=winners_view(winners_list, info["prize"], host, url),
            allowed_mentions=discord.AllowedMentions(users=winners_list, roles=False, everyone=False)
        )
        try: await ctx.message.delete()
        except: pass

    # ─── GLIST ───
    @commands.command(name="glist")
    @commands.has_permissions(manage_guild=True)
    async def glist(self, ctx):
        data = load_gw()
        active = [(mid, i) for mid, i in data.items()
                  if not i.get("ended") and i.get("guild_id") == str(ctx.guild.id)]

        view = discord.ui.LayoutView()
        if not active:
            container = MatrixContainer(
                text(f"### {Emojis.GIFT_NEW}  Active Giveaways"),
                make_separator(),
                text("-# No active giveaways.")
            )
        else:
            lines = []
            for mid, i in active:
                ts = int(datetime.fromisoformat(i["ends_at"]).replace(tzinfo=timezone.utc).timestamp())
                url = f"https://discord.com/channels/{ctx.guild.id}/{i['channel_id']}/{mid}"
                lines.append(f"{Emojis.ARROW} **{i['prize']}** — Ends <t:{ts}:R> — [Jump]({url})")
            container = MatrixContainer(
                text(f"### {Emojis.GIFT_NEW}  Active Giveaways [{len(active)}]"),
                make_separator(),
                text("\n".join(lines))
            )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── GDELETE ───
    @commands.command(name="gdelete")
    @commands.has_permissions(manage_guild=True)
    async def gdelete(self, ctx, message_id: int):
        data = load_gw()
        info = data.get(str(message_id))
        if not info:
            return await send_v2(ctx, error_view(f"No giveaway with ID `{message_id}`."))

        try:
            ch = ctx.guild.get_channel(int(info["channel_id"]))
            if ch:
                msg = await ch.fetch_message(int(message_id))
                await msg.delete()
        except: pass

        del data[str(message_id)]
        save_gw(data)

        try: await ctx.message.delete()
        except: pass


async def setup(bot):
    await bot.add_cog(Giveaway(bot))