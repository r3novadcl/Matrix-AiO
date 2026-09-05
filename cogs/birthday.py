import discord
from discord.ext import commands, tasks
import json, os
from datetime import datetime, date
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

BDAY_FILE = "birthday.json"

DEFAULT_MESSAGE = "🎉 Happy Birthday {user}! Hope you have an amazing day filled with joy and cake! 🎂🥳"


# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(BDAY_FILE, dict)

def load_bday():
    return _cache.load()

def save_bday(d):
    _cache.save(d)


class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.birthday_check.start()

    def cog_unload(self):
        self.birthday_check.cancel()

    # ─── BASE BIRTHDAY MENU ───
    @commands.group(name="birthday", aliases=["bday"], invoke_without_command=True)
    async def birthday(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.GIFT}  |  Birthday Commands"),
            make_separator(),

            text(f"**{Config.PREFIX}birthday set <DD> <MM> <YYYY>**"),
            text(f"Set your birthday."),

            text(f"**{Config.PREFIX}birthday check [user]**"),
            text(f"Check your or someone's birthday."),

            text(f"**{Config.PREFIX}birthday list**"),
            text(f"List birthdays today."),

            text(f"**{Config.PREFIX}birthday reset <user>**"),
            text(f"**(Admin)** Reset a user's birthday."),

            text(f"**{Config.PREFIX}birthday setup <#channel> <@role>**"),
            text(f"**(Admin)** Configure birthday wishes."),

            text(f"**{Config.PREFIX}birthday setup message**"),
            text(f"**(Admin)** Set custom birthday message."),

            make_separator(),
            text(f"-# © {Config.FOOTER_TEXT}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BIRTHDAY SET ───
    @birthday.command(name="set")
    async def bday_set(self, ctx, day: int, month: int, year: int):
        # Validate date
        try:
            bday = date(year, month, day)
        except ValueError:
            return await send_v2(ctx, error_view("Invalid date. Use format: `&birthday set DD MM YYYY`"))

        if year < 1900 or year > datetime.now().year:
            return await send_v2(ctx, error_view("Please provide a valid year."))

        data = load_bday()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"users": {}, "channel": None, "role": None, "message": DEFAULT_MESSAGE})
        data[gid]["users"][str(ctx.author.id)] = {
            "day": day, "month": month, "year": year
        }
        save_bday(data)

        age = datetime.now().year - year
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Birthday Set"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {ctx.author.mention}\n"
                f"{Emojis.CALENDAR} **Birthday:** {day:02d}/{month:02d}/{year}\n"
                f"{Emojis.BIRTHDAY} **Age:** {age} years"
            ),
            make_separator(),
            text(f"-# I'll wish you on your birthday! {Emojis.PARTY}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BIRTHDAY CHECK ───
    @birthday.command(name="check")
    async def bday_check(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load_bday()
        gid = str(ctx.guild.id)
        user_data = data.get(gid, {}).get("users", {}).get(str(member.id))

        if not user_data:
            return await send_v2(ctx, error_view(f"{member.mention} hasn't set their birthday yet."))

        day = user_data["day"]
        month = user_data["month"]
        year = user_data["year"]
        age = datetime.now().year - year

        # Calculate days until next birthday
        today = date.today()
        next_bday = date(today.year, month, day)
        if next_bday < today:
            next_bday = date(today.year + 1, month, day)
        days_until = (next_bday - today).days

        view = discord.ui.LayoutView()
        section = discord.ui.Section(
            text(f"### {Emojis.BIRTHDAY}  Birthday Info"),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.CALENDAR} **Birthday:** {day:02d}/{month:02d}/{year}\n"
                f"{Emojis.PARTY} **Current Age:** {age}\n"
                f"{Emojis.CLOCK} **Days Until Next:** {days_until} days"
            ),
            accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
        )
        container = MatrixContainer(
            section,
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BIRTHDAY LIST ───
    @birthday.command(name="list")
    async def bday_list(self, ctx):
        data = load_bday()
        gid = str(ctx.guild.id)
        users = data.get(gid, {}).get("users", {})
        today = date.today()

        today_bdays = []
        for uid, info in users.items():
            if info["day"] == today.day and info["month"] == today.month:
                today_bdays.append((uid, info))

        view = discord.ui.LayoutView()
        if not today_bdays:
            container = MatrixContainer(
                text(f"### {Emojis.BIRTHDAY}  Birthdays Today"),
                make_separator(),
                text(f"No birthdays today! {Emojis.CALENDAR}")
            )
        else:
            lines = []
            for uid, info in today_bdays:
                age = today.year - info["year"]
                lines.append(f"{Emojis.CAKE} <@{uid}> — Turning **{age}** today! {Emojis.PARTY}")
            container = MatrixContainer(
                text(f"### {Emojis.BIRTHDAY}  Birthdays Today [{len(today_bdays)}]"),
                make_separator(),
                text("\n".join(lines))
            )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BIRTHDAY RESET ───
    @birthday.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def bday_reset(self, ctx, member: discord.Member):
        data = load_bday()
        gid = str(ctx.guild.id)
        users = data.get(gid, {}).get("users", {})
        if str(member.id) not in users:
            return await send_v2(ctx, error_view(f"{member.mention} doesn't have a birthday set."))
        del data[gid]["users"][str(member.id)]
        save_bday(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Birthday reset for {member.mention}")))
        await send_v2(ctx, view)

    # ─── BIRTHDAY SETUP ───
    @birthday.group(name="setup", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def bday_setup(self, ctx, channel: discord.TextChannel, role: discord.Role = None):
        data = load_bday()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"users": {}, "channel": None, "role": None, "message": DEFAULT_MESSAGE})
        data[gid]["channel"] = str(channel.id)
        if role:
            data[gid]["role"] = str(role.id)
        save_bday(data)

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Birthday Setup Complete"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n"
                f"{Emojis.ROLE} **Birthday Role:** {role.mention if role else 'None'}\n"
                f"{Emojis.BIRTHDAY} **Message:** Default (use `{Config.PREFIX}birthday setup message` to customize)"
            ),
            make_separator(),
            text(f"-# Birthday wishes will be sent to {channel.mention} {Emojis.PARTY}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BIRTHDAY SETUP MESSAGE ───
    @bday_setup.command(name="message")
    @commands.has_permissions(administrator=True)
    async def bday_setup_message(self, ctx, *, message: str = None):
        if not message:
            view = discord.ui.LayoutView()
            container = MatrixContainer(
                text(f"### {Emojis.BIRTHDAY}  Custom Birthday Message"),
                make_separator(),
                text(
                    "Set a custom birthday wish message!\n\n"
                    f"**Usage:** `{Config.PREFIX}birthday setup message <message>`\n\n"
                    f"**Variables:**\n"
                    f"`{{user}}` — User mention\n"
                    f"`{{name}}` — Username\n"
                    f"`{{age}}` — Current age\n"
                    f"`{{server}}` — Server name\n\n"
                    f"**Example:**\n"
                    f"`{Config.PREFIX}birthday setup message 🎉 Happy {{age}}th Birthday {{user}}! Welcome to another year in {{server}}!`"
                )
            )
            view.add_item(container)
            return await send_v2(ctx, view)

        data = load_bday()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"users": {}, "channel": None, "role": None, "message": DEFAULT_MESSAGE})
        data[gid]["message"] = message
        save_bday(data)

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Birthday Message Updated"),
            make_separator(),
            text(f"{Emojis.ARROW} **New Message:**\n{message}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BIRTHDAY CONFIG ───
    @birthday.command(name="config")
    async def bday_config(self, ctx):
        data = load_bday()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, {"users": {}, "channel": None, "role": None, "message": DEFAULT_MESSAGE})

        ch = f"<#{gcfg['channel']}>" if gcfg.get("channel") else "Not Set"
        role = f"<@&{gcfg['role']}>" if gcfg.get("role") else "Not Set"
        message = gcfg.get("message", DEFAULT_MESSAGE)
        total_users = len(gcfg.get("users", {}))

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.BIRTHDAY}  Birthday Configuration"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {ch}\n"
                f"{Emojis.ROLE} **Birthday Role:** {role}\n"
                f"{Emojis.MEMBERS} **Total Birthdays Saved:** {total_users}"
            ),
            make_separator(),
            text(f"{Emojis.PENCIL} **Message:**\n{message}"),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── BACKGROUND CHECKER ───
    @tasks.loop(hours=1)
    async def birthday_check(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        # Run only between 8-9 AM server time
        if now.hour != 9:
            return

        data = load_bday()
        today = date.today()

        for gid, gcfg in data.items():
            ch_id = gcfg.get("channel")
            if not ch_id:
                continue
            channel = self.bot.get_channel(int(ch_id))
            if not channel:
                continue

            guild = self.bot.get_guild(int(gid))
            if not guild:
                continue

            role_id = gcfg.get("role")
            role = guild.get_role(int(role_id)) if role_id else None

            template = gcfg.get("message", DEFAULT_MESSAGE)

            for uid, info in gcfg.get("users", {}).items():
                if info["day"] == today.day and info["month"] == today.month:
                    member = guild.get_member(int(uid))
                    if not member:
                        continue
                    age = today.year - info["year"]

                    # Format message
                    msg = template.replace("{user}", member.mention)\
                                  .replace("{name}", member.name)\
                                  .replace("{age}", str(age))\
                                  .replace("{server}", guild.name)

                    view = discord.ui.LayoutView()
                    section = discord.ui.Section(
                        text(f"### {Emojis.BIRTHDAY}  Happy Birthday!"),
                        text(msg),
                        accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
                    )
                    container = MatrixContainer(
                        section,
                        make_separator(),
                        text(
                            f"{Emojis.CAKE} **Turning:** {age} years old\n"
                            f"{Emojis.PARTY} Wishing you joy, love, and lots of cake!"
                        ),
                        make_separator(),
                        text(f"-# {Emojis.CONFETTI} From everyone at {guild.name} {Emojis.CONFETTI}")
                    )
                    view.add_item(container)

                    try:
                        await channel.send(view=view)
                    except:
                        pass

                    # Add birthday role
                    if role:
                        try:
                            await member.add_roles(role, reason="Birthday role")
                        except:
                            pass


async def setup(bot):
    await bot.add_cog(Birthday(bot))