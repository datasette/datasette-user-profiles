import re
from urllib.parse import quote

# 16 Bootstrap Icons (outline style) — inner SVG content only (no <svg> wrapper).
# Source: https://icons.getbootstrap.com/ (MIT license)
AVATAR_ICONS: dict[str, str] = {}


def _load_icons():
    """Load icon SVG paths from the icons/ directory."""
    import os

    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    for filename in os.listdir(icons_dir):
        if not filename.endswith(".svg"):
            continue
        name = filename[:-4]
        with open(os.path.join(icons_dir, filename)) as f:
            content = f.read().strip()
        # Strip the outer <svg> wrapper, keep inner paths
        inner = re.sub(r"^<svg[^>]*>", "", content)
        inner = re.sub(r"</svg>\s*$", "", inner).strip()
        AVATAR_ICONS[name] = inner


_load_icons()

# Catppuccin Mocha accent colors
# Source: https://github.com/catppuccin/catppuccin
AVATAR_COLORS: dict[str, str] = {
    "red": "#d20f39",
    "peach": "#fe640b",
    "yellow": "#df8e1d",
    "green": "#40a02b",
    "teal": "#179299",
    "blue": "#1e66f5",
    "mauve": "#8839ef",
    "pink": "#ea76cb",
}


def valid_avatar(icon_name: str | None, color: str | None) -> bool:
    """True if ``generate_avatar_svg`` can render this icon/colour pair."""
    return (
        icon_name is not None
        and icon_name in AVATAR_ICONS
        and color is not None
        and re.match(r"^#[0-9a-fA-F]{6}$", color) is not None
    )


def generate_avatar_svg(icon_name: str, color: str, size: int = 96) -> str | None:
    """Generate an SVG avatar: colored circle with white icon centered inside."""
    if not valid_avatar(icon_name, color):
        return None
    inner = AVATAR_ICONS[icon_name]
    # The Bootstrap icons use a 16x16 viewBox. Scale to fill ~60% of the circle.
    icon_size = size * 0.5625  # 54 out of 96
    offset = (size - icon_size) / 2
    scale = icon_size / 16
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{size // 2}" cy="{size // 2}" r="{size // 2}" fill="{color}"/>'
        f'<g transform="translate({offset:.1f},{offset:.1f}) scale({scale:.4f})" fill="white">'
        f"{inner}"
        f"</g></svg>"
    )


# Characters left unescaped in the actor id path segment: RFC 3986 "pchar"
# minus "%", so ids like ``alice@example.com`` keep their existing URLs.
_PATH_SAFE = "@:!$&'()*+,;="


def quote_actor_id(actor_id: str) -> str:
    """Percent-encode an actor id for use as a single URL path segment."""
    return quote(str(actor_id), safe=_PATH_SAFE)


def avatar_url(
    datasette,
    actor_id: str,
    *,
    photo_updated_at: str | None,
    avatar_icon: str | None,
    avatar_color: str | None,
    profile_updated_at: str | None,
) -> str | None:
    """URL of ``/-/profile/pic/<id>``, or ``None`` when that route would 404.

    Mirrors ``routes.pages.profile_pic``: an uploaded photo wins, then a valid
    generated icon avatar. The ``?v=`` stamp changes whenever the rendered
    image does (photo replaced or removed, icon changed), so the long
    ``max-age`` on the pic route never serves a stale face.
    """
    if photo_updated_at:
        stamp = photo_updated_at
    elif valid_avatar(avatar_icon, avatar_color):
        stamp = profile_updated_at or ""
    else:
        return None
    path = datasette.urls.path(f"/-/profile/pic/{quote_actor_id(actor_id)}")
    return f"{path}?v={quote(stamp, safe=':')}"
