"""
Matrix Bot - Help Menu & Support Panel
Components V2 with red accent, category dropdown, pagination
"""

import discord
from discord.ext import commands
from config import Config
from emojis import Emojis
from utils.components import MatrixContainer, text, make_separator, send_v2


# ─── IGNORED CATEGORIES ───
# Nothing to ignore anymore — every category below is backed by a real, working cog.
IGNORED_CATEGORIES = set()


# ─── CATEGORY DATA ───
# Note: Voicemaster commands → "Jointocreate" category
# Logs category bnayi gyi separately
CATEGORIES = {
    "antinuke": {
        "label": "Antinuke",
        "emoji": Emojis.ANTINUKE if hasattr(Emojis, "ANTINUKE") else "🛡️",
        "commands": [
            "&antinuke", "&extraowner", "&nightmode",
            "&unwhitelist", "&vanityguard", "&verification",
            "&whitelist", "&wlisted", "&whitelistreset"
        ],
        "badge": "LATEST"
    },
    "automod": {
        "label": "Automod",
        "emoji": Emojis.AUTOMOD if hasattr(Emojis, "AUTOMOD") else "🔨",
        "commands": ["&automod"],
        "badge": "LATEST"
    },
    "autonick": {
        "label": "Autonick",
        "emoji": Emojis.AUTONICK if hasattr(Emojis, "AUTONICK") else "🎮",
        "commands": [
            "&autonick", "&autonicklog", "&fixautonick",
            "&bulkautonick", "&resetnicks"
        ]
    },
    "autoresponder": {
        "label": "Autoresponder",
        "emoji": Emojis.AUTORESPONDER if hasattr(Emojis, "AUTORESPONDER") else "⭐",
        "commands": ["&autoreact", "&autoresponder"]
    },
    "birthday": {
        "label": "Birthday",
        "emoji": Emojis.BIRTHDAY if hasattr(Emojis, "BIRTHDAY") else "🎉",
        "commands": ["&birthday"]
    },
    "configration": {
        "label": "Configration",
        "emoji": Emojis.CONFIG if hasattr(Emojis, "CONFIG") else "⚙️",
        "commands": ["&module"],
        "badge": "LATEST"
    },
    "customrole": {
        "label": "Customrole",
        "emoji": Emojis.CUSTOMROLE if hasattr(Emojis, "CUSTOMROLE") else "🗡️",
        "commands": ["&setup"]
    },
    "fun": {
        "label": "Fun",
        "emoji": Emojis.FUN if hasattr(Emojis, "FUN") else "🎈",
        "commands": [
            "&cute", "&dare", "&fakeban", "&hack", "&howgay", "&hug",
            "&intelligence", "&iplookup", "&lesbian",
            "&mydog", "&qr", "&quote", "&sayhello", "&ship", "&slap",
            "&slots", "&sudo", "&token", "&translate", "&truth",
            "&weather", "&wizz"
        ]
    },
    "games": {
        "label": "Games",
        "emoji": Emojis.GAMES if hasattr(Emojis, "GAMES") else "🎮",
        "commands": ["&counting"]
    },
    "giveaway": {
        "label": "Giveaway",
        "emoji": Emojis.GIVEAWAY if hasattr(Emojis, "GIVEAWAY") else "🎉",
        "commands": ["&giveaway", "&gstart", "&gend", "&greroll", "&glist", "&gdelete"]
    },
    "information": {
        "label": "Information",
        "emoji": Emojis.INFORMATION if hasattr(Emojis, "INFORMATION") else "🔧",
        "commands": [
            "&afk", "&avatar", "&banner", "&boost", "&boostcount",
            "&calculator", "&channelinfo", "&emojilist",
            "&firstmsg", "&github", "&serverbanner", "&help",
            "&invite", "&membercount", "&ping", "&profile", "&report",
            "&roleicon", "&roleinfo", "&servericon", "&serverinfo",
            "&stats", "&uptime", "&userinfo"
        ]
    },
    "jointocreate": {
        "label": "Jointocreate",
        "emoji": Emojis.VOICE_MIC if hasattr(Emojis, "VOICE_MIC") else "🎤",
        "commands": [
            "&voicemaster", "&vm setup", "&vm config",
            "&vm reset", "&vm buttons"
        ]
    },
    "leveling": {
        "label": "Leveling",
        "emoji": Emojis.LEVEL if hasattr(Emojis, "LEVEL") else "🌐",
        "commands": ["&level", "&rank"]
    },
    "logs": {
        "label": "Logs",
        "emoji": Emojis.LOGS if hasattr(Emojis, "LOGS") else "📋",
        "commands": [
            "&logs", "&logs setup", "&logs disable",
            "&logs config", "&logs reset"
        ]
    },
    "moderation": {
        "label": "Moderation",
        "emoji": Emojis.MODERATION if hasattr(Emojis, "MODERATION") else "🛠️",
        "commands": [
            "&ban", "&botnick", "&category", "&channel", "&chatban",
            "&embed", "&esnipe", "&hide", "&hideall", "&ignore",
            "&ignorecommand", "&kick", "&list", "&lock", "&lockall",
            "&mediachannel", "&mute", "&nick", "&nuke", "&prefix",
            "&purge", "&purgebot", "&remindme", "&rename", "&role",
            "&massrole", "&snipe", "&steal", "&unban", "&unbanall",
            "&unhide", "&unhideall", "&unlock", "&unlockall",
            "&unmute", "&voiceban", "&warn", "&warnlist",
            "&warnremove", "&webhook"
        ]
    },
    "selfrole": {
        "label": "Selfrole",
        "emoji": Emojis.SELFROLE if hasattr(Emojis, "SELFROLE") else "🪪",
        "commands": ["&selfrole"],
        "badge": "BETA"
    },
    "ticket": {
        "label": "Ticket",
        "emoji": Emojis.TICKET if hasattr(Emojis, "TICKET") else "🎫",
        "commands": [
            "&tadd", "&tclose", "&tdelete", "&tedit",
            "&ticket", "&tpanel", "&tremove"
        ]
    },
    "voice": {
        "label": "Voice",
        "emoji": Emojis.VOICE_MIC if hasattr(Emojis, "VOICE_MIC") else "🎙️",
        "commands": [
            "&record", "&vcban", "&vcdeafen", "&vcdeafenall",
            "&vchide", "&vckick", "&vckickall", "&vclist", "&vclock",
            "&vcmove", "&vcmoveall", "&vcmute", "&vcmuteall",
            "&vcpull", "&vcpullall", "&vcpushall", "&vcrequest",
            "&vcrole", "&vcunban", "&vcundeafen", "&vcundeafenall",
            "&vcunhide", "&vcunlock", "&vcunmute", "&vcunmuteall",
            "&voice", "&voicepannel"
        ]
    },
    "welcomer": {
        "label": "Welcomer",
        "emoji": Emojis.WELCOMER if hasattr(Emojis, "WELCOMER") else "🔺",
        "commands": ["&welcome"]
    },
    "logs": {
        "label": "Logs",
        "emoji": Emojis.LOGS if hasattr(Emojis, "LOGS") else "📋",
        "commands": ["&logs"]
    },
    "invites": {
        "label": "Invites",
        "emoji": Emojis.INVITES if hasattr(Emojis, "INVITES") else "💌",
        "commands": [
            "&tracker", "&invites", "&messages", "&addmessages",
            "&removemessages", "&resetmessages", "&blacklistchannel",
            "&unblacklistchannel", "&blacklistedchannels"
        ]
    },
}


