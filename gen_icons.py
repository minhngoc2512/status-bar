#!/usr/bin/env python3
"""Generate every tray icon as an SVG, one file per state.

Animation is done in the tray label, not here: GNOME Shell coalesces icon
changes to about one repaint per second, which is too slow for a spinner.

Icons are drawn on a 22x22 canvas with a 1.5px safety margin, use gradients so
they still read on both light and dark panels, and never rely on the panel's
own foreground colour (AppIndicator does not recolour symbolic icons).
"""

from __future__ import annotations

import math
from pathlib import Path

ICONS = Path(__file__).resolve().parent / "icons"

# Claude session states
BLUE, BLUE_DEEP = "#5aa9ff", "#2d6fd4"
AMBER, AMBER_DEEP, AMBER_INK = "#ffc14d", "#f59300", "#3d2600"
RED, RED_DEEP, RED_INK = "#ff6b6b", "#d93636", "#380505"
TEAL, TEAL_DEEP = "#3fd1c0", "#1a9e8f"
GREY, GREY_DEEP = "#b0b6bd", "#7d848c"

# Weather
SUN, SUN_DEEP = "#ffd451", "#ff9f1a"
MOON, MOON_DEEP = "#ccd7fb", "#8b9dd8"
CLOUD, CLOUD_DEEP = "#e2eaf3", "#93a6ba"
RAIN, RAIN_DEEP = "#63b8ff", "#2b7fd4"
SNOW = "#63b8ff"
BOLT, BOLT_DEEP = "#ffd451", "#ffa000"
FOG = "#a9b6c4"

# Crypto
GREEN, GREEN_DEEP = "#3ddc84", "#12a35b"
PINK, PINK_DEEP = "#ff6b6b", "#d93636"

HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
    'viewBox="0 0 22 22" shape-rendering="geometricPrecision">'
)
TAIL = "</svg>"


def write(name: str, body: str, defs: str = "") -> None:
    block = f"  <defs>\n{defs}  </defs>\n" if defs else ""
    (ICONS / f"{name}.svg").write_text(f"{HEAD}\n{block}{body}\n{TAIL}\n")


def linear(gid: str, top: str, bottom: str, x1=0, y1=0, x2=0, y2=22) -> str:
    """Vertical gradient in user space so it stays continuous across a group."""
    return (
        f'    <linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
        f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">\n'
        f'      <stop offset="0" stop-color="{top}"/>\n'
        f'      <stop offset="1" stop-color="{bottom}"/>\n'
        f"    </linearGradient>\n"
    )


def radial(gid: str, inner: str, outer: str, cx=11.0, cy=11.0, r=8.0) -> str:
    return (
        f'    <radialGradient id="{gid}" gradientUnits="userSpaceOnUse" '
        f'cx="{cx}" cy="{cy}" r="{r}">\n'
        f'      <stop offset="0" stop-color="{inner}"/>\n'
        f'      <stop offset="1" stop-color="{outer}"/>\n'
        f"    </radialGradient>\n"
    )


# --------------------------------------------------------------------------- #
# shared pieces
# --------------------------------------------------------------------------- #


def cloud(fill: str, cx: float = 11.0, cy: float = 12.2, scale: float = 1.0) -> str:
    """A cloud built from two discs and a rounded base, filled as one shape."""
    s = scale
    return (
        f'  <g fill="{fill}">\n'
        f'    <circle cx="{cx - 2.4 * s:.2f}" cy="{cy + 0.2 * s:.2f}" r="{3.35 * s:.2f}"/>\n'
        f'    <circle cx="{cx + 1.5 * s:.2f}" cy="{cy - 1.0 * s:.2f}" r="{4.15 * s:.2f}"/>\n'
        f'    <rect x="{cx - 5.7 * s:.2f}" y="{cy + 0.1 * s:.2f}" '
        f'width="{11.2 * s:.2f}" height="{3.5 * s:.2f}" rx="{1.75 * s:.2f}"/>\n'
        f"  </g>\n"
    )


def sun_rays(cx: float, cy: float, inner: float, outer: float, colour: str, width: float) -> str:
    out = []
    for step in range(8):
        angle = math.radians(step * 45)
        dx, dy = math.cos(angle), math.sin(angle)
        out.append(
            f'    <path d="M{cx + dx * inner:.2f} {cy + dy * inner:.2f}'
            f'L{cx + dx * outer:.2f} {cy + dy * outer:.2f}"/>'
        )
    return (
        f'  <g stroke="{colour}" stroke-width="{width}" stroke-linecap="round">\n'
        + "\n".join(out)
        + "\n  </g>\n"
    )


def streaks(points: list[tuple[float, float]], colour: str, width: float, dx: float, dy: float) -> str:
    lines = "\n".join(
        f'    <path d="M{x:.2f} {y:.2f}L{x + dx:.2f} {y + dy:.2f}"/>' for x, y in points
    )
    return (
        f'  <g stroke="{colour}" stroke-width="{width}" stroke-linecap="round">\n'
        f"{lines}\n  </g>\n"
    )


