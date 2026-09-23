"""
Login-screen ASCII art (Section 60).

A single banner combining a simple symbol for each of the five
villages (a leaf, a mountain, waves, a sun/desert mark, a cloud) side
by side, colored with the exact same per-village xterm color pairs
already used for village names in the who list
(commands.VILLAGE_FULL_NAME_COLORS) for visual consistency -- each
symbol's letters alternate between its village's two assigned colors,
same technique as commands._who_village_name(). Deliberately original,
generic imagery, not a reproduction of any official Naruto logo,
character likeness, or copyrighted artwork.

A footer with basic server info (owner, programming language/engine,
and version) is appended below the banner, pulled live from
config.ADMIN_NAME and changelog.CHANGELOG's latest entry rather than
hardcoded, so it can't silently drift out of date as the changelog
grows.
"""

VILLAGE_ORDER = ["leaf", "stone", "water", "sand", "cloud"]

VILLAGE_COLORS = {
    "leaf": (34, 118),    # Konohagakure
    "cloud": (33, 255),   # Kumogakure
    "water": (38, 67),    # Kirigakure
    "sand": (214, 220),   # Sunagakure
    "stone": (130, 244),  # Iwagakure
}

# Four-line symbol per village, each line the same fixed width so the
# five columns line up regardless of how different each symbol's shape
# is -- centered into GLYPH_WIDTH rather than hand-padded, so editing
# any one symbol's art can never throw off the others' alignment.
# Redesigned to actually reflect each village's real symbol CONCEPT
# (looked up, not guessed): Konoha is a swirl/spiral, Iwa is two rocks,
# Kiri is a stylized wave, Suna is a stylized hourglass, Kumo is a
# cloud swirl -- these are original ASCII interpretations of that
# concept, not a trace of the actual copyrighted artwork.
GLYPHS = {
    "leaf": ["   __   ", "  /  `-.", "  \\__.-'", " KONOHA "],
    "stone": [" __  __ ", "/  \\/  \\", "\\__/\\__/", "  IWA   "],
    "water": [" ~~~~~~ ", "~~~~~~~~", " ~~~~~~ ", "  KIRI  "],
    "sand": ["  .--.  ", "   \\/   ", "   /\\   ", "  SUNA  "],
    "cloud": ["  .--.  ", " ( @  ) ", "  `--'  ", "  KUMO  "],
}
GLYPH_WIDTH = 8
COLUMN_GAP = "  "


def _color_glyph_line(village: str, line: str) -> str:
    color_a, color_b = VILLAGE_COLORS[village]
    letters = []
    for i, ch in enumerate(line):
        color = color_a if i % 2 == 0 else color_b
        letters.append(f"&[{color}]{ch}")
    return "".join(letters) + "&x"


def five_villages_banner() -> str:
    lines = ["&Y=== THE FIVE GREAT SHINOBI VILLAGES ===&x", ""]
    for row in range(4):
        parts = [
            _color_glyph_line(village, GLYPHS[village][row].center(GLYPH_WIDTH))
            for village in VILLAGE_ORDER
        ]
        lines.append(COLUMN_GAP.join(parts))
    return "\n".join(lines)


def footer() -> str:
    """Owner, programming language/engine, and version -- shown below
    the banner. Version is the latest changelog entry, read live so
    it can never silently drift out of date."""
    import changelog
    import config

    version = changelog.CHANGELOG[-1][0] if changelog.CHANGELOG else "0.00"
    return (
        f"Owner: {config.ADMIN_NAME.capitalize()}   "
        f"Programming: Python 3   "
        f"Version: {version}"
    )


def mud_name_title() -> str:
    """The MUD's own name, shown prominently at the very top of the
    login screen, above the five-villages banner. Pulled from
    config.MUD_NAME rather than hardcoded -- the name isn't finalized
    yet (see config.py's own comment), so this can't drift out of sync
    if it changes again, same reasoning as the [Login] join broadcast."""
    import config

    spaced = "  ".join(config.MUD_NAME.upper())
    width = max(len(spaced) + 8, 40)
    return (
        f"&Y{'=' * width}&x\n"
        f"&Y{spaced.center(width)}&x\n"
        f"&Y{'=' * width}&x"
    )


def login_screen() -> str:
    return mud_name_title() + "\n\n" + five_villages_banner() + "\n\n" + footer()
