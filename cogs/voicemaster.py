"""
Matrix Bot - VoiceMaster (Join To Create)
Components V2 with red accent + interactive button panel
"""

import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

VM_FILE = "voicemaster.json"

BTN_LABELS = {
    "lock": "Lock", "unlock": "Unlock", "hide": "Hide", "unhide": "Unhide",
    "rename": "Rename", "limit": "Limit", "mute": "Mute", "unmute": "Unmute",
    "deafen": "Deafen", "undeafen": "Undeafen", "permit": "Permit", "ban": "Ban",
    "transfer": "Transfer", "claim": "Claim",
}

BTN_EMOJI = {
    "lock": Emojis.VM_LOCK, "unlock": Emojis.VM_UNLOCK,
    "hide": Emojis.VM_HIDE, "unhide": Emojis.VM_UNHIDE,
    "rename": Emojis.VM_RENAME, "limit": Emojis.VM_LIMIT,
    "mute": Emojis.VM_MUTE, "unmute": Emojis.VM_UNMUTE,
    "deafen": Emojis.VM_DEAFEN, "undeafen": Emojis.VM_UNDEAFEN,
    "permit": Emojis.VM_PERMIT, "ban": Emojis.VM_BAN,
    "transfer": Emojis.VM_TRANSFER, "claim": Emojis.VM_CLAIM,
}

BTN_DESC = {
    "lock":     "Lock your voice channel",
    "unlock":   "Unlock your voice channel",
    "hide":     "Hide your voice channel",
    "unhide":   "Reveal your voice channel",
    "rename":   "Rename your voice channel",
    "limit":    "Set user limit",
    "mute":     "Mute a user in your channel",
    "unmute":   "Unmute a user",
    "deafen":   "Deafen a user",
    "undeafen": "Undeafen a user",
    "permit":   "Permit a user to join",
    "ban":      "Ban a user from your channel",
    "transfer": "Transfer ownership",
    "claim":    "Claim an abandoned channel",
}

ALL_BUTTONS = list(BTN_LABELS.keys())


# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(VM_FILE, dict)

def load_vm():
    return _cache.load()

def save_vm(d):
    _cache.save(d)

def get_guild_vm(gid):
    return load_vm().get(str(gid))

def set_guild_vm(gid, cfg):
    data = load_vm()
    data[str(gid)] = cfg
    save_vm(data)

def del_guild_vm(gid):
    data = load_vm()
    data.pop(str(gid), None)
    save_vm(data)


# ─── Reply helper ───
def reply_text(msg):
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(MatrixContainer(text(msg)))
    return view


# ─── Modals ───
class RenameModal(discord.ui.Modal, title="Rename Voice Channel"):
    name = discord.ui.TextInput(label="New Channel Name", placeholder="Enter new name...", max_length=100, min_length=1)
    def __init__(self, vc):
        super().__init__()
        self.vc = vc
    async def on_submit(self, i):
        try:
            await self.vc.edit(name=self.name.value.strip())
            await i.response.send_message(view=reply_text(f"{Emojis.VM_RENAME} Renamed to **{self.name.value}**"), ephemeral=True)
        except Exception as e:
            await i.response.send_message(view=reply_text(f"{Emojis.ERROR} Error: `{e}`"), ephemeral=True)


class LimitModal(discord.ui.Modal, title="Set User Limit"):
    limit = discord.ui.TextInput(label="User Limit (0 = unlimited)", placeholder="0-99", max_length=2)
    def __init__(self, vc):
        super().__init__()
        self.vc = vc
    async def on_submit(self, i):
        try:
            v = max(0, min(99, int(self.limit.value)))
            await self.vc.edit(user_limit=v)
            t = "unlimited" if v == 0 else str(v)
            await i.response.send_message(view=reply_text(f"{Emojis.VM_LIMIT} Limit set to **{t}**"), ephemeral=True)
        except:
            await i.response.send_message(view=reply_text(f"{Emojis.ERROR} Invalid number."), ephemeral=True)


