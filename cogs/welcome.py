import discord
from discord.ext import commands
from discord.ui import Modal, TextInput, Button, Select, ChannelSelect
import json
import os
import re
from datetime import datetime
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import (
    MatrixContainer, make_separator, text,
    error_view, success_view, send_v2
)

DB_PATH = "data/welcome.json"
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


def get_guild_config(guild_id: int, action: str = "welcome") -> dict:
    db = load_db()
    gid = str(guild_id)
    if gid not in db:
        db[gid] = {}
    if action not in db[gid]:
        db[gid][action] = {
            "enabled": False,
            "channel_id": None,
            "thumbnail": True,
            "plain_text": "{user.mention}",
            "embed_title": "",
            "embed_desc": f"Welcome to **{{server.name}}**, {{user.mention}}!\n{{divider}}\nYou are member **#{{server.count_ordinal}}**.",
            "color": "#FF0000",
            "footer": "",
            "image": "",
        }
        save_db(db)
    return db[gid][action]


def update_guild_config(guild_id: int, action: str, **kwargs):
    db = load_db()
    gid = str(guild_id)
    if gid not in db:
        db[gid] = {}
    if action not in db[gid]:
        get_guild_config(guild_id, action)
        db = load_db()
    db[gid][action].update(kwargs)
    save_db(db)


# ═══════════════════════════════════════════════
#  PLACEHOLDER PARSER
# ═══════════════════════════════════════════════
def parse_placeholders(content: str, member: discord.Member) -> str:
    if not content:
        return ""
    guild = member.guild
    now = datetime.utcnow()
    ts = int(now.timestamp())

    def ordinal(n):
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    replacements = {
        "{user.mention}":      member.mention,
        "{user.username}":     member.name,
        "{user.name}":         member.display_name,
        "{user.id}":           str(member.id),
        "{user.created_at}":   f"<t:{int(member.created_at.timestamp())}:R>",
        "{server.name}":       guild.name,
        "{server.count}":      str(guild.member_count),
        "{server.count_ordinal}": ordinal(guild.member_count),
        "{server.vanity}":     guild.vanity_url or "None",
        "{server.id}":         str(guild.id),
        "{time}":              f"<t:{ts}:t>",
        "{time.relative}":     f"<t:{ts}:R>",
        "{time.short}":        f"<t:{ts}:f>",
        "{time.full}":         f"<t:{ts}:F>",
    }
    for k, v in replacements.items():
        content = content.replace(k, v)
    return content


def hex_to_int(hex_str: str) -> int:
    try:
        return int(hex_str.lstrip("#"), 16)
    except Exception:
        return Config.COLOR_PRIMARY


# ═══════════════════════════════════════════════
#  HELP MENU VIEW
# ═══════════════════════════════════════════════
class WelcomeHelpView(discord.ui.LayoutView):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=180)
        self.author = author

        container = MatrixContainer(
            text("### Greeter System Help"),
            text(f"## {Emojis.WELCOMER}  Welcome/Goodbye Message Configuration"),
            make_separator(),
            text(
                "Configure custom welcome and goodbye messages with full "
                "embed support and placeholders."
            ),
            make_separator(),
            text("**Available Placeholders**"),
            text(
                "**User:** `{user.mention}`, `{user.username}`, "
                "`{user.name}`, `{user.id}`, `{user.created_at}`\n"
                "**Server:** `{server.name}`, `{server.count}`, "
                "`{server.count_ordinal}`, `{server.vanity}`, `{server.id}`\n"
                "**Time:** `{time}`, `{time.relative}`, `{time.short}`, `{time.full}`\n"
                "**V2 Layout:** `{divider}` *(real Discord separator component, not a text line)*"
            ),
            make_separator(),
            text("**Command Usage**"),
            text("`&welcome <type> <action>` or `&welcome <action>`"),
            text("**Types**"),
            text("`welcome`, `goodbye` *(Defaults to welcome)*"),
            text("**Actions**"),
            text("`config` *(Wizard)*\n`edit` *(Manual Editor)*\n`preview` *(Test)*\n`disable`"),
            make_separator(),
            text(f"-# {Emojis.SPARKLE} {Config.FOOTER_TEXT}"),
        )
        self.add_item(container)


