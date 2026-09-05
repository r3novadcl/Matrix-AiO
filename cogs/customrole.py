import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

SETUP_FILE = "customrole.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(SETUP_FILE, dict)

def load_setup():
    return _cache.load()

def save_setup(d):
    _cache.save(d)


class Customrole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── BASE SETUP MENU ───
    @commands.group(name="setup", invoke_without_command=True)
    async def setup(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WARNING}   {ctx.guild.name}'s server"),
            make_separator(),

            text(f"__**Main Setup Commands**__:"),
            text(
                f"`{Config.PREFIX}setup add <name> <role>` - Set up a new role.\n"
                f"`{Config.PREFIX}setup remove <name>` - Remove an existing role.\n"
                f"`{Config.PREFIX}setup reqrole <@role|ID|name>` - Set a role as requirement.\n"
                f"`{Config.PREFIX}setup list` - View all custom roles.\n"
                f"`{Config.PREFIX}setup reset` - Reset custom roles configuration.\n"
                f"`{Config.PREFIX}setup config` - View custom roles configuration."
            ),
            make_separator(),

            text(f"__**Predefined Setup Commands**__:"),
            text(
                f"`{Config.PREFIX}setup add girl <role>` - Set a role specifically for females.\n"
                f"`{Config.PREFIX}setup add guest <role>` - Set a role for guests.\n"
                f"`{Config.PREFIX}setup add vip <role>` - Set a role for VIP members.\n"
                f"`{Config.PREFIX}setup add official <role>` - Set a role for official members."
            ),
            make_separator(),

            text(f"__**User Commands (after setup)**__:"),
            text(
                f"`{Config.PREFIX}girl` - Get or remove girl role.\n"
                f"`{Config.PREFIX}guest` - Get or remove guest role.\n"
                f"`{Config.PREFIX}vip` - Get or remove VIP role.\n"
                f"`{Config.PREFIX}official` - Get or remove official role."
            ),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SETUP ADD ───
    @setup.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def setup_add(self, ctx, name: str, role: discord.Role):
        data = load_setup()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"roles": {}, "reqrole": None})
        data[gid]["roles"][name.lower()] = role.id
        save_setup(data)

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Custom Role Added"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Name:** `{name}`\n"
                f"{Emojis.ROLE} **Role:** {role.mention}\n"
                f"{Emojis.MOD} **Added by:** {ctx.author.mention}\n\n"
                f"Users can now type `{Config.PREFIX}{name.lower()}` to get/remove this role."
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SETUP REMOVE ───
    @setup.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def setup_remove(self, ctx, name: str):
        data = load_setup()
        gid = str(ctx.guild.id)
        if name.lower() not in data.get(gid, {}).get("roles", {}):
            return await send_v2(ctx, error_view(f"No custom role named `{name}` found."))
        del data[gid]["roles"][name.lower()]
        save_setup(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Removed custom role `{name}`")))
        await send_v2(ctx, view)

    # ─── SETUP REQROLE ───
    @setup.command(name="reqrole")
    @commands.has_permissions(administrator=True)
    async def setup_reqrole(self, ctx, role: discord.Role):
        data = load_setup()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {"roles": {}, "reqrole": None})
        data[gid]["reqrole"] = role.id
        save_setup(data)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SUCCESS}  Required Role Set"),
            make_separator(),
            text(
                f"{Emojis.ROLE} **Required Role:** {role.mention}\n"
                f"Members must have this role to use custom role commands."
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SETUP LIST ───
    @setup.command(name="list")
    async def setup_list(self, ctx):
        data = load_setup()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, {"roles": {}, "reqrole": None})
        roles = gcfg.get("roles", {})

        if not roles:
            return await send_v2(ctx, error_view("No custom roles set up. Use `&setup add <name> <role>`."))

        lines = "\n".join([
            f"{Emojis.ARROW} `{Config.PREFIX}{name}` → <@&{rid}>"
            for name, rid in roles.items()
        ])
        reqrole = f"<@&{gcfg['reqrole']}>" if gcfg.get("reqrole") else "None"

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.CUSTOMROLE}  Custom Roles [{len(roles)}]"),
            make_separator(),
            text(lines),
            make_separator(),
            text(f"{Emojis.SHIELD} **Required Role:** {reqrole}"),
            make_separator(),
            text(f"-# Requested by {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SETUP RESET ───
    @setup.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def setup_reset(self, ctx):
        data = load_setup()
        data[str(ctx.guild.id)] = {"roles": {}, "reqrole": None}
        save_setup(data)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  Custom roles configuration reset.")))
        await send_v2(ctx, view)

    # ─── SETUP CONFIG ───
    @setup.command(name="config")
    async def setup_config(self, ctx):
        data = load_setup()
        gid = str(ctx.guild.id)
        gcfg = data.get(gid, {"roles": {}, "reqrole": None})
        roles_count = len(gcfg.get("roles", {}))
        reqrole = f"<@&{gcfg['reqrole']}>" if gcfg.get("reqrole") else "Not Set"

        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SETTINGS}  Customrole Configuration"),
            make_separator(),
            text(
                f"{Emojis.ARROW} **Total Custom Roles:** `{roles_count}`\n"
                f"{Emojis.SHIELD} **Required Role:** {reqrole}\n"
                f"{Emojis.SERVER} **Server:** {ctx.guild.name}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── DYNAMIC ROLE HANDLER ───
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if not message.content.startswith(Config.PREFIX):
            return

        # Extract command name
        cmd_name = message.content[len(Config.PREFIX):].split()[0].lower() if len(message.content) > len(Config.PREFIX) else None
        if not cmd_name:
            return

        # Check if it's a registered bot command (skip if yes)
        if self.bot.get_command(cmd_name):
            return

        data = load_setup()
        gid = str(message.guild.id)
        gcfg = data.get(gid, {})
        roles = gcfg.get("roles", {})

        if cmd_name not in roles:
            return

        member = message.author

        # Check required role
        reqrole_id = gcfg.get("reqrole")
        if reqrole_id:
            reqrole = message.guild.get_role(int(reqrole_id))
            if reqrole and reqrole not in member.roles:
                view = discord.ui.LayoutView()
                view.add_item(MatrixContainer(
                    text(f"### {Emojis.ERROR}  Access Denied"),
                    make_separator(),
                    text(f"You need {reqrole.mention} role to use this command.")
                ))
                return await message.reply(view=view, mention_author=False)

        # Get role and toggle
        role = message.guild.get_role(int(roles[cmd_name]))
        if not role:
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(text(f"### {Emojis.ERROR}  Role no longer exists.")))
            return await message.reply(view=view, mention_author=False)

        try:
            if role in member.roles:
                await member.remove_roles(role)
                action = "Removed"
                emoji = Emojis.ERROR
            else:
                await member.add_roles(role)
                action = "Added"
                emoji = Emojis.SUCCESS

            view = discord.ui.LayoutView()
            container = MatrixContainer(
                text(f"### {emoji}  Role {action}"),
                make_separator(),
                text(
                    f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                    f"{Emojis.ROLE} **Role:** {role.mention}\n"
                    f"{Emojis.ARROW} **Action:** {action}"
                )
            )
            view.add_item(container)
            await message.reply(view=view, mention_author=False)
        except discord.Forbidden:
            view = discord.ui.LayoutView()
            view.add_item(MatrixContainer(text(f"### {Emojis.ERROR}  I don't have permission to manage this role.")))
            await message.reply(view=view, mention_author=False)


async def setup(bot):
    await bot.add_cog(Customrole(bot))