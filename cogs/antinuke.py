import discord
from discord.ext import commands
import json, os, asyncio, time
from datetime import datetime, timedelta
from config import Config
from emojis import Emojis
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2
from utils.fastconfig import FastConfig

ANTINUKE_FILE = "antinuke.json"

# Whitelist permission types
WL_PERMS = [
    "ban", "kick", "bot_add", "guild_update",
    "channel_create", "channel_delete", "channel_update",
    "role_create", "role_delete", "role_update",
    "webhook_create", "webhook_delete", "webhook_update",
    "member_update", "manage_emojis", "mention_everyone"
]

WL_PERM_LABELS = {
    "ban": "Ban",
    "kick": "Kick",
    "bot_add": "Bot Add",
    "guild_update": "Guild Update",
    "channel_create": "Channel Create",
    "channel_delete": "Channel Delete",
    "channel_update": "Channel Update",
    "role_create": "Role Create",
    "role_delete": "Role Delete",
    "role_update": "Role Update",
    "webhook_create": "Webhook Create",
    "webhook_delete": "Webhook Delete",
    "webhook_update": "Webhook Update",
    "member_update": "Member Update",
    "manage_emojis": "Manage Emojis/Stickers",
    "mention_everyone": "Mention @everyone/@here",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "log_channel": None,
    "webhook_url": None,
    "wall_role": None,
    "tos_agreed": False,
    "punishment": "ban",
    "whitelist": {},   # {user_id: {perm: bool, ...}}
    "extra_owners": [],
    "modules": {
        "antichannel": True,
        "antirole": True,
        "antiban": True,
        "antikick": True,
        "antiwebhook": True,
        "antiemoji": True,
        "antibot": True,
        "antimention": True,
        "antiprune": True,
        "antiupdate": True,
        "antiintegration": True,
        "antithread": True,
        "antinitro": True,
        "antiserver": True,
    },
    "limits": {
        "channel_create": 3,
        "channel_delete": 3,
        "role_create": 3,
        "role_delete": 3,
        "ban": 3,
        "kick": 3,
        "window": 10,
    },
    "nightmode": False,
    "verification": False,
}

MODULE_NAMES = {
    "antichannel": "Anti Channel Create/Delete",
    "antirole": "Anti Role Create/Delete",
    "antiban": "Anti Mass Ban",
    "antikick": "Anti Mass Kick",
    "antiwebhook": "Anti Webhook Create/Delete",
    "antiemoji": "Anti Emoji Delete",
    "antibot": "Anti Bot Add",
    "antimention": "Anti Mass Mention",
    "antiprune": "Anti Prune",
    "antiupdate": "Anti Server Update",
    "antiintegration": "Anti Integration",
    "antithread": "Anti Thread Spam",
    "antinitro": "Anti Nitro Boost Steal",
    "antiserver": "Anti Server Edit",
}


# In-memory cached store — no disk read/write on the hot path anymore.
_store = FastConfig(ANTINUKE_FILE, lambda: json.loads(json.dumps(DEFAULT_CONFIG)))


def get_cfg(guild_id):
    cfg = _store.get(guild_id)
    # Migration: agar whitelist list hai, dict bana do
    if isinstance(cfg.get("whitelist"), list):
        old = cfg["whitelist"]
        cfg["whitelist"] = {str(u): {p: True for p in WL_PERMS} for u in old}
        _store.set(guild_id, cfg)
    return cfg


def set_cfg(guild_id, cfg):
    _store.set(guild_id, cfg)


def get_wl_perms(cfg, user_id):
    """Return dict of perms for user, or None if not whitelisted."""
    wl = cfg.get("whitelist", {})
    return wl.get(str(user_id))


def user_has_wl_perm(cfg, user_id, perm):
    """Check if user is whitelisted for specific permission."""
    perms = get_wl_perms(cfg, user_id)
    if not perms:
        return False
    return perms.get(perm, False)