# ═══════════════════════════════════════════════
#  SETUP WIZARD (Auto / Manual choice)
# ═══════════════════════════════════════════════
class SetupWizardView(discord.ui.LayoutView):
    def __init__(self, author: discord.Member, action: str = "welcome"):
        super().__init__(timeout=300)
        self.author = author
        self.action = action

        container = MatrixContainer(
            text(f"### {Config.BOT_NAME} Welcomer System"),
            text(f"## {Emojis.DIAMOND}  Welcome Setup Wizard"),
            make_separator(),
            text(
                f"Welcome to the **interactive setup wizard** for your "
                f"server's **{action}** messages!\n\n"
                f"**Please choose a configuration mode:**"
            ),
            make_separator(),
            text(
                f"{Emojis.SETTINGS}  **Auto Setup (Templates)**\n"
                f"> Browse our collection of premium pre-built designs "
                f"and set up everything in just a few clicks. "
                f"Perfect for quick setups!"
            ),
            make_separator(),
            text(
                f"{Emojis.TOOLS}  **Manual Setup (Advanced)**\n"
                f"> Access the full control panel to customize every "
                f"detail (plain text, embeds, thumbnails, images, "
                f"and colors) exactly how you want it."
            ),
            make_separator(),
            text("Please make a selection using the buttons below"),
            discord.ui.ActionRow(
                AutoSetupButton(author, action),
                ManualSetupButton(author, action),
            ),
        )
        self.add_item(container)


class AutoSetupButton(Button):
    def __init__(self, author, action):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Auto Setup",
            emoji=Emojis.DIAMOND,
        )
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} This is not your panel.", ephemeral=True
            )
        view = AutoTemplatesView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class ManualSetupButton(Button):
    def __init__(self, author, action):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Manual Setup",
            emoji=Emojis.TOOLS,
        )
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} This is not your panel.", ephemeral=True
            )
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  AUTO TEMPLATES
# ═══════════════════════════════════════════════
TEMPLATES = {
    "Classic": {
        "plain_text": "{user.mention}",
        "embed_title": f"{Emojis.HELLO} Welcome!",
        "embed_desc": "Welcome to **{server.name}**, {user.mention}!\n{divider}\nYou are member **#{server.count_ordinal}**",
        "color": "#FF0000",
        "footer": "Member #{server.count}",
    },
    "Minimal": {
        "plain_text": "",
        "embed_title": "",
        "embed_desc": "{user.mention} joined **{server.name}**",
        "color": "#FF0000",
        "footer": "",
    },
    "Premium": {
        "plain_text": "{user.mention}",
        "embed_title": f"{Emojis.DIAMOND} A new member arrived!",
        "embed_desc": "Welcome **{user.name}** to **{server.name}**\n{divider}\nYou are our **{server.count_ordinal}** member\nAccount created: {user.created_at}",
        "color": "#FF0000",
        "footer": "Joined at {time.short}",
    },
}


class AutoTemplatesView(discord.ui.LayoutView):
    def __init__(self, author, action):
        super().__init__(timeout=300)
        self.author = author
        self.action = action

        children = [
            text(f"## {Emojis.STAR}  Auto Setup: Choose Template"),
            make_separator(),
            text("Select one of the premium pre-built templates below to instantly apply it to your server."),
            make_separator(),
        ]
        for name in TEMPLATES.keys():
            children.append(
                discord.ui.ActionRow(TemplateButton(author, action, name))
            )
        children.append(make_separator())
        children.append(discord.ui.ActionRow(BackToWizardButton(author, action)))

        container = MatrixContainer(*children)
        self.add_item(container)


