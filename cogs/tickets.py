import discord
from discord.ext import commands
from discord.ui import Modal, TextInput, Button, Select, ChannelSelect, RoleSelect
import json
import os
import io
import asyncio
from datetime import datetime
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import (
    MatrixContainer, make_separator, text,
    error_view, success_view, send_v2
)

DB_PATH = "data/tickets.json"
os.makedirs("data", exist_ok=True)


# ═══════════════════════════════════════════════
#  DATABASE HELPERS
# ═══════════════════════════════════════════════
# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(DB_PATH, dict)

def load_db() -> dict:
    return _cache.load()


def save_db(data: dict):
    _cache.save(data)


def default_guild_cfg() -> dict:
    return {
        "panel_style": None,
        "mode": None,
        "staff_role": None,
        "open_category": None,
        "closed_category": None,
        "log_channel": None,
        "transcript_channel": None,
        "panel_channel": None,
        "panel_message_id": None,
        "panel": {
            "title": "Support Ticket",
            "description": "Click the button below to open a ticket.",
            "image": "",
            "thumbnail": "",
            "footer": f"{Config.BOT_NAME} Ticket System",
        },
        "dropdown_categories": [],
        "counter": 0,
        "tickets": {},
    }


def get_guild_cfg(guild_id: int) -> dict:
    db = load_db()
    gid = str(guild_id)
    if gid not in db:
        db[gid] = default_guild_cfg()
        save_db(db)
    base = default_guild_cfg()
    changed = False
    for k, v in base.items():
        if k not in db[gid]:
            db[gid][k] = v
            changed = True
    if changed:
        save_db(db)
    return db[gid]


def update_guild_cfg(guild_id: int, **kwargs):
    db = load_db()
    gid = str(guild_id)
    if gid not in db:
        db[gid] = default_guild_cfg()
    db[gid].update(kwargs)
    save_db(db)


def update_panel(guild_id: int, **kwargs):
    db = load_db()
    gid = str(guild_id)
    if gid not in db:
        db[gid] = default_guild_cfg()
    db[gid]["panel"].update(kwargs)
    save_db(db)


def add_ticket(guild_id: int, channel_id: int, data: dict):
    db = load_db()
    gid = str(guild_id)
    db[gid]["tickets"][str(channel_id)] = data
    save_db(db)


def remove_ticket(guild_id: int, channel_id: int):
    db = load_db()
    gid = str(guild_id)
    db[gid]["tickets"].pop(str(channel_id), None)
    save_db(db)


def get_ticket(guild_id: int, channel_id: int):
    cfg = get_guild_cfg(guild_id)
    return cfg["tickets"].get(str(channel_id))


def update_ticket(guild_id: int, channel_id: int, **kwargs):
    db = load_db()
    gid = str(guild_id)
    if str(channel_id) in db[gid]["tickets"]:
        db[gid]["tickets"][str(channel_id)].update(kwargs)
        save_db(db)


def next_counter(guild_id: int) -> int:
    db = load_db()
    gid = str(guild_id)
    db[gid]["counter"] = db[gid].get("counter", 0) + 1
    save_db(db)
    return db[gid]["counter"]


# Helper: resolve channel from ChannelSelect value
async def resolve_channel(guild: discord.Guild, partial):
    """ChannelSelect returns AppCommandChannel sometimes - resolve to full channel."""
    ch = guild.get_channel(partial.id)
    if ch is None:
        try:
            ch = await guild.fetch_channel(partial.id)
        except Exception:
            return None
    return ch