# ─── HOME (MAIN HELP) MODULE LIST ───
# Only real, working categories — every key here must exist in CATEGORIES.
MODULE_LIST = [
    ("antinuke", "Antinuke", "LATEST"),
    ("automod", "Automod", "LATEST"),
    ("autonick", "Autonick", None),
    ("autoresponder", "Autoresponder", None),
    ("birthday", "Birthday", None),
    ("configration", "Configration", "LATEST"),
    ("customrole", "Customrole", None),
    ("fun", "Fun", None),
    ("games", "Games", None),
    ("giveaway", "Giveaway", None),
    ("information", "Information", None),
    ("invites", "Invites", None),
    ("jointocreate", "Jointocreate", None),
    ("leveling", "Leveling", None),
    ("logs", "Logs", None),
    ("moderation", "Moderation", None),
    ("selfrole", "Selfrole", "BETA"),
    ("ticket", "Ticket", None),
    ("voice", "Voice", None),
    ("welcomer", "Welcomer", None),
]

assert set(k for k, _, _ in MODULE_LIST) <= set(CATEGORIES.keys()), \
    "MODULE_LIST references a category with no CATEGORIES entry"

# Only categories shown in the dropdown (ignored ones excluded)
VISIBLE_CATEGORIES = [k for k in CATEGORIES.keys() if k not in IGNORED_CATEGORIES]


def get_module_emoji(key):
    fallback = {
        "antinuke": "🛡️", "automod": "🔨", "autonick": "🎮",
        "autoresponder": "⭐", "birthday": "🎉", "configration": "⚙️",
        "customrole": "🗡️", "fun": "🎈", "games": "🎮", "giveaway": "🎉",
        "information": "🔧", "invites": "💌", "jointocreate": "🐉",
        "leveling": "🌐", "logs": "📋", "moderation": "🛠️",
        "selfrole": "🪪", "ticket": "🎫", "voice": "🎙️", "welcomer": "🔺"
    }
    em_name = key.upper()
    if hasattr(Emojis, em_name):
        return getattr(Emojis, em_name)
    return fallback.get(key, "•")


