import discord
from discord.ext import commands
import random, aiohttp, asyncio, base64
from config import Config
from emojis import Emojis
from utils.components import MatrixContainer, text, make_separator, error_view, send_v2


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── CUTE ───
    @commands.command(name="cute")
    async def cute(self, ctx, member: discord.Member = None):
        if not member:
            return await send_v2(ctx, error_view("Please provide a person to check!"))
        percent = random.randint(1, 200)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.CUTE}  About your cuteness"),
            make_separator(),
            text(f"{member.mention} is **{percent}% Cute** {Emojis.HEART}"),
            make_separator(),
            text(f"-# How cute are you? - {ctx.author.name}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── DARE ───
    @commands.command(name="dare")
    async def dare(self, ctx):
        dares = [
            "Send your last selfie in the chat!",
            "DM your crush right now.",
            "Change your nickname to 'Loser' for 1 hour.",
            "Tell a deep secret in chat.",
            "Send a voice message singing a song.",
            "Post your most embarrassing photo.",
            "Type with your nose for the next 3 messages.",
        ]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.DARE}  Dare for {ctx.author.name}"),
            make_separator(),
            text(random.choice(dares))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── TRUTH ───
    @commands.command(name="truth")
    async def truth(self, ctx):
        truths = [
            "What's your biggest fear?",
            "Who was your first crush?",
            "What's the most embarrassing thing you've done?",
            "Have you ever lied to your best friend?",
            "What's a secret you've never told anyone?",
            "What's your weirdest habit?",
        ]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.TRUTH}  Truth for {ctx.author.name}"),
            make_separator(),
            text(random.choice(truths))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── FAKEBAN ───
    @commands.command(name="fakeban")
    async def fakeban(self, ctx, member: discord.Member = None, *, reason="No reason"):
        if not member:
            return await send_v2(ctx, error_view("Please mention a person to fakeban."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.BAN}  Successfully Banned {member}"),
            make_separator(),
            text(
                f"{Emojis.MEMBERS} **User:** {member.mention}\n"
                f"{Emojis.WARNING} **Reason:** {reason}\n"
                f"{Emojis.MOD} **Moderator:** {ctx.author.mention}"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── HACK ───
    @commands.command(name="hack")
    async def hack(self, ctx, member: discord.Member = None):
        if not member:
            return await send_v2(ctx, error_view("Please mention a person to hack."))
        msg = await ctx.send(f"```Hacking {member.name}...```")
        steps = [
            "🔍 Finding IP Address...",
            "📧 Getting Email...",
            "🔑 Cracking Password...",
            "📱 Accessing Phone...",
            "💾 Downloading Data...",
            f"{Emojis.SUCCESS} Hack Complete!"
        ]
        for s in steps:
            await asyncio.sleep(1)
            await msg.edit(content=f"```{s}```")
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.HACK}  Hack Results for {member.name}"),
            make_separator(),
            text(
                f"**IP:** `192.168.{random.randint(1,255)}.{random.randint(1,255)}`\n"
                f"**Email:** `{member.name.lower()}@gmail.com`\n"
                f"**Password:** `{member.name.lower()}123`\n"
                f"**Phone:** `+1 555-{random.randint(1000,9999)}`"
            ),
            make_separator(),
            text("-# This is just for fun, not real!")
        )
        view.add_item(container)
        await msg.delete()
        await send_v2(ctx, view)

    # ─── HOWGAY ───
    @commands.command(name="howgay")
    async def howgay(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        percent = random.randint(0, 100)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.GAY}  Gay Meter"),
            make_separator(),
            text(f"{member.mention} is **{percent}% Gay** {Emojis.GAY}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── HUG ───
    @commands.command(name="hug")
    async def hug(self, ctx, member: discord.Member = None):
        if not member:
            return await send_v2(ctx, error_view("Please mention someone to hug."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.HUG}  Hug"),
            make_separator(),
            text(f"{ctx.author.mention} hugged {member.mention} {Emojis.HEART}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── INTELLIGENCE ───
    @commands.command(name="intelligence", aliases=["iq"])
    async def intelligence(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        iq = random.randint(0, 200)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.IQ}  Intelligence Test"),
            make_separator(),
            text(f"{member.mention} has an IQ of **{iq}**")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── IPLOOKUP ───
    @commands.command(name="iplookup")
    async def iplookup(self, ctx, ip: str):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.GLOBE}  IP Lookup"),
            make_separator(),
            text(
                f"**IP:** `{ip}`\n"
                f"**Country:** Unknown\n"
                f"**ISP:** Unknown\n"
                f"-# Demo lookup (no real API)."
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── LESBIAN ───
    @commands.command(name="lesbian")
    async def lesbian(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        percent = random.randint(0, 100)
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.GAY}  Lesbian Meter"),
            make_separator(),
            text(f"{member.mention} is **{percent}% Lesbian**")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── MYDOG ───
    @commands.command(name="mydog")
    async def mydog(self, ctx):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://dog.ceo/api/breeds/image/random") as r:
                    data = await r.json()
                    img = data["message"]
        except:
            return await send_v2(ctx, error_view("Couldn't fetch dog image."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.DOG}  Here's a random dog!"),
            make_separator(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=img))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── QR ───
    @commands.command(name="qr")
    async def qr(self, ctx, *, text_data: str):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text_data}"
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.QR}  QR Code"),
            make_separator(),
            text(f"**Data:** {text_data}"),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=qr_url))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── QUOTE ───
    @commands.command(name="quote")
    async def quote(self, ctx):
        quotes = [
            "“Be yourself; everyone else is already taken.” — Oscar Wilde",
            "“The only way to do great work is to love what you do.” — Steve Jobs",
            "“In the end, we will remember not the words of our enemies, but the silence of our friends.” — MLK",
            "“Success is not final, failure is not fatal.” — Winston Churchill",
        ]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.QUOTE}  Random Quote"),
            make_separator(),
            text(random.choice(quotes))
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SAYHELLO ───
    @commands.command(name="sayhello")
    async def sayhello(self, ctx):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.HELLO}  Hello!"),
            make_separator(),
            text(f"Hi there {ctx.author.mention}! Hope you're having a great day! {Emojis.SPARKLE}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SHIP ───
    @commands.command(name="ship")
    async def ship(self, ctx, m1: discord.Member, m2: discord.Member):
        percent = random.randint(0, 100)
        name = m1.name[:len(m1.name)//2] + m2.name[len(m2.name)//2:]
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.LOVE}  Love Calculator"),
            make_separator(),
            text(
                f"**{m1.mention} {Emojis.HEART} {m2.mention}**\n"
                f"Compatibility: **{percent}%**\n"
                f"Ship Name: **{name}**"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SLAP ───
    @commands.command(name="slap")
    async def slap(self, ctx, member: discord.Member = None):
        if not member:
            return await send_v2(ctx, error_view("Please mention someone to slap."))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SLAP}  Slap!"),
            make_separator(),
            text(f"{ctx.author.mention} slapped {member.mention} {Emojis.CRASH}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SLOTS ───
    @commands.command(name="slots")
    async def slots(self, ctx):
        emojis = ["🍒", "🍋", "🍇", "🍉", "⭐", "💎"]
        result = [random.choice(emojis) for _ in range(3)]
        won = len(set(result)) == 1
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.SLOTS}  Slots"),
            make_separator(),
            text(f"**[ {' | '.join(result)} ]**\n\n{'🎉 You won!' if won else '😢 You lost!'}")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── SUDO ───
    @commands.command(name="sudo")
    @commands.has_permissions(manage_messages=True)
    async def sudo(self, ctx, member: discord.Member, *, message: str):
        wh = await ctx.channel.create_webhook(name=member.display_name)
        await wh.send(message, username=member.display_name, avatar_url=member.display_avatar.url)
        await wh.delete()
        try: await ctx.message.delete()
        except: pass

    # ─── TOKEN ───
    @commands.command(name="token")
    async def token(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        fake = base64.b64encode(str(member.id).encode()).decode() + "." + "".join(random.choices("abcdefghijklmnop0123456789", k=6)) + "." + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789_-", k=27))
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.KEY}  Fake Token Generator"),
            make_separator(),
            text(f"**{member.name}'s token:**\n||`{fake}`||\n-# Not a real token, just for fun.")
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── TRANSLATE ───
    @commands.command(name="translate")
    async def translate(self, ctx, lang: str, *, text_data: str):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.TRANSLATE}  Translator"),
            make_separator(),
            text(
                f"**Target Language:** `{lang}`\n"
                f"**Original:** {text_data}\n"
                f"**Translated:** *[Demo only — integrate Google Translate API for real use]*"
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── WEATHER ───
    @commands.command(name="weather")
    async def weather(self, ctx, *, city: str):
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WEATHER}  Weather - {city}"),
            make_separator(),
            text(
                f"**Temperature:** {random.randint(15,40)}°C\n"
                f"**Condition:** {random.choice(['Sunny','Cloudy','Rainy','Windy'])}\n"
                f"-# Demo data — integrate OpenWeather API for real."
            )
        )
        view.add_item(container)
        await send_v2(ctx, view)

    # ─── WIZZ ───
    @commands.command(name="wizz")
    async def wizz(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        view = discord.ui.LayoutView()
        container = MatrixContainer(
            text(f"### {Emojis.WIZZ}  Wizz!"),
            make_separator(),
            text(f"*{member.mention} got wizzed by {ctx.author.mention}!* {Emojis.SPARKLE}")
        )
        view.add_item(container)
        await send_v2(ctx, view)


async def setup(bot):
    await bot.add_cog(Fun(bot))