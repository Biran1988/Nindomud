"""SMAUGFUSS/SWR-compatible ampersand colors, plus xterm-256.

Lowercase named codes select dark foregrounds; uppercase codes are bright.
&w is gray, &W bright white; &m dark purple, &M bright magenta.
&x resets, && prints a literal ampersand. Numeric &N or &[N] selects
any xterm-256 foreground (0-255). Switching shades clears bold intensity.
"""

import re

ANSI_CODES = {
    "&r": "\x1b[22;31m",  # Dark red
    "&R": "\x1b[22;91m",  # Bright red
    "&g": "\x1b[22;32m",  # Dark green
    "&G": "\x1b[22;92m",  # Bright green
    "&y": "\x1b[22;33m",  # Dark yellow
    "&Y": "\x1b[22;93m",  # Bright yellow
    "&b": "\x1b[22;34m",  # Dark blue
    "&B": "\x1b[22;94m",  # Bright blue
    "&c": "\x1b[22;36m",  # Dark cyan
    "&C": "\x1b[22;96m",  # Bright cyan
    "&m": "\x1b[22;35m",  # Dark purple
    "&M": "\x1b[22;95m",  # Bright magenta
    "&w": "\x1b[22;37m",  # Gray
    "&W": "\x1b[22;97m",  # Bright white
    "&d": "\x1b[22;90m",  # Dark gray
    "&D": "\x1b[22;37m",  # Light gray
    "&z": "\x1b[22;30m",  # Black
    "&Z": "\x1b[22;90m",  # Charcoal
    "&o": "\x1b[22;38;5;130m",  # Dark orange
    "&O": "\x1b[22;38;5;208m",  # Bright orange
    "&x": "\x1b[0m",  # Reset
}

_CODE_RE = re.compile("|".join(re.escape(c) for c in ANSI_CODES))
_XTERM256_RE = re.compile(r"&\[(\d{1,3})\]|&(\d{1,3})")

XTERM256_MAX = 255


def _xterm256_escape(digits: str) -> str:
    n = int(digits)
    if n > XTERM256_MAX:
        return ""  # invalid code -- silently drop rather than emit garbage
    return f"\x1b[38;5;{n}m"


_ESCAPE_PLACEHOLDER = "\x00AMP\x00"  # extremely unlikely to collide with real text


def render(text: str, color_enabled: bool) -> str:
    """Convert &-codes to real ANSI escapes, or strip them if color is
    off. '&&' is an escape for a literal '&' -- e.g. '&&R' displays as
    the two characters '&R' instead of being interpreted as the red
    code, so color-code syntax can be written about, not just used.
    Processed before the code substitutions below so an escaped '&&'
    is never itself mistaken for (half of) a real code."""
    text = text.replace("&&", _ESCAPE_PLACEHOLDER)
    if color_enabled:
        text = _XTERM256_RE.sub(lambda m: _xterm256_escape(m.group(1) or m.group(2)), text)
        text = _CODE_RE.sub(lambda m: ANSI_CODES[m.group(0)], text)
    else:
        text = _XTERM256_RE.sub("", text)
        text = _CODE_RE.sub("", text)
    return text.replace(_ESCAPE_PLACEHOLDER, "&")


def resource_color(current: int, maximum: int) -> str:
    """Threshold coloring per Section 30 (green/yellow/red)."""
    if maximum <= 0:
        return "&W"
    pct = current / maximum * 100
    if pct > 50:
        return "&G"
    if pct > 25:
        return "&Y"
    return "&R"