# ─── HOME VIEW ───
class HomeView(discord.ui.LayoutView):
    def __init__(self, ctx, bot, author):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.author = author
        self._build()

    def _build(self):
        self.clear_items()
        user = self.author

        # Module lines
        module_lines = []
        for key, label, badge in MODULE_LIST:
            em = get_module_emoji(key)
            badge_str = ""
            if badge == "NEW":
                badge_str = f" {Emojis.NEW if hasattr(Emojis,'NEW') else '`NEW`'}"
            elif badge == "LATEST":
                badge_str = f" {Emojis.LATEST if hasattr(Emojis,'LATEST') else '`LATEST`'}"
            elif badge == "BETA":
                badge_str = f" {Emojis.BETA if hasattr(Emojis,'BETA') else '`BETA`'}"
            elif badge == "PREMIUM":
                badge_str = f" {Emojis.PREMIUM_BADGE if hasattr(Emojis,'PREMIUM_BADGE') else '`PREMIUM`'}"
            module_lines.append(f"{em} {label}{badge_str}")

        modules_text = "\n".join(module_lines)

        # Header section with logo as accessory
        header = discord.ui.Section(
            text(f"### {Config.BOT_NAME} Help Menu & Support Panel"),
            text(
                f"Hello **{user.name}**!\n"
                f"I am **{Config.BOT_NAME}**, {Config.BOT_TAGLINE}"
            ),
            accessory=discord.ui.Thumbnail(media=self.bot.user.display_avatar.url)
        )

        total_cmds = len(set(self.bot.commands))
        info_text = text(
            f"**Server Prefix:** `{Config.PREFIX}`\n"
            f"**Total Commands:** `{total_cmds}`\n"
            f"**Get Started:** Type `{Config.PREFIX}antinuke enable` to Secure your Server!\n"
            f"**How do you use me?** Use `{Config.PREFIX}help <category>` to Get Commands for that Category."
        )

        modules_block = text(f"**Available Modules:**\n{modules_text}")

        useful_links = text(
            f"**Useful Links:**\n"
            f"[Invite Me!]({Config.INVITE_URL}) | "
            f"[Join Support Server]({Config.SUPPORT_SERVER}) | "
            f"[website]({Config.WEBSITE}) | "
            f"[Vote Me]({Config.VOTE_URL})"
        )

        footer = text(f"-# {Config.BOT_NAME} Help Panel | © {Config.FOOTER_TEXT}")

        # Select dropdown
        options = []
        for key in VISIBLE_CATEGORIES:
            cat = CATEGORIES[key]
            options.append(discord.SelectOption(
                label=cat["label"],
                value=key,
                emoji=cat.get("emoji") if isinstance(cat.get("emoji"), str) else None
            ))

        # Discord allows max 25 options
        options = options[:25]

        select = discord.ui.Select(
            placeholder="Select a category",
            min_values=1, max_values=1,
            options=options,
            custom_id="help_category_select"
        )

        # Pagination buttons row
        first_btn = discord.ui.Button(emoji="⏪", style=discord.ButtonStyle.secondary,
                                       custom_id="help_first", disabled=True)
        prev_btn  = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary,
                                       custom_id="help_prev", disabled=True)
        del_btn   = discord.ui.Button(emoji="🗑️", style=discord.ButtonStyle.danger,
                                       custom_id="help_delete")
        next_btn  = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary,
                                       custom_id="help_next", disabled=True)
        last_btn  = discord.ui.Button(emoji="⏩", style=discord.ButtonStyle.secondary,
                                       custom_id="help_last", disabled=True)

        container = MatrixContainer(
            header,
            make_separator(),
            info_text,
            make_separator(),
            modules_block,
            make_separator(),
            useful_links,
            make_separator(),
            footer,
            discord.ui.ActionRow(select),
            discord.ui.ActionRow(first_btn, prev_btn, del_btn, next_btn, last_btn)
        )
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"{Emojis.ERROR} This help menu is not for you.", ephemeral=True
            )
            return False

        cid = interaction.data.get("custom_id", "")

        if cid == "help_category_select":
            selected = interaction.data["values"][0]
            view = CategoryView(self.ctx, self.bot, self.author, selected)
            await interaction.response.edit_message(view=view)
            return False

        if cid == "help_delete":
            try:
                await interaction.message.delete()
            except:
                pass
            return False

        return False