class UserActionModal(discord.ui.Modal):
    user_input = discord.ui.TextInput(label="User ID or Username", placeholder="Enter user...", max_length=100)
    def __init__(self, vc, guild, action):
        super().__init__(title=f"{action.title()} User")
        self.vc = vc
        self.guild = guild
        self.action = action
    async def on_submit(self, i):
        raw = self.user_input.value.strip()
        member = None
        try:
            member = self.guild.get_member(int(raw))
        except: pass
        if not member:
            rl = raw.lower()
            member = discord.utils.find(lambda m: m.name.lower() == rl or m.display_name.lower() == rl, self.guild.members)
        if not member:
            return await i.response.send_message(view=reply_text(f"{Emojis.ERROR} Member not found."), ephemeral=True)

        try:
            a = self.action
            if a in ("mute", "unmute", "deafen", "undeafen"):
                if not (member.voice and member.voice.channel == self.vc):
                    return await i.response.send_message(view=reply_text(f"{Emojis.ERROR} User not in your VC."), ephemeral=True)
                kw = {a if a in ("mute", "deafen") else a.replace("un",""): a.startswith("un") == False}
                if a == "mute":      await member.edit(mute=True);    em = Emojis.VM_MUTE
                elif a == "unmute":  await member.edit(mute=False);   em = Emojis.VM_UNMUTE
                elif a == "deafen":  await member.edit(deafen=True);  em = Emojis.VM_DEAFEN
                elif a == "undeafen":await member.edit(deafen=False); em = Emojis.VM_UNDEAFEN
                msg = f"{em} {member.display_name} {a}d"
            elif a == "permit":
                ow = self.vc.overwrites_for(member)
                ow.connect = True; ow.view_channel = True
                await self.vc.set_permissions(member, overwrite=ow)
                msg = f"{Emojis.VM_PERMIT} {member.display_name} permitted"
            elif a == "ban":
                ow = self.vc.overwrites_for(member)
                ow.connect = False; ow.view_channel = False
                await self.vc.set_permissions(member, overwrite=ow)
                if member.voice and member.voice.channel == self.vc:
                    await member.move_to(None)
                msg = f"{Emojis.VM_BAN} {member.display_name} banned"
            else:
                msg = "Done"
            await i.response.send_message(view=reply_text(msg), ephemeral=True)
        except Exception as e:
            await i.response.send_message(view=reply_text(f"{Emojis.ERROR} `{e}`"), ephemeral=True)


class TransferModal(discord.ui.Modal, title="Transfer Ownership"):
    user_input = discord.ui.TextInput(label="User ID or Username", max_length=100)
    def __init__(self, vc, guild, config, owner):
        super().__init__()
        self.vc = vc; self.guild = guild
        self.config = config; self.owner = owner
    async def on_submit(self, i):
        raw = self.user_input.value.strip()
        member = None
        try: member = self.guild.get_member(int(raw))
        except: pass
        if not member:
            rl = raw.lower()
            member = discord.utils.find(lambda m: m.name.lower() == rl or m.display_name.lower() == rl, self.guild.members)
        if not member:
            return await i.response.send_message(view=reply_text(f"{Emojis.ERROR} Member not found."), ephemeral=True)
        if member.id == self.owner.id:
            return await i.response.send_message(view=reply_text(f"{Emojis.ERROR} Can't transfer to yourself."), ephemeral=True)
        if not (member.voice and member.voice.channel == self.vc):
            return await i.response.send_message(view=reply_text(f"{Emojis.ERROR} Member must be in your VC."), ephemeral=True)

        tc = self.config.get("temp_channels", {})
        tc.pop(str(self.owner.id), None)
        tc[str(member.id)] = self.vc.id
        self.config["temp_channels"] = tc
        set_guild_vm(self.guild.id, self.config)
        await i.response.send_message(view=reply_text(f"{Emojis.VM_TRANSFER} Ownership → {member.display_name}"), ephemeral=True)


