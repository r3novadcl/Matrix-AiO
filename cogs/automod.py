import discord
from discord.ext import commands
import json, os, re, asyncio, time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from config import Config
from emojis import Emojis
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2
from utils.fastconfig import FastConfig

AUTOMOD_FILE = "automod.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "log_channel": None,
    "timeout_duration": 300,  # 5 minutes
    "modules": {
        "antispam": False,
        "anticaps": False,
        "smartlink": False,
        "antiinvite": False,
        "antimention": False,
        "antiemoji": False,
        "antitoken": False,
        "antibadwords": False,
        "antiownermention": False,
        "antiscam": False,
    },
    "punishments": {
        "antispam": "mute",
        "anticaps": "warn",
        "smartlink": "delete",
        "antiinvite": "mute",
        "antimention": "mute",
        "antiemoji": "delete",
        "antitoken": "ban",
        "antibadwords": "mute",
        "antiownermention": "mute",
        "antiscam": "ban",
    },
    "thresholds": {
        "spam_messages": 5,
        "spam_seconds": 5,
        "caps_percent": 70,
        "caps_minlen": 10,
        "mention_limit": 5,
        "emoji_limit": 10,
    },
    "whitelist": {
        "users": [],
        "roles": [],
        "channels": [],
    },
    "antilink": {
        "allow": [],
        "deny": [],
    },
    "badwords": ["badword1", "badword2"],
}

INVITE_REGEX = re.compile(r"(discord\.(gg|io|me|li)|discordapp\.com/invite|discord\.com/invite)/\S+", re.IGNORECASE)
LINK_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)
TOKEN_REGEX = re.compile(r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27,}")
SCAM_REGEX = re.compile(r"(free\s*nitro|steam\s*gift|nitro\s*gift|@everyone\s*free)", re.IGNORECASE)


# In-memory cached store — no disk read/write on the hot path anymore.
_store = FastConfig(AUTOMOD_FILE, lambda: json.loads(json.dumps(DEFAULT_CONFIG)))


def get_guild_config(guild_id):
    return _store.get(guild_id)


def update_guild_config(guild_id, config):
    _store.set(guild_id, config)