# ─── CATEGORY VIEW ───
class CategoryView(discord.ui.LayoutView):
    def __init__(self, ctx, bot, author, category_key):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.author = author
        self.category_key = category_key
        self._build()

    def _build(self):
        self.clear_items()
        cat = CATEGORIES[self.category_key]
        label = cat["label"]
        em = cat.get("emoji", "•")
        cmds = cat.get("commands", [])

        # Sort category list (alphabetic, except home)
        idx = VISIBLE_CATEGORIES.index(self.category_key)
        total = len(VISIBLE_CATEGORIES)

        header_text = text(f"**{self.author.name}'s Help Menu**")
        title_text = text(f"## {label} Commands")

        cmds_str = ", ".join([f"`{c}`" for c in cmds]) if cmds else "_No commands available._"
        cmds_block = text(f"**Available commands:**\n{cmds_str}")

        footer_line = text(f"{Config.BOT_NAME} | {label} Commands")

        # Show selected category card-like row (mimics screenshots)
        cat_row = text(f"{em} **{label}**")

        # Category dropdown (same as home, but now allows switching)
        options = []
        for key in VISIBLE_CATEGORIES:
            c = CATEGORIES[key]
            options.append(discord.SelectOption(
                label=c["label"],
                value=key,
                emoji=c.get("emoji") if isinstance(c.get("emoji"), str) else None,
                default=(key == self.category_key)
            ))
        options = options[:25]

        select = discord.ui.Select(
            placeholder="Select a category",
            min_values=1, max_values=1,
            options=options,
            custom_id="help_category_select"
        )

        # Pagination
        first_btn = discord.ui.Button(emoji="⏪", style=discord.ButtonStyle.secondary,
                                       custom_id="help_first", disabled=(idx == 0))
        prev_btn  = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary,
                                       custom_id="help_prev", disabled=(idx == 0))
        del_btn   = discord.ui.Button(emoji="🗑️", style=discord.ButtonStyle.danger,
                                       custom_id="help_delete")
        next_btn  = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary,
                                       custom_id="help_next", disabled=(idx == total - 1))
        last_btn  = discord.ui.Button(emoji="⏩", style=discord.ButtonStyle.secondary,
                                       custom_id="help_last", disabled=(idx == total - 1))

        container = MatrixContainer(
            header_text,
            title_text,
            make_separator(),
            cmds_block,
            make_separator(),
            footer_line,
            cat_row,
            discord.ui.ActionRow(select),
            discord.ui.ActionRow(first_btn, prev_btn, del_btn, next_btn, last_btn)
        )
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"{Emojis.ERROR} This help menu is not for you.", ephemeral=True
            )
            return False

        cid = interaction.data.get("custom_id", "")
        idx = VISIBLE_CATEGORIES.index(self.category_key)
        total = len(VISIBLE_CATEGORIES)

        if cid == "help_category_select":
            new_key = interaction.data["values"][0]
            new_view = CategoryView(self.ctx, self.bot, self.author, new_key)
            await interaction.response.edit_message(view=new_view)
            return False

        if cid == "help_first":
            new_view = CategoryView(self.ctx, self.bot, self.author, VISIBLE_CATEGORIES[0])
            await interaction.response.edit_message(view=new_view)
            return False

        if cid == "help_prev":
            new_idx = max(0, idx - 1)
            new_view = CategoryView(self.ctx, self.bot, self.author, VISIBLE_CATEGORIES[new_idx])
            await interaction.response.edit_message(view=new_view)
            return False

        if cid == "help_next":
            new_idx = min(total - 1, idx + 1)
            new_view = CategoryView(self.ctx, self.bot, self.author, VISIBLE_CATEGORIES[new_idx])
            await interaction.response.edit_message(view=new_view)
            return False

        if cid == "help_last":
            new_view = CategoryView(self.ctx, self.bot, self.author, VISIBLE_CATEGORIES[total - 1])
            await interaction.response.edit_message(view=new_view)
            return False

        if cid == "help_delete":
            try:
                await interaction.message.delete()
            except:
                pass
            return False

        return False


# ─── COG ───
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            bot.remove_command("help")
        except:
            pass

    @commands.command(name="help", aliases=["h", "cmds", "commands"])
    async def help_cmd(self, ctx, *, category: str = None):
        # Direct category invoke
        if category:
            key = category.lower().strip()
            # Aliases
            alias_map = {
                "vm": "jointocreate", "voicemaster": "jointocreate",
                "jtc": "jointocreate", "level": "leveling", "lvl": "leveling",
                "log": "logs", "info": "information",
                "mod": "moderation", "config": "configration"
            }
            key = alias_map.get(key, key)

            if key in IGNORED_CATEGORIES:
                return await ctx.send(f"{Emojis.ERROR} Category `{category}` is not available.")

            if key in CATEGORIES:
                view = CategoryView(ctx, self.bot, ctx.author, key)
                return await send_v2(ctx, view)
            else:
                return await ctx.send(f"{Emojis.ERROR} Category `{category}` not found.")

        # Default home view
        view = HomeView(ctx, self.bot, ctx.author)
        await send_v2(ctx, view)


async def setup(bot):
    await bot.add_cog(Help(bot))