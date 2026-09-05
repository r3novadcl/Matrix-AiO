import discord
from discord.ext import commands
import json, os, time, random
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

LVL_FILE = "leveling.json"

DEFAULT_MESSAGE = "🎉 Congrats {user}! You leveled up to **Level {level}** in **{server}**!"

CARD_THEMES = {
    "default": {"color": Config.COLOR_PRIMARY, "name": "Default Red"},
    "1": {"color": 0x00AAFF, "name": "Ocean Blue"},
    "2": {"color": 0x00CC66, "name": "Emerald Green"},
    "3": {"color": 0xFFAA00, "name": "Sunset Gold"},
}


# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(LVL_FILE, dict)

def load_lvl():
    return _cache.load()

def save_lvl(d):
    _cache.save(d)


def xp_for_level(level: int) -> int:
    """XP required to reach next level."""
    return 5 * (level ** 2) + 50 * level + 100


def get_default_guild_cfg():
    return {
        "enabled": False,
        "voice_enabled": False,
        "channel": None,
        "message": DEFAULT_MESSAGE,
        "xp_per_msg": 20,
        "card": "default",
        "noxp_channels": [],
        "users": {}  # user_id -> {"xp": 0, "level": 0, "last_msg": 0, "voice_time": 0}
    }


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join_times = {}  # (guild_id, user_id) -> join_timestamp

    # ─── BASE LEVEL MENU ───
    @commands.group(name="level", aliases=["lvl"], invoke_without_command=True)
    async def level(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SETTINGS}  |  Leveling Commands"),
            make_separator(),

            text(f"**level enable/disable**"),
            text("Enable or Disable leveling system"),

            text(f"**level voice <enable/disable>**"),
            text("Enable or Disable Voice Leveling specifically"),

            text(f"**level channel #channel**"),
            text("Set level-up notification channel"),

            text(f"**level message**"),
            text("Set customization level up message.\nVariables: `{user}`, `{level}`, `{server}`"),

            text(f"**level xp <amount>**"),
            text("Set XP per message (default 20)"),

            text(f"**level card <default/1/2/3>**"),
            text("Select rank card theme & design"),

            text(f"**level noxp**"),
            text("Configure channels where chatting gives no XP"),

            text(f"**level config**"),
            text("View current configuration"),

            text(f"**level reset**"),
            text("Reset all member configurations, levels, and XP"),

            text(f"**level leaderboard**"),
            text("Display the server leveling leaderboard (alias: lb)"),

            make_separator(),
            text(f"-# © {Config.FOOTER_TEXT}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── LEVEL ENABLE ───
    @level.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def lvl_enable(self, ctx):
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["enabled"] = True
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Leveling System Enabled"),
            make_separator(),
            text(f"{Emojis.LEVEL} Members will now earn XP from chatting!")
        ))
        await send_v2(ctx, view)

    # ─── LEVEL DISABLE ───
    @level.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def lvl_disable(self, ctx):
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["enabled"] = False
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Leveling System Disabled")))
        await send_v2(ctx, view)

    # ─── LEVEL VOICE ───
    @level.command(name="voice")
    @commands.has_permissions(administrator=True)
    async def lvl_voice(self, ctx, action: str):
        if action.lower() not in ("enable", "disable"):
            return await send_v2(ctx, error_view("Use `&level voice enable` or `&level voice disable`."))
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["voice_enabled"] = (action.lower() == "enable")
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Voice Leveling {action.capitalize()}d"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} Members will {'now' if gcfg['voice_enabled'] else 'no longer'} earn XP from voice channels.")
        ))
        await send_v2(ctx, view)

    # ─── LEVEL CHANNEL ───
    @level.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def lvl_channel(self, ctx, channel: discord.TextChannel):
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["channel"] = str(channel.id)
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Level-Up Channel Set"),
            make_separator(),
            text(f"{Emojis.CHANNEL} Level up messages will be sent to {channel.mention}")
        ))
        await send_v2(ctx, view)

    # ─── LEVEL MESSAGE ───
    @level.command(name="message")
    @commands.has_permissions(administrator=True)
    async def lvl_message(self, ctx, *, message: str = None):
        if not message:
            view = discord.ui.LayoutView()
            container = MatrixContainer(
                text(f"### {Emojis.PENCIL}  Level Up Message"),
                make_separator(),
                text(
                    f"Set a custom level-up message!\n\n"
                    f"**Usage:** `{Config.PREFIX}level message <message>`\n\n"
                    f"**Variables:**\n"
                    f"`{{user}}` - User mention\n"
                    f"`{{level}}` - New level\n"
                    f"`{{server}}` - Server name\n\n"
                    f"**Default:**\n{DEFAULT_MESSAGE}"
                )
            )
            view.add_item(container)
            return await send_v2(ctx, view)
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["message"] = message
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Level Up Message Updated"),
            make_separator(),
            text(f"{Emojis.ARROW} **New Message:**\n{message}")
        ))
        await send_v2(ctx, view)

    # ─── LEVEL XP ───
    @level.command(name="xp")
    @commands.has_permissions(administrator=True)
    async def lvl_xp(self, ctx, amount: int):
        if amount < 1 or amount > 500:
            return await send_v2(ctx, error_view("XP must be between 1-500."))
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["xp_per_msg"] = amount
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  XP Per Message Updated"),
            make_separator(),
            text(f"{Emojis.XP} Members will now earn `{amount}` XP per message.")
        ))
        await send_v2(ctx, view)

    # ─── LEVEL CARD ───
    @level.command(name="card")
    @commands.has_permissions(administrator=True)
    async def lvl_card(self, ctx, theme: str):
        if theme.lower() not in CARD_THEMES:
            return await send_v2(ctx, error_view("Use `default`, `1`, `2`, or `3`."))
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())
        gcfg["card"] = theme.lower()
        save_lvl(data)
        chosen = CARD_THEMES[theme.lower()]
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Rank Card Theme Updated"),
            make_separator(),
            text(f"{Emojis.ARROW} **Theme:** {chosen['name']}")
        ))
        await send_v2(ctx, view)

    # ─── LEVEL NOXP ───
    @level.command(name="noxp")
    @commands.has_permissions(administrator=True)
    async def lvl_noxp(self, ctx, channel: discord.TextChannel = None):
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.setdefault(gid, get_default_guild_cfg())

        if not channel:
            channels = gcfg.get("noxp_channels", [])
            lines = "\n".join([f"{Emojis.ARROW} <#{c}>" for c in channels]) or "None"
            view = discord.ui.LayoutView()
            container = MatrixContainer(
                text(f"### {Emojis.LEVEL}  No-XP Channels"),
                make_separator(),
                text(lines),
                make_separator(),
                text(f"-# Use `{Config.PREFIX}level noxp #channel` to toggle.")
            )
            view.add_item(container)
            return await send_v2(ctx, view)

        ch_id = str(channel.id)
        if ch_id in gcfg.get("noxp_channels", []):
            gcfg["noxp_channels"].remove(ch_id)
            action = "removed from"
        else:
            gcfg.setdefault("noxp_channels", []).append(ch_id)
            action = "added to"
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  {channel.mention} {action} no-XP list.")))
        await send_v2(ctx, view)

    # ─── LEVEL CONFIG ───
    @level.command(name="config")
    async def lvl_config(self, ctx):
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, get_default_guild_cfg())

        status = f"{Emojis.ON} Enabled" if gcfg.get("enabled") else f"{Emojis.OFF} Disabled"
        voice_status = f"{Emojis.ON} Enabled" if gcfg.get("voice_enabled") else f"{Emojis.OFF} Disabled"
        ch = f"<#{gcfg['channel']}>" if gcfg.get("channel") else "Not Set"
        noxp_count = len(gcfg.get("noxp_channels", []))
        card = CARD_THEMES.get(gcfg.get("card", "default"), CARD_THEMES["default"])["name"]

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SETTINGS}  Leveling Configuration"),
            make_separator(),
            text(
                f"{Emojis.LEVEL} **Status:** {status}\n"
                f"{Emojis.VOICE_MIC} **Voice XP:** {voice_status}\n"
                f"{Emojis.CHANNEL} **Level-Up Channel:** {ch}\n"
                f"{Emojis.XP} **XP per Message:** {gcfg.get('xp_per_msg', 20)}\n"
                f"{Emojis.RANK} **Card Theme:** {card}\n"
                f"{Emojis.ARROW} **No-XP Channels:** {noxp_count}\n"
                f"{Emojis.MEMBERS} **Tracked Users:** {len(gcfg.get('users', {}))}"
            ),
            make_separator(),
            text(f"{Emojis.PENCIL} **Level Up Message:**\n{gcfg.get('message', DEFAULT_MESSAGE)}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── LEVEL RESET ───
    @level.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def lvl_reset(self, ctx):
        data = load_lvl()
        data[str(ctx.guild.id)] = get_default_guild_cfg()
        save_lvl(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  All leveling data reset.")))
        await send_v2(ctx, view)

    # ─── LEADERBOARD ───
    @level.command(name="leaderboard", aliases=["lb", "top"])
    async def lvl_leaderboard(self, ctx):
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, get_default_guild_cfg())

        if not gcfg.get("enabled"):
            return await send_v2(ctx, error_view("The leveling system is disabled in this server."))

        users = gcfg.get("users", {})
        if not users:
            return await send_v2(ctx, error_view("No leveling data yet."))

        # Sort by level then xp
        sorted_users = sorted(
            users.items(),
            key=lambda x: (x[1].get("level", 0), x[1].get("xp", 0)),
            reverse=True
        )[:10]

        lines = []
        medals = [Emojis.GOLD, Emojis.SILVER, Emojis.BRONZE]
        for i, (uid, info) in enumerate(sorted_users):
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{medal} <@{uid}> — **Level {info.get('level',0)}** | `{info.get('xp',0)} XP`")

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.LEADERBOARD}  Server Leaderboard"),
            make_separator(),
            text("\n".join(lines)),
            make_separator(),
            text(f"-# Top {len(sorted_users)} members | Total tracked: {len(users)}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── RANK ───
    @commands.command(name="rank")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load_lvl()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid)

        if not gcfg or not gcfg.get("enabled"):
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(text(f"{Emojis.ERROR} | The leveling system is disabled in this server.")))
            return await send_v2(ctx, view)

        user_data = gcfg.get("users", {}).get(str(member.id), {"xp": 0, "level": 0})
        level = user_data.get("level", 0)
        xp = user_data.get("xp", 0)
        next_xp = xp_for_level(level)

        # Calculate rank position
        users = gcfg.get("users", {})
        sorted_users = sorted(
            users.items(),
            key=lambda x: (x[1].get("level", 0), x[1].get("xp", 0)),
            reverse=True
        )
        rank_pos = next((i+1 for i, (uid, _) in enumerate(sorted_users) if uid == str(member.id)), "N/A")

        # Progress bar
        progress = int((xp / next_xp) * 20) if next_xp > 0 else 0
        bar = "▓" * progress + "░" * (20 - progress)
        percent = int((xp / next_xp) * 100) if next_xp > 0 else 0

        theme = CARD_THEMES.get(gcfg.get("card", "default"), CARD_THEMES["default"])

        view = discord.ui.LayoutView()
        section = discord.ui.Section(
            text(f"### {Emojis.RANK}  Rank Card"),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.LEVEL} **Level:** {level}\n"
                f"{Emojis.LEADERBOARD} **Rank:** #{rank_pos}\n"
                f"{Emojis.XP} **XP:** {xp} / {next_xp}"
            ),
            accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
        )

        # Custom container with theme color
        from utils.components import MatrixContainer as MC
        container = discord.ui.Container(
            section,
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True),
            text(f"`{bar}` **{percent}%**"),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True),
            text(f"-# Theme: {theme['name']}"),
            accent_color=theme["color"]
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── MESSAGE LISTENER (XP) ───
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith(Config.PREFIX):
            return

        data = load_lvl()
        gid = str(message.guild.id)
        gcfg = data.get(gid)

        if not gcfg or not gcfg.get("enabled"):
            return

        # Skip no-xp channels
        if str(message.channel.id) in gcfg.get("noxp_channels", []):
            return

        uid = str(message.author.id)
        user = gcfg.setdefault("users", {}).setdefault(uid, {"xp": 0, "level": 0, "last_msg": 0})

        # Cooldown (60 seconds)
        now = time.time()
        if now - user.get("last_msg", 0) < 60:
            return

        # Add XP
        xp_gain = gcfg.get("xp_per_msg", 20)
        xp_gain = random.randint(int(xp_gain * 0.8), int(xp_gain * 1.2))
        user["xp"] += xp_gain
        user["last_msg"] = now

        # Check level up
        needed = xp_for_level(user["level"])
        if user["xp"] >= needed:
            user["xp"] -= needed
            user["level"] += 1
            save_lvl(data)

            # Send level up message
            template = gcfg.get("message", DEFAULT_MESSAGE)
            msg = template.replace("{user}", message.author.mention)\
                          .replace("{level}", str(user["level"]))\
                          .replace("{server}", message.guild.name)

            ch_id = gcfg.get("channel")
            channel = self.bot.get_channel(int(ch_id)) if ch_id else message.channel

            theme = CARD_THEMES.get(gcfg.get("card", "default"), CARD_THEMES["default"])

            view = discord.ui.LayoutView()
            section = discord.ui.Section(
                text(f"### {Emojis.LEVEL_UP}  Level Up!"),
                text(msg),
                accessory=discord.ui.Thumbnail(media=message.author.display_avatar.url)
            )
            container = discord.ui.Container(
                section,
                discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True),
                text(f"{Emojis.LEVEL} **New Level:** {user['level']}\n{Emojis.XP} **Total XP needed for next:** {xp_for_level(user['level'])}"),
                accent_color=theme["color"]
            )
            view.add_item(container)
            try:
                await channel.send(view=view)
            except:
                pass
        else:
            save_lvl(data)

    # ─── VOICE XP LISTENER ───
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        data = load_lvl()
        gid = str(member.guild.id)
        gcfg = data.get(gid)

        if not gcfg or not gcfg.get("voice_enabled"):
            return

        key = (gid, str(member.id))

        # Joined voice
        if before.channel is None and after.channel is not None:
            self.voice_join_times[key] = time.time()

        # Left voice
        elif before.channel is not None and after.channel is None:
            join_time = self.voice_join_times.pop(key, None)
            if not join_time:
                return
            elapsed = time.time() - join_time
            minutes = int(elapsed // 60)
            if minutes < 1:
                return

            uid = str(member.id)
            user = gcfg.setdefault("users", {}).setdefault(uid, {"xp": 0, "level": 0, "last_msg": 0})

            # Award 5 XP per minute in VC
            xp_gain = minutes * 5
            user["xp"] += xp_gain

            # Level check
            needed = xp_for_level(user["level"])
            leveled = False
            while user["xp"] >= needed:
                user["xp"] -= needed
                user["level"] += 1
                needed = xp_for_level(user["level"])
                leveled = True

            save_lvl(data)

            if leveled:
                ch_id = gcfg.get("channel")
                if ch_id:
                    channel = self.bot.get_channel(int(ch_id))
                    if channel:
                        template = gcfg.get("message", DEFAULT_MESSAGE)
                        msg = template.replace("{user}", member.mention)\
                                      .replace("{level}", str(user["level"]))\
                                      .replace("{server}", member.guild.name)

                        theme = CARD_THEMES.get(gcfg.get("card", "default"), CARD_THEMES["default"])
                        view = discord.ui.LayoutView()
                        container = discord.ui.Container(
                            text(f"### {Emojis.LEVEL_UP}  Voice Level Up!"),
                            discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True),
                            text(msg),
                            discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=True),
                            text(f"{Emojis.VOICE_MIC} **Earned from:** {minutes} minutes in voice"),
                            accent_color=theme["color"]
                        )
                        view.add_item(container)
                        try: await channel.send(view=view)
                        except: pass


async def setup(bot):
    await bot.add_cog(Leveling(bot))