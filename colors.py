"""
ROM-style ANSI color codes (Section 30), extended two ways beyond the
original 8-color set:

1. Bright/bold variants -- lowercase letters mirror the 8 uppercase
   base colors (&r/&g/&y/&b/&c/&m/&w/&d), rendered bold+color. This
   doubles the named palette to 16 without touching any existing
   code's meaning (no lowercase letter was in use before).
2. Full 256-color xterm palette via &[N] (N = 0-255), e.g. &[208] for
   an orange not otherwise reachable with named codes. This is the
   standard 8-bit ANSI color extension (\\x1b[38;5;Nm) -- far more
   broadly supported by real terminals/MUD clients than 24-bit true
   color, which is why it's the one implemented here; true color
   (&[R,G,B] style) would be a natural next step if ever needed.

Text is authored with these codes (e.g. "&RHP&x", "&[208]a stick of
dango&x") and rendered to real ANSI escapes at send-time, or stripped
entirely if the session has color disabled. Keeping this as a pure
text transform (not baked into every string at creation time) means
'color off' is a single render-time switch.
"""

import re

ANSI_CODES = {
    "&R": "\x1b[31m",   # Red
    "&G": "\x1b[32m",   # Green
    "&Y": "\x1b[33m",   # Yellow
    "&B": "\x1b[34m",   # Blue
    "&C": "\x1b[36m",   # Cyan
    "&M": "\x1b[35m",   # Magenta
    "&W": "\x1b[37m",   # White
    "&D": "\x1b[90m",   # Dark gray
    # Bright/bold variants (16-color set) -- same 8 hues, bold+color.
    "&r": "\x1b[1;31m",  # Bright red
    "&g": "\x1b[1;32m",  # Bright green
    "&y": "\x1b[1;33m",  # Bright yellow
    "&b": "\x1b[1;34m",  # Bright blue
    "&c": "\x1b[1;36m",  # Bright cyan
    "&m": "\x1b[1;35m",  # Bright magenta
    "&w": "\x1b[1;37m",  # Bright white
    "&d": "\x1b[1;90m",  # Bright dark gray (light gray)
    "&O": "\x1b[38;5;208m",  # Orange -- a convenience alias built on the 256-color palette
    "&x": "\x1b[0m",    # Reset
}

_CODE_RE = re.compile("|".join(re.escape(c) for c in ANSI_CODES))
_XTERM256_RE = re.compile(r"&\[(\d{1,3})\]")

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
        text = _XTERM256_RE.sub(lambda m: _xterm256_escape(m.group(1)), text)
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