def flake(cx: float, cy: float, r: float, colour: str) -> str:
    arms = []
    for step in range(3):
        angle = math.radians(step * 60)
        dx, dy = math.cos(angle) * r, math.sin(angle) * r
        arms.append(f'    <path d="M{cx - dx:.2f} {cy - dy:.2f}L{cx + dx:.2f} {cy + dy:.2f}"/>')
    return (
        f'  <g stroke="{colour}" stroke-width="0.95" stroke-linecap="round">\n'
        + "\n".join(arms)
        + "\n  </g>\n"
    )


# --------------------------------------------------------------------------- #
# claude session states
# --------------------------------------------------------------------------- #


def claude_icons() -> None:
    write(
        "claude-idle",
        f'  <circle cx="11" cy="11" r="6.6" fill="none" stroke="url(#g)" stroke-width="1.9"/>\n'
        f'  <circle cx="11" cy="11" r="1.7" fill="{GREY_DEEP}" opacity="0.7"/>',
        linear("g", GREY, GREY_DEEP, y1=4, y2=18),
    )
    write(
        "claude-working",
        f'  <circle cx="11" cy="11" r="6.6" fill="none" stroke="{BLUE}" '
        f'stroke-width="1.9" opacity="0.35"/>\n'
        f'  <path d="M11 4.4a6.6 6.6 0 0 1 6.6 6.6" fill="none" stroke="url(#g)" '
        f'stroke-width="2.4" stroke-linecap="round"/>\n'
        f'  <circle cx="11" cy="11" r="2.5" fill="url(#g)"/>',
        linear("g", BLUE, BLUE_DEEP, y1=4, y2=18),
    )
    write(
        "claude-confirm",
        f'  <circle cx="11" cy="11" r="7.8" fill="url(#g)"/>\n'
        f'  <rect x="9.85" y="6.1" width="2.3" height="6.7" rx="1.15" fill="{AMBER_INK}"/>\n'
        f'  <circle cx="11" cy="15.2" r="1.35" fill="{AMBER_INK}"/>',
        radial("g", AMBER, AMBER_DEEP, r=9),
    )
    write(
        "claude-error",
        f'  <circle cx="11" cy="11" r="7.8" fill="url(#g)"/>\n'
        f'  <path d="M8.1 8.1l5.8 5.8M13.9 8.1l-5.8 5.8" stroke="{RED_INK}" '
        f'stroke-width="2.2" stroke-linecap="round"/>',
        radial("g", RED, RED_DEEP, r=9),
    )
    write(
        "claude-background",
        f'  <circle cx="11" cy="11" r="6.6" fill="none" stroke="url(#g)" stroke-width="1.9" '
        f'stroke-dasharray="3.3 2.7" stroke-linecap="round"/>\n'
        f'  <circle cx="11" cy="11" r="2.5" fill="url(#g)"/>',
        linear("g", TEAL, TEAL_DEEP, y1=4, y2=18),
    )


# --------------------------------------------------------------------------- #
# weather
# --------------------------------------------------------------------------- #