# ─── Action Handler ───
async def handle_action(interaction: discord.Interaction, action: str):
    member = interaction.user
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} Server only."), ephemeral=True)

    config = get_guild_vm(guild.id)
    if not config:
        return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} VoiceMaster not configured."), ephemeral=True)

    temp_channels = config.get("temp_channels", {})

    # CLAIM
    if action == "claim":
        if not (member.voice and member.voice.channel):
            return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} Join a VC first."), ephemeral=True)
        vc = member.voice.channel
        owner_id = next((uid for uid, vid in temp_channels.items() if vid == vc.id), None)
        if not owner_id:
            return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} Not a temp channel."), ephemeral=True)
        owner = guild.get_member(int(owner_id))
        if owner and owner.voice and owner.voice.channel == vc:
            return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} Owner still here."), ephemeral=True)
        temp_channels.pop(owner_id, None)
        temp_channels[str(member.id)] = vc.id
        config["temp_channels"] = temp_channels
        set_guild_vm(guild.id, config)
        return await interaction.response.send_message(view=reply_text(f"{Emojis.VM_CLAIM} You claimed **{vc.name}**"), ephemeral=True)

    # Ownership check
    vc_id = temp_channels.get(str(member.id))
    if not vc_id:
        return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} You don't own a VC. Join the JTC channel first."), ephemeral=True)

    vc = guild.get_channel(vc_id)
    if not vc:
        temp_channels.pop(str(member.id), None)
        config["temp_channels"] = temp_channels
        set_guild_vm(guild.id, config)
        return await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} Your VC no longer exists."), ephemeral=True)

    try:
        if action == "lock":
            ow = vc.overwrites_for(guild.default_role); ow.connect = False
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(view=reply_text(f"{Emojis.VM_LOCK} Locked"), ephemeral=True)
        elif action == "unlock":
            ow = vc.overwrites_for(guild.default_role); ow.connect = True
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(view=reply_text(f"{Emojis.VM_UNLOCK} Unlocked"), ephemeral=True)
        elif action == "hide":
            ow = vc.overwrites_for(guild.default_role); ow.view_channel = False
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(view=reply_text(f"{Emojis.VM_HIDE} Hidden"), ephemeral=True)
        elif action == "unhide":
            ow = vc.overwrites_for(guild.default_role); ow.view_channel = True
            await vc.set_permissions(guild.default_role, overwrite=ow)
            await interaction.response.send_message(view=reply_text(f"{Emojis.VM_UNHIDE} Visible"), ephemeral=True)
        elif action == "rename":
            await interaction.response.send_modal(RenameModal(vc))
        elif action == "limit":
            await interaction.response.send_modal(LimitModal(vc))
        elif action in ("mute", "unmute", "deafen", "undeafen", "permit", "ban"):
            await interaction.response.send_modal(UserActionModal(vc, guild, action))
        elif action == "transfer":
            await interaction.response.send_modal(TransferModal(vc, guild, config, member))
    except Exception as e:
        try: await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} `{e}`"), ephemeral=True)
        except: pass


# ─── Interface Panel View ───
class VMInterfaceView(discord.ui.LayoutView):
    def __init__(self, enabled_buttons):
        super().__init__(timeout=None)
        self.enabled = enabled_buttons
        self._build()

    def _build(self):
        self.clear_items()

        # Description text
        desc_lines = [f"{Emojis.SETTINGS} **VoiceMaster Interface**", "Use the buttons below to manage your voice channel.", ""]
        desc_lines.append("**__Control Buttons__**")
        for b in self.enabled:
            desc_lines.append(f"{BTN_EMOJI[b]} — {BTN_DESC[b]}")

        container = MatrixContainer(
            text("\n".join(desc_lines)),
            make_separator()
        )

        # Add buttons (5 per row)
        chunks = [self.enabled[i:i+5] for i in range(0, len(self.enabled), 5)]
        for chunk in chunks:
            row = discord.ui.ActionRow()
            for b in chunk:
                btn = discord.ui.Button(
                    emoji=BTN_EMOJI[b],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"vm_btn_{b}"
                )
                row.add_item(btn)
            container.add_item(row)

        container.add_item(make_separator())
        container.add_item(text(f"-# Powered by {Config.BOT_NAME} Development"))

        self.add_item(container)

    async def interaction_check(self, interaction):
        cid = interaction.data.get("custom_id", "")
        if cid.startswith("vm_btn_"):
            await handle_action(interaction, cid[7:])
        return False