# ═══════════════════════════════════════════════
#  MAIN OVERVIEW (Auto / Manual)
# ═══════════════════════════════════════════════
class TicketOverviewView(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        cfg = get_guild_cfg(author.guild.id)
        auto_used = 1 if cfg.get("panel_message_id") and cfg.get("panel_style") == "button" else 0
        manual_used = 1 if cfg.get("panel_message_id") and cfg.get("panel_style") == "dropdown" else 0

        container = MatrixContainer(
            text(f"## {Emojis.TICKET}  {Config.BOT_NAME} Ticket System"),
            text("Welcome to the most advanced and professional ticket management solution."),
            make_separator(),
            text(f"### {Emojis.DIAMOND} Option 1: Auto Setup (Recommended)"),
            text(
                f"The bot will automatically create a **Ticket Manager** role, "
                f"**Support/Closed** categories, and **Log** channels for you instantly."
            ),
            make_separator(),
            text(f"### {Emojis.TOOLS} Option 2: Manual Setup"),
            text(
                "Total control over your infrastructure. You choose the existing "
                "roles, categories, and logging channels manually."
            ),
            make_separator(),
            text(f"**Panels used:** Auto `{auto_used}/1` | Manual `{manual_used}/1`"),
            text(f"**Quick Tip:** Use `&tclose`, `&tadd`, `&tremove` inside ticket channels!"),
            make_separator(),
            text(f"-# {Emojis.PREMIUM} {Config.BOT_NAME} Premium Ticket System"),
            discord.ui.ActionRow(
                AutoSetupBtn(author),
                ManualSetupBtn(author),
            ),
        )
        self.add_item(container)


class AutoSetupBtn(Button):
    def __init__(self, author):
        super().__init__(style=discord.ButtonStyle.danger, label="Auto Setup", emoji=Emojis.DIAMOND)
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        cog: Ticket = interaction.client.get_cog("Ticket")
        await cog.run_auto_setup(interaction)


class ManualSetupBtn(Button):
    def __init__(self, author):
        super().__init__(style=discord.ButtonStyle.danger, label="Manual Setup", emoji=Emojis.TOOLS)
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        view = ManualStep1View(self.author)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  MANUAL SETUP - STEP 1: Panel Style
# ═══════════════════════════════════════════════
class ManualStep1View(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        container = MatrixContainer(
            text(f"## {Emojis.TICKET}  | Step 1: Select Panel Style"),
            make_separator(),
            text("How should users interact with the ticket panel?"),
            text(
                f"**Button:** Standard 'Open Ticket' button (Uses global categories/roles).\n"
                f"**Dropdown:** Professional menu with custom categories."
            ),
            make_separator(),
            text(f"{Config.BOT_NAME} Setup | {author.guild.name}"),
            discord.ui.ActionRow(
                PanelStyleBtn(author, "button", "Button System", discord.ButtonStyle.primary),
                PanelStyleBtn(author, "dropdown", "Dropdown System", discord.ButtonStyle.success),
            ),
        )
        self.add_item(container)


class PanelStyleBtn(Button):
    def __init__(self, author, style, label, btn_style):
        super().__init__(style=btn_style, label=label)
        self.author = author
        self.style_value = style

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        update_guild_cfg(interaction.guild.id, panel_style=self.style_value)
        view = ManualModeView(self.author)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  MANUAL MODE
# ═══════════════════════════════════════════════
class ManualModeView(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        container = MatrixContainer(
            text(f"## {Emojis.TICKET}  | Manual Setup: System Mode"),
            make_separator(),
            text(f"How should **{Config.BOT_NAME}** handle closed tickets?"),
            make_separator(),
            text(
                f"**Archive:** Tickets are moved to a 'Closed' category.\n"
                f"**Delete:** Tickets are permanently deleted 5s after closure."
            ),
            make_separator(),
            text(f"{Config.BOT_NAME} Setup | {author.guild.name}"),
            discord.ui.ActionRow(
                ModeBtn(author, "archive", "Archive Mode", discord.ButtonStyle.success),
                ModeBtn(author, "delete", "Delete Mode", discord.ButtonStyle.danger),
            ),
        )
        self.add_item(container)


class ModeBtn(Button):
    def __init__(self, author, mode, label, style):
        super().__init__(style=style, label=label)
        self.author = author
        self.mode = mode

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        update_guild_cfg(interaction.guild.id, mode=self.mode)
        view = ManualStep2View(self.author)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  STEP 2: Infrastructure
# ═══════════════════════════════════════════════
class ManualStep2View(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        cfg = get_guild_cfg(author.guild.id)
        mode = cfg.get("mode", "archive").capitalize()

        container = MatrixContainer(
            text(f"## {Emojis.TICKET}  | Ticket Setup: Step 2 (Infrastructure)"),
            make_separator(),
            text(f"Mode: **{mode}**. Select **Staff Role** and **Open Category**."),
            make_separator(),
            text(f"{Config.BOT_NAME} Setup | {author.guild.name}"),
            discord.ui.ActionRow(StaffRolePicker(author)),
            discord.ui.ActionRow(OpenCategoryPicker(author)),
            discord.ui.ActionRow(NextStepBtn(author)),
        )
        self.add_item(container)


class StaffRolePicker(RoleSelect):
    def __init__(self, author):
        super().__init__(placeholder="Select Staff Role", min_values=1, max_values=1)
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        update_guild_cfg(interaction.guild.id, staff_role=self.values[0].id)
        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Staff role set to {self.values[0].mention}", ephemeral=True
        )


class OpenCategoryPicker(ChannelSelect):
    def __init__(self, author):
        super().__init__(
            channel_types=[discord.ChannelType.category],
            placeholder="Select Open Category",
            min_values=1, max_values=1,
        )
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        ch = await resolve_channel(interaction.guild, self.values[0])
        update_guild_cfg(interaction.guild.id, open_category=self.values[0].id)
        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Open category set to **{ch.name if ch else self.values[0].name}**", ephemeral=True
        )


class NextStepBtn(Button):
    def __init__(self, author):
        super().__init__(style=discord.ButtonStyle.primary, label="Next Step")
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        cfg = get_guild_cfg(interaction.guild.id)
        if not cfg.get("staff_role") or not cfg.get("open_category"):
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Please select both Staff Role and Open Category first.",
                ephemeral=True,
            )
        if cfg.get("mode") == "archive" and not cfg.get("closed_category"):
            view = ClosedCategoryView(self.author)
        else:
            view = ManualStep3View(self.author)
        await interaction.response.edit_message(view=view)


class ClosedCategoryView(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        container = MatrixContainer(
            text(f"## {Emojis.CATEGORY}  | Select Closed Category"),
            make_separator(),
            text("Archive Mode is selected. Choose the category where **closed tickets** will be moved."),
            make_separator(),
            discord.ui.ActionRow(ClosedCategoryPicker(author)),
            discord.ui.ActionRow(GoToStep3Btn(author)),
        )
        self.add_item(container)


class ClosedCategoryPicker(ChannelSelect):
    def __init__(self, author):
        super().__init__(
            channel_types=[discord.ChannelType.category],
            placeholder="Select Closed Category",
            min_values=1, max_values=1,
        )
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        ch = await resolve_channel(interaction.guild, self.values[0])
        update_guild_cfg(interaction.guild.id, closed_category=self.values[0].id)
        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Closed category set to **{ch.name if ch else self.values[0].name}**", ephemeral=True
        )


class GoToStep3Btn(Button):
    def __init__(self, author):
        super().__init__(style=discord.ButtonStyle.primary, label="Next Step")
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        cfg = get_guild_cfg(interaction.guild.id)
        if not cfg.get("closed_category"):
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Please select the Closed Category first.", ephemeral=True
            )
        view = ManualStep3View(self.author)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  STEP 3: Logging
