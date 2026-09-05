import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

PANEL_FILE = "selfroles.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(PANEL_FILE, dict)

def load_panels():
    return _cache.load()

def save_panels(d):
    _cache.save(d)


class PanelBuilderView(discord.ui.LayoutView):
    def __init__(self, ctx, panel_data: dict, panel_id: str):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.panel = panel_data
        self.panel_id = panel_id
        self.build()

    def build(self):
        self.clear_items()
        p = self.panel
        info = (
            f"**Channel** — {p.get('channel') or 'not set'}\n"
            f"**Type** — {p.get('type') or 'not set'}\n"
            f"**Title** — {p.get('title') or 'not set'}\n"
            f"**Description** — {p.get('description') or 'not set'}\n"
            f"**Colour** — {p.get('colour') or '#2b2d31'}\n"
            f"**Thumbnail** — {Emojis.SUCCESS if p.get('thumbnail') else Emojis.ERROR} | "
            f"**Image** — {Emojis.SUCCESS if p.get('image') else Emojis.ERROR}\n"
            f"**Author** — {Emojis.SUCCESS if p.get('author') else Emojis.ERROR} | "
            f"**Footer** — {Emojis.SUCCESS if p.get('footer') else Emojis.ERROR}"
        )

        top = MatrixContainer(
            text(f"### {Emojis.PANEL}  Panel Builder Configuration"),
            make_separator(),
            text(info),
            make_separator(),
            text(f"-# Requested by {self.ctx.author.name}")
        )

        note = p.get("description") or "No description set — use **Set Description** to add one."

        def make_btn(label, key):
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            async def cb(i):
                await self.prompt(i, key, label)
            btn.callback = cb
            return btn

        async def cancel_cb(i):
            await i.response.edit_message(view=None)
            v = discord.ui.LayoutView()
            v.add_item(MatrixContainer(text(f"### {Emojis.ERROR}  Panel setup cancelled.")))
            await i.followup.send(view=v, ephemeral=True)

        async def set_type_cb(i):
            options = [
                discord.SelectOption(label="Buttons",  value="buttons",  emoji=Emojis.BUTTON),
                discord.SelectOption(label="Dropdown", value="dropdown", emoji=Emojis.DROPDOWN),
                discord.SelectOption(label="Reactions",value="reactions",emoji=Emojis.REACTION),
            ]
            sel = discord.ui.Select(placeholder="Choose panel type...", options=options)
            async def sel_cb(inter):
                self.panel["type"] = sel.values[0]
                self.save()
                self.build()
                await inter.response.edit_message(view=self)
            sel.callback = sel_cb
            tmp = discord.ui.LayoutView()
            tmp.add_item(MatrixContainer(text("Select panel type:"), discord.ui.ActionRow(sel)))
            await i.response.send_message(view=tmp, ephemeral=True)

        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_btn.callback = cancel_cb

        set_type_btn = discord.ui.Button(label="Set Type", style=discord.ButtonStyle.primary)
        set_type_btn.callback = set_type_cb

        bottom = MatrixContainer(
            text(note),
            make_separator(),
            text(f"-# Requested by {self.ctx.author.name}"),
            discord.ui.ActionRow(make_btn("Set Title", "title"), make_btn("Set Description", "description")),
            discord.ui.ActionRow(make_btn("Set Thumbnail", "thumbnail"), make_btn("Set Image", "image")),
            discord.ui.ActionRow(make_btn("Set Colour", "colour")),
            discord.ui.ActionRow(make_btn("Set Footer", "footer"), make_btn("Set Footer Icon", "footer_icon")),
            discord.ui.ActionRow(make_btn("Set Author", "author"), make_btn("Set Author Icon", "author_icon")),
            discord.ui.ActionRow(set_type_btn),
            discord.ui.ActionRow(cancel_btn)
        )

        self.add_item(top)
        self.add_item(bottom)

    def save(self):
        all_panels = load_panels()
        all_panels.setdefault(str(self.ctx.guild.id), {})[self.panel_id] = self.panel
        save_panels(all_panels)

    async def prompt(self, interaction, key, label):
        await interaction.response.send_message(f"Send the new **{label}** in chat (60s timeout).", ephemeral=True)
        def check(m): return m.author == self.ctx.author and m.channel == self.ctx.channel
        try:
            msg = await self.ctx.bot.wait_for("message", check=check, timeout=60)
            self.panel[key] = msg.content
            self.save()
            try: await msg.delete()
            except: pass
            self.build()
            await interaction.message.edit(view=self)
        except:
            pass


class Selfrole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="selfrole", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def selfrole(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SELFROLE}  Self-Assign Roles Menu"),
            make_separator(),
            text(
                "Set up automated role panels for your members using custom interactive buttons, menus, or reactions."
            ),
            make_separator(),
            text(f"{Emojis.LIST}  **Commands List**"),
            text(
                "`&selfrole setup` — Interactive setup panel\n"
                "`&selfrole list` — List configured selfrole panels\n"
                "`&selfrole delete <panelId>` — Remove a panel\n"
                "`&selfrole edit <panelId>` — Edit panel fields\n"
                "`&selfrole reset` — Clear all panels"
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    @selfrole.command(name="setup")
    async def setup(self, ctx):
        panel_id = str(ctx.message.id)
        panel = {
            "channel": ctx.channel.mention,
            "type": None, "title": None, "description": None,
            "colour": "#2b2d31", "thumbnail": None, "image": None,
            "author": None, "footer": None,
            "footer_icon": None, "author_icon": None
        }
        view = PanelBuilderView(ctx, panel, panel_id)
        await ctx.send(view=view)

    @selfrole.command(name="list")
    async def list_panels(self, ctx):
        panels = load_panels().get(str(ctx.guild.id), {})
        view = discord.ui.LayoutView()
        if not panels:
            container = MatrixContainer(text(f"### {Emojis.SELFROLE}  No selfrole panels configured."))
        else:
            lines = "\n".join([f"`{pid}` — {p.get('title') or 'Untitled'}" for pid, p in panels.items()])
            container = MatrixContainer(
                text(f"### {Emojis.SELFROLE}  Selfrole Panels"),
                make_separator(),
                text(lines)
            )
        view.add_item(container)
        await send_v2(ctx, view)

    @selfrole.command(name="delete")
    async def delete_panel(self, ctx, panel_id: str):
        all_panels = load_panels()
        gid = str(ctx.guild.id)
        if panel_id not in all_panels.get(gid, {}):
            return await send_v2(ctx, error_view("Panel not found."))
        del all_panels[gid][panel_id]
        save_panels(all_panels)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Panel `{panel_id}` deleted.")))
        await send_v2(ctx, view)

    @selfrole.command(name="reset")
    async def reset_panels(self, ctx):
        all_panels = load_panels()
        all_panels[str(ctx.guild.id)] = {}
        save_panels(all_panels)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  All selfrole panels cleared.")))
        await send_v2(ctx, view)

    @selfrole.command(name="edit")
    async def edit_panel(self, ctx, panel_id: str):
        all_panels = load_panels()
        panel = all_panels.get(str(ctx.guild.id), {}).get(panel_id)
        if not panel:
            return await send_v2(ctx, error_view("Panel not found."))
        view = PanelBuilderView(ctx, panel, panel_id)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Selfrole(bot))