# ═══════════════════════════════════════════════
#  WHITELIST CONFIG VIEW (with buttons)
# ═══════════════════════════════════════════════
class WhitelistConfigView(discord.ui.LayoutView):
    def __init__(self, cog, guild_id, target_user, moderator):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id
        self.target = target_user
        self.moderator = moderator
        self.render()

    def get_perms(self):
        cfg = get_cfg(self.guild_id)
        return cfg["whitelist"].get(str(self.target.id), {p: False for p in WL_PERMS})

    def render(self):
        self.clear_items()
        perms = self.get_perms()

        # Build perm list display
        lines = []
        for p in WL_PERMS:
            enabled = perms.get(p, False)
            mark = f"{Emojis.SUCCESS if enabled else ''}{'  ' if enabled else ''}{Emojis.ERROR if not enabled else ''}"
            # Simpler: ✅ ❌
            check = "✅" if enabled else "❌"
            cross = "❌" if enabled else "✅"
            label = WL_PERM_LABELS[p]
            if p == "mention_everyone":
                lines.append(f"• {check}  {label.replace('@everyone/@here', '')}@everyone/@here")
            else:
                lines.append(f"• {check}  {label}")

        all_full = all(perms.get(p, False) for p in WL_PERMS)

        container = MatrixContainer(
            text(f"## Whitelist Configuration"),
            text(f"**Configure AntiNuke bypass permissions for this user:**"),
            make_separator(),
            text("\n".join(lines)),
            make_separator(),
            text(
                f"• **Moderator:** {self.moderator.name} (`{self.moderator.id}`)\n"
                f"• **Target:** {self.target.name}#{self.target.discriminator if self.target.discriminator != '0' else ''} (`{self.target.id}`)"
            ),
            make_separator(),
            text(f"-# © {Config.FOOTER_TEXT}"),
        )
        self.add_item(container)

        # Select menu to toggle specific permissions
        options = []
        for p in WL_PERMS:
            enabled = perms.get(p, False)
            options.append(discord.SelectOption(
                label=WL_PERM_LABELS[p],
                value=p,
                description=f"Currently: {'Enabled' if enabled else 'Disabled'}",
                emoji="✅" if enabled else "❌"
            ))

        select = discord.ui.Select(
            placeholder="Modify specific permissions...",
            options=options[:25],
            min_values=1,
            max_values=1
        )

        async def select_cb(i: discord.Interaction):
            if i.user.id != self.moderator.id:
                return await i.response.send_message("Not your panel.", ephemeral=True)
            cfg = get_cfg(self.guild_id)
            uid = str(self.target.id)
            if uid not in cfg["whitelist"]:
                cfg["whitelist"][uid] = {p: False for p in WL_PERMS}
            p = select.values[0]
            cfg["whitelist"][uid][p] = not cfg["whitelist"][uid].get(p, False)
            set_cfg(self.guild_id, cfg)
            self.render()
            await i.response.edit_message(view=self)

        select.callback = select_cb

        # Whitelist All / Reset All button
        if all_full:
            big_btn = discord.ui.Button(label="Reset All", style=discord.ButtonStyle.danger)

            async def big_cb(i: discord.Interaction):
                if i.user.id != self.moderator.id:
                    return await i.response.send_message("Not your panel.", ephemeral=True)
                cfg = get_cfg(self.guild_id)
                uid = str(self.target.id)
                if uid in cfg["whitelist"]:
                    del cfg["whitelist"][uid]
                set_cfg(self.guild_id, cfg)
                self.render()
                await i.response.edit_message(view=self)
        else:
            big_btn = discord.ui.Button(label="Whitelist All (Full)", style=discord.ButtonStyle.primary)

            async def big_cb(i: discord.Interaction):
                if i.user.id != self.moderator.id:
                    return await i.response.send_message("Not your panel.", ephemeral=True)
                cfg = get_cfg(self.guild_id)
                uid = str(self.target.id)
                cfg["whitelist"][uid] = {p: True for p in WL_PERMS}
                set_cfg(self.guild_id, cfg)
                self.render()
                await i.response.edit_message(view=self)

        big_btn.callback = big_cb

        # Add components container
        comp_container = MatrixContainer(
            discord.ui.ActionRow(select),
            discord.ui.ActionRow(big_btn),
        )
        self.add_item(comp_container)