# ═══════════════════════════════════════════════
class ManualStep3View(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        container = MatrixContainer(
            text(f"## {Emojis.TICKET}  | Ticket Setup: Step 3 (Logging)"),
            make_separator(),
            text(f"Select channels for **Logs** and **Transcripts**."),
            make_separator(),
            text(f"{Config.BOT_NAME} Setup | {author.guild.name}"),
            discord.ui.ActionRow(LogChannelPicker(author)),
            discord.ui.ActionRow(TranscriptChannelPicker(author)),
            discord.ui.ActionRow(NextCustomizeBtn(author)),
        )
        self.add_item(container)


class LogChannelPicker(ChannelSelect):
    def __init__(self, author):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder="Select Log Channel",
            min_values=1, max_values=1,
        )
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        ch = await resolve_channel(interaction.guild, self.values[0])
        update_guild_cfg(interaction.guild.id, log_channel=self.values[0].id)
        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Log channel set to {ch.mention if ch else f'<#{self.values[0].id}>'}", ephemeral=True
        )


class TranscriptChannelPicker(ChannelSelect):
    def __init__(self, author):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder="Select Transcript Channel",
            min_values=1, max_values=1,
        )
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        ch = await resolve_channel(interaction.guild, self.values[0])
        update_guild_cfg(interaction.guild.id, transcript_channel=self.values[0].id)
        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Transcript channel set to {ch.mention if ch else f'<#{self.values[0].id}>'}", ephemeral=True
        )


class NextCustomizeBtn(Button):
    def __init__(self, author):
        super().__init__(style=discord.ButtonStyle.primary, label="Next: Customize Panel")
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
        cfg = get_guild_cfg(interaction.guild.id)
        if not cfg.get("log_channel") or not cfg.get("transcript_channel"):
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Please select both Log and Transcript channels first.", ephemeral=True
            )
        await interaction.response.send_modal(CustomizePanelModal(self.author, from_setup=True))


# ═══════════════════════════════════════════════
#  CUSTOMIZE PANEL MODAL
# ═══════════════════════════════════════════════
class CustomizePanelModal(Modal, title="Customize Ticket Panel"):
    def __init__(self, author, from_setup: bool = False):
        super().__init__()
        self.author = author
        self.from_setup = from_setup
        cfg = get_guild_cfg(author.guild.id)
        p = cfg["panel"]

        self.t_title = TextInput(label="Title", default=p.get("title", "Support Ticket"), required=True, max_length=256)
        self.t_desc = TextInput(
            label="Description", style=discord.TextStyle.paragraph,
            default=p.get("description", ""), required=True, max_length=4000,
        )
        self.t_image = TextInput(label="Image URL", default=p.get("image", ""), required=False)
        self.t_thumb = TextInput(label="Thumbnail URL", default=p.get("thumbnail", ""), required=False)
        self.t_footer = TextInput(label="Footer", default=p.get("footer", ""), required=False, max_length=2048)

        self.add_item(self.t_title)
        self.add_item(self.t_desc)
        self.add_item(self.t_image)
        self.add_item(self.t_thumb)
        self.add_item(self.t_footer)

    async def on_submit(self, interaction):
        update_panel(
            interaction.guild.id,
            title=self.t_title.value,
            description=self.t_desc.value,
            image=self.t_image.value,
            thumbnail=self.t_thumb.value,
            footer=self.t_footer.value,
        )
        if self.from_setup:
            view = FinalTargetView(self.author)
            await interaction.response.edit_message(view=view)
        else:
            v = discord.ui.LayoutView()
            v.add_item(MatrixContainer(
                text(f"## {Emojis.SUCCESS}  Panel Updated"),
                make_separator(),
                text("Your panel customization has been saved. Use `&tpanel` to redeploy it."),
            ))
            await interaction.response.send_message(view=v, ephemeral=True)


# ═══════════════════════════════════════════════
#  FINAL TARGET CHANNEL
# ═══════════════════════════════════════════════
class FinalTargetView(discord.ui.LayoutView):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        container = MatrixContainer(
            text(f"## {Emojis.TICKET}  Final Step: Target Channel"),
            make_separator(),
            text("Select the channel where you want to post the **Ticket Panel**."),
            make_separator(),
            text(f"Requested by {author.name} • <t:{int(datetime.utcnow().timestamp())}:t>"),
            discord.ui.ActionRow(TargetChannelPicker(author)),
        )
        self.add_item(container)


