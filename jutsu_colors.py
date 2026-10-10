"""Distinct, readable three-color palettes for every registered jutsu.

Highlighting happens at send time, so existing learned-skill names and saved
player data remain plain text. Sessions with ANSI disabled get plain text.
"""

from itertools import permutations
import re
import unicodedata

import data_jutsu


# Six bright xterm-256 shades per theme. Permutations make each individual
# technique unique within its element or combat style, not merely per class.
THEME_SHADES = {
    "ice": (45, 51, 81, 117, 159, 195),
    "fire": (196, 202, 208, 214, 220, 226),
    "water": (33, 39, 45, 51, 81, 117),
    "wind": (34, 40, 46, 82, 118, 154),
    "earth": (130, 136, 142, 172, 178, 214),
    "lightning": (57, 63, 69, 75, 111, 159),
    "genjutsu": (93, 99, 135, 141, 171, 207),
    "taijutsu": (160, 166, 172, 178, 220, 226),
    "bukijutsu": (31, 37, 43, 49, 81, 123),
    "general": (74, 80, 86, 117, 153, 189),
    "ninjutsu": (129, 135, 141, 177, 213, 219),
}


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _schemes() -> dict[str, tuple[int, int, int]]:
    groups = {theme: [] for theme in THEME_SHADES}
    for key, jutsu in data_jutsu.JUTSU.items():
        theme = "ice" if jutsu.get("kkg_gate") == "ice_release" else jutsu.get("element", "none")
        if theme not in THEME_SHADES:
            theme = jutsu["class_requirement"]
        groups[theme].append(key)
    schemes = {}
    for theme, keys in groups.items():
        variants = list(permutations(THEME_SHADES[theme], 3))
        for index, key in enumerate(sorted(keys)):
            if index >= len(variants):
                raise ValueError(f"Too many jutsu for the {theme} color palette")
            # Stepping 37 positions varies the first and second shades too;
            # neighboring jutsu do not look almost identical in a roster.
            schemes[key] = variants[(index * 37) % len(variants)]
    if len(set(schemes.values())) != len(data_jutsu.JUTSU):
        raise ValueError("Jutsu color palettes must be unique")
    return schemes


SCHEMES = _schemes()
_NAME_TO_KEY = {_plain(jutsu["display_name"]).casefold(): key
                for key, jutsu in data_jutsu.JUTSU.items()}
_NAME_RE = re.compile(r"(?<!\w)((?:&(?:[A-Za-z]|\[\d{1,3}\]))*)(" + "|".join(
    re.escape(name) for name in sorted(_NAME_TO_KEY, key=len, reverse=True)
) + r")(?!\w)", re.IGNORECASE)


def colorful_name(key: str, name: str = None) -> str:
    """Alternate three vivid colors every few letters, retaining spaces."""
    name = name if name is not None else _plain(data_jutsu.JUTSU[key]["display_name"])
    palette = SCHEMES[key]
    chunks = []
    letters = 0
    last_shade = None
    for char in name:
        if not char.isspace():
            shade = palette[(letters // 3) % len(palette)]
            if shade != last_shade:
                chunks.append(f"&[{shade}]")
                last_shade = shade
            letters += 1
        chunks.append(char)
    return "".join(chunks) + "&x"


def highlight_names(text: str) -> str:
    """Style any displayed jutsu name without changing other message text."""
    if not text:
        return text
    return _NAME_RE.sub(lambda match: match.group(1) + colorful_name(
        _NAME_TO_KEY[match.group(2).casefold()], match.group(2)), text)


def send(session, text: str) -> None:
    """Use the decorated output path, including with lightweight test sessions."""
    method = getattr(session, "send_jutsu", session.send)
    method(text)
