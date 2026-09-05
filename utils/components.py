import discord
from config import Config
from emojis import Emojis


class MatrixContainer(discord.ui.Container):
    """Base Container with red accent color."""
    def __init__(self, *children, accent_color: int = None):
        super().__init__(*children, accent_color=accent_color or Config.COLOR_PRIMARY)


def make_separator(spacing: discord.SeparatorSpacing = discord.SeparatorSpacing.small,
                   divider: bool = True) -> discord.ui.Separator:
    return discord.ui.Separator(spacing=spacing, visible=divider)


def text(content: str) -> discord.ui.TextDisplay:
    return discord.ui.TextDisplay(content)


def error_view(message: str, usage: str = None) -> discord.ui.LayoutView:
    """Quick error container."""
    body = f"{Emojis.ERROR}  | {message}"
    if usage:
        body += f"\n```\n{usage}\n```"
    view = discord.ui.LayoutView()
    container = MatrixContainer(text(body))
    view.add_item(container)
    return view


def success_view(title: str, fields: list[tuple[str, str]] = None,
                 footer: str = None, buttons: list[discord.ui.Button] = None) -> discord.ui.LayoutView:
    """Quick success container with fields."""
    view = discord.ui.LayoutView()
    children = [text(f"### {Emojis.SUCCESS}  {title}")]
    if fields:
        children.append(make_separator())
        for name, value in fields:
            children.append(text(f"**{name}** {value}"))
    if footer:
        children.append(make_separator())
        children.append(text(f"-# {footer}"))
    if buttons:
        children.append(discord.ui.ActionRow(*buttons))
    container = MatrixContainer(*children)
    view.add_item(container)
    return view


async def send_v2(ctx, view: discord.ui.LayoutView):
    """Send a Components V2 message."""
    return await ctx.send(view=view)