# ─── Setup View ───
class VMSetupView(discord.ui.LayoutView):
    def __init__(self, ctx, bot):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bot = bot
        self._build()

    def _build(self):
        self.clear_items()
        opts = [discord.SelectOption(label=BTN_LABELS[k], value=k, emoji=BTN_EMOJI[k]) for k in BTN_LABELS]
        opts.append(discord.SelectOption(label="Enable All", value="enable_all", emoji=Emojis.SUCCESS))

        select = discord.ui.Select(
            placeholder="Select buttons to enable...",
            min_values=1, max_values=len(opts),
            options=opts, custom_id="vm_setup_sel"
        )

        container = MatrixContainer(
            text(f"### {Emojis.SETTINGS}  VoiceMaster Setup"),
            make_separator(),
            text(
                "**Select the buttons you want to enable for the VoiceMaster system.**\n\n"
                "Select `Enable All` to enable everything, or choose specific buttons."
            ),
            make_separator(),
            discord.ui.ActionRow(select),
            make_separator(),
            text(f"-# Powered by {Config.BOT_NAME} Development")
        )
        self.add_item(container)

    async def interaction_check(self, interaction):
        if interaction.data.get("custom_id") != "vm_setup_sel": return False
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(view=reply_text(f"{Emojis.ERROR} Not your setup."), ephemeral=True)
            return False

        selected = interaction.data["values"]
        enabled = ALL_BUTTONS.copy() if "enable_all" in selected else [v for v in selected if v in ALL_BUTTONS]

        await interaction.response.defer()
        guild = interaction.guild
        try:
            category = await guild.create_category("VoiceMaster")
            trigger_vc = await guild.create_voice_channel(name="Join to Create", category=category)
            interface_ch = await guild.create_text_channel(
                name="interface", category=category,
                overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)}
            )

            cfg = {
                "trigger_vc": trigger_vc.id,
                "interface_ch": interface_ch.id,
                "category": category.id,
                "enabled_buttons": enabled,
                "temp_channels": {}
            }
            set_guild_vm(guild.id, cfg)

            iface = VMInterfaceView(enabled)
            await interface_ch.send(view=iface)
            self.bot.add_view(iface)

            done = discord.ui.LayoutView()
            done.add_item(MatrixContainer(
                text(f"### {Emojis.SUCCESS}  VoiceMaster Setup Complete"),
                make_separator(),
                text(
                    f"{Emojis.VOICE_MIC} **Trigger VC:** {trigger_vc.mention}\n"
                    f"{Emojis.CHANNEL} **Interface:** {interface_ch.mention}\n"
                    f"{Emojis.CATEGORY} **Category:** `{category.name}`\n"
                    f"{Emojis.ARROW} **Buttons:** `{len(enabled)}`"
                )
            ))
            await interaction.followup.send(view=done)
        except Exception as e:
            await interaction.followup.send(view=reply_text(f"{Emojis.ERROR} Setup failed: `{e}`"))

        return False


