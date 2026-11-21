"""SMAUGFUSS classic ANSI foregrounds plus Nindo compatibility extensions.

Classic dark/bright colors use ANSI intensity 0/1. Canonical purple/pink are
&p/&P, while &m/&M remain backwards-compatible. The project's &x reset and
xterm-256 formats remain unchanged to avoid breaking existing game content.
"""

import re

ANSI_CODES = {
    "&r": "\x1b[0;31m",
    "&R": "\x1b[1;31m",
    "&g": "\x1b[0;32m",
    "&G": "\x1b[1;32m",
    "&y": "\x1b[0;33m",
    "&Y": "\x1b[1;33m",
    "&b": "\x1b[0;34m",
    "&B": "\x1b[1;34m",
    "&c": "\x1b[0;36m",
    "&C": "\x1b[1;36m",
    "&p": "\x1b[0;35m",
    "&P": "\x1b[1;35m",
    "&m": "\x1b[0;35m",
    "&M": "\x1b[1;35m",
    "&w": "\x1b[0;37m",
    "&W": "\x1b[1;37m",
    "&d": "\x1b[1;30m",
    "&D": "\x1b[0;37m",
    "&z": "\x1b[0;30m",
    "&Z": "\x1b[1;30m",
    "&o": "\x1b[38;5;130m",
    "&O": "\x1b[38;5;208m",
    "&x": "\x1b[0m",  # Nindo reset retained for existing content
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