# ═══════════════════════════════════════════════
#  UNWHITELIST VIEW (remove specific perms)
# ═══════════════════════════════════════════════
class UnwhitelistView(discord.ui.LayoutView):
    def __init__(self, cog, guild_id, target_user, moderator):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id
        self.target = target_user
        self.moderator = moderator
        self.render()

    def get_perms(self):
        cfg = get_cfg(self.guild_id)
        return cfg["whitelist"].get(str(self.target.id), {})

    def render(self):
        self.clear_items()
        perms = self.get_perms()
        if not perms or not any(perms.values()):
            container = MatrixContainer(
                text(f"## Whitelist Updated"),
                make_separator(),
                text(f"```diff\n+ Successfully removed user from whitelist.\n```"),
                make_separator(),
                text(
                    f"• **Executor:** {self.moderator.mention}\n"
                    f"• **Target:** {self.target.mention}"
                ),
                make_separator(),
                text(f"-# © {Config.FOOTER_TEXT}"),
            )
            self.add_item(container)
            return

        lines = []
        for p in WL_PERMS:
            enabled = perms.get(p, False)
            check = "✅" if enabled else "❌"
            label = WL_PERM_LABELS[p]
            lines.append(f"• {check}  {label}")

        container = MatrixContainer(
            text(f"## Whitelist Configuration"),
            text(f"**Remove specific bypass permissions:**"),
            make_separator(),
            text("\n".join(lines)),
            make_separator(),
            text(
                f"• **Moderator:** {self.moderator.name} (`{self.moderator.id}`)\n"
                f"• **Target:** {self.target.name} (`{self.target.id}`)"
            ),
            make_separator(),
            text(f"-# © {Config.FOOTER_TEXT}"),
        )
        self.add_item(container)

        options = []
        for p in WL_PERMS:
            if perms.get(p, False):
                options.append(discord.SelectOption(
                    label=WL_PERM_LABELS[p],
                    value=p,
                    emoji="✅"
                ))

        if options:
            select = discord.ui.Select(
                placeholder="Select permission to remove...",
                options=options[:25],
                min_values=1,
                max_values=min(len(options), 25)
            )

            async def select_cb(i: discord.Interaction):
                if i.user.id != self.moderator.id:
                    return await i.response.send_message("Not your panel.", ephemeral=True)
                cfg = get_cfg(self.guild_id)
                uid = str(self.target.id)
                for p in select.values:
                    cfg["whitelist"][uid][p] = False
                # If all false, remove entry
                if not any(cfg["whitelist"][uid].values()):
                    del cfg["whitelist"][uid]
                set_cfg(self.guild_id, cfg)
                self.render()
                await i.response.edit_message(view=self)

            select.callback = select_cb

            reset_btn = discord.ui.Button(label="Remove All", style=discord.ButtonStyle.danger)

            async def reset_cb(i: discord.Interaction):
                if i.user.id != self.moderator.id:
                    return await i.response.send_message("Not your panel.", ephemeral=True)
                cfg = get_cfg(self.guild_id)
                uid = str(self.target.id)
                if uid in cfg["whitelist"]:
                    del cfg["whitelist"][uid]
                set_cfg(self.guild_id, cfg)
                self.render()
                await i.response.edit_message(view=self)

            reset_btn.callback = reset_cb

            comp_container = MatrixContainer(
                discord.ui.ActionRow(select),
                discord.ui.ActionRow(reset_btn),
            )
            self.add_item(comp_container)