class TemplateButton(Button):
    def __init__(self, author, action, name):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=name,
            emoji=Emojis.SPARKLE,
        )
        self.author = author
        self.action = action
        self.template_name = name

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        tpl = TEMPLATES[self.template_name]
        update_guild_config(interaction.guild.id, self.action, **tpl)
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class BackToWizardButton(Button):
    def __init__(self, author, action):
        super().__init__(style=discord.ButtonStyle.secondary, label="« Back", )
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        view = SetupWizardView(self.author, self.action)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  MANUAL CONFIG PANEL (Main editor)
# ═══════════════════════════════════════════════
class ManualConfigView(discord.ui.LayoutView):
    def __init__(self, author: discord.Member, action: str = "welcome"):
        super().__init__(timeout=300)
        self.author = author
        self.action = action

        cfg = get_guild_config(author.guild.id, action)
        ch_text = f"<#{cfg['channel_id']}>" if cfg.get("channel_id") else "`Not Set`"
        enabled = cfg.get("enabled", False)
        status_emoji = Emojis.ENABLED if enabled else Emojis.DISABLED
        status_text = "Enabled" if enabled else "Disabled"

        thumb_emoji = Emojis.SUCCESS if cfg.get("thumbnail") else Emojis.ERROR
        thumb_text = "Shown" if cfg.get("thumbnail") else "Hidden"

        plain_emoji = Emojis.SUCCESS if cfg.get("plain_text") else Emojis.ERROR
        plain_text = "Configured" if cfg.get("plain_text") else "Empty"

        title_emoji = Emojis.SUCCESS if cfg.get("embed_title") else Emojis.ERROR
        title_text = "Configured" if cfg.get("embed_title") else "Empty"

        desc_emoji = Emojis.SUCCESS if cfg.get("embed_desc") else Emojis.ERROR
        desc_text = "Configured" if cfg.get("embed_desc") else "Empty"

        footer_emoji = Emojis.SUCCESS if cfg.get("footer") else Emojis.ERROR
        footer_text = "Configured" if cfg.get("footer") else "Empty"

        img_emoji = Emojis.SUCCESS if cfg.get("image") else Emojis.ERROR
        img_text = "Configured" if cfg.get("image") else "Empty"

        children = [
            text(f"### {action.capitalize()} Configuration Panel"),
            text(f"## {Emojis.SETTINGS}  Message Settings Overview"),
            make_separator(),
            text(
                "Manage your custom welcome messages below. You can update "
                "the channel, tweak the text and embed formatting, or preview "
                "your current setup."
            ),
            make_separator(),
            text("**General Settings**"),
            text(
                f"**Status:** {status_emoji} {status_text}\n"
                f"**Channel:** {ch_text}\n"
                f"**Thumbnail:** {thumb_emoji} {thumb_text}"
            ),
            text("**Message Content**"),
            text(
                f"**Plain Text:** {plain_emoji} {plain_text}\n"
                f"**Embed Title:** {title_emoji} {title_text}\n"
                f"**Embed Desc:** {desc_emoji} {desc_text}"
            ),
            text("**Appearance**"),
            text(
                f"**Color:** `{cfg.get('color', '#FF0000')}`\n"
                f"**Footer:** {footer_emoji} {footer_text}\n"
                f"**Image/Banner:** {img_emoji} {img_text}"
            ),
            make_separator(),
        ]

        if not cfg.get("channel_id"):
            children.append(text(f"{Emojis.ERROR} You must set a channel to enable the system"))
            children.append(make_separator())

        # Row 1: Enable / Set Channel
        children.append(discord.ui.ActionRow(
            EnableToggleButton(author, action, enabled, bool(cfg.get("channel_id"))),
            SetChannelButton(author, action),
        ))
        # Row 2: Preview
        children.append(discord.ui.ActionRow(
            SendPreviewButton(author, action, bool(cfg.get("channel_id"))),
        ))
        # Row 3: Edit message / Footer & Color
        children.append(discord.ui.ActionRow(
            EditMessageButton(author, action),
            EditFooterColorButton(author, action),
        ))
        # Row 4: Toggle Thumbnail
        children.append(discord.ui.ActionRow(
            ToggleThumbnailButton(author, action),
        ))

        container = MatrixContainer(*children)
        self.add_item(container)


