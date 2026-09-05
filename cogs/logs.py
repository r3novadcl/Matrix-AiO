import discord
from discord.ext import commands
import json, os
from datetime import datetime
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

LOG_FILE = "log_config.json"

# Log event types
LOG_TYPES = [
    "message_delete", "message_edit", "bulk_delete",
    "member_join", "member_leave",
    "member_ban", "member_unban",
    "role_create", "role_delete", "role_update",
    "member_role_add", "member_role_remove",
    "nickname_change",
    "channel_create", "channel_delete", "channel_update",
    "voice_join", "voice_leave", "voice_move",
    "server_update",
    "invite_create", "invite_delete",
    "member_timeout",
    "boost",
    "thread_create", "thread_delete",
]


# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(LOG_FILE, dict)

def load_log_cfg():
    return _cache.load()

def save_log_cfg(d):
    _cache.save(d)

def get_log_channel(guild_id, event_type=None):
    cfg = load_log_cfg()
    gcfg = cfg.get(str(guild_id), {})
    if event_type and event_type in gcfg.get("specific", {}):
        return gcfg["specific"][event_type]
    return gcfg.get("default_channel")


async def send_log(bot, guild_id, event_type, container):
    ch_id = get_log_channel(guild_id, event_type)
    if not ch_id:
        return
    ch = bot.get_channel(int(ch_id))
    if not ch:
        return
    view = discord.ui.LayoutView()
    view.add_item(container)
    try:
        await ch.send(view=view)
    except:
        pass


