import discord
from discord.ext import commands
from datetime import datetime
import platform, psutil
from config import Config
from emojis import Emojis
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── MEMBERCOUNT ───
    @commands.command(name="membercount", aliases=["mc"])
    async def membercount(self, ctx):
        g = ctx.guild
        total = g.member_count
        humans = sum(1 for m in g.members if not m.bot)
        bots = sum(1 for m in g.members if m.bot)

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {g.name}'s server Member Stats:-"),
            make_separator(),
            text(
                f"**Total Members** {Emojis.ARROW} {total}\n"
                f"**Total Humans** {Emojis.ARROW} {humans}\n"
                f"**Total Bots** {Emojis.ARROW} {bots}"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name} • <t:{int(datetime.utcnow().timestamp())}:t>")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SERVERINFO ───
    @commands.command(name="serverinfo", aliases=["sinfo"])
    async def serverinfo(self, ctx):
        g = ctx.guild
        text_ch = len(g.text_channels)
        voice_ch = len(g.voice_channels)
        total_ch = text_ch + voice_ch
        regular_emojis = sum(1 for e in g.emojis if not e.animated)
        animated_emojis = sum(1 for e in g.emojis if e.animated)
        try:
            bans = len([b async for b in g.bans(limit=None)])
        except:
            bans = 0
        verification = str(g.verification_level).title()
        inactive = f"{Emojis.ERROR}  Disabled" if not g.afk_channel else f"#{g.afk_channel.name}"
        system_ch = g.system_channel.mention if g.system_channel else "None"
        roles_display = " ".join([r.mention for r in g.roles[1:6]]) or "None"

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {g.name}'s server's Profile"),
            text(f"Detailed overview and statistics of {g.name} server."),
            make_separator(),

            text(f"{Emojis.WARNING} **General Information**"),
            text(
                f"{Emojis.ARROW} **Name:** {g.name}\n"
                f"{Emojis.ARROW} **Server ID:** `{g.id}`\n"
                f"{Emojis.ARROW} **Owner:** {g.owner.mention}\n"
                f"{Emojis.ARROW} **Created At:** <t:{int(g.created_at.timestamp())}:R>\n"
                f"{Emojis.ARROW} **Members:** {g.member_count} | **Banned:** {bans}"
            ),
            make_separator(),

            text(f"{Emojis.SETTINGS} **Server Settings**"),
            text(
                f"{Emojis.ARROW} **Verification Level:** {verification}\n"
                f"{Emojis.ARROW} **Inactive Channel:** {inactive}\n"
                f"{Emojis.ARROW} **Inactive Timeout:** {g.afk_timeout // 60} mins\n"
                f"{Emojis.ARROW} **System Channel:** {system_ch}"
            ),
            make_separator(),

            text(f"{Emojis.CHANNEL} **Channels**"),
            text(f"**Total:** {total_ch} | **Text:** {text_ch} | **Voice:** {voice_ch}"),
            make_separator(),

            text(f"{Emojis.CATEGORY} **Categories**"),
            text(f"**Total:** {len(g.categories)}"),
            make_separator(),

            text(f"{Emojis.EMOJI} **Emojis**"),
            text(f"**Regular:** {regular_emojis} | **Animated:** {animated_emojis}"),
            make_separator(),

            text(f"{Emojis.BOOST} **Server Boosts**"),
            text(f"**Level:** Level {g.premium_tier} | **Booster:** {g.premium_subscription_count}"),
            make_separator(),

            text(f"{Emojis.ROLE} **Server Roles [{len(g.roles)-1}]**"),
            text(roles_display),
            make_separator(),

            text(f"-# MATRIX Profile System • Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── USERINFO ───
    @commands.command(name="userinfo", aliases=["uinfo", "whois"])
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [r.mention for r in member.roles[1:]]
        view = discord.ui.LayoutView()
        section = discord.ui.Section(
            text(f"### {Emojis.WARNING}   {member.name}'s Profile"),
            text(
                f"{Emojis.ARROW} **Name:** {member}\n"
                f"{Emojis.ARROW} **ID:** `{member.id}`\n"
                f"{Emojis.ARROW} **Nickname:** {member.nick or 'None'}\n"
                f"{Emojis.ARROW} **Top Role:** {member.top_role.mention}"
            ),
            accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
        )
        container = MatrixContainer(
            section,
            make_separator(),
            text(
                f"{Emojis.ARROW} **Created:** <t:{int(member.created_at.timestamp())}:R>\n"
                f"{Emojis.ARROW} **Joined:** <t:{int(member.joined_at.timestamp())}:R>"
            ),
            make_separator(),
            text(f"{Emojis.ROLE} **Roles [{len(roles)}]**"),
            text(" ".join(roles[:15]) if roles else "None"),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── AVATAR ───
    @commands.command(name="avatar", aliases=["av"])
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {member.name}'s Avatar"),
            make_separator(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=member.display_avatar.url)),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BANNER ───
    @commands.command(name="banner")
    async def banner(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)
        if not user.banner:
            return await send_v2(ctx, error_view("This user doesn't have a banner."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {member.name}'s Banner"),
            make_separator(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=user.banner.url))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SERVERICON ───
    @commands.command(name="servericon", aliases=["sicon"])
    async def servericon(self, ctx):
        if not ctx.guild.icon:
            return await send_v2(ctx, error_view("This server has no icon."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {ctx.guild.name}'s Icon"),
            make_separator(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=ctx.guild.icon.url))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SERVERBANNER ───
    @commands.command(name="serverbanner", aliases=["sbanner"])
    async def serverbanner(self, ctx):
        if not ctx.guild.banner:
            return await send_v2(ctx, error_view("This server has no banner."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {ctx.guild.name}'s Banner"),
            make_separator(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=ctx.guild.banner.url))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── ROLEINFO ───
    @commands.command(name="roleinfo", aliases=["rinfo"])
    async def roleinfo(self, ctx, *, role: discord.Role):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   Role Info - {role.name}"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Name:** {role.name}\n"
                f"{Emojis.ARROW} **ID:** `{role.id}`\n"
                f"{Emojis.ARROW} **Color:** `{role.color}`\n"
                f"{Emojis.ARROW} **Members:** {len(role.members)}\n"
                f"{Emojis.ARROW} **Position:** {role.position}\n"
                f"{Emojis.ARROW} **Mentionable:** {role.mentionable}\n"
                f"{Emojis.ARROW} **Hoisted:** {role.hoist}\n"
                f"{Emojis.ARROW} **Created:** <t:{int(role.created_at.timestamp())}:R>"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── ROLEICON ───
    @commands.command(name="roleicon")
    async def roleicon(self, ctx, *, role: discord.Role):
        if not role.icon:
            return await send_v2(ctx, error_view("This role has no icon."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {role.name}'s Icon"),
            make_separator(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=role.icon.url))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── CHANNELINFO ───
    @commands.command(name="channelinfo", aliases=["cinfo"])
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   Channel Info"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Name:** {channel.name}\n"
                f"{Emojis.ARROW} **ID:** `{channel.id}`\n"
                f"{Emojis.ARROW} **Type:** {channel.type}\n"
                f"{Emojis.ARROW} **Category:** {channel.category.name if channel.category else 'None'}\n"
                f"{Emojis.ARROW} **NSFW:** {channel.nsfw}\n"
                f"{Emojis.ARROW} **Slowmode:** {channel.slowmode_delay}s\n"
                f"{Emojis.ARROW} **Created:** <t:{int(channel.created_at.timestamp())}:R>"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── EMOJILIST ───
    @commands.command(name="emojilist")
    async def emojilist(self, ctx):
        emojis = [str(e) for e in ctx.guild.emojis]
        if not emojis:
            return await send_v2(ctx, error_view("No emojis in this server."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.EMOJI}  Server Emojis [{len(emojis)}]"),
            make_separator(),
            text(" ".join(emojis[:80]))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── PING ───
    @commands.command(name="ping")
    async def ping(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   Pong!"),
            make_separator(),
            text(f"{Emojis.ARROW} **Latency:** `{round(self.bot.latency * 1000)}ms`")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── UPTIME ───
    @commands.command(name="uptime")
    async def uptime(self, ctx):
        delta = datetime.utcnow() - self.bot.start_time
        hours, rem = divmod(int(delta.total_seconds()), 3600)
        mins, secs = divmod(rem, 60)
        days, hours = divmod(hours, 24)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   Bot Uptime"),
            make_separator(),
            text(f"{Emojis.ARROW} `{days}d {hours}h {mins}m {secs}s`")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── INVITE ───
    @commands.command(name="invite")
    async def invite(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   Invite {Config.BOT_NAME}"),
            text("Click the buttons below to invite or get support."),
            make_separator(),
            discord.ui.ActionRow(
                discord.ui.Button(label="Invite Me",      style=discord.ButtonStyle.link, url=Config.INVITE_URL),
                discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url=Config.SUPPORT_SERVER),
                discord.ui.Button(label="Vote",           style=discord.ButtonStyle.link, url=Config.VOTE_URL),
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── PROFILE ───
    @commands.command(name="profile")
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        view = discord.ui.LayoutView()
        section = discord.ui.Section(
            text(f"### {Emojis.WARNING}   {member.name}'s Profile"),
            text(f"User ID: `{member.id}`"),
            accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
        )
        container = MatrixContainer(
            section,
            make_separator(),
            text(
                f"{Emojis.ARROW} **Joined:** <t:{int(member.joined_at.timestamp())}:R>\n"
                f"{Emojis.ARROW} **Created:** <t:{int(member.created_at.timestamp())}:R>\n"
                f"{Emojis.ARROW} **Top Role:** {member.top_role.mention}\n"
                f"{Emojis.ARROW} **Boosting:** {'Yes' if member.premium_since else 'No'}"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── AFK ───
    @commands.command(name="afk")
    async def afk(self, ctx, *, reason="AFK"):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   You are now AFK"),
            make_separator(),
            text(f"{Emojis.ARROW} **Reason:** {reason}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BOOST ───
    @commands.command(name="boost")
    async def boost(self, ctx):
        g = ctx.guild
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.BOOST}   {g.name}'s Boost Status"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Level:** Level {g.premium_tier}\n"
                f"{Emojis.ARROW} **Boosters:** {g.premium_subscription_count}\n"
                f"{Emojis.ARROW} **Boost Role:** {g.premium_subscriber_role.mention if g.premium_subscriber_role else 'None'}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BOOSTCOUNT ───
    @commands.command(name="boostcount")
    async def boostcount(self, ctx):
        boosters = [m.mention for m in ctx.guild.members if m.premium_since]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.BOOST}   Boosters [{len(boosters)}]"),
            make_separator(),
            text(" ".join(boosters[:30]) if boosters else "No boosters yet.")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── CALCULATOR ───
    @commands.command(name="calculator", aliases=["calc"])
    async def calculator(self, ctx, *, expression: str):
        try:
            allowed = set("0123456789+-*/(). ")
            if not set(expression) <= allowed:
                raise ValueError("Invalid chars")
            result = eval(expression)
        except Exception:
            return await send_v2(ctx, error_view("Invalid math expression."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   Calculator"),
            make_separator(),
            text(f"**Expression:** `{expression}`\n**Result:** `{result}`")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── FIRSTMSG ───
    @commands.command(name="firstmsg")
    async def firstmsg(self, ctx):
        async for msg in ctx.channel.history(limit=1, oldest_first=True):
            view = discord.ui.LayoutView()
            container = MatrixContainer(
                text(f"### {Emojis.WARNING}   First Message"),
                make_separator(),
                text(
                    f"**Author:** {msg.author.mention}\n"
                    f"**Content:** {msg.content or '*[Empty]*'}\n"
                    f"**Sent:** <t:{int(msg.created_at.timestamp())}:R>\n"
                    f"[Jump to Message]({msg.jump_url})"
                )
            )
            view.add_item(container)
            return await send_v2(ctx, view)

    # ─── GITHUB ───
    @commands.command(name="github")
    async def github(self, ctx, username: str):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   GitHub Profile"),
            make_separator(),
            text(f"[View {username} on GitHub](https://github.com/{username})")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── REPORT ───
    @commands.command(name="report")
    async def report(self, ctx, member: discord.Member, *, reason: str):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Report Submitted"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Reported:** {member.mention}\n"
                f"{Emojis.ARROW} **By:** {ctx.author.mention}\n"
                f"{Emojis.ARROW} **Reason:** {reason}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── STATS ───
    @commands.command(name="stats")
    async def stats(self, ctx):
        cpu = psutil.cpu_percent()
        mem = psutil.Process().memory_info().rss / 1024 ** 2
        view = discord.ui.LayoutView()
        section = discord.ui.Section(
            text(f"### **{Config.BOT_NAME.upper()} • System Information**"),
            text("Detailed real-time system performance statistics."),
            accessory=discord.ui.Thumbnail(media=Config.BOT_LOGO if Config.BOT_LOGO.startswith("http") else self.bot.user.display_avatar.url)
        )
        container = MatrixContainer(
            section,
            make_separator(),
            text(f"**• Latency Metrics**\n**System:** `{round(self.bot.latency*1000)}ms`\n**Database:** `N/A`"),
            make_separator(),
            text(f"**• Hardware Usage**\n**CPU:** `{cpu}%`\n**Memory:** `{mem:.2f} MB`"),
            make_separator(),
            text(
                f"**• Environment**\n"
                f"**Platform:** `{platform.system().lower()} {platform.machine()}`\n"
                f"**Python:** `v{platform.python_version()}`\n"
                f"**CPU Model:** `{platform.processor() or 'Unknown'}`"
            ),
            make_separator(),
            text(f"-# {Config.BOT_NAME} • Developed by {Config.DEVELOPER_CREDIT} • Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)


async def setup(bot):
    await bot.add_cog(Information(bot))