class TargetChannelPicker(ChannelSelect):
    def __init__(self, author):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder="Select Target Channel",
            min_values=1, max_values=1,
        )
        self.author = author

    async def callback(self, interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)

        # Defer first so we don't lose the interaction
        await interaction.response.defer(ephemeral=True)

        ch = await resolve_channel(interaction.guild, self.values[0])
        if ch is None:
            return await interaction.followup.send(
                f"{Emojis.ERROR} Could not resolve the selected channel.", ephemeral=True
            )

        update_guild_cfg(interaction.guild.id, panel_channel=ch.id)
        cog: Ticket = interaction.client.get_cog("Ticket")

        try:
            await cog.deploy_panel(interaction.guild, ch)
        except Exception as e:
            return await interaction.followup.send(
                f"{Emojis.ERROR} Failed to deploy panel: `{e}`", ephemeral=True
            )

        # Edit the original setup message to show completion
        complete_view = discord.ui.LayoutView()
        complete_view.add_item(MatrixContainer(
            text(f"## {Emojis.SUCCESS}  | Setup Complete!"),
            make_separator(),
            text(
                f"Congratulations! Your **{Config.BOT_NAME} Ticket System** is now "
                f"live. The panel has been successfully posted in {ch.mention}."
            ),
            make_separator(),
            text(f"-# {Config.BOT_NAME} Ticket System | Deployment Successful"),
        ))
        try:
            await interaction.edit_original_response(view=complete_view)
        except Exception:
            await interaction.followup.send(view=complete_view, ephemeral=True)


# ═══════════════════════════════════════════════
#  TICKET PANEL (Public)
# ═══════════════════════════════════════════════
class TicketPanelView(discord.ui.LayoutView):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        cfg = get_guild_cfg(guild_id)
        p = cfg["panel"]

        children = [
            text(f"## {p.get('title', 'Support Ticket')}"),
            make_separator(),
            text(p.get("description", "Click below to open a ticket.")),
        ]
        if p.get("thumbnail"):
            try:
                children.append(discord.ui.MediaGallery(discord.MediaGalleryItem(p["thumbnail"])))
            except Exception:
                pass
        if p.get("image"):
            try:
                children.append(discord.ui.MediaGallery(discord.MediaGalleryItem(p["image"])))
            except Exception:
                pass

        children.append(make_separator())
        footer = p.get("footer") or f"{Config.BOT_NAME} Ticket System"
        children.append(text(f"-# {footer} • <t:{int(datetime.utcnow().timestamp())}:t>"))

        if cfg.get("panel_style") == "dropdown" and cfg.get("dropdown_categories"):
            children.append(discord.ui.ActionRow(TicketCategoryDropdown(guild_id)))
        else:
            children.append(discord.ui.ActionRow(OpenTicketBtn()))

        container = MatrixContainer(*children)
        self.add_item(container)


class OpenTicketBtn(Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Open Ticket",
            emoji=Emojis.TICKET,
            custom_id="matrix_open_ticket",
        )

    async def callback(self, interaction):
        await interaction.response.send_modal(OpenTicketModal(category=None))


class TicketCategoryDropdown(Select):
    def __init__(self, guild_id: int):
        cfg = get_guild_cfg(guild_id)
        options = []
        for cat in cfg.get("dropdown_categories", []):
            options.append(discord.SelectOption(
                label=cat["name"],
                description=cat.get("description", "")[:100] or None,
                emoji=cat.get("emoji") or Emojis.TICKET,
                value=cat["name"],
            ))
        if not options:
            options = [discord.SelectOption(label="General Support", value="General Support")]
        super().__init__(
            placeholder="Select a category...",
            options=options,
            custom_id="matrix_ticket_dropdown",
        )

    async def callback(self, interaction):
        await interaction.response.send_modal(OpenTicketModal(category=self.values[0]))


class OpenTicketModal(Modal, title="Support Ticket"):
    def __init__(self, category):
        super().__init__()
        self.category = category
        self.issue = TextInput(
            label="What is your issue?",
            placeholder="Explain your query in detail...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
        )
        self.add_item(self.issue)

    async def on_submit(self, interaction):
        cog: Ticket = interaction.client.get_cog("Ticket")
        await cog.create_ticket(interaction, self.issue.value, self.category)


# ═══════════════════════════════════════════════
#  TICKET CHANNEL WELCOME VIEW
# ═══════════════════════════════════════════════
class TicketChannelView(discord.ui.LayoutView):
    def __init__(self, guild_id: int, channel_id: int, member: discord.Member, issue: str, category):
        super().__init__(timeout=None)
        cfg = get_guild_cfg(guild_id)
        staff_role_id = cfg.get("staff_role")
        tk = get_ticket(guild_id, channel_id)
        ticket_num = tk.get("number", 1) if tk else 1
        title = cfg["panel"].get("title", "Support Ticket")

        ping_line = f"{member.mention} | <@&{staff_role_id}>" if staff_role_id else member.mention
        welcome_line = (
            f"Welcome {member.mention}! Our support team (<@&{staff_role_id}>) will assist you shortly."
            if staff_role_id else
            f"Welcome {member.mention}! Our support team will assist you shortly."
        )

        children = [
            text(f"## {title} - Ticket #{ticket_num}"),
            make_separator(),
            text(ping_line),
            text(welcome_line),
            make_separator(),
            text("**Issue Submitted:**"),
            text(f"> {issue}"),
        ]
        if category:
            children.append(text(f"**Category:** {category}"))
        children.append(make_separator())
        children.append(text(f"-# {Emojis.SPARKLE} {Config.BOT_NAME} Ticket System"))
        children.append(discord.ui.ActionRow(
            CloseTicketBtn(),
            ClaimTicketBtn(),
            NotifyTicketBtn(),
        ))
        children.append(discord.ui.ActionRow(DeleteTicketBtn()))

        container = MatrixContainer(*children)
        self.add_item(container)


