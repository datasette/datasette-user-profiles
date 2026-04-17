import re

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


def generate_avatar_svg(icon_name: str, color: str, size: int = 96) -> str | None:
    """Generate an SVG avatar: colored circle with white icon centered inside."""
    inner = AVATAR_ICONS.get(icon_name)
    if inner is None:
        return None
    # Validate color is a hex color
    if not re.match(r"^#[0-9a-fA-F]{6}$", color):
        return None
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
