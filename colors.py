"""
ROM-style ANSI color codes (Section 30), extended two ways beyond the
original 8-color set:

1. Lowercase bright codes use explicit bright ANSI foregrounds instead
   of relying on bold. Uppercase uses normal/darker shades. Every named
   color switch clears bold intensity so prior brightness cannot bleed
   into a following normal code.
2. Full 256-color xterm palette via &N or &[N] (N = 0-255), e.g. &208 for
   an orange not otherwise reachable with named codes. This is the
   standard 8-bit ANSI color extension (\\x1b[38;5;Nm) -- far more
   broadly supported by real terminals/MUD clients than 24-bit true
   color, which is why it's the one implemented here; true color
   (&[R,G,B] style) would be a natural next step if ever needed.

Text is authored with these codes (e.g. "&RHP&x", "&208a stick of
dango&x") and rendered to real ANSI escapes at send-time, or stripped
entirely if the session has color disabled. Keeping this as a pure
text transform (not baked into every string at creation time) means
'color off' is a single render-time switch.
"""

import re

ANSI_CODES = {
    "&R": "\x1b[22;31m",          # Red
    "&G": "\x1b[22;32m",          # Green
    "&Y": "\x1b[22;33m",          # Yellow
    "&B": "\x1b[22;34m",          # Blue
    "&C": "\x1b[22;36m",          # Cyan
    "&M": "\x1b[22;35m",          # Magenta
    "&W": "\x1b[22;37m",          # White
    "&D": "\x1b[22;90m",          # Dark gray
    # Explicit bright ANSI foregrounds; gray: &D dark, &d light.
    # SGR 22 cancels lingering bold intensity before each new shade.
    "&r": "\x1b[22;91m",          # Bright red
    "&g": "\x1b[22;92m",          # Bright green
    "&y": "\x1b[22;93m",          # Bright yellow
    "&b": "\x1b[22;94m",          # Bright blue
    "&c": "\x1b[22;96m",          # Bright cyan
    "&m": "\x1b[22;95m",          # Bright magenta
    "&w": "\x1b[22;97m",          # Bright white
    "&d": "\x1b[22;37m",          # Light gray
    "&O": "\x1b[38;5;208m",  # Orange -- a convenience alias built on the 256-color palette
    "&x": "\x1b[0m",    # Reset
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