# ─── Main Cog ───
class VoiceMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        data = load_vm()
        for gid, cfg in data.items():
            enabled = cfg.get("enabled_buttons", ALL_BUTTONS)
            if enabled:
                self.bot.add_view(VMInterfaceView(enabled))

    @commands.group(name="voicemaster", aliases=["vm", "jtc"], invoke_without_command=True)
    @commands.guild_only()
    async def voicemaster(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.VOICE_MIC}  {Config.BOT_NAME} VoiceMaster"),
            make_separator(),
            text(
                f"`{Config.PREFIX}vm setup` — Setup VoiceMaster system\n"
                f"`{Config.PREFIX}vm config` — View current configuration\n"
                f"`{Config.PREFIX}vm reset` — Reset VoiceMaster system\n"
                f"`{Config.PREFIX}vm buttons` — Reconfigure buttons"
            ),
            make_separator(),
            text(f"-# Powered by {Config.BOT_NAME} Development")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @voicemaster.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def vm_setup(self, ctx):
        if get_guild_vm(ctx.guild.id):
            return await send_v2(ctx, error_view(f"Already configured. Use `{Config.PREFIX}vm reset` first."))
        await ctx.send(view=VMSetupView(ctx, self.bot))

    @voicemaster.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def vm_config(self, ctx):
        cfg = get_guild_vm(ctx.guild.id)
        if not cfg:
            return await send_v2(ctx, error_view(f"Not configured. Use `{Config.PREFIX}vm setup`."))
        trigger = ctx.guild.get_channel(cfg.get("trigger_vc", 0))
        interface = ctx.guild.get_channel(cfg.get("interface_ch", 0))
        category = ctx.guild.get_channel(cfg.get("category", 0))
        enabled = cfg.get("enabled_buttons", [])
        temp = len(cfg.get("temp_channels", {}))

        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.SETTINGS}  VoiceMaster Configuration"),
            make_separator(),
            text(
                f"{Emojis.VOICE_MIC} **Trigger VC:** {trigger.mention if trigger else '`Not found`'}\n"
                f"{Emojis.CHANNEL} **Interface:** {interface.mention if interface else '`Not found`'}\n"
                f"{Emojis.CATEGORY} **Category:** {f'`{category.name}`' if category else '`Not found`'}\n"
                f"{Emojis.MEMBERS} **Active Channels:** `{temp}`\n"
                f"{Emojis.ARROW} **Enabled Buttons:** `{len(enabled)}/{len(ALL_BUTTONS)}`"
            )
        ))
        await send_v2(ctx, view)

    @voicemaster.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def vm_reset(self, ctx):
        cfg = get_guild_vm(ctx.guild.id)
        if not cfg:
            return await send_v2(ctx, error_view("VoiceMaster not configured."))

        for vid in cfg.get("temp_channels", {}).values():
            ch = ctx.guild.get_channel(vid)
            if ch:
                try: await ch.delete()
                except: pass
        for key in ("interface_ch", "trigger_vc", "category"):
            ch = ctx.guild.get_channel(cfg.get(key, 0))
            if ch:
                try: await ch.delete()
                except: pass
        del_guild_vm(ctx.guild.id)
        await send_v2(ctx, reply_text(f"{Emojis.SUCCESS} VoiceMaster reset successfully."))

    @voicemaster.command(name="buttons")
    @commands.has_permissions(administrator=True)
    async def vm_buttons(self, ctx):
        cfg = get_guild_vm(ctx.guild.id)
        if not cfg:
            return await send_v2(ctx, error_view(f"Not configured. Use `{Config.PREFIX}vm setup`."))
        await ctx.send(view=VMSetupView(ctx, self.bot))

    # ─── Voice State Listener ───
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        cfg = get_guild_vm(member.guild.id)
        if not cfg: return

        trigger_id = cfg.get("trigger_vc")
        category_id = cfg.get("category")
        temp_channels = cfg.get("temp_channels", {})

        # Join trigger
        if after.channel and after.channel.id == trigger_id:
            category = member.guild.get_channel(category_id)
            try:
                new_vc = await member.guild.create_voice_channel(
                    name=f"{member.display_name}'s Channel", category=category
                )
                await member.move_to(new_vc)
                temp_channels[str(member.id)] = new_vc.id
                cfg["temp_channels"] = temp_channels
                set_guild_vm(member.guild.id, cfg)
            except Exception as e:
                print(f"[VM] {e}")

        # Leave temp VC
        if before.channel and before.channel.id != trigger_id:
            if before.channel.id in temp_channels.values() and len(before.channel.members) == 0:
                try: await before.channel.delete(reason="VM: Empty temp")
                except: pass
                owner_key = next((u for u, v in temp_channels.items() if v == before.channel.id), None)
                if owner_key:
                    temp_channels.pop(owner_key, None)
                    cfg["temp_channels"] = temp_channels
                    set_guild_vm(member.guild.id, cfg)


async def setup(bot):
    await bot.add_cog(VoiceMaster(bot))