# ─── Buttons ───
class EnableToggleButton(Button):
    def __init__(self, author, action, enabled: bool, can_enable: bool):
        super().__init__(
            style=discord.ButtonStyle.success if not enabled else discord.ButtonStyle.danger,
            label="Disable" if enabled else "Enable",
            disabled=not can_enable,
        )
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        cfg = get_guild_config(interaction.guild.id, self.action)
        update_guild_config(interaction.guild.id, self.action, enabled=not cfg["enabled"])
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class SetChannelButton(Button):
    def __init__(self, author, action):
        super().__init__(style=discord.ButtonStyle.secondary, label="Set Channel", emoji=Emojis.CHANNEL)
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        view = ChannelSelectView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class ChannelSelectView(discord.ui.LayoutView):
    def __init__(self, author, action):
        super().__init__(timeout=180)
        self.author = author
        self.action = action

        container = MatrixContainer(
            text(f"## {Emojis.CHANNEL}  Select Welcome Channel"),
            make_separator(),
            text("Choose the channel where messages will be sent."),
            discord.ui.ActionRow(_ChannelPicker(author, action)),
            discord.ui.ActionRow(BackToManualButton(author, action)),
        )
        self.add_item(container)


class _ChannelPicker(ChannelSelect):
    def __init__(self, author, action):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder="Select a channel...",
            min_values=1, max_values=1,
        )
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        ch = self.values[0]
        update_guild_config(interaction.guild.id, self.action, channel_id=ch.id)
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class BackToManualButton(Button):
    def __init__(self, author, action):
        super().__init__(style=discord.ButtonStyle.secondary, label="« Back")
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class SendPreviewButton(Button):
    def __init__(self, author, action, enabled):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Send Preview",
            emoji=Emojis.SPARKLE,
            disabled=not enabled,
        )
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        cog: Welcome = interaction.client.get_cog("Welcome")
        await cog.send_welcome(interaction.user, action=self.action, preview=True)
        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Preview sent in the configured channel.",
            ephemeral=True,
        )


class EditMessageButton(Button):
    def __init__(self, author, action):
        super().__init__(style=discord.ButtonStyle.primary, label="Edit Message", emoji=Emojis.PENCIL)
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        await interaction.response.send_modal(EditMessageModal(self.author, self.action))


class EditMessageModal(Modal, title="Edit Welcome Message"):
    def __init__(self, author, action):
        super().__init__()
        self.author = author
        self.action = action
        cfg = get_guild_config(author.guild.id, action)

        self.plain = TextInput(
            label="Plain Text (above embed)",
            style=discord.TextStyle.paragraph,
            default=cfg.get("plain_text", ""),
            required=False, max_length=2000,
        )
        self.embed_title = TextInput(
            label="Embed Title",
            default=cfg.get("embed_title", ""),
            required=False, max_length=256,
        )
        self.embed_desc = TextInput(
            label="Embed Description",
            style=discord.TextStyle.paragraph,
            default=cfg.get("embed_desc", ""),
            required=False, max_length=4000,
        )
        self.image = TextInput(
            label="Image URL (Banner)",
            default=cfg.get("image", ""),
            required=False,
        )
        self.add_item(self.plain)
        self.add_item(self.embed_title)
        self.add_item(self.embed_desc)
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        update_guild_config(
            interaction.guild.id, self.action,
            plain_text=self.plain.value,
            embed_title=self.embed_title.value,
            embed_desc=self.embed_desc.value,
            image=self.image.value,
        )
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class EditFooterColorButton(Button):
    def __init__(self, author, action):
        super().__init__(style=discord.ButtonStyle.primary, label="Edit Footer & Color", emoji=Emojis.SETTINGS)
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        await interaction.response.send_modal(EditFooterColorModal(self.author, self.action))


class EditFooterColorModal(Modal, title="Edit Footer & Color"):
    def __init__(self, author, action):
        super().__init__()
        self.author = author
        self.action = action
        cfg = get_guild_config(author.guild.id, action)

        self.footer = TextInput(
            label="Footer Text",
            default=cfg.get("footer", ""),
            required=False, max_length=2048,
        )
        self.color = TextInput(
            label="Color (Hex e.g. #FF0000)",
            default=cfg.get("color", "#FF0000"),
            required=False, max_length=7,
        )
        self.add_item(self.footer)
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        color_val = self.color.value.strip()
        if color_val and not re.match(r"^#?[0-9A-Fa-f]{6}$", color_val):
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Invalid hex color. Example: `#FF0000`",
                ephemeral=True,
            )
        if color_val and not color_val.startswith("#"):
            color_val = "#" + color_val
        update_guild_config(
            interaction.guild.id, self.action,
            footer=self.footer.value,
            color=color_val or "#FF0000",
        )
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