def weather_icons() -> None:
    """Geometry note: the artwork fills roughly x/y 2..20 of the 22px canvas.

    GNOME scales the whole canvas to the panel's icon size, so a glyph drawn
    small inside it ends up visibly smaller than every neighbouring icon.
    """
    write(
        "weather-sun",
        sun_rays(11, 11, 6.5, 9.4, "url(#s)", 1.8)
        + '  <circle cx="11" cy="11" r="4.8" fill="url(#s)"/>',
        radial("s", SUN, SUN_DEEP, r=9.5),
    )

    # Crescent: a disc with a second disc masked out, so the geometry is exact.
    write(
        "weather-moon",
        '  <circle cx="10.4" cy="11" r="8.0" fill="url(#m)" mask="url(#bite)"/>',
        radial("m", MOON, MOON_DEEP, cx=8.4, cy=8.6, r=11)
        + '    <mask id="bite">\n'
        '      <rect width="22" height="22" fill="white"/>\n'
        '      <circle cx="14.9" cy="7.7" r="7.1" fill="black"/>\n'
        "    </mask>\n",
    )

    write("weather-cloud", cloud("url(#c)", cy=12.2, scale=1.6), linear("c", CLOUD, CLOUD_DEEP, y1=4, y2=18))

    write(
        "weather-cloud-sun",
        sun_rays(6.8, 6.6, 4.2, 6.4, "url(#s)", 1.4)
        + '  <circle cx="6.8" cy="6.6" r="3.1" fill="url(#s)"/>\n'
        + cloud("url(#c)", cx=12.6, cy=13.0, scale=1.15),
        radial("s", SUN, SUN_DEEP, cx=6.8, cy=6.6, r=6.5) + linear("c", CLOUD, CLOUD_DEEP, y1=7, y2=19),
    )

    write(
        "weather-cloud-moon",
        '  <circle cx="7.2" cy="7.0" r="5.6" fill="url(#m)" mask="url(#bite)"/>\n'
        + cloud("url(#c)", cx=12.6, cy=13.0, scale=1.15),
        radial("m", MOON, MOON_DEEP, cx=5.6, cy=5.4, r=8)
        + '    <mask id="bite">\n'
        '      <rect width="22" height="22" fill="white"/>\n'
        '      <circle cx="10.6" cy="4.6" r="5.0" fill="black"/>\n'
        "    </mask>\n"
        + linear("c", CLOUD, CLOUD_DEEP, y1=7, y2=19),
    )

    write(
        "weather-rain",
        cloud("url(#c)", cy=8.6, scale=1.3)
        + streaks([(6.6, 14.9), (11.0, 14.9), (15.4, 14.9)], "url(#r)", 1.9, -1.4, 4.2),
        linear("c", CLOUD, CLOUD_DEEP, y1=1, y2=14) + linear("r", RAIN, RAIN_DEEP, y1=14, y2=20),
    )

    write(
        "weather-snow",
        cloud("url(#c)", cy=8.6, scale=1.3)
        + flake(6.2, 16.6, 2.1, SNOW)
        + flake(11.0, 17.8, 2.1, SNOW)
        + flake(15.8, 16.6, 2.1, SNOW),
        linear("c", CLOUD, CLOUD_DEEP, y1=1, y2=14),
    )

    write(
        "weather-storm",
        cloud("url(#c)", cy=8.0, scale=1.3)
        + '  <path d="M11.9 12.4h3.6l-5.4 8.0 1.3-5.0H8.0l4.0-6.0z" fill="url(#b)"/>',
        linear("c", CLOUD, CLOUD_DEEP, y1=1, y2=13) + linear("b", BOLT, BOLT_DEEP, y1=11, y2=21),
    )

    write(
        "weather-fog",
        cloud("url(#c)", cy=7.6, scale=1.25)
        + f'  <g stroke="{FOG}" stroke-width="1.9" stroke-linecap="round">\n'
        '    <path d="M3.4 15.4h15.2"/>\n'
        '    <path d="M5.6 18.8h11.6"/>\n'
        "  </g>",
        linear("c", CLOUD, CLOUD_DEEP, y1=1, y2=13),
    )

    write(
        "weather-unknown",
        cloud("url(#c)", cy=11.6, scale=1.5)
        + f'  <path d="M9.1 10.0a2.1 2.1 0 1 1 2.9 1.95c-.65.33-.9.8-.9 1.5" fill="none" '
        f'stroke="{GREY_DEEP}" stroke-width="1.6" stroke-linecap="round"/>\n'
        f'  <circle cx="11.05" cy="15.7" r="1.05" fill="{GREY_DEEP}"/>',
        linear("c", CLOUD, CLOUD_DEEP, y1=3, y2=18),
    )


# --------------------------------------------------------------------------- #
# crypto
# --------------------------------------------------------------------------- #


def chart(gid: str, rising: bool) -> str:
    """Trend line with a filled arrow head in the corner it points at."""
    if rising:
        line = "M3.6 16.4L8.3 11.6L11.4 14.1L17.0 7.4"
        head = "M12.9 6.0h5.6v5.6z"
    else:
        line = "M3.6 5.6L8.3 10.4L11.4 7.9L17.0 14.6"
        head = "M12.9 16.0h5.6v-5.6z"
    return (
        f'  <path d="{line}" fill="none" stroke="url(#{gid})" stroke-width="2.15" '
        f'stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'  <path d="{head}" fill="url(#{gid})"/>'
    )


def crypto_icons() -> None:
    write("crypto-up", chart("g", True), linear("g", GREEN, GREEN_DEEP, y1=5, y2=17))
    write("crypto-down", chart("g", False), linear("g", PINK, PINK_DEEP, y1=5, y2=17))
    write(
        "crypto-flat",
        '  <path d="M3.6 13.6L8.3 13.6L11.4 9.4L14.4 13.6L18.4 13.6" fill="none" '
        'stroke="url(#g)" stroke-width="2.15" stroke-linecap="round" stroke-linejoin="round"/>',
        linear("g", GREY, GREY_DEEP, y1=8, y2=16),
    )
    write(
        "crypto-error",
        '  <path d="M3.4 15.4L8.0 10.8L11.0 13.2L15.2 8.6" fill="none" stroke="url(#g)" '
        'stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'  <circle cx="16.6" cy="6.2" r="4.4" fill="{AMBER_DEEP}"/>\n'
        f'  <rect x="15.95" y="3.5" width="1.3" height="3.4" rx="0.65" fill="{AMBER_INK}"/>\n'
        f'  <circle cx="16.6" cy="8.05" r="0.8" fill="{AMBER_INK}"/>',
        linear("g", GREY, GREY_DEEP, y1=8, y2=16),
    )


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    claude_icons()
    weather_icons()
    crypto_icons()
    print(f"wrote {len(list(ICONS.glob('*.svg')))} icons into {ICONS}")


if __name__ == "__main__":
    main()