MODULE_NAMES = {
    "antispam": "Anti spam",
    "anticaps": "Anti caps",
    "smartlink": "Smart link",
    "antiinvite": "Anti invite-links",
    "antimention": "Anti mass mention",
    "antiemoji": "Anti emoji spam",
    "antitoken": "Anti Token Spam",
    "antibadwords": "Anti bad words",
    "antiownermention": "Anti owner mention",
    "antiscam": "Anti scam-promo",
}


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = defaultdict(lambda: deque(maxlen=20))
        self.punishment_lock = defaultdict(asyncio.Lock)

    # ═══════════════════════════════════════════════
    #  HELPER: Punish User
    # ═══════════════════════════════════════════════
    async def punish(self, message, module, reason):
        config = get_guild_config(message.guild.id)
        punishment = config["punishments"].get(module, "warn")
        duration = config.get("timeout_duration", 300)

        member = message.author
        if not isinstance(member, discord.Member):
            asyncio.create_task(self._safe_delete(message))
            return

        try:
            if punishment == "mute":
                until = discord.utils.utcnow() + timedelta(seconds=duration)
                await member.timeout(until, reason=f"AutoMod: {reason}")
            elif punishment == "kick":
                await member.kick(reason=f"AutoMod: {reason}")
            elif punishment == "ban":
                await member.ban(reason=f"AutoMod: {reason}", delete_message_seconds=86400)
            elif punishment == "warn":
                pass
        except discord.Forbidden:
            asyncio.create_task(self._safe_delete(message))
            return await self.log_action(message.guild, member, module, reason, "FAILED - No permission")
        except Exception as e:
            print(f"AutoMod punish error: {e}")
            asyncio.create_task(self._safe_delete(message))
            return await self.log_action(message.guild, member, module, reason, f"FAILED - {e}")

        # Message cleanup runs in the background — never delays the punishment itself.
        asyncio.create_task(self._safe_delete(message))
        await self.log_action(message.guild, member, module, reason, punishment)

    async def _safe_delete(self, message):
        try:
            await message.delete()
        except:
            pass

    async def log_action(self, guild, member, module, reason, punishment):
        config = get_guild_config(guild.id)
        log_ch_id = config.get("log_channel")
        if not log_ch_id:
            return
        ch = guild.get_channel(log_ch_id)
        if not ch:
            return
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.LOG_AUTOMOD}  AutoMod Action"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention} (`{member.id}`)\n"
                f"{Emojis.AUTOMOD} **Module:** `{MODULE_NAMES.get(module, module)}`\n"
                f"{Emojis.WARNING} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Punishment:** `{punishment.upper()}`"
            ),
            make_separator(),
            text(f"-# {Config.FOOTER_TEXT}")
        )
        view.add_item(container)
        try:
            await ch.send(view=view)
        except:
            pass

    # ═══════════════════════════════════════════════
    #  MAIN LISTENER (Fast Detection)
    # ═══════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.author.id == message.guild.owner_id:
            return
        if isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator:
            return

        config = get_guild_config(message.guild.id)
        if not config["enabled"]:
            return

        # Whitelist check
        wl = config["whitelist"]
        if message.author.id in wl["users"]:
            return
        if message.channel.id in wl["channels"]:
            return
        if any(r.id in wl["roles"] for r in message.author.roles):
            return

        modules = config["modules"]
        content = message.content
        lower = content.lower()

        # ─── Anti Token Spam ───
        if modules.get("antitoken") and TOKEN_REGEX.search(content):
            return await self.punish(message, "antitoken", "Posted a Discord token")

        # ─── Anti Scam ───
        if modules.get("antiscam") and SCAM_REGEX.search(content):
            return await self.punish(message, "antiscam", "Scam/Promo detected")

        # ─── Anti Invite ───
        if modules.get("antiinvite") and INVITE_REGEX.search(content):
            return await self.punish(message, "antiinvite", "Posted invite link")

        # ─── Smart Link ───
        if modules.get("smartlink"):
            links = LINK_REGEX.findall(content)
            if links:
                allow = config["antilink"]["allow"]
                deny = config["antilink"]["deny"]
                for link in links:
                    if deny and any(d in link for d in deny):
                        return await self.punish(message, "smartlink", "Blocked link")
                    if allow and not any(a in link for a in allow):
                        return await self.punish(message, "smartlink", "Non-whitelisted link")

        # ─── Anti Mass Mention ───
        if modules.get("antimention"):
            limit = config["thresholds"]["mention_limit"]
            mentions = len(message.mentions) + len(message.role_mentions)
            if mentions >= limit:
                return await self.punish(message, "antimention", f"Mass mention ({mentions})")

        # ─── Anti Owner Mention ───
        if modules.get("antiownermention"):
            owner_id = message.guild.owner_id
            if any(u.id == owner_id for u in message.mentions):
                return await self.punish(message, "antiownermention", "Mentioned server owner")

        # ─── Anti Emoji Spam ───
        if modules.get("antiemoji"):
            limit = config["thresholds"]["emoji_limit"]
            emoji_count = len(re.findall(r"<a?:\w+:\d+>", content)) + sum(1 for c in content if ord(c) > 10000)
            if emoji_count >= limit:
                return await self.punish(message, "antiemoji", f"Emoji spam ({emoji_count})")

        # ─── Anti Caps ───
        if modules.get("anticaps"):
            minlen = config["thresholds"]["caps_minlen"]
            percent = config["thresholds"]["caps_percent"]
            if len(content) >= minlen:
                letters = [c for c in content if c.isalpha()]
                if letters:
                    caps_pct = sum(1 for c in letters if c.isupper()) / len(letters) * 100
                    if caps_pct >= percent:
                        return await self.punish(message, "anticaps", f"Excessive caps ({int(caps_pct)}%)")

        # ─── Anti Bad Words ───
        if modules.get("antibadwords"):
            for word in config.get("badwords", []):
                if word.lower() in lower:
                    return await self.punish(message, "antibadwords", f"Bad word: {word}")

        # ─── Anti Spam (rate based) ───
        if modules.get("antispam"):
            tracker = self.spam_tracker[(message.guild.id, message.author.id)]
            now = time.time()
            tracker.append(now)
            window = config["thresholds"]["spam_seconds"]
            limit = config["thresholds"]["spam_messages"]
            recent = [t for t in tracker if now - t <= window]
            if len(recent) >= limit:
                tracker.clear()
                return await self.punish(message, "antispam", f"Spamming ({len(recent)} msgs/{window}s)")

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod (Help)
    # ═══════════════════════════════════════════════
    @commands.group(name="automod", invoke_without_command=True)
    async def automod(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"## {Config.BOT_NAME} AutoMod System Help"),
            text(
                f"Welcome to the **{Config.BOT_NAME} AutoMod System**. Automod helps keep your "
                f"server clean by automatically detecting and punishing spam, links, invites, bad "
                f"words, and excessive mentions."
            ),
            make_separator(),
            text(f"{Emojis.LIST} **Subcommands List**"),
            text(
                f"• `&automod setup` › Opens the interactive AutoMod configuration dashboard.\n"
                f"• `&automod enable` › Wizard to quickly enable AutoMod features.\n"
                f"• `&automod disable` › Disables the entire AutoMod system.\n"
                f"• `&automod status` › Displays the current configuration status of all modules.\n"
                f"• `&automod log <channel>` › Sets the logging channel for AutoMod violations.\n"
                f"• `&automod timeout <duration>` › Sets default timeout punishment duration (e.g. 5m, 1h).\n"
                f"• `&automod whitelist <add/remove/list> <user/role/channel>` › Manages the bypass whitelist.\n"
                f"• `&automod punishment <module> <mute/kick/ban/warn>` › Sets punishment for a module.\n"
                f"• `&automod threshold <module> <limit>` › Sets limit thresholds (spam rate, emoji count, etc.).\n"
                f"• `&automod antilink <allow/deny/list>` › Manages domain whitelists for links."
            ),
            make_separator(),
            text(f"-# © {Config.FOOTER_TEXT}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod setup
    # ═══════════════════════════════════════════════
    @automod.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def automod_setup(self, ctx):
        config = get_guild_config(ctx.guild.id)
        await self._send_setup_dashboard(ctx, config)

    async def _send_setup_dashboard(self, ctx_or_inter, config, edit=False):
        status_emoji = Emojis.SUCCESS if config["enabled"] else Emojis.ERROR
        status_text = "Enabled" if config["enabled"] else "Disabled"
        log_emoji = Emojis.SUCCESS if config["log_channel"] else Emojis.ERROR
        log_text = f"<#{config['log_channel']}>" if config["log_channel"] else "Not Configured"
        timeout = config["timeout_duration"] // 60

        select = discord.ui.Select(
            placeholder="Select a category to configure...",
            options=[
                discord.SelectOption(label="General Settings", value="general",
                                     description="Toggle AutoMod, set logs channel & timeout duration"),
                discord.SelectOption(label="Toggle Modules", value="modules",
                                     description="Enable or disable specific protection filters"),
                discord.SelectOption(label="Configure Punishments", value="punishments",
                                     description="Set penalty action for each violation"),
                discord.SelectOption(label="Thresholds & Limits", value="thresholds",
                                     description="Adjust message, emoji, spam, & caps sensitivity"),
                discord.SelectOption(label="Manage Whitelist", value="whitelist",
                                     description="Bypass settings for channels, roles, or users"),
            ]
        )

        async def select_cb(interaction: discord.Interaction):
            choice = select.values[0]
            if choice == "general":
                await self._send_general_settings(interaction, config)
            elif choice == "modules":
                await self._send_modules_panel(interaction, config)
            elif choice == "punishments":
                await self._send_punishments_panel(interaction, config)
            elif choice == "thresholds":
                await self._send_thresholds_panel(interaction, config)
            elif choice == "whitelist":
                await self._send_whitelist_panel(interaction, config)

        select.callback = select_cb

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.ANTINUKE}  AutoMod Configuration Dashboard"),
            text(
                f"Welcome to the interactive AutoMod setup menu! "
                f"Choose a configuration category from the select "
                f"menu below to easily configure logs, punishments, "
                f"thresholds, modules, and whitelists."
            ),
            make_separator(),
            text(
                f"**System Status**\n{status_emoji} {status_text}\n"
                f"**Log Channel**\n{log_emoji} {log_text}\n"
                f"**Timeout Duration**\n{timeout} minutes"
            ),
            make_separator(),
            text(f"-# Server: {ctx_or_inter.guild.name} | Prefix: `{Config.PREFIX}`"),
            discord.ui.ActionRow(select)
        )
        view.add_item(container)
        if edit:
            await ctx_or_inter.response.edit_message(view=view)
        else:
            await send_v2(ctx_or_inter, view)

    async def _send_general_settings(self, interaction, config):
        status_emoji = Emojis.SUCCESS if config["enabled"] else Emojis.ERROR
        status_text = "Enabled" if config["enabled"] else "Disabled"
        log_emoji = Emojis.SUCCESS if config["log_channel"] else Emojis.ERROR
        log_text = f"<#{config['log_channel']}>" if config["log_channel"] else "None"
        timeout = config["timeout_duration"] // 60

        enable_btn = discord.ui.Button(
            label=f"{'Disable' if config['enabled'] else 'Enable'} AutoMod",
            style=discord.ButtonStyle.success if not config["enabled"] else discord.ButtonStyle.danger
        )
        log_btn = discord.ui.Button(label="Setup Logs Channel", style=discord.ButtonStyle.primary)
        timeout_btn = discord.ui.Button(label="Set Timeout Duration", style=discord.ButtonStyle.secondary)
        back_btn = discord.ui.Button(label="Back to Menu", style=discord.ButtonStyle.secondary)

        async def enable_cb(i: discord.Interaction):
            config["enabled"] = not config["enabled"]
            update_guild_config(i.guild.id, config)
            await self._send_general_settings(i, config)

        async def log_cb(i: discord.Interaction):
            modal = discord.ui.Modal(title="Setup Logs Channel")
            ch_input = discord.ui.TextInput(label="Channel ID or Name", required=True)
            modal.add_item(ch_input)

            async def modal_sub(mi: discord.Interaction):
                val = ch_input.value.strip().replace("<#", "").replace(">", "")
                ch = None
                if val.isdigit():
                    ch = mi.guild.get_channel(int(val))
                else:
                    ch = discord.utils.get(mi.guild.text_channels, name=val)
                if not ch:
                    return await mi.response.send_message("Channel not found.", ephemeral=True)
                config["log_channel"] = ch.id
                update_guild_config(mi.guild.id, config)
                await mi.response.defer()
                await self._send_general_settings(i, config)

            modal.on_submit = modal_sub
            await i.response.send_modal(modal)

        async def timeout_cb(i: discord.Interaction):
            modal = discord.ui.Modal(title="Set Timeout Duration")
            dur_input = discord.ui.TextInput(label="Duration in minutes", required=True, default="5")
            modal.add_item(dur_input)

            async def modal_sub(mi: discord.Interaction):
                try:
                    mins = int(dur_input.value)
                    config["timeout_duration"] = mins * 60
                    update_guild_config(mi.guild.id, config)
                    await mi.response.defer()
                    await self._send_general_settings(i, config)
                except:
                    await mi.response.send_message("Invalid input.", ephemeral=True)

            modal.on_submit = modal_sub
            await i.response.send_modal(modal)

        async def back_cb(i: discord.Interaction):
            await self._send_setup_dashboard(i, config, edit=True)

        enable_btn.callback = enable_cb
        log_btn.callback = log_cb
        timeout_btn.callback = timeout_cb
        back_btn.callback = back_cb

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.ANTINUKE}  AutoMod - General Settings"),
            text("Configure base settings for the AutoMod system:"),
            make_separator(),
            text(
                f"**Status**\n{status_emoji} {status_text}\n"
                f"**Logging**\n{log_emoji} {log_text}\n"
                f"**Timeout Duration**\n{timeout} mins"
            ),
            make_separator(),
            text(f"-# Requested by {interaction.user.name}"),
            discord.ui.ActionRow(enable_btn, log_btn),
            discord.ui.ActionRow(timeout_btn, back_btn)
        )
        view.add_item(container)
        await interaction.response.edit_message(view=view)

    async def _send_modules_panel(self, interaction, config):
        modules = config["modules"]
        lines = []
        for key, name in MODULE_NAMES.items():
            emoji = Emojis.SUCCESS if modules.get(key) else Emojis.ERROR
            lines.append(f"{emoji} : {name}")
        body = "\n".join(lines)

        options = [
            discord.SelectOption(label=name, value=key,
                                 description=f"Currently: {'ON' if modules.get(key) else 'OFF'}")
            for key, name in MODULE_NAMES.items()
        ]
        select = discord.ui.Select(placeholder="Select events to enable", options=options, max_values=len(options))

        async def select_cb(i: discord.Interaction):
            for v in select.values:
                config["modules"][v] = not config["modules"].get(v, False)
            update_guild_config(i.guild.id, config)
            await self._send_modules_panel(i, config)

        select.callback = select_cb

        enable_all = discord.ui.Button(label="Enable for All Events", style=discord.ButtonStyle.primary)
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)

        async def enable_all_cb(i: discord.Interaction):
            for k in MODULE_NAMES:
                config["modules"][k] = True
            update_guild_config(i.guild.id, config)
            await self._send_modules_panel(i, config)

        async def cancel_cb(i: discord.Interaction):
            await self._send_setup_dashboard(i, config, edit=True)

        enable_all.callback = enable_all_cb
        cancel.callback = cancel_cb

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}  {interaction.guild.name}'s server's Automod Setup"),
            make_separator(),
            text(body),
            make_separator(),
            text(f"-# Requested by {interaction.user.name}"),
            discord.ui.ActionRow(select),
            discord.ui.ActionRow(enable_all, cancel)
        )
        view.add_item(container)
        await interaction.response.edit_message(view=view)

    async def _send_punishments_panel(self, interaction, config):
        lines = [f"`{name}` → `{config['punishments'].get(key, 'warn').upper()}`"
                 for key, name in MODULE_NAMES.items()]
        back = discord.ui.Button(label="Back to Menu", style=discord.ButtonStyle.secondary)

        async def back_cb(i: discord.Interaction):
            await self._send_setup_dashboard(i, config, edit=True)

        back.callback = back_cb
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.MOD}  Configure Punishments"),
            text("Use `&automod punishment <module> <mute/kick/ban/warn>` to change."),
            make_separator(),
            text("\n".join(lines)),
            discord.ui.ActionRow(back)
        )
        view.add_item(container)
        await interaction.response.edit_message(view=view)

    async def _send_thresholds_panel(self, interaction, config):
        t = config["thresholds"]
        body = (
            f"**Spam Messages:** `{t['spam_messages']}` per `{t['spam_seconds']}s`\n"
            f"**Caps Percent:** `{t['caps_percent']}%` (min length `{t['caps_minlen']}`)\n"
            f"**Mention Limit:** `{t['mention_limit']}`\n"
            f"**Emoji Limit:** `{t['emoji_limit']}`"
        )
        back = discord.ui.Button(label="Back to Menu", style=discord.ButtonStyle.secondary)

        async def back_cb(i: discord.Interaction):
            await self._send_setup_dashboard(i, config, edit=True)

        back.callback = back_cb
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SETTINGS}  Thresholds & Limits"),
            text("Use `&automod threshold <module> <limit>` to change."),
            make_separator(),
            text(body),
            discord.ui.ActionRow(back)
        )
        view.add_item(container)
        await interaction.response.edit_message(view=view)

    async def _send_whitelist_panel(self, interaction, config):
        wl = config["whitelist"]
        body = (
            f"**Users:** {len(wl['users'])}\n"
            f"**Roles:** {len(wl['roles'])}\n"
            f"**Channels:** {len(wl['channels'])}"
        )
        back = discord.ui.Button(label="Back to Menu", style=discord.ButtonStyle.secondary)

        async def back_cb(i: discord.Interaction):
            await self._send_setup_dashboard(i, config, edit=True)

        back.callback = back_cb
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SHIELD}  Manage Whitelist"),
            text("Use `&automod whitelist add/remove user|role|channel <id>` to manage."),
            make_separator(),
            text(body),
            discord.ui.ActionRow(back)
        )
        view.add_item(container)
        await interaction.response.edit_message(view=view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod enable
    # ═══════════════════════════════════════════════
    @automod.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def automod_enable(self, ctx):
        config = get_guild_config(ctx.guild.id)

        lines = [f"{Emojis.ERROR} : {name}" for key, name in MODULE_NAMES.items()]
        body = "\n".join(lines)

        options = [
            discord.SelectOption(label=name, value=key)
            for key, name in MODULE_NAMES.items()
        ]
        select = discord.ui.Select(
            placeholder="Select events to enable",
            options=options,
            max_values=len(options),
            min_values=1
        )

        enable_all = discord.ui.Button(label="Enable for All Events", style=discord.ButtonStyle.primary)
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)

        async def select_cb(i: discord.Interaction):
            for v in select.values:
                config["modules"][v] = True
            config["enabled"] = True
            update_guild_config(i.guild.id, config)
            await self._send_enabled_status(i, config, all_enabled=False)

        async def all_cb(i: discord.Interaction):
            for k in MODULE_NAMES:
                config["modules"][k] = True
            config["enabled"] = True
            update_guild_config(i.guild.id, config)
            await self._send_enabled_status(i, config, all_enabled=True)

        async def cancel_cb(i: discord.Interaction):
            await i.message.delete()

        select.callback = select_cb
        enable_all.callback = all_cb
        cancel.callback = cancel_cb

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}  {ctx.guild.name}'s server's Automod Setup"),
            make_separator(),
            text(body),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}"),
            discord.ui.ActionRow(select),
            discord.ui.ActionRow(enable_all, cancel)
        )
        view.add_item(container)
        await send_v2(ctx, view)

    async def _send_enabled_status(self, interaction, config, all_enabled=False):
        lines = []
        for key, name in MODULE_NAMES.items():
            emoji = Emojis.SUCCESS if config["modules"].get(key) else Emojis.ERROR
            lines.append(f"{emoji} : {name}")
        body = "\n".join(lines)
        footer = "All modules enabled successfully!" if all_enabled else "Selected modules enabled successfully!"

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}  {interaction.guild.name}'s server's Automod Setup"),
            make_separator(),
            text(body),
            make_separator(),
            text(f"-# Requested by {interaction.user.name} | {footer}")
        )
        view.add_item(container)
        await interaction.response.edit_message(view=view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod disable
    # ═══════════════════════════════════════════════
    @automod.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def automod_disable(self, ctx):
        config = get_guild_config(ctx.guild.id)
        config["enabled"] = False
        for k in config["modules"]:
            config["modules"][k] = False
        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   AutoMod system disabled"),
            make_separator(),
            text(f"All modules have been turned off.")
        ))
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod status
    # ═══════════════════════════════════════════════
    @automod.command(name="status")
    async def automod_status(self, ctx):
        config = get_guild_config(ctx.guild.id)
        status = "ENABLED" if config["enabled"] else "DISABLED"
        active = sum(1 for v in config["modules"].values() if v)
        total = len(config["modules"])
        lines = [f"{Emojis.SUCCESS if v else Emojis.ERROR} {MODULE_NAMES[k]}"
                 for k, v in config["modules"].items()]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.AUTOMOD}  AutoMod Status"),
            make_separator(),
            text(f"**System:** `{status}`\n**Active Modules:** `{active}/{total}`"),
            make_separator(),
            text("\n".join(lines))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod log <channel>
    # ═══════════════════════════════════════════════
    @automod.command(name="log")
    @commands.has_permissions(administrator=True)
    async def automod_log(self, ctx, channel: discord.TextChannel):
        config = get_guild_config(ctx.guild.id)
        config["log_channel"] = channel.id
        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Log Channel Set"),
            make_separator(),
            text(f"{Emojis.CHANNEL} **Channel:** {channel.mention}")
        ))
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod timeout <duration>
    # ═══════════════════════════════════════════════
    @automod.command(name="timeout")
    @commands.has_permissions(administrator=True)
    async def automod_timeout(self, ctx, duration: str):
        seconds = self._parse_duration(duration)
        if not seconds:
            return await send_v2(ctx, error_view("Invalid duration. Use `5m`, `1h`, etc."))
        config = get_guild_config(ctx.guild.id)
        config["timeout_duration"] = seconds
        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Timeout duration set to `{duration}`")
        ))
        await send_v2(ctx, view)

    def _parse_duration(self, s):
        try:
            unit = s[-1].lower()
            val = int(s[:-1])
            return {"s": val, "m": val * 60, "h": val * 3600, "d": val * 86400}.get(unit)
        except:
            return None

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod whitelist
    # ═══════════════════════════════════════════════
    @automod.command(name="whitelist")
    @commands.has_permissions(administrator=True)
    async def automod_whitelist(self, ctx, action: str = None, target: str = None, *, value: str = None):
        config = get_guild_config(ctx.guild.id)
        if not action:
            return await send_v2(ctx, error_view("Usage: `&automod whitelist add/remove/list user/role/channel <id>`"))

        if action == "list":
            wl = config["whitelist"]
            body = (
                f"**Users:** {', '.join(f'<@{u}>' for u in wl['users']) or 'None'}\n"
                f"**Roles:** {', '.join(f'<@&{r}>' for r in wl['roles']) or 'None'}\n"
                f"**Channels:** {', '.join(f'<#{c}>' for c in wl['channels']) or 'None'}"
            )
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(
                text(f"### {Emojis.SHIELD}  Whitelist"),
                make_separator(),
                text(body)
            ))
            return await send_v2(ctx, view)

        if action not in ("add", "remove") or target not in ("user", "role", "channel") or not value:
            return await send_v2(ctx, error_view("Usage: `&automod whitelist add/remove user/role/channel <id>`"))

        key = f"{target}s"
        try:
            tid = int(value.replace("<@", "").replace("<@&", "").replace("<#", "").replace(">", "").replace("!", ""))
        except:
            return await send_v2(ctx, error_view("Invalid ID."))

        if action == "add" and tid not in config["whitelist"][key]:
            config["whitelist"][key].append(tid)
        elif action == "remove" and tid in config["whitelist"][key]:
            config["whitelist"][key].remove(tid)

        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Whitelist updated"),
            make_separator(),
            text(f"`{action.title()}ed` {target} `{tid}`")
        ))
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod punishment
    # ═══════════════════════════════════════════════
    @automod.command(name="punishment")
    @commands.has_permissions(administrator=True)
    async def automod_punishment(self, ctx, module: str, action: str):
        if module not in MODULE_NAMES:
            return await send_v2(ctx, error_view(f"Invalid module. Choose from: {', '.join(MODULE_NAMES.keys())}"))
        if action not in ("mute", "kick", "ban", "warn", "delete"):
            return await send_v2(ctx, error_view("Action must be: mute / kick / ban / warn / delete"))
        config = get_guild_config(ctx.guild.id)
        config["punishments"][module] = action
        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Punishment Updated"),
            make_separator(),
            text(f"**Module:** `{MODULE_NAMES[module]}`\n**Action:** `{action.upper()}`")
        ))
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod threshold
    # ═══════════════════════════════════════════════
    @automod.command(name="threshold")
    @commands.has_permissions(administrator=True)
    async def automod_threshold(self, ctx, key: str, value: int):
        config = get_guild_config(ctx.guild.id)
        if key not in config["thresholds"]:
            return await send_v2(ctx, error_view(f"Invalid key. Choose from: {', '.join(config['thresholds'].keys())}"))
        config["thresholds"][key] = value
        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Threshold Updated"),
            make_separator(),
            text(f"**{key}** = `{value}`")
        ))
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &automod antilink
    # ═══════════════════════════════════════════════
    @automod.command(name="antilink")
    @commands.has_permissions(administrator=True)
    async def automod_antilink(self, ctx, action: str, *, domain: str = None):
        config = get_guild_config(ctx.guild.id)
        if action == "list":
            body = (
                f"**Allowed:** {', '.join(config['antilink']['allow']) or 'None'}\n"
                f"**Denied:** {', '.join(config['antilink']['deny']) or 'None'}"
            )
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(
                text(f"### {Emojis.LINK}  AntiLink Config"),
                make_separator(),
                text(body)
            ))
            return await send_v2(ctx, view)
        if not domain:
            return await send_v2(ctx, error_view("Provide a domain."))
        if action == "allow":
            config["antilink"]["allow"].append(domain)
        elif action == "deny":
            config["antilink"]["deny"].append(domain)
        else:
            return await send_v2(ctx, error_view("Use: allow / deny / list"))
        update_guild_config(ctx.guild.id, config)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   AntiLink Updated"),
            make_separator(),
            text(f"`{action}` → `{domain}`")
        ))
        await send_v2(ctx, view)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))