class ToggleThumbnailButton(Button):
    def __init__(self, author, action):
        super().__init__(style=discord.ButtonStyle.secondary, label="Toggle Thumbnail", emoji=Emojis.STAR)
        self.author = author
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                f"{Emojis.ERROR} Not your panel.", ephemeral=True
            )
        cfg = get_guild_config(interaction.guild.id, self.action)
        update_guild_config(interaction.guild.id, self.action, thumbnail=not cfg.get("thumbnail", True))
        view = ManualConfigView(self.author, self.action)
        await interaction.response.edit_message(view=view)


# ═══════════════════════════════════════════════
#  COG
# ═══════════════════════════════════════════════
class Welcome(commands.Cog):
    """Welcome / Goodbye system - MATRIX AIO Style."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── Send Welcome / Goodbye Message ───
    async def send_welcome(self, member: discord.Member, action: str = "welcome", preview: bool = False):
        cfg = get_guild_config(member.guild.id, action)
        if not preview and not cfg.get("enabled"):
            return
        ch_id = cfg.get("channel_id")
        if not ch_id:
            return
        channel = member.guild.get_channel(ch_id)
        if not channel:
            return

        plain = parse_placeholders(cfg.get("plain_text", ""), member)
        title = parse_placeholders(cfg.get("embed_title", ""), member)
        desc = parse_placeholders(cfg.get("embed_desc", ""), member)
        footer = parse_placeholders(cfg.get("footer", ""), member)

        # {divider} becomes a real CV2 separator component, not a fake unicode line.
        desc_parts = [p.strip() for p in desc.split("{divider}")] if desc else []

        children = []
        if plain:
            children.append(text(plain))
        if title:
            children.append(text(f"### {title}"))
        if desc_parts:
            first = desc_parts[0]
            if cfg.get("thumbnail") and first:
                children.append(discord.ui.Section(
                    text(first),
                    accessory=discord.ui.Thumbnail(media=member.display_avatar.url)
                ))
            elif first:
                children.append(text(first))
            for part in desc_parts[1:]:
                children.append(make_separator())
                if part:
                    children.append(text(part))
        if cfg.get("image"):
            children.append(discord.ui.MediaGallery(discord.MediaGalleryItem(cfg["image"])))
        if footer:
            children.append(make_separator())
            children.append(text(f"-# {footer}"))

        if not children:
            return

        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(*children, accent_color=hex_to_int(cfg.get("color", "#FF0000"))))

        try:
            await channel.send(view=view)
        except discord.Forbidden:
            pass

    # ─── Listeners ───
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.send_welcome(member, action="welcome")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
        await self.send_welcome(member, action="goodbye")

    # ─── Commands ───
    @commands.group(name="welcome", aliases=["greet", "greeter"], invoke_without_command=True)
    async def welcome_grp(self, ctx: commands.Context, *args):
        """Welcome system commands."""
        # Parse: &welcome <type> <action>  or  &welcome <action>
        action_type = "welcome"
        sub = None
        if len(args) == 1:
            sub = args[0].lower()
        elif len(args) >= 2:
            if args[0].lower() in ("welcome", "goodbye"):
                action_type = args[0].lower()
                sub = args[1].lower()
            else:
                sub = args[0].lower()
        if not sub:
            view = WelcomeHelpView(ctx.author)
            return await send_v2(ctx, view)

        if sub == "config":
            view = SetupWizardView(ctx.author, action_type)
            return await send_v2(ctx, view)
        elif sub == "edit":
            view = ManualConfigView(ctx.author, action_type)
            return await send_v2(ctx, view)
        elif sub == "preview":
            await self.send_welcome(ctx.author, action=action_type, preview=True)
            return await send_v2(ctx, success_view(
                "Preview Sent",
                fields=[("Action:", action_type.capitalize())],
                footer="Check your configured channel.",
            ))
        elif sub == "disable":
            update_guild_config(ctx.guild.id, action_type, enabled=False)
            return await send_v2(ctx, success_view(
                f"{action_type.capitalize()} Disabled",
                fields=[("Status:", f"{Emojis.DISABLED} Disabled")],
            ))
        else:
            return await send_v2(ctx, error_view(
                f"Unknown subcommand `{sub}`",
                usage="&welcome <welcome/goodbye> <config|edit|preview|disable>",
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))