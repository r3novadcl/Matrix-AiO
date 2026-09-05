import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

CONFIG_FILE = "module_config.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(CONFIG_FILE, dict)

def load_cfg():
    return _cache.load()

def save_cfg(d):
    _cache.save(d)


CATEGORIES = [
    "AI", "Antinuke", "Automod", "Autonick", "Autoresponder",
    "Birthday", "Configuration", "Customrole", "Fun", "Games",
    "Giveaway", "Information", "Invites", "Jointocreate", "Leveling",
    "Logs", "Moderation", "Music", "Roleguard", "Selfrole",
    "Stat", "Ticket", "Voice", "Welcomer"
]


class ModuleConfigView(discord.ui.LayoutView):
    def __init__(self, ctx, mode="main"):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.mode = mode
        self.build()

    def build(self):
        self.clear_items()
        cfg = load_cfg()
        gid = str(self.ctx.guild.id)
        guild_cfg = cfg.get(gid, {"disabled_categories": [], "disabled_commands": []})

        if self.mode == "main":
            disabled_cats = guild_cfg.get("disabled_categories", [])
            disabled_cmds = guild_cfg.get("disabled_commands", [])

            section = discord.ui.Section(
                text(f"### {Emojis.CONFIG}  {Config.BOT_NAME} Module Configuration"),
                text(
                    "Welcome to the **Module Management System!** This tool allows you to "
                    "customize which features of " + Config.BOT_NAME + " are active in your server."
                ),
                accessory=discord.ui.Thumbnail(media=Config.BOT_LOGO if Config.BOT_LOGO.startswith("http") else self.ctx.bot.user.display_avatar.url)
            )

            main_btn = discord.ui.Button(label="Main Menu", style=discord.ButtonStyle.secondary, disabled=True)
            cat_btn  = discord.ui.Button(label="Categories", style=discord.ButtonStyle.primary)
            cmd_btn  = discord.ui.Button(label="Individual Commands", style=discord.ButtonStyle.secondary)

            async def cat_cb(i):
                self.mode = "categories"; self.build()
                await i.response.edit_message(view=self)
            async def cmd_cb(i):
                self.mode = "commands"; self.build()
                await i.response.edit_message(view=self)

            cat_btn.callback = cat_cb
            cmd_btn.callback = cmd_cb

            container = MatrixContainer(
                section,
                make_separator(),
                text(
                    "**How it works:**\n"
                    f"• **Categories:** Disable entire systems (e.g., disable all Music commands).\n"
                    f"• **Individual Commands:** Disable specific commands (e.g., disable `ban` but keep `kick`).\n\n"
                    "Use the buttons below to start configuring."
                ),
                make_separator(),
                text(
                    f"**Disabled Categories**\n{', '.join(disabled_cats) if disabled_cats else 'None'}\n"
                    f"**Disabled Commands**\n{', '.join(disabled_cmds) if disabled_cmds else 'None'}"
                ),
                make_separator(),
                text(f"-# Requested by {self.ctx.author.name}"),
                discord.ui.ActionRow(main_btn, cat_btn, cmd_btn)
            )
            self.add_item(container)

        elif self.mode == "categories":
            disabled_cats = guild_cfg.get("disabled_categories", [])

            select = discord.ui.Select(
                placeholder="Toggle a category...",
                options=[discord.SelectOption(label=c, value=c, default=(c in disabled_cats)) for c in CATEGORIES[:25]]
            )

            async def select_cb(i):
                chosen = select.values[0]
                cfg2 = load_cfg()
                gcfg = cfg2.setdefault(gid, {"disabled_categories": [], "disabled_commands": []})
                if chosen in gcfg["disabled_categories"]:
                    gcfg["disabled_categories"].remove(chosen)
                    msg = f"{Emojis.SUCCESS} Enabled `{chosen}`"
                else:
                    gcfg["disabled_categories"].append(chosen)
                    msg = f"{Emojis.ERROR} Disabled `{chosen}`"
                save_cfg(cfg2)
                self.build()
                await i.response.edit_message(view=self)
                await i.followup.send(msg, ephemeral=True)

            select.callback = select_cb

            main_btn = discord.ui.Button(label="Main Menu", style=discord.ButtonStyle.secondary)
            cat_btn  = discord.ui.Button(label="Categories", style=discord.ButtonStyle.primary, disabled=True)
            cmd_btn  = discord.ui.Button(label="Individual Commands", style=discord.ButtonStyle.secondary)

            async def main_cb(i):
                self.mode = "main"; self.build()
                await i.response.edit_message(view=self)
            async def cmd_cb(i):
                self.mode = "commands"; self.build()
                await i.response.edit_message(view=self)

            main_btn.callback = main_cb
            cmd_btn.callback  = cmd_cb

            container = MatrixContainer(
                discord.ui.Section(
                    text(f"### {Emojis.CONFIG}  {Config.BOT_NAME} Module Configuration"),
                    text(f"### Category Settings"),
                    accessory=discord.ui.Thumbnail(media=Config.BOT_LOGO if Config.BOT_LOGO.startswith("http") else self.ctx.bot.user.display_avatar.url)
                ),
                make_separator(),
                text(
                    "Select a category from the menu below to toggle its status.\n\n"
                    f"**Currently Disabled:** {', '.join(disabled_cats) if disabled_cats else 'None'}"
                ),
                make_separator(),
                text(f"-# Requested by {self.ctx.author.name}"),
                discord.ui.ActionRow(main_btn, cat_btn, cmd_btn),
                discord.ui.ActionRow(select)
            )
            self.add_item(container)

        elif self.mode == "commands":
            disabled_cmds = guild_cfg.get("disabled_commands", [])
            all_cmds = [c.name for c in self.ctx.bot.commands][:25]

            select = discord.ui.Select(
                placeholder="Toggle a command...",
                options=[discord.SelectOption(label=c, value=c, default=(c in disabled_cmds)) for c in all_cmds]
            )

            async def select_cb(i):
                chosen = select.values[0]
                cfg2 = load_cfg()
                gcfg = cfg2.setdefault(gid, {"disabled_categories": [], "disabled_commands": []})
                if chosen in gcfg["disabled_commands"]:
                    gcfg["disabled_commands"].remove(chosen)
                    msg = f"{Emojis.SUCCESS} Enabled `{chosen}`"
                else:
                    gcfg["disabled_commands"].append(chosen)
                    msg = f"{Emojis.ERROR} Disabled `{chosen}`"
                save_cfg(cfg2)
                self.build()
                await i.response.edit_message(view=self)
                await i.followup.send(msg, ephemeral=True)

            select.callback = select_cb

            main_btn = discord.ui.Button(label="Main Menu", style=discord.ButtonStyle.secondary)
            cat_btn  = discord.ui.Button(label="Categories", style=discord.ButtonStyle.secondary)
            cmd_btn  = discord.ui.Button(label="Individual Commands", style=discord.ButtonStyle.primary, disabled=True)

            async def main_cb(i):
                self.mode = "main"; self.build()
                await i.response.edit_message(view=self)
            async def cat_cb(i):
                self.mode = "categories"; self.build()
                await i.response.edit_message(view=self)

            main_btn.callback = main_cb
            cat_btn.callback  = cat_cb

            container = MatrixContainer(
                text(f"### {Emojis.CONFIG}  {Config.BOT_NAME} Module Configuration"),
                text(f"### Command Settings"),
                make_separator(),
                text(
                    "Select a command from the menu below to toggle its status.\n\n"
                    f"**Currently Disabled:** {', '.join(disabled_cmds) if disabled_cmds else 'None'}"
                ),
                make_separator(),
                text(f"-# Requested by {self.ctx.author.name}"),
                discord.ui.ActionRow(main_btn, cat_btn, cmd_btn),
                discord.ui.ActionRow(select)
            )
            self.add_item(container)


class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="module", aliases=["modules"])
    @commands.has_permissions(administrator=True)
    async def module(self, ctx):
        view = ModuleConfigView(ctx, mode="main")
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Configuration(bot))