class LogSetupView(discord.ui.LayoutView):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.page = "main"
        self.build()

    def build(self):
        self.clear_items()
        cfg = load_log_cfg()
        gid = str(self.ctx.guild.id)
        gcfg = cfg.get(gid, {"default_channel": None, "specific": {}, "enabled": []})

        if self.page == "main":
            default_ch = gcfg.get("default_channel")
            default_mention = f"<#{default_ch}>" if default_ch else "Not Set"
            enabled = gcfg.get("enabled", [])

            section = discord.ui.Section(
                text(f"### {Emojis.LOGS}  Logging Configuration"),
                text("Configure what events get logged and where."),
                accessory=discord.ui.Thumbnail(
                    media=Config.BOT_LOGO if Config.BOT_LOGO.startswith("http") else self.ctx.bot.user.display_avatar.url
                )
            )

            # Buttons
            set_ch_btn = discord.ui.Button(label="Set Default Channel", style=discord.ButtonStyle.primary)
            toggle_btn = discord.ui.Button(label="Toggle Events",       style=discord.ButtonStyle.secondary)
            spec_btn   = discord.ui.Button(label="Specific Channels",   style=discord.ButtonStyle.secondary)
            enable_all = discord.ui.Button(label="Enable All",          style=discord.ButtonStyle.success)
            disable_all= discord.ui.Button(label="Disable All",        style=discord.ButtonStyle.danger)

            async def set_ch_cb(i):
                self.page = "set_channel"; self.build()
                await i.response.edit_message(view=self)
            async def toggle_cb(i):
                self.page = "toggle"; self.build()
                await i.response.edit_message(view=self)
            async def spec_cb(i):
                self.page = "specific"; self.build()
                await i.response.edit_message(view=self)
            async def enable_all_cb(i):
                cfg2 = load_log_cfg()
                cfg2.setdefault(gid, {"default_channel": None, "specific": {}, "enabled": []})
                cfg2[gid]["enabled"] = LOG_TYPES[:]
                save_log_cfg(cfg2); self.build()
                await i.response.edit_message(view=self)
            async def disable_all_cb(i):
                cfg2 = load_log_cfg()
                cfg2.setdefault(gid, {"default_channel": None, "specific": {}, "enabled": []})
                cfg2[gid]["enabled"] = []
                save_log_cfg(cfg2); self.build()
                await i.response.edit_message(view=self)

            set_ch_btn.callback = set_ch_cb; toggle_btn.callback = toggle_cb
            spec_btn.callback   = spec_cb; enable_all.callback = enable_all_cb
            disable_all.callback = disable_all_cb

            events_status = ""
            for e in LOG_TYPES:
                status = Emojis.ON if e in enabled else Emojis.OFF
                events_status += f"{status} `{e}`\n"

            container = MatrixContainer(
                section,
                make_separator(),
                text(f"{Emojis.CHANNEL} **Default Log Channel:** {default_mention}"),
                text(f"{Emojis.ARROW} **Enabled Events:** {len(enabled)}/{len(LOG_TYPES)}"),
                make_separator(),
                text(events_status),
                make_separator(),
                text(f"-# Requested by {self.ctx.author.name}"),
                discord.ui.ActionRow(set_ch_btn, toggle_btn, spec_btn),
                discord.ui.ActionRow(enable_all, disable_all)
            )
            self.add_item(container)

        elif self.page == "set_channel":
            select = discord.ui.ChannelSelect(
                placeholder="Select default log channel...",
                channel_types=[discord.ChannelType.text]
            )
            async def ch_cb(i):
                ch = select.values[0]
                cfg2 = load_log_cfg()
                cfg2.setdefault(gid, {"default_channel": None, "specific": {}, "enabled": []})
                cfg2[gid]["default_channel"] = str(ch.id)
                save_log_cfg(cfg2)
                self.page = "main"; self.build()
                await i.response.edit_message(view=self)
            select.callback = ch_cb

            back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
            async def back_cb(i):
                self.page = "main"; self.build()
                await i.response.edit_message(view=self)
            back_btn.callback = back_cb

            container = MatrixContainer(
                text(f"### {Emojis.LOGS}  Set Default Log Channel"),
                make_separator(),
                text("Select a channel below where all log events will be sent by default."),
                discord.ui.ActionRow(select),
                discord.ui.ActionRow(back_btn)
            )
            self.add_item(container)

        elif self.page == "toggle":
            enabled = gcfg.get("enabled", [])
            # Show first 25
            opts = [
                discord.SelectOption(label=e.replace("_", " ").title(), value=e,
                    description="Enabled" if e in enabled else "Disabled",
                    emoji=Emojis.ON if e in enabled else Emojis.OFF
                ) for e in LOG_TYPES[:25]
            ]
            select = discord.ui.Select(placeholder="Toggle an event...", options=opts, max_values=1)
            async def tog_cb(i):
                chosen = select.values[0]
                cfg2 = load_log_cfg()
                gcfg2 = cfg2.setdefault(gid, {"default_channel": None, "specific": {}, "enabled": []})
                if chosen in gcfg2["enabled"]:
                    gcfg2["enabled"].remove(chosen)
                else:
                    gcfg2["enabled"].append(chosen)
                save_log_cfg(cfg2); self.build()
                await i.response.edit_message(view=self)
            select.callback = tog_cb

            back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
            async def back_cb(i):
                self.page = "main"; self.build()
                await i.response.edit_message(view=self)
            back_btn.callback = back_cb

            container = MatrixContainer(
                text(f"### {Emojis.LOGS}  Toggle Log Events"),
                make_separator(),
                text("Select an event to enable/disable it."),
                discord.ui.ActionRow(select),
                discord.ui.ActionRow(back_btn)
            )
            self.add_item(container)

        elif self.page == "specific":
            specific = gcfg.get("specific", {})
            lines = ""
            for e, ch in specific.items():
                lines += f"`{e}` → <#{ch}>\n"
            if not lines: lines = "No specific channels set."

            select_event = discord.ui.Select(
                placeholder="Select event for specific channel...",
                options=[discord.SelectOption(label=e.replace("_"," ").title(), value=e) for e in LOG_TYPES[:25]]
            )

            async def ev_cb(i):
                chosen = select_event.values[0]
                # Now ask channel
                self.page = f"specific_set:{chosen}"; self.build()
                await i.response.edit_message(view=self)
            select_event.callback = ev_cb

            back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
            async def back_cb(i):
                self.page = "main"; self.build()
                await i.response.edit_message(view=self)
            back_btn.callback = back_cb

            container = MatrixContainer(
                text(f"### {Emojis.LOGS}  Specific Log Channels"),
                make_separator(),
                text("Set different channels for different events.\n"),
                text(lines),
                make_separator(),
                discord.ui.ActionRow(select_event),
                discord.ui.ActionRow(back_btn)
            )
            self.add_item(container)

        elif self.page.startswith("specific_set:"):
            event_name = self.page.split(":", 1)[1]
            ch_select = discord.ui.ChannelSelect(
                placeholder=f"Channel for {event_name}...",
                channel_types=[discord.ChannelType.text]
            )
            async def ch_cb(i):
                cfg2 = load_log_cfg()
                cfg2.setdefault(gid, {"default_channel": None, "specific": {}, "enabled": []})
                cfg2[gid].setdefault("specific", {})[event_name] = str(ch_select.values[0].id)
                save_log_cfg(cfg2)
                self.page = "specific"; self.build()
                await i.response.edit_message(view=self)
            ch_select.callback = ch_cb

            back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
            async def back_cb(i):
                self.page = "specific"; self.build()
                await i.response.edit_message(view=self)
            back_btn.callback = back_cb

            container = MatrixContainer(
                text(f"### {Emojis.LOGS}  Set Channel for `{event_name}`"),
                discord.ui.ActionRow(ch_select),
                discord.ui.ActionRow(back_btn)
            )
            self.add_item(container)


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_enabled(self, guild_id, event):
        cfg = load_log_cfg()
        gcfg = cfg.get(str(guild_id), {})
        return event in gcfg.get("enabled", [])

    # ─── LOGGING SETUP COMMAND ───
    @commands.command(name="logging", aliases=["logs", "logsetup"])
    @commands.has_permissions(administrator=True)
    async def logging_cmd(self, ctx):
        view = LogSetupView(ctx)
        await ctx.send(view=view)

    # ─── LISTENERS ───

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild: return
        if not self._is_enabled(message.guild.id, "message_delete"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_MSG_DEL}  Message Deleted"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **Author:** {message.author.mention} (`{message.author}`)\n"
                f"{Emojis.CHANNEL} **Channel:** {message.channel.mention}\n"
                f"{Emojis.CLOCK} **Time:** <t:{int(datetime.utcnow().timestamp())}:R>"
            ),
            make_separator(),
            text(f"**Content:**\n{message.content[:1000] or '*[No content]*'}"),
            make_separator(),
            text(f"-# Message ID: {message.id}")
        )
        await send_log(self.bot, message.guild.id, "message_delete", container)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild: return
        if before.content == after.content: return
        if not self._is_enabled(before.guild.id, "message_edit"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_MSG_EDIT}  Message Edited"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **Author:** {before.author.mention}\n"
                f"{Emojis.CHANNEL} **Channel:** {before.channel.mention}\n"
                f"{Emojis.CLOCK} **Time:** <t:{int(datetime.utcnow().timestamp())}:R>"
            ),
            make_separator(),
            text(f"**Before:**\n{before.content[:500] or '*[Empty]*'}"),
            make_separator(),
            text(f"**After:**\n{after.content[:500] or '*[Empty]*'}"),
            make_separator(),
            text(f"-# [Jump to Message]({after.jump_url})")
        )
        await send_log(self.bot, before.guild.id, "message_edit", container)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages: return
        guild = messages[0].guild
        if not guild: return
        if not self._is_enabled(guild.id, "bulk_delete"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_BULK_DEL}  Bulk Message Delete"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Channel:** {messages[0].channel.mention}\n"
                f"{Emojis.ARROW} **Messages Deleted:** {len(messages)}\n"
                f"{Emojis.CLOCK} **Time:** <t:{int(datetime.utcnow().timestamp())}:R>"
            )
        )
        await send_log(self.bot, guild.id, "bulk_delete", container)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not self._is_enabled(member.guild.id, "member_join"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_JOIN}  Member Joined"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **Member:** {member.mention} (`{member}`)\n"
                f"{Emojis.ID} **ID:** `{member.id}`\n"
                f"{Emojis.CREATED} **Account Created:** <t:{int(member.created_at.timestamp())}:R>\n"
                f"{Emojis.ARROW} **Member Count:** {member.guild.member_count}"
            )
        )
        await send_log(self.bot, member.guild.id, "member_join", container)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not self._is_enabled(member.guild.id, "member_leave"): return
        roles = " ".join([r.mention for r in member.roles[1:][:10]]) or "None"
        container = MatrixContainer(
            text(f"### {Emojis.LOG_LEAVE}  Member Left"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **Member:** {member} (`{member.id}`)\n"
                f"{Emojis.ROLE} **Roles:** {roles}\n"
                f"{Emojis.ARROW} **Joined:** <t:{int(member.joined_at.timestamp())}:R>"
            )
        )
        await send_log(self.bot, member.guild.id, "member_leave", container)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if not self._is_enabled(guild.id, "member_ban"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_BAN}  Member Banned"),
            make_separator(),
            text(f"{Emojis.MEMBERS} **User:** {user} (`{user.id}`)")
        )
        await send_log(self.bot, guild.id, "member_ban", container)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        if not self._is_enabled(guild.id, "member_unban"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_UNBAN}  Member Unbanned"),
            make_separator(),
            text(f"{Emojis.MEMBERS} **User:** {user} (`{user.id}`)")
        )
        await send_log(self.bot, guild.id, "member_unban", container)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = before.guild

        # Nickname change
        if before.nick != after.nick:
            if not self._is_enabled(guild.id, "nickname_change"): return
            container = MatrixContainer(
                text(f"### {Emojis.LOG_NICK}  Nickname Changed"),
                make_separator(),
                text(
                    f"{Emojis.MEMBERS} **Member:** {after.mention}\n"
                    f"{Emojis.ARROW} **Before:** {before.nick or before.name}\n"
                    f"{Emojis.ARROW} **After:** {after.nick or after.name}"
                )
            )
            await send_log(self.bot, guild.id, "nickname_change", container)

        # Role add
        added = set(after.roles) - set(before.roles)
        if added:
            if not self._is_enabled(guild.id, "member_role_add"): return
            for r in added:
                container = MatrixContainer(
                    text(f"### {Emojis.LOG_ROLE_ADD}  Role Added"),
                    make_separator(),
                    text(
                        f"{Emojis.MEMBERS} **Member:** {after.mention}\n"
                        f"{Emojis.ROLE} **Role:** {r.mention}"
                    )
                )
                await send_log(self.bot, guild.id, "member_role_add", container)

        # Role remove
        removed = set(before.roles) - set(after.roles)
        if removed:
            if not self._is_enabled(guild.id, "member_role_remove"): return
            for r in removed:
                container = MatrixContainer(
                    text(f"### {Emojis.LOG_ROLE_REM}  Role Removed"),
                    make_separator(),
                    text(
                        f"{Emojis.MEMBERS} **Member:** {after.mention}\n"
                        f"{Emojis.ROLE} **Role:** {r.mention}"
                    )
                )
                await send_log(self.bot, guild.id, "member_role_remove", container)

        # Timeout
        if before.timed_out_until != after.timed_out_until and after.timed_out_until:
            if not self._is_enabled(guild.id, "member_timeout"): return
            container = MatrixContainer(
                text(f"### {Emojis.LOG_TIMEOUT}  Member Timed Out"),
                make_separator(),
                text(
                    f"{Emojis.MEMBERS} **Member:** {after.mention}\n"
                    f"{Emojis.CLOCK} **Until:** <t:{int(after.timed_out_until.timestamp())}:R>"
                )
            )
            await send_log(self.bot, guild.id, "member_timeout", container)

        # Boost
        if before.premium_since is None and after.premium_since is not None:
            if not self._is_enabled(guild.id, "boost"): return
            container = MatrixContainer(
                text(f"### {Emojis.LOG_BOOST}  Server Boosted"),
                make_separator(),
                text(f"{Emojis.MEMBERS} **Booster:** {after.mention}\n{Emojis.BOOST} **Total Boosts:** {guild.premium_subscription_count}")
            )
            await send_log(self.bot, guild.id, "boost", container)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not self._is_enabled(channel.guild.id, "channel_create"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_CHANNEL}  Channel Created"),
            make_separator(),
            text(f"{Emojis.CHANNEL} **Channel:** {channel.mention}\n{Emojis.ARROW} **Type:** {channel.type}")
        )
        await send_log(self.bot, channel.guild.id, "channel_create", container)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not self._is_enabled(channel.guild.id, "channel_delete"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_CHANNEL}  Channel Deleted"),
            make_separator(),
            text(f"{Emojis.CHANNEL} **Channel:** `{channel.name}`\n{Emojis.ARROW} **Type:** {channel.type}")
        )
        await send_log(self.bot, channel.guild.id, "channel_delete", container)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if not self._is_enabled(role.guild.id, "role_create"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_ROLE_ADD}  Role Created"),
            make_separator(),
            text(f"{Emojis.ROLE} **Role:** {role.mention}\n{Emojis.ID} **ID:** `{role.id}`")
        )
        await send_log(self.bot, role.guild.id, "role_create", container)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if not self._is_enabled(role.guild.id, "role_delete"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_ROLE_REM}  Role Deleted"),
            make_separator(),
            text(f"{Emojis.ROLE} **Role:** `{role.name}`\n{Emojis.ID} **ID:** `{role.id}`")
        )
        await send_log(self.bot, role.guild.id, "role_delete", container)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        if before.channel is None and after.channel is not None:
            if not self._is_enabled(guild.id, "voice_join"): return
            container = MatrixContainer(
                text(f"### {Emojis.LOG_VOICE}  Voice Join"),
                make_separator(),
                text(f"{Emojis.MEMBERS} {member.mention} joined {after.channel.mention}")
            )
            await send_log(self.bot, guild.id, "voice_join", container)
        elif before.channel is not None and after.channel is None:
            if not self._is_enabled(guild.id, "voice_leave"): return
            container = MatrixContainer(
                text(f"### {Emojis.LOG_VOICE}  Voice Leave"),
                make_separator(),
                text(f"{Emojis.MEMBERS} {member.mention} left {before.channel.mention}")
            )
            await send_log(self.bot, guild.id, "voice_leave", container)
        elif before.channel != after.channel:
            if not self._is_enabled(guild.id, "voice_move"): return
            container = MatrixContainer(
                text(f"### {Emojis.LOG_VOICE}  Voice Move"),
                make_separator(),
                text(f"{Emojis.MEMBERS} {member.mention} moved {before.channel.mention} → {after.channel.mention}")
            )
            await send_log(self.bot, guild.id, "voice_move", container)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if not self._is_enabled(invite.guild.id, "invite_create"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_INVITE}  Invite Created"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **By:** {invite.inviter.mention if invite.inviter else 'Unknown'}\n"
                f"{Emojis.LINK} **Code:** `{invite.code}`\n"
                f"{Emojis.CHANNEL} **Channel:** {invite.channel.mention}"
            )
        )
        await send_log(self.bot, invite.guild.id, "invite_create", container)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if not self._is_enabled(invite.guild.id, "invite_delete"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_INVITE}  Invite Deleted"),
            make_separator(),
            text(f"{Emojis.LINK} **Code:** `{invite.code}`")
        )
        await send_log(self.bot, invite.guild.id, "invite_delete", container)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if not self._is_enabled(thread.guild.id, "thread_create"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_THREAD}  Thread Created"),
            make_separator(),
            text(f"{Emojis.CHANNEL} **Thread:** {thread.mention}")
        )
        await send_log(self.bot, thread.guild.id, "thread_create", container)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if not self._is_enabled(thread.guild.id, "thread_delete"): return
        container = MatrixContainer(
            text(f"### {Emojis.LOG_THREAD}  Thread Deleted"),
            make_separator(),
            text(f"{Emojis.CHANNEL} **Thread:** `{thread.name}`")
        )
        await send_log(self.bot, thread.guild.id, "thread_delete", container)


async def setup(bot):
    await bot.add_cog(Logs(bot))