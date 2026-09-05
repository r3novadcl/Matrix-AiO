import discord
from discord.ext import commands
import json, os
from config import Config
from emojis import Emojis
from utils.fastconfig import CachedFile
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2

VOICE_FILE = "voice.json"

# In-memory cached — no disk read/write on the hot path anymore.
_cache = CachedFile(VOICE_FILE, dict)

def load_voice():
    return _cache.load()

def save_voice(d):
    _cache.save(d)


def get_user_vc(member: discord.Member):
    """Get the voice channel a member is in."""
    if member.voice and member.voice.channel:
        return member.voice.channel
    return None


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── VC BAN ───
    @commands.command(name="vcban")
    @commands.has_permissions(move_members=True)
    async def vcban(self, ctx, member: discord.Member):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        await vc.set_permissions(member, connect=False, speak=False)
        if member.voice and member.voice.channel == vc:
            await member.move_to(None)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_BAN}  VC Banned"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} banned from {vc.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC UNBAN ───
    @commands.command(name="vcunban")
    @commands.has_permissions(move_members=True)
    async def vcunban(self, ctx, member: discord.Member):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        await vc.set_permissions(member, overwrite=None)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_UNBAN}  VC Unbanned"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} unbanned from {vc.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC DEAFEN ───
    @commands.command(name="vcdeafen")
    @commands.has_permissions(deafen_members=True)
    async def vcdeafen(self, ctx, member: discord.Member):
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in a voice channel."))
        await member.edit(deafen=True)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_DEAF}  Deafened"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} has been deafened.")
        ))
        await send_v2(ctx, view)

    # ─── VC UNDEAFEN ───
    @commands.command(name="vcundeafen")
    @commands.has_permissions(deafen_members=True)
    async def vcundeafen(self, ctx, member: discord.Member):
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in a voice channel."))
        await member.edit(deafen=False)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_UNDEAF}  Undeafened"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} has been undeafened.")
        ))
        await send_v2(ctx, view)

    # ─── VC DEAFEN ALL ───
    @commands.command(name="vcdeafenall")
    @commands.has_permissions(deafen_members=True)
    async def vcdeafenall(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in vc.members:
            try: await m.edit(deafen=True); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_DEAF}  Deafened All"),
            make_separator(),
            text(f"{Emojis.ARROW} Deafened {count} members in {vc.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC UNDEAFEN ALL ───
    @commands.command(name="vcundeafenall")
    @commands.has_permissions(deafen_members=True)
    async def vcundeafenall(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in vc.members:
            try: await m.edit(deafen=False); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_UNDEAF}  Undeafened All"),
            make_separator(),
            text(f"{Emojis.ARROW} Undeafened {count} members.")
        ))
        await send_v2(ctx, view)

    # ─── VC MUTE ───
    @commands.command(name="vcmute")
    @commands.has_permissions(mute_members=True)
    async def vcmute(self, ctx, member: discord.Member):
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in a voice channel."))
        await member.edit(mute=True)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_MUTE}  VC Muted"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} has been muted.")
        ))
        await send_v2(ctx, view)

    # ─── VC UNMUTE ───
    @commands.command(name="vcunmute")
    @commands.has_permissions(mute_members=True)
    async def vcunmute(self, ctx, member: discord.Member):
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in a voice channel."))
        await member.edit(mute=False)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_UNMUTE}  VC Unmuted"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} has been unmuted.")
        ))
        await send_v2(ctx, view)

    # ─── VC MUTE ALL ───
    @commands.command(name="vcmuteall")
    @commands.has_permissions(mute_members=True)
    async def vcmuteall(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in vc.members:
            try: await m.edit(mute=True); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.VOICE_MUTE}  Muted {count} members.")))
        await send_v2(ctx, view)

    # ─── VC UNMUTE ALL ───
    @commands.command(name="vcunmuteall")
    @commands.has_permissions(mute_members=True)
    async def vcunmuteall(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in vc.members:
            try: await m.edit(mute=False); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.VOICE_UNMUTE}  Unmuted {count} members.")))
        await send_v2(ctx, view)

    # ─── VC KICK ───
    @commands.command(name="vckick")
    @commands.has_permissions(move_members=True)
    async def vckick(self, ctx, member: discord.Member):
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in a voice channel."))
        await member.move_to(None)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_KICK}  VC Kicked"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} kicked from voice channel.")
        ))
        await send_v2(ctx, view)

    # ─── VC KICK ALL ───
    @commands.command(name="vckickall")
    @commands.has_permissions(move_members=True)
    async def vckickall(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in vc.members:
            if m == ctx.author:
                continue
            try: await m.move_to(None); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.VOICE_KICK}  Kicked {count} members from {vc.mention}")))
        await send_v2(ctx, view)

    # ─── VC HIDE ───
    @commands.command(name="vchide")
    @commands.has_permissions(manage_channels=True)
    async def vchide(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        await vc.set_permissions(ctx.guild.default_role, view_channel=False)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_HIDE}  VC Hidden"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} {vc.mention} is now hidden.")
        ))
        await send_v2(ctx, view)

    # ─── VC UNHIDE ───
    @commands.command(name="vcunhide")
    @commands.has_permissions(manage_channels=True)
    async def vcunhide(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        await vc.set_permissions(ctx.guild.default_role, view_channel=None)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_UNHIDE}  VC Unhidden"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} {vc.mention} is now visible.")
        ))
        await send_v2(ctx, view)

    # ─── VC LOCK ───
    @commands.command(name="vclock")
    @commands.has_permissions(manage_channels=True)
    async def vclock(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        await vc.set_permissions(ctx.guild.default_role, connect=False)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_LOCK}  VC Locked"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} {vc.mention} is now locked.")
        ))
        await send_v2(ctx, view)

    # ─── VC UNLOCK ───
    @commands.command(name="vcunlock")
    @commands.has_permissions(manage_channels=True)
    async def vcunlock(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        await vc.set_permissions(ctx.guild.default_role, connect=None)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_UNLOCK}  VC Unlocked"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} {vc.mention} is now unlocked.")
        ))
        await send_v2(ctx, view)

    # ─── VC LIST ───
    @commands.command(name="vclist")
    async def vclist(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        members = "\n".join([f"{Emojis.ARROW} {m.mention}" for m in vc.members]) or "Empty"
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.VOICE_LIST}  VC Members [{len(vc.members)}]"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} **Channel:** {vc.mention}"),
            make_separator(),
            text(members)
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── VC MOVE ───
    @commands.command(name="vcmove")
    @commands.has_permissions(move_members=True)
    async def vcmove(self, ctx, member: discord.Member, *, channel: discord.VoiceChannel):
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in a voice channel."))
        await member.move_to(channel)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_MOVE}  Moved"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} moved to {channel.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC MOVE ALL ───
    @commands.command(name="vcmoveall")
    @commands.has_permissions(move_members=True)
    async def vcmoveall(self, ctx, *, channel: discord.VoiceChannel):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in list(vc.members):
            try: await m.move_to(channel); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_MOVE}  Moved All"),
            make_separator(),
            text(f"{Emojis.ARROW} Moved {count} members to {channel.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC PULL ───
    @commands.command(name="vcpull")
    @commands.has_permissions(move_members=True)
    async def vcpull(self, ctx, member: discord.Member):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        if not member.voice:
            return await send_v2(ctx, error_view("Member is not in any voice channel."))
        await member.move_to(vc)
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_PULL}  Pulled"),
            make_separator(),
            text(f"{Emojis.MEMBERS} {member.mention} pulled to {vc.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC PULL ALL ───
    @commands.command(name="vcpullall")
    @commands.has_permissions(move_members=True)
    async def vcpullall(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for ch in ctx.guild.voice_channels:
            if ch == vc: continue
            for m in list(ch.members):
                try: await m.move_to(vc); count += 1
                except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.VOICE_PULL}  Pulled {count} members to {vc.mention}")))
        await send_v2(ctx, view)

    # ─── VC PUSH ALL ───
    @commands.command(name="vcpushall")
    @commands.has_permissions(move_members=True)
    async def vcpushall(self, ctx, *, channel: discord.VoiceChannel):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in list(vc.members):
            if m == ctx.author: continue
            try: await m.move_to(channel); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(text(f"### {Emojis.VOICE_PUSH}  Pushed {count} members to {channel.mention}")))
        await send_v2(ctx, view)

    # ─── VC REQUEST ───
    @commands.command(name="vcrequest")
    async def vcrequest(self, ctx, member: discord.Member):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))

        view = discord.ui.LayoutView()

        async def accept_cb(i):
            if i.user != member:
                return await i.response.send_message("This is not for you.", ephemeral=True)
            try:
                await member.move_to(vc)
                await i.response.edit_message(view=None)
                vv = discord.ui.LayoutView()
                vv.add_item(MatrixContainer(text(f"### {Emojis.SUCCESS}  {member.mention} accepted!")))
                await i.followup.send(view=vv)
            except:
                await i.response.send_message("Couldn't move you.", ephemeral=True)

        async def decline_cb(i):
            if i.user != member:
                return await i.response.send_message("This is not for you.", ephemeral=True)
            await i.response.edit_message(view=None)
            vv = discord.ui.LayoutView()
            vv.add_item(MatrixContainer(text(f"### {Emojis.ERROR}  {member.mention} declined.")))
            await i.followup.send(view=vv)

        accept_btn = discord.ui.Button(label="Accept", style=discord.ButtonStyle.success)
        decline_btn = discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger)
        accept_btn.callback = accept_cb
        decline_btn.callback = decline_cb

        container = MatrixContainer(
            text(member.mention),
            text(f"### {Emojis.VOICE_REQUEST}  Voice Channel Request"),
            make_separator(),
            text(f"{ctx.author.mention} is inviting {member.mention} to join {vc.mention}"),
            make_separator(),
            discord.ui.ActionRow(accept_btn, decline_btn)
        )
        view.add_item(container)
        await ctx.send(view=view)

    # ─── VC ROLE ───
    @commands.command(name="vcrole")
    @commands.has_permissions(manage_roles=True)
    async def vcrole(self, ctx, role: discord.Role):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))
        count = 0
        for m in vc.members:
            try: await m.add_roles(role); count += 1
            except: pass
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_ROLE}  VC Role Applied"),
            make_separator(),
            text(f"{Emojis.ARROW} Gave {role.mention} to {count} members in {vc.mention}")
        ))
        await send_v2(ctx, view)

    # ─── VC RECORD (placeholder) ───
    @commands.command(name="record")
    async def record(self, ctx):
        view = discord.ui.LayoutView()
        view.add_item(MatrixContainer(
            text(f"### {Emojis.VOICE_REC}  Recording"),
            make_separator(),
            text("Voice recording feature requires extra setup. Coming soon!")
        ))
        await send_v2(ctx, view)

    # ─── VOICE INFO ───
    @commands.command(name="voice")
    async def voice_info(self, ctx, channel: discord.VoiceChannel = None):
        channel = channel or get_user_vc(ctx.author)
        if not channel:
            return await send_v2(ctx, error_view("Please specify a voice channel or join one."))
        members = "\n".join([f"{Emojis.ARROW} {m.mention}" for m in channel.members]) or "Empty"
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.VOICE_MIC}  Voice Channel Info"),
            make_separator(),
            text(
                f"{Emojis.CHANNEL} **Name:** {channel.name}\n"
                f"{Emojis.ID} **ID:** `{channel.id}`\n"
                f"{Emojis.MEMBERS} **Members:** {len(channel.members)}/{channel.user_limit or '∞'}\n"
                f"{Emojis.ARROW} **Bitrate:** {channel.bitrate // 1000}kbps\n"
                f"{Emojis.CATEGORY} **Category:** {channel.category.name if channel.category else 'None'}"
            ),
            make_separator(),
            text(f"**Members:**\n{members}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── VOICE PANEL ───
    @commands.command(name="voicepannel", aliases=["voicepanel"])
    @commands.has_permissions(manage_channels=True)
    async def voicepannel(self, ctx):
        vc = get_user_vc(ctx.author)
        if not vc:
            return await send_v2(ctx, error_view("You must be in a voice channel."))

        view = discord.ui.LayoutView()

        def make_btn(label, emoji, style, action):
            btn = discord.ui.Button(label=label, emoji=emoji, style=style)
            async def cb(i):
                if not i.user.guild_permissions.manage_channels:
                    return await i.response.send_message("No permission.", ephemeral=True)
                if action == "lock":
                    await vc.set_permissions(ctx.guild.default_role, connect=False)
                    msg = "🔒 Locked"
                elif action == "unlock":
                    await vc.set_permissions(ctx.guild.default_role, connect=None)
                    msg = "🔓 Unlocked"
                elif action == "hide":
                    await vc.set_permissions(ctx.guild.default_role, view_channel=False)
                    msg = "🙈 Hidden"
                elif action == "unhide":
                    await vc.set_permissions(ctx.guild.default_role, view_channel=None)
                    msg = "👁️ Unhidden"
                elif action == "muteall":
                    for m in vc.members:
                        try: await m.edit(mute=True)
                        except: pass
                    msg = "🔇 Muted all"
                elif action == "unmuteall":
                    for m in vc.members:
                        try: await m.edit(mute=False)
                        except: pass
                    msg = "🔊 Unmuted all"
                await i.response.send_message(msg, ephemeral=True)
            btn.callback = cb
            return btn

        container = MatrixContainer(
            text(f"### {Emojis.VOICE_PANEL}  Voice Control Panel"),
            make_separator(),
            text(f"{Emojis.VOICE_MIC} **Channel:** {vc.mention}\n{Emojis.MEMBERS} **Members:** {len(vc.members)}"),
            make_separator(),
            discord.ui.ActionRow(
                make_btn("Lock",   Emojis.VOICE_LOCK,   discord.ButtonStyle.danger,  "lock"),
                make_btn("Unlock", Emojis.VOICE_UNLOCK, discord.ButtonStyle.success, "unlock"),
            ),
            discord.ui.ActionRow(
                make_btn("Hide",    Emojis.VOICE_HIDE,   discord.ButtonStyle.danger,  "hide"),
                make_btn("Unhide",  Emojis.VOICE_UNHIDE, discord.ButtonStyle.success, "unhide"),
            ),
            discord.ui.ActionRow(
                make_btn("Mute All",   Emojis.VOICE_MUTE,   discord.ButtonStyle.danger,  "muteall"),
                make_btn("Unmute All", Emojis.VOICE_UNMUTE, discord.ButtonStyle.success, "unmuteall"),
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)


async def setup(bot):
    await bot.add_cog(Voice(bot))