"""Constant-width number formatting for tray labels.

GNOME's status area is right-aligned, so an indicator that gets one character
wider pushes every indicator to its left sideways. A network rate crossing from
2 digits to 3 is enough to make the CPU and RAM readings visibly jitter.

Measured in Ubuntu 11, the panel font on the test machine:

    digits 0-9      8 px each (tabular, so numbers already line up)
    "."             4 px
    U+0020 space    3 px      <- padding with this does NOT line up
    U+2007 figure   8 px      <- defined as the width of a digit
    U+2008 punct    4 px      <- defined as the width of a period
    "K" "M" "G" "B" 9, 13, 10, 10 px

So digits and the decimal point can be padded with characters that are defined
relative to them, but the unit letters cannot -- nothing in Unicode is defined
as "the width of a K". Those are matched by measuring the actual font; see
``use_font_metrics``.

Escape sequences rather than literal characters on purpose: every space here is
invisible in an editor and trivial to destroy with a careless edit.
"""

from __future__ import annotations

FIGURE_SPACE = " "  # advance width of a digit, by definition
POINT_SPACE = " "  # advance width of a period, by definition
THIN_SPACE = " "
HAIR_SPACE = " "

# Widest first: pad_unit fills a gap greedily from these.
PAD_GLYPHS = (FIGURE_SPACE, POINT_SPACE, THIN_SPACE, HAIR_SPACE)

# Installed by the app once GTK is up (claude_status/panel.py). Without it the
# unit letters are left alone, which is what the tests and headless use get.
_measure = None


def use_font_metrics(measure) -> None:
    """Install a text -> pixel-width function so unit padding can be exact."""
    global _measure
    _measure = measure


def pad(text: str, width: int) -> str:
    """Right-align to ``width`` characters using digit-width spaces."""
    return FIGURE_SPACE * max(0, width - len(text)) + text


def pad_number(text: str, digits: int = 3) -> str:
    """Pad to ``digits`` digit slots plus exactly one period slot.

    "1.1" and "512" must come out the same width even though one spends a slot
    on a period, which is narrower than a digit -- hence the extra POINT_SPACE
    for the values that carry no decimal point.
    """
    body = FIGURE_SPACE * max(0, digits - sum(c.isdigit() for c in text)) + text
    return body if "." in text else POINT_SPACE + body


def unit_fill(unit: str, family: tuple[str, ...]) -> str:
    """Spaces that make ``unit`` occupy as much room as the widest of ``family``.

    Returned as a *prefix* rather than appended to the unit: a label must never
    end in padding, because anything that trims trailing whitespace on the way
    to the panel would bring the jitter straight back.
    """
    if _measure is None:
        return ""
    try:
        gap = max(_measure(u) for u in family) - _measure(unit)
    except Exception:  # noqa: BLE001 - a broken measurer must not break the label
        return ""
    fill = ""
    for glyph in PAD_GLYPHS:
        step = _measure(glyph)
        while step > 0 and gap >= step:
            fill += glyph
            gap -= step
    return fill


# Smallest unit first. The mantissa must stay under 999.5 so it never rounds to
# a fourth digit -- 1023 B/s would otherwise render as "1023B" and be one cell
# wider than everything else. That means switching unit slightly before the
# usual 1024 (or 1000) boundary, which costs nothing visually.
BYTE_UNITS = ((1, "B"), (1024, "K"), (1024**2, "M"), (1024**3, "G"), (1024**4, "T"))
# Bits never scale below kb, so the suffix is always two characters wide.
BIT_UNITS = ((1e3, "kb"), (1e6, "Mb"), (1e9, "Gb"), (1e12, "Tb"))

MANTISSA_CEILING = 999.5


def _scale(value: float, units) -> tuple[float, str]:
    """Smallest unit that keeps the mantissa renderable in three digits."""
    divisor, name = units[-1]
    for step, label in units:
        if value / step < MANTISSA_CEILING:
            divisor, name = step, label
            break
    return value / divisor, name


def percent(value, width: int = 3) -> str:
    """"100%", "<pad><pad>7%" -- always the same rendered width."""
    try:
        return pad(f"{float(value):.0f}", width) + "%"
    except (TypeError, ValueError):
        return pad("-", width) + "%"


def temperature(value, width: int = 3) -> str:
    try:
        return pad(f"{float(value):.0f}", width) + "°C"
    except (TypeError, ValueError):
        return pad("-", width) + "°C"


def rate(bytes_per_second, unit: str = "bytes") -> str:
    """Fixed-width transfer rate: three digit slots, a period slot, the unit."""
    if unit == "bits":
        scaled, suffix = _scale(float(bytes_per_second or 0) * 8, BIT_UNITS)
        family = tuple(name for _, name in BIT_UNITS)
    else:
        scaled, suffix = _scale(float(bytes_per_second or 0), BYTE_UNITS)
        family = tuple(name for _, name in BYTE_UNITS)
    number = f"{scaled:.1f}" if scaled < 10 else f"{scaled:.0f}"
    return unit_fill(suffix, family) + pad_number(number, 3) + suffix