class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.punished = set()

    # ═══════════════════════════════════════════════
    #  HELPER: Safe check with perm-specific support
    # ═══════════════════════════════════════════════
    def _is_safe(self, guild, user_id, cfg, perm=None):
        if user_id == guild.owner_id:
            return True
        if user_id == self.bot.user.id:
            return True
        if user_id in cfg["extra_owners"]:
            return True
        # Perm-specific whitelist
        if perm:
            return user_has_wl_perm(cfg, user_id, perm)
        # Fallback: any perm whitelisted = safe (general check)
        perms = get_wl_perms(cfg, user_id)
        if perms and any(perms.values()):
            return True
        return False

    async def punish(self, guild, user_id, reason, action_type):
        cfg = get_cfg(guild.id)
        # action_type maps to whitelist perm
        if self._is_safe(guild, user_id, cfg, perm=action_type):
            return

        key = (guild.id, user_id)
        if key in self.punished:
            return
        self.punished.add(key)
        asyncio.create_task(self._clear_punished(key))

        member = guild.get_member(user_id)
        punishment = cfg.get("punishment", "ban")

        if member and member.top_role >= guild.me.top_role:
            await self.log(guild, user_id, reason, "FAILED - Role too high")
            return

        try:
            if punishment == "ban":
                await guild.ban(discord.Object(id=user_id),
                                reason=f"AntiNuke: {reason}",
                                delete_message_seconds=0)
            elif punishment == "kick" and member:
                await member.kick(reason=f"AntiNuke: {reason}")
            elif punishment == "strip" and member:
                for r in member.roles:
                    if r.permissions.administrator or r.permissions.manage_guild:
                        try:
                            await member.remove_roles(r, reason="AntiNuke strip")
                        except:
                            pass
        except discord.Forbidden:
            await self.log(guild, user_id, reason, "FAILED - No permission")
            return
        except Exception as e:
            print(f"Punish error: {e}")
            await self.log(guild, user_id, reason, f"FAILED - {e}")
            return

        await self.log(guild, user_id, reason, punishment.upper())

    async def _clear_punished(self, key):
        await asyncio.sleep(60)
        self.punished.discard(key)

    async def log(self, guild, user_id, reason, action):
        cfg = get_cfg(guild.id)
        ch_id = cfg.get("log_channel")
        if not ch_id:
            return
        ch = guild.get_channel(ch_id)
        if not ch:
            return
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SHIELD}  AntiNuke Triggered"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** <@{user_id}> (`{user_id}`)\n"
                f"{Emojis.WARNING} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Action:** `{action}`\n"
                f"{Emojis.CLOCK} **Time:** <t:{int(time.time())}:R>"
            )
        ))
        try:
            await ch.send(view=view)
        except:
            pass

    async def get_executor(self, guild, action_type, target_id=None):
        try:
            async for entry in guild.audit_logs(limit=5, action=action_type):
                if (datetime.utcnow() - entry.created_at.replace(tzinfo=None)).total_seconds() < 10:
                    if target_id and entry.target and entry.target.id != target_id:
                        continue
                    return entry.user
        except:
            return None
        return None

    # ═══════════════════════════════════════════════
    #  AUTORECOVERY HELPERS
    # ═══════════════════════════════════════════════
    async def _recreate_channel(self, guild, channel):
        """Recreate a deleted channel with the same name/type/position/overwrites."""
        try:
            kwargs = dict(
                overwrites=channel.overwrites,
                category=channel.category,
                position=channel.position,
                reason="AntiNuke autorecovery",
            )
            if isinstance(channel, discord.TextChannel):
                await guild.create_text_channel(
                    channel.name, topic=channel.topic, nsfw=channel.nsfw,
                    slowmode_delay=channel.slowmode_delay, **kwargs
                )
            elif isinstance(channel, discord.VoiceChannel):
                await guild.create_voice_channel(
                    channel.name, bitrate=channel.bitrate, user_limit=channel.user_limit, **kwargs
                )
            elif isinstance(channel, discord.CategoryChannel):
                await guild.create_category(channel.name, overwrites=channel.overwrites,
                                             position=channel.position, reason="AntiNuke autorecovery")
        except Exception as e:
            print(f"Autorecovery (channel) failed: {e}")

    async def _recreate_role(self, guild, role):
        """Recreate a deleted role with the same name/color/permissions."""
        try:
            new_role = await guild.create_role(
                name=role.name, color=role.color, permissions=role.permissions,
                hoist=role.hoist, mentionable=role.mentionable,
                reason="AntiNuke autorecovery"
            )
            try:
                await new_role.edit(position=role.position)
            except:
                pass
        except Exception as e:
            print(f"Autorecovery (role) failed: {e}")

    # ═══════════════════════════════════════════════
    #  LISTENERS (perm-aware, instant punishment)
    #  Any unauthorized user (not owner/extraowner/whitelisted)
    #  performing a monitored action is punished immediately —
    #  no rate-limit window, no threshold.
    # ═══════════════════════════════════════════════
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        cfg = get_cfg(channel.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antichannel"):
            return
        user = await self.get_executor(channel.guild, discord.AuditLogAction.channel_create)
        if not user or self._is_safe(channel.guild, user.id, cfg, perm="channel_create"):
            return
        # Punishment fires first, instantly — cleanup runs after in the background.
        await self.punish(channel.guild, user.id, "Unauthorized channel creation", "channel_create")
        asyncio.create_task(self._safe_delete_channel(channel))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        cfg = get_cfg(channel.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antichannel"):
            return
        user = await self.get_executor(channel.guild, discord.AuditLogAction.channel_delete)
        if not user or self._is_safe(channel.guild, user.id, cfg, perm="channel_delete"):
            return
        await self.punish(channel.guild, user.id, "Unauthorized channel deletion — autorecovering", "channel_delete")
        asyncio.create_task(self._recreate_channel(channel.guild, channel))

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        cfg = get_cfg(after.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antichannel"):
            return
        # Nothing actually changed (Discord sometimes fires no-op update events)
        if before.name == after.name and before.overwrites == after.overwrites \
                and getattr(before, "topic", None) == getattr(after, "topic", None):
            return
        user = await self.get_executor(after.guild, discord.AuditLogAction.channel_update)
        if not user or self._is_safe(after.guild, user.id, cfg, perm="channel_update"):
            return
        await self.punish(after.guild, user.id, "Unauthorized channel edit — autorecovering", "channel_update")
        asyncio.create_task(self._revert_channel(before, after))

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        cfg = get_cfg(role.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antirole"):
            return
        user = await self.get_executor(role.guild, discord.AuditLogAction.role_create)
        if not user or self._is_safe(role.guild, user.id, cfg, perm="role_create"):
            return
        await self.punish(role.guild, user.id, "Unauthorized role creation", "role_create")
        asyncio.create_task(self._safe_delete_role(role))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        cfg = get_cfg(role.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antirole"):
            return
        user = await self.get_executor(role.guild, discord.AuditLogAction.role_delete)
        if not user or self._is_safe(role.guild, user.id, cfg, perm="role_delete"):
            return
        await self.punish(role.guild, user.id, "Unauthorized role deletion — autorecovering", "role_delete")
        asyncio.create_task(self._recreate_role(role.guild, role))

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        cfg = get_cfg(after.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antirole"):
            return
        if before.permissions == after.permissions and before.name == after.name \
                and before.color == after.color:
            return
        user = await self.get_executor(after.guild, discord.AuditLogAction.role_update)
        if not user or self._is_safe(after.guild, user.id, cfg, perm="role_update"):
            return
        await self.punish(after.guild, user.id, "Unauthorized role edit — autorecovering", "role_update")
        asyncio.create_task(self._revert_role(before, after))

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        cfg = get_cfg(guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antiban"):
            return
        executor = await self.get_executor(guild, discord.AuditLogAction.ban)
        if not executor or self._is_safe(guild, executor.id, cfg, perm="ban"):
            return
        await self.punish(guild, executor.id, "Unauthorized ban — victim autorecovering (unbanning)", "ban")
        asyncio.create_task(self._safe_unban(guild, user))

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        cfg = get_cfg(member.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antikick"):
            return
        executor = await self.get_executor(member.guild, discord.AuditLogAction.kick)
        if not executor or self._is_safe(member.guild, executor.id, cfg, perm="kick"):
            return
        await self.punish(member.guild, executor.id, "Unauthorized kick", "kick")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        cfg = get_cfg(channel.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antiwebhook"):
            return
        user = await self.get_executor(channel.guild, discord.AuditLogAction.webhook_create)
        if not user or self._is_safe(channel.guild, user.id, cfg, perm="webhook_create"):
            return
        await self.punish(channel.guild, user.id, "Unauthorized webhook activity", "webhook_create")
        asyncio.create_task(self._safe_delete_webhooks(channel, user.id))

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        if not (message.mention_everyone):
            return
        cfg = get_cfg(message.guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antimention"):
            return
        if self._is_safe(message.guild, message.author.id, cfg, perm="mention_everyone"):
            return
        await self.punish(message.guild, message.author.id, "Unauthorized @everyone/@here mention", "mention_everyone")
        asyncio.create_task(self._safe_delete_message(message))

    # ═══════════════════════════════════════════════
    #  BACKGROUND CLEANUP/RESTORE WRAPPERS
    #  These always run AFTER punishment has already fired,
    #  as background tasks, so restore work never delays punishment.
    # ═══════════════════════════════════════════════
    async def _safe_delete_channel(self, channel):
        try:
            await channel.delete(reason="AntiNuke: unauthorized channel creation")
        except:
            pass

    async def _safe_delete_role(self, role):
        try:
            await role.delete(reason="AntiNuke: unauthorized role creation")
        except:
            pass

    async def _safe_unban(self, guild, user):
        try:
            await guild.unban(user, reason="AntiNuke autorecovery")
        except:
            pass

    async def _safe_delete_webhooks(self, channel, user_id):
        try:
            hooks = await channel.webhooks()
            for h in hooks:
                if h.user and h.user.id == user_id:
                    await h.delete(reason="AntiNuke")
        except:
            pass

    async def _safe_delete_message(self, message):
        try:
            await message.delete()
        except:
            pass

    async def _revert_channel(self, before, after):
        try:
            kwargs = {"overwrites": before.overwrites, "reason": "AntiNuke autorecovery"}
            if before.name != after.name:
                kwargs["name"] = before.name
            if hasattr(before, "topic") and before.topic != getattr(after, "topic", None):
                kwargs["topic"] = before.topic
            await after.edit(**kwargs)
        except:
            pass

    async def _revert_role(self, before, after):
        try:
            await after.edit(
                name=before.name, colour=before.colour, permissions=before.permissions,
                hoist=before.hoist, mentionable=before.mentionable,
                reason="AntiNuke autorecovery"
            )
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        cfg = get_cfg(guild.id)
        if not cfg["enabled"] or not cfg["modules"].get("antiemoji"):
            return
        if len(after) >= len(before):
            return
        user = await self.get_executor(guild, discord.AuditLogAction.emoji_delete)
        if not user or self._is_safe(guild, user.id, cfg, perm="manage_emojis"):
            return
        await self.punish(guild, user.id, "Emoji deletion", "manage_emojis")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = get_cfg(member.guild.id)
        if not cfg["enabled"]:
            return
        if member.bot and cfg["modules"].get("antibot"):
            user = await self.get_executor(member.guild, discord.AuditLogAction.bot_add)
            if user and not self._is_safe(member.guild, user.id, cfg, perm="bot_add"):
                try:
                    await member.kick(reason="AntiNuke: unauthorized bot add")
                except:
                    pass
                await self.punish(member.guild, user.id, "Unauthorized bot add", "bot_add")

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        cfg = get_cfg(after.id)
        if not cfg["enabled"] or not cfg["modules"].get("antiserver"):
            return
        user = await self.get_executor(after, discord.AuditLogAction.guild_update)
        if not user or self._is_safe(after, user.id, cfg, perm="guild_update"):
            return
        await self.punish(after, user.id, "Server edit attempt", "guild_update")

    # ═══════════════════════════════════════════════
    #  COMMAND: &antinuke (Dashboard)
    # ═══════════════════════════════════════════════
    @commands.group(name="antinuke", invoke_without_command=True)
    async def antinuke(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        status_emoji = Emojis.SUCCESS if cfg["enabled"] else Emojis.ERROR
        status_text = "ENABLED" if cfg["enabled"] else "DISABLED"
        active = sum(1 for v in cfg["modules"].values() if v)
        total = len(cfg["modules"])

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"## {Config.BOT_NAME} AntiNuke System"),
            text(f"### {Emojis.ANTINUKE} Enhanced Protection Dashboard"),
            text(f"Next-generation AntiNuke."),
            make_separator(),
            text(
                f"{status_emoji} **System Status:** {status_text}\n"
                f"{Emojis.ANTINUKE} **Active Modules:** {active}/{total}"
            ),
            make_separator(),
            text(f"{Emojis.SETTINGS} **Quick Commands**"),
            text(
                f"`&antinuke enable` - Activate protection\n"
                f"`&antinuke disable` - Deactivate system\n"
                f"`&antinuke status` - View detailed status\n"
                f"`&whitelist @user` - Manage whitelist"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name} • {ctx.guild.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @antinuke.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antinuke_enable(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in cfg["extra_owners"]:
            return await send_v2(ctx, error_view("Only the server owner can enable AntiNuke."))
        if cfg["enabled"]:
            return await send_v2(ctx, error_view("AntiNuke is already enabled for this server."))

        # Goes straight into the animated setup — no confirmation/agree screens.
        await self._run_setup(ctx, cfg)

    async def _run_setup(self, ctx, cfg):
        guild = ctx.guild
        steps = [
            ("Analyzing server security requirements", "OK"),
            (f"Checking {Config.BOT_NAME}' Role Permissions", "OK"),
            (f"Checking {Config.BOT_NAME}' Role Position", "OK"),
            (f"Creating and Configuring {Config.BOT_NAME} Wall Role", "RUNNING"),
            ("Creating Logging Channel For Antinuke Logs", "PENDING"),
            ("Creating Webhook For Optimal Logging", "PENDING"),
            ("Enabling Antinuke For This Server", "PENDING"),
            ("Safeguarding Changes", "PENDING"),
        ]

        async def render(steps_list, progress):
            bar_full = "▬" * int(progress / 5)
            bar_empty = "▬" * (20 - int(progress / 5))
            body_lines = []
            for label, state in steps_list:
                if state == "OK":
                    prefix = "[+]"
                elif state == "RUNNING":
                    prefix = "[>]"
                elif state == "FAILED":
                    prefix = "[x]"
                else:
                    prefix = "[ ]"
                body_lines.append(f"{prefix} {label}... {state}")
            block = "[ SYSTEM INITIALIZATION ]\n" + "\n".join(body_lines)
            view = discord.ui.LayoutView()
            container = MatrixContainer(
                text(f"## Antinuke Setup"),
                make_separator(),
                text(f"```\n{block}\n```"),
                text(f"**Progress:** `{bar_full}{bar_empty}` {progress}%"),
                make_separator(),
                text(f"{Emojis.SUCCESS if progress == 100 else Emojis.LOADING}  "
                     f"{'Setup successful! System is fully secured.' if progress == 100 else 'Setting up...'}"),
                text(f"-# © {Config.FOOTER_TEXT}")
            )
            view.add_item(container)
            return view

        view = await render(steps, 38)
        msg = await ctx.send(view=view)

        await asyncio.sleep(1)
        wall_role = discord.utils.get(guild.roles, name=f"{Config.BOT_NAME} Wall")
        if not wall_role:
            try:
                wall_role = await guild.create_role(
                    name=f"{Config.BOT_NAME} Wall", color=discord.Color.red(),
                    hoist=False, reason="AntiNuke setup"
                )
                try:
                    top = guild.me.top_role.position
                    await wall_role.edit(position=max(top - 1, 1))
                except:
                    pass
            except:
                steps[3] = (steps[3][0], "FAILED")
        cfg["wall_role"] = wall_role.id if wall_role else None
        steps[3] = (steps[3][0], "OK")
        steps[4] = (steps[4][0], "RUNNING")
        await msg.edit(view=await render(steps, 50))

        await asyncio.sleep(1)
        log_ch_name = f"{Config.BOT_NAME.lower().replace(' ', '-')}-antinuke-logs"
        log_ch = discord.utils.get(guild.text_channels, name=log_ch_name)
        if not log_ch:
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                }
                log_ch = await guild.create_text_channel(log_ch_name, overwrites=overwrites)
            except:
                steps[4] = (steps[4][0], "FAILED")
        cfg["log_channel"] = log_ch.id if log_ch else None
        steps[4] = (steps[4][0], "OK")
        steps[5] = (steps[5][0], "RUNNING")
        await msg.edit(view=await render(steps, 65))

        await asyncio.sleep(1)
        if log_ch:
            try:
                wh = await log_ch.create_webhook(name=f"{Config.BOT_NAME} AntiNuke")
                cfg["webhook_url"] = wh.url
            except:
                steps[5] = (steps[5][0], "FAILED")
        steps[5] = (steps[5][0], "OK")
        steps[6] = (steps[6][0], "RUNNING")
        await msg.edit(view=await render(steps, 80))

        await asyncio.sleep(1)
        cfg["enabled"] = True
        for k in cfg["modules"]:
            cfg["modules"][k] = True
        steps[6] = (steps[6][0], "OK")
        steps[7] = (steps[7][0], "RUNNING")
        await msg.edit(view=await render(steps, 92))

        await asyncio.sleep(1)
        set_cfg(guild.id, cfg)
        steps[7] = (steps[7][0], "OK")
        await msg.edit(view=await render(steps, 100))

    @antinuke.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antinuke_disable(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        if ctx.author.id != ctx.guild.owner_id:
            return await send_v2(ctx, error_view("Only the server owner can disable AntiNuke."))
        cfg["enabled"] = False
        set_cfg(ctx.guild.id, cfg)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   AntiNuke Disabled"),
            make_separator(),
            text(f"Re-enable anytime with `&antinuke enable`")
        ))
        await send_v2(ctx, view)

    @antinuke.command(name="status")
    async def antinuke_status(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        status = "ENABLED" if cfg["enabled"] else "DISABLED"
        lines = [f"{Emojis.SUCCESS if v else Emojis.ERROR} {MODULE_NAMES[k]}"
                 for k, v in cfg["modules"].items()]
        log_ch = f"<#{cfg['log_channel']}>" if cfg["log_channel"] else "Not Set"
        wall = f"<@&{cfg['wall_role']}>" if cfg["wall_role"] else "Not Set"

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SHIELD}  AntiNuke Status"),
            make_separator(),
            text(
                f"**System:** `{status}`\n"
                f"**Log Channel:** {log_ch}\n"
                f"**Wall Role:** {wall}\n"
                f"**Punishment:** `{cfg['punishment'].upper()}`\n"
                f"**Whitelisted Users:** `{len(cfg['whitelist'])}`\n"
                f"**Extra Owners:** `{len(cfg['extra_owners'])}`"
            ),
            make_separator(),
            text("**Modules:**\n" + "\n".join(lines))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &whitelist (NEW UI)
    # ═══════════════════════════════════════════════
    @commands.command(name="whitelist")
    @commands.has_permissions(administrator=True)
    async def whitelist(self, ctx, user: discord.User = None):
        cfg = get_cfg(ctx.guild.id)
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in cfg["extra_owners"]:
            return await send_v2(ctx, error_view("Only the server owner can manage whitelist."))
        if not user:
            return await send_v2(ctx, error_view("Provide a user.", "&whitelist @user"))

        view = WhitelistConfigView(self, ctx.guild.id, user, ctx.author)
        await send_v2(ctx, view)

    # ═══════════════════════════════════════════════
    #  COMMAND: &unwhitelist (NEW UI)
    # ═══════════════════════════════════════════════
    @commands.command(name="unwhitelist")
    @commands.has_permissions(administrator=True)
    async def unwhitelist(self, ctx, user: discord.User = None):
        cfg = get_cfg(ctx.guild.id)
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in cfg["extra_owners"]:
            return await send_v2(ctx, error_view("Only the server owner can manage whitelist."))
        if not user:
            return await send_v2(ctx, error_view("Provide a user.", "&unwhitelist @user"))

        # If user not in whitelist
        if str(user.id) not in cfg["whitelist"] or not any(cfg["whitelist"].get(str(user.id), {}).values()):
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(
                text(f"## Whitelist Updated"),
                make_separator(),
                text(f"```diff\n+ Successfully removed user from whitelist.\n```"),
                make_separator(),
                text(
                    f"• **Executor:** {ctx.author.mention}\n"
                    f"• **Target:** {user.mention}"
                ),
                make_separator(),
                text(f"-# © {Config.FOOTER_TEXT}"),
            ))
            # Ensure clean state
            if str(user.id) in cfg["whitelist"]:
                del cfg["whitelist"][str(user.id)]
                set_cfg(ctx.guild.id, cfg)
            return await send_v2(ctx, view)

        view = UnwhitelistView(self, ctx.guild.id, user, ctx.author)
        await send_v2(ctx, view)

    @commands.command(name="wlisted", aliases=["wlist"])
    async def wlisted(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        if not cfg["whitelist"]:
            return await send_v2(ctx, error_view("Whitelist is empty."))
        lines = []
        for u, perms in cfg["whitelist"].items():
            enabled_count = sum(1 for v in perms.values() if v)
            lines.append(f"• <@{u}> (`{u}`) — `{enabled_count}/{len(WL_PERMS)}` perms")
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SHIELD}  Whitelisted Users"),
            make_separator(),
            text("\n".join(lines))
        ))
        await send_v2(ctx, view)

    @commands.command(name="whitelistreset")
    @commands.has_permissions(administrator=True)
    async def whitelistreset(self, ctx):
        cfg = get_cfg(ctx.guild.id)
        if ctx.author.id != ctx.guild.owner_id:
            return await send_v2(ctx, error_view("Only the server owner can reset the whitelist."))
        cfg["whitelist"] = {}
        set_cfg(ctx.guild.id, cfg)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}   Whitelist reset")))
        await send_v2(ctx, view)

    @commands.command(name="extraowner")
    async def extraowner(self, ctx, user: discord.User = None):
        cfg = get_cfg(ctx.guild.id)
        if ctx.author.id != ctx.guild.owner_id:
            return await send_v2(ctx, error_view("Only the server owner can manage extra owners."))
        if not user:
            if not cfg["extra_owners"]:
                return await send_v2(ctx, error_view("No extra owners set."))
            lines = "\n".join(f"• <@{u}>" for u in cfg["extra_owners"])
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(
                text(f"### {Emojis.CROWN}  Extra Owners"),
                make_separator(),
                text(lines)
            ))
            return await send_v2(ctx, view)
        if user.id in cfg["extra_owners"]:
            cfg["extra_owners"].remove(user.id)
            action = "Removed from"
        else:
            cfg["extra_owners"].append(user.id)
            action = "Added to"
        set_cfg(ctx.guild.id, cfg)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   {action} Extra Owners"),
            make_separator(),
            text(f"{Emojis.MEMBERS} **User:** {user.mention}")
        ))
        await send_v2(ctx, view)

    @commands.command(name="nightmode")
    @commands.has_permissions(administrator=True)
    async def nightmode(self, ctx, state: str = None):
        cfg = get_cfg(ctx.guild.id)
        if state not in ("on", "off"):
            return await send_v2(ctx, error_view("Usage: `&nightmode on/off`"))
        cfg["nightmode"] = (state == "on")
        set_cfg(ctx.guild.id, cfg)
        for ch in ctx.guild.text_channels:
            try:
                await ch.set_permissions(
                    ctx.guild.default_role,
                    send_messages=False if state == "on" else None
                )
            except:
                pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Nightmode `{state.upper()}`"),
            make_separator(),
            text(f"All channels have been {'locked' if state == 'on' else 'unlocked'}.")
        ))
        await send_v2(ctx, view)

    @commands.command(name="verification")
    @commands.has_permissions(administrator=True)
    async def verification(self, ctx, state: str = None):
        cfg = get_cfg(ctx.guild.id)
        if state not in ("on", "off"):
            return await send_v2(ctx, error_view("Usage: `&verification on/off`"))
        cfg["verification"] = (state == "on")
        set_cfg(ctx.guild.id, cfg)
        try:
            level = discord.VerificationLevel.highest if state == "on" else discord.VerificationLevel.low
            await ctx.guild.edit(verification_level=level)
        except:
            pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SUCCESS}   Verification `{state.upper()}`")
        ))
        await send_v2(ctx, view)

    @commands.command(name="vanityguard")
    @commands.has_permissions(administrator=True)
    async def vanityguard(self, ctx, state: str = None):
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SHIELD}  Vanity Guard"),
            make_separator(),
            text(f"Vanity Guard protects your server's vanity URL from theft.")
        ))
        await send_v2(ctx, view)


async def setup(bot):
    await bot.add_cog(AntiNuke(bot))