class CloseTicketBtn(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Close", emoji=Emojis.LOCK, custom_id="matrix_t_close")

    async def callback(self, interaction):
        cog: Ticket = interaction.client.get_cog("Ticket")
        await cog.close_ticket(interaction)


class ClaimTicketBtn(Button):
    def __init__(self):
        emoji = Emojis.STAFF if hasattr(Emojis, "STAFF") else Emojis.MOD
        super().__init__(style=discord.ButtonStyle.primary, label="Claim", emoji=emoji, custom_id="matrix_t_claim")

    async def callback(self, interaction):
        cog: Ticket = interaction.client.get_cog("Ticket")
        await cog.claim_ticket(interaction)


class NotifyTicketBtn(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="Notify/Call", emoji=Emojis.BELL, custom_id="matrix_t_notify")

    async def callback(self, interaction):
        cog: Ticket = interaction.client.get_cog("Ticket")
        await cog.notify_ticket(interaction)


class DeleteTicketBtn(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Delete", emoji=Emojis.TRASH, custom_id="matrix_t_delete")

    async def callback(self, interaction):
        cog: Ticket = interaction.client.get_cog("Ticket")
        await cog.delete_ticket(interaction)


# ═══════════════════════════════════════════════
#  COG
# ═══════════════════════════════════════════════
class Ticket(commands.Cog):
    """MATRIX AIO Ticket System."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        try:
            self.bot.add_view(self._panel_persistent())
            self.bot.add_view(self._channel_persistent())
        except Exception as e:
            print(f"[Ticket] persistent view register failed: {e}")

    def _panel_persistent(self):
        v = discord.ui.View(timeout=None)
        v.add_item(OpenTicketBtn())
        return v

    def _channel_persistent(self):
        v = discord.ui.View(timeout=None)
        v.add_item(CloseTicketBtn())
        v.add_item(ClaimTicketBtn())
        v.add_item(NotifyTicketBtn())
        v.add_item(DeleteTicketBtn())
        return v

    # ─── Auto Setup ───
    async def run_auto_setup(self, interaction: discord.Interaction):
        guild = interaction.guild
        try:
            role = discord.utils.get(guild.roles, name="Ticket Manager")
            if not role:
                role = await guild.create_role(name="Ticket Manager", color=discord.Color.red(), reason=f"{Config.BOT_NAME} auto setup")
            open_cat = discord.utils.get(guild.categories, name="Support")
            if not open_cat:
                open_cat = await guild.create_category("Support")
            closed_cat = discord.utils.get(guild.categories, name="Closed")
            if not closed_cat:
                closed_cat = await guild.create_category("Closed")
            log = discord.utils.get(guild.text_channels, name="ticket-logs")
            if not log:
                log = await guild.create_text_channel("ticket-logs", category=closed_cat)
            transcript = discord.utils.get(guild.text_channels, name="ticket-transcripts")
            if not transcript:
                transcript = await guild.create_text_channel("ticket-transcripts", category=closed_cat)
        except Exception as e:
            return await interaction.followup.send(f"{Emojis.ERROR} Setup failed: `{e}`", ephemeral=True)

        update_guild_cfg(
            guild.id,
            panel_style="button",
            mode="archive",
            staff_role=role.id,
            open_category=open_cat.id,
            closed_category=closed_cat.id,
            log_channel=log.id,
            transcript_channel=transcript.id,
        )
        await interaction.followup.send(
            f"{Emojis.SUCCESS} Auto setup complete!\n"
            f"**Role:** {role.mention}\n"
            f"**Open:** {open_cat.name} | **Closed:** {closed_cat.name}\n"
            f"**Log:** {log.mention} | **Transcript:** {transcript.mention}\n\n"
            f"Now run `&tpanel` in the channel where you want the panel to be posted.",
            ephemeral=True,
        )

    # ─── Deploy Panel ───
    async def deploy_panel(self, guild: discord.Guild, channel: discord.TextChannel):
        # Make sure channel is a full TextChannel
        if not isinstance(channel, discord.TextChannel):
            real = guild.get_channel(channel.id) or await guild.fetch_channel(channel.id)
            channel = real
        view = TicketPanelView(guild.id)
        msg = await channel.send(view=view)
        update_guild_cfg(guild.id, panel_channel=channel.id, panel_message_id=msg.id)
        return msg

    # ─── Create Ticket ───
    async def create_ticket(self, interaction: discord.Interaction, issue: str, category):
        guild = interaction.guild
        member = interaction.user
        cfg = get_guild_cfg(guild.id)

        if not cfg.get("open_category") or not cfg.get("staff_role"):
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Ticket system not fully configured.", ephemeral=True
            )

        for ch_id, tk in cfg.get("tickets", {}).items():
            if tk.get("user_id") == member.id and not tk.get("closed"):
                existing = guild.get_channel(int(ch_id))
                if existing:
                    return await interaction.response.send_message(
                        f"{Emojis.ERROR} You already have an open ticket: {existing.mention}", ephemeral=True
                    )

        await interaction.response.defer(ephemeral=True)

        open_cat = guild.get_channel(cfg["open_category"])
        staff_role = guild.get_role(cfg["staff_role"])
        number = next_counter(guild.id)
        name = f"ticket-{number:04d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True,
                embed_links=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, manage_messages=True
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_messages=True, attach_files=True,
                embed_links=True, read_message_history=True
            )

        try:
            ticket_channel = await guild.create_text_channel(
                name=name,
                category=open_cat,
                overwrites=overwrites,
                reason=f"Ticket opened by {member}",
            )
        except Exception as e:
            return await interaction.followup.send(
                f"{Emojis.ERROR} Failed to create ticket channel: `{e}`", ephemeral=True
            )

        add_ticket(guild.id, ticket_channel.id, {
            "user_id": member.id,
            "number": number,
            "issue": issue,
            "category": category,
            "claimed_by": None,
            "notified": False,
            "closed": False,
            "created_at": datetime.utcnow().isoformat(),
        })

        # ─── SEND WELCOME MESSAGE (FIXED) ───
        # First, send a plain ping message so notifications fire
        try:
            ping_text = f"{member.mention}"
            if staff_role:
                ping_text += f" {staff_role.mention}"
            await ticket_channel.send(
                content=ping_text,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True),
            )
        except Exception as e:
            print(f"[Ticket] ping send failed: {e}")

        # Then send the welcome view (Components V2 - cannot have content)
        try:
            welcome_view = TicketChannelView(guild.id, ticket_channel.id, member, issue, category)
            await ticket_channel.send(view=welcome_view)
        except Exception as e:
            print(f"[Ticket] welcome view send failed: {e}")
            # Fallback: plain welcome
            try:
                await ticket_channel.send(
                    f"**Welcome to your ticket, {member.mention}!**\n"
                    f"**Issue:** {issue}\n"
                    f"Staff will be with you shortly."
                )
            except Exception:
                pass

        # Log
        log_ch = guild.get_channel(cfg.get("log_channel")) if cfg.get("log_channel") else None
        if log_ch:
            try:
                log_view = discord.ui.LayoutView()
                log_view.add_item(MatrixContainer(
                    text(f"## {Emojis.TICKET}  Ticket Created"),
                    make_separator(),
                    text(f"**Ticket**\n{ticket_channel.mention} (`#{name}`)"),
                    text(f"**Creator**\n{member.mention} ({member.name})"),
                    text(f"**Category**\n{category or 'General Support'}"),
                    make_separator(),
                    text(f"-# <t:{int(datetime.utcnow().timestamp())}:t>"),
                ))
                await log_ch.send(view=log_view)
            except Exception as e:
                print(f"[Ticket] log send failed: {e}")

        await interaction.followup.send(
            f"{Emojis.SUCCESS} | Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True,
        )

    # ─── Claim ───
    async def claim_ticket(self, interaction: discord.Interaction):
        cfg = get_guild_cfg(interaction.guild.id)
        staff_role_id = cfg.get("staff_role")
        if not staff_role_id or staff_role_id not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Only staff can claim tickets.", ephemeral=True
            )
        tk = get_ticket(interaction.guild.id, interaction.channel.id)
        if not tk:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not a ticket channel.", ephemeral=True)
        if tk.get("claimed_by"):
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Already claimed by <@{tk['claimed_by']}>", ephemeral=True
            )
        update_ticket(interaction.guild.id, interaction.channel.id, claimed_by=interaction.user.id)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"## {Emojis.SUCCESS}  Ticket Claimed"),
            make_separator(),
            text(f"This ticket has been claimed by {interaction.user.mention}."),
            text("They will assist you from now on."),
        ))
        await interaction.response.send_message(view=view)

    # ─── Notify ───
    async def notify_ticket(self, interaction: discord.Interaction):
        tk = get_ticket(interaction.guild.id, interaction.channel.id)
        if not tk:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not a ticket channel.", ephemeral=True)
        user = interaction.guild.get_member(tk["user_id"])
        if not user:
            return await interaction.response.send_message(f"{Emojis.ERROR} Ticket user not found.", ephemeral=True)
        await interaction.channel.send(
            f"{Emojis.BELL} {user.mention} — A staff member has responded. Please check your ticket!"
        )
        try:
            await user.send(
                f"{Emojis.BELL} Hey {user.mention}, a staff member has replied in your ticket "
                f"{interaction.channel.mention}. Please check it now!"
            )
        except Exception:
            pass
        update_ticket(interaction.guild.id, interaction.channel.id, notified=True)
        await interaction.response.send_message(f"{Emojis.SUCCESS} User notified.", ephemeral=True)

    # ─── Close ───
    async def close_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        cfg = get_guild_cfg(guild.id)
        tk = get_ticket(guild.id, interaction.channel.id)
        if not tk:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not a ticket channel.", ephemeral=True)
        if tk.get("closed"):
            return await interaction.response.send_message(f"{Emojis.ERROR} Already closed.", ephemeral=True)

        await interaction.response.defer()
        try:
            transcript_html = await self._generate_transcript(interaction.channel, tk)
            transcript_file = discord.File(io.BytesIO(transcript_html.encode("utf-8")),
                                           filename=f"{interaction.channel.name}.html")
            t_ch = guild.get_channel(cfg.get("transcript_channel")) if cfg.get("transcript_channel") else None
            if t_ch:
                user = guild.get_member(tk["user_id"])
                view = discord.ui.LayoutView()
                view.add_item(MatrixContainer(
                    text(f"## {Emojis.LOG_MSG_EDIT}  Ticket Transcript"),
                    make_separator(),
                    text(f"**Channel:** `{interaction.channel.name}`"),
                    text(f"**User:** {user.mention if user else tk['user_id']}"),
                    text(f"**Closed by:** {interaction.user.mention}"),
                    text(f"**Issue:** {tk.get('issue', 'N/A')}"),
                    make_separator(),
                    text(f"-# <t:{int(datetime.utcnow().timestamp())}:f>"),
                ))
                await t_ch.send(view=view, file=transcript_file)
        except Exception as e:
            print(f"[Ticket] transcript failed: {e}")

        update_ticket(guild.id, interaction.channel.id, closed=True)

        if cfg.get("mode") == "delete":
            await interaction.channel.send(f"{Emojis.WARNING} This channel will be deleted in 5 seconds...")
            await asyncio.sleep(5)
            try:
                await interaction.channel.delete(reason="Ticket closed (delete mode)")
            except Exception:
                pass
            remove_ticket(guild.id, interaction.channel.id)
        else:
            closed_cat = guild.get_channel(cfg.get("closed_category")) if cfg.get("closed_category") else None
            if closed_cat:
                try:
                    await interaction.channel.edit(category=closed_cat, name=f"closed-{interaction.channel.name}")
                except Exception:
                    pass
            user = guild.get_member(tk["user_id"])
            if user:
                try:
                    await interaction.channel.set_permissions(user, view_channel=False)
                except Exception:
                    pass
            await interaction.channel.send(f"{Emojis.LOCK} Ticket closed by {interaction.user.mention}.")

    # ─── Delete ───
    async def delete_ticket(self, interaction: discord.Interaction):
        cfg = get_guild_cfg(interaction.guild.id)
        staff_role_id = cfg.get("staff_role")
        if not staff_role_id or staff_role_id not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Only staff can delete tickets.", ephemeral=True
            )
        tk = get_ticket(interaction.guild.id, interaction.channel.id)
        if not tk:
            return await interaction.response.send_message(f"{Emojis.ERROR} Not a ticket channel.", ephemeral=True)
        await interaction.response.send_message(f"{Emojis.WARNING} Deleting ticket in 3 seconds...")
        await asyncio.sleep(3)
        remove_ticket(interaction.guild.id, interaction.channel.id)
        try:
            await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
        except Exception:
            pass

    # ─── Transcript ───
    async def _generate_transcript(self, channel: discord.TextChannel, tk: dict) -> str:
        messages = []
        try:
            async for m in channel.history(limit=None, oldest_first=True):
                messages.append(m)
        except Exception:
            pass

        rows = []
        for m in messages:
            author = m.author
            avatar = author.display_avatar.url
            ts = m.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = (m.content or "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            attachments = "".join(
                f'<div class="att"><a href="{a.url}" target="_blank">{a.filename}</a></div>'
                for a in m.attachments
            )
            rows.append(f"""
            <div class="msg">
                <img class="avatar" src="{avatar}" />
                <div class="content">
                    <div class="header"><span class="author">{author.display_name}</span> <span class="ts">{ts}</span></div>
                    <div class="text">{content}</div>
                    {attachments}
                </div>
            </div>
            """)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Transcript - {channel.name}</title>
<style>
body {{ background:#0d0d0d; color:#eee; font-family:'Segoe UI',sans-serif; padding:20px; }}
.header-top {{ background:#1a1a1a; border-left:4px solid #FF0000; padding:15px; border-radius:8px; margin-bottom:20px; }}
.header-top h1 {{ margin:0; color:#FF0000; }}
.msg {{ display:flex; gap:12px; padding:10px; border-bottom:1px solid #222; }}
.avatar {{ width:40px; height:40px; border-radius:50%; }}
.content {{ flex:1; }}
.header {{ font-size:14px; }}
.author {{ color:#FF4444; font-weight:bold; }}
.ts {{ color:#888; font-size:11px; margin-left:8px; }}
.text {{ margin-top:4px; color:#ddd; }}
.att a {{ color:#5BC0EB; }}
</style></head>
<body>
<div class="header-top">
    <h1>Matrix Ticket Transcript</h1>
    <div>Channel: #{channel.name}</div>
    <div>Issue: {tk.get('issue','N/A')}</div>
    <div>Total Messages: {len(messages)}</div>
</div>
{''.join(rows)}
</body></html>"""
        return html

    # ═══════════════════════════════════════════════
    #  COMMANDS
    # ═══════════════════════════════════════════════
    @commands.group(name="ticket", invoke_without_command=True)
    async def ticket_grp(self, ctx: commands.Context):
        view = TicketOverviewView(ctx.author)
        await send_v2(ctx, view)

    @ticket_grp.command(name="setup")
    async def ticket_setup(self, ctx: commands.Context):
        view = TicketOverviewView(ctx.author)
        await send_v2(ctx, view)

    @ticket_grp.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def ticket_reset(self, ctx: commands.Context):
        db = load_db()
        db.pop(str(ctx.guild.id), None)
        save_db(db)
        await send_v2(ctx, success_view("Ticket Config Reset",
                                        fields=[("Status:", "All settings cleared.")]))

    @ticket_grp.command(name="add")
    async def ticket_add(self, ctx: commands.Context, member: discord.Member):
        await self._add_user(ctx, member)

    @ticket_grp.command(name="remove")
    async def ticket_remove(self, ctx: commands.Context, member: discord.Member):
        await self._remove_user(ctx, member)

    @ticket_grp.command(name="rename")
    async def ticket_rename(self, ctx: commands.Context, *, name: str):
        tk = get_ticket(ctx.guild.id, ctx.channel.id)
        if not tk:
            return await send_v2(ctx, error_view("This is not a ticket channel."))
        try:
            await ctx.channel.edit(name=name)
            await send_v2(ctx, success_view("Ticket Renamed", fields=[("New Name:", f"`{name}`")]))
        except Exception as e:
            await send_v2(ctx, error_view(f"Failed to rename: {e}"))

    # ─── Shortcuts ───
    @commands.command(name="tadd")
    async def tadd(self, ctx, member: discord.Member):
        await self._add_user(ctx, member)

    @commands.command(name="tremove")
    async def tremove(self, ctx, member: discord.Member):
        await self._remove_user(ctx, member)

    @commands.command(name="tclose")
    async def tclose(self, ctx):
        tk = get_ticket(ctx.guild.id, ctx.channel.id)
        if not tk:
            return await send_v2(ctx, error_view("This is not a ticket channel."))
        if tk.get("closed"):
            return await send_v2(ctx, error_view("This ticket is already closed."))

        cfg = get_guild_cfg(ctx.guild.id)
        await ctx.send(f"{Emojis.LOCK} Closing ticket and generating transcript...")

        try:
            transcript_html = await self._generate_transcript(ctx.channel, tk)
            transcript_file = discord.File(io.BytesIO(transcript_html.encode("utf-8")),
                                           filename=f"{ctx.channel.name}.html")
            t_ch = ctx.guild.get_channel(cfg.get("transcript_channel")) if cfg.get("transcript_channel") else None
            if t_ch:
                user = ctx.guild.get_member(tk["user_id"])
                v = discord.ui.LayoutView()
                v.add_item(MatrixContainer(
                    text(f"## {Emojis.LOG_MSG_EDIT}  Ticket Transcript"),
                    make_separator(),
                    text(f"**Channel:** `{ctx.channel.name}`"),
                    text(f"**User:** {user.mention if user else tk['user_id']}"),
                    text(f"**Closed by:** {ctx.author.mention}"),
                    text(f"**Issue:** {tk.get('issue', 'N/A')}"),
                    make_separator(),
                    text(f"-# <t:{int(datetime.utcnow().timestamp())}:f>"),
                ))
                await t_ch.send(view=v, file=transcript_file)
        except Exception as e:
            print(f"[Ticket] tclose transcript failed: {e}")

        update_ticket(ctx.guild.id, ctx.channel.id, closed=True)

        if cfg.get("mode") == "delete":
            await asyncio.sleep(5)
            try:
                await ctx.channel.delete()
            except Exception:
                pass
            remove_ticket(ctx.guild.id, ctx.channel.id)
        else:
            closed_cat = ctx.guild.get_channel(cfg.get("closed_category")) if cfg.get("closed_category") else None
            if closed_cat:
                try:
                    await ctx.channel.edit(category=closed_cat, name=f"closed-{ctx.channel.name}")
                except Exception:
                    pass
            user = ctx.guild.get_member(tk["user_id"])
            if user:
                try:
                    await ctx.channel.set_permissions(user, view_channel=False)
                except Exception:
                    pass

    @commands.command(name="tdelete")
    @commands.has_permissions(manage_channels=True)
    async def tdelete(self, ctx):
        tk = get_ticket(ctx.guild.id, ctx.channel.id)
        if not tk:
            return await send_v2(ctx, error_view("This is not a ticket channel."))
        await ctx.send(f"{Emojis.WARNING} Deleting ticket...")
        await asyncio.sleep(3)
        remove_ticket(ctx.guild.id, ctx.channel.id)
        try:
            await ctx.channel.delete()
        except Exception:
            pass

    @commands.command(name="tpanel")
    @commands.has_permissions(administrator=True)
    async def tpanel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        try:
            await self.deploy_panel(ctx.guild, channel)
        except Exception as e:
            return await send_v2(ctx, error_view(f"Failed to deploy panel: {e}"))
        await send_v2(ctx, success_view("Panel Deployed", fields=[("Channel:", channel.mention)]))

    @commands.command(name="tedit")
    @commands.has_permissions(administrator=True)
    async def tedit(self, ctx):
        cfg = get_guild_cfg(ctx.guild.id)
        if not cfg.get("panel_style"):
            return await send_v2(ctx, error_view("Ticket system not configured.", usage="&ticket setup"))

        author = ctx.author

        class _OpenBtn(Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.primary, label="Open Editor", emoji=Emojis.PENCIL)

            async def callback(self, interaction):
                if interaction.user.id != author.id:
                    return await interaction.response.send_message(f"{Emojis.ERROR} Not your panel.", ephemeral=True)
                await interaction.response.send_modal(CustomizePanelModal(author, from_setup=False))

        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"## {Emojis.PENCIL}  Ticket Panel Editor"),
            make_separator(),
            text("Click below to open the interactive editor."),
            discord.ui.ActionRow(_OpenBtn()),
        ))
        await send_v2(ctx, view)

    # ─── Helpers ───
    async def _add_user(self, ctx, member: discord.Member):
        tk = get_ticket(ctx.guild.id, ctx.channel.id)
        if not tk:
            return await send_v2(ctx, error_view("This is not a ticket channel."))
        try:
            await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await send_v2(ctx, success_view("User Added", fields=[("Member:", member.mention)]))
        except Exception as e:
            await send_v2(ctx, error_view(f"Failed: {e}"))

    async def _remove_user(self, ctx, member: discord.Member):
        tk = get_ticket(ctx.guild.id, ctx.channel.id)
        if not tk:
            return await send_v2(ctx, error_view("This is not a ticket channel."))
        try:
            await ctx.channel.set_permissions(member, overwrite=None)
            await send_v2(ctx, success_view("User Removed", fields=[("Member:", member.mention)]))
        except Exception as e:
            await send_v2(ctx, error_view(f"Failed: {e}"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Ticket(bot))