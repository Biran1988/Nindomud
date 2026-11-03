"""Safe, persistent player title displayed EXCLUSIVELY on the WHO list.

Never attach a player's cosmetic title to OOC, WHOIS, SCORE, LOOK, emotes,
speech, combat logs, targeting or the underlying character/account name.
"""
import re

MAX_TITLE_LENGTH = 40  # visible characters, excluding legal color markup
MAX_TITLE_COLOR_CODES = 16
MAX_TITLE_STORED_LENGTH = 160
# Brackets are optional player text, never added by the renderer.
_TITLE_RE = re.compile(r"^[A-Za-z0-9\\[][A-Za-z0-9 ',.!?_\\-\\[\\]]*$")
# Inline ROM/xterm colors may change *within* a title (not the player name).
# Do not accept terminal escapes, reset codes or other arbitrary & controls.
_INLINE_COLOR_RE = re.compile(r"&\[(\d{1,3})\]|&([RGBYCMWDOrgybcmwd])")
COLOR_CHOICES = {
    "red": "&r", "green": "&g", "yellow": "&y", "blue": "&b",
    "cyan": "&c", "magenta": "&m", "purple": "&m",
    "white": "&w", "gray": "&D", "grey": "&D",
    "orange": "&O", "pink": "&[213]", "gold": "&[220]",
}
DEFAULT_COLOR = "gray"


def clean_title(text):
    """Validate plain title or safely formatted multicolor title.

    Recognize only the game's actual color syntax (&R, &C, &[208], etc).
    A maximum of 40 *visible* characters avoids penalizing color markup.
    All other ampersands and terminal/control characters are rejected.
    """
    if not isinstance(text, str):
        return None
    value = " ".join(text.split())
    if len(value) > MAX_TITLE_STORED_LENGTH:
        return None
    matches = list(_INLINE_COLOR_RE.finditer(value))
    if len(matches) > MAX_TITLE_COLOR_CODES:
        return None
    if any(match.group(1) is not None and int(match.group(1)) > 255
           for match in matches):
        return None
    visible = _INLINE_COLOR_RE.sub("", value)
    if (not 1 <= len(visible) <= MAX_TITLE_LENGTH
            or not _TITLE_RE.fullmatch(visible)
            or not any(char.isalnum() for char in visible)):
        return None
    return value


def valid_color(value):
    if not isinstance(value, str):
        return False
    option = value.lower().strip()
    return option in COLOR_CHOICES or (option.isascii() and option.isdecimal()
                                       and 0 <= int(option) <= 255)


def color_code(value):
    option = (value or "").strip().lower() if isinstance(value, str) else ""
    if option in COLOR_CHOICES:
        return COLOR_CHOICES[option]
    if option.isascii() and option.isdecimal() and 0 <= int(option) <= 255:
        return f"&[{int(option)}]"
    return COLOR_CHOICES[DEFAULT_COLOR]


def display_name(name, title="", color=DEFAULT_COLOR):
    """Formatted player name with independently colored cosmetic title, if valid."""
    title = clean_title(title)
    if not title:
        return name
    return f"{name} {color_code(color)}{title}&x"


def player_display(player):
    return display_name(player.name, getattr(player, "ooc_title", ""),
                        getattr(player, "ooc_title_color", DEFAULT_COLOR))


def command(session, args):
    """title [text] | title set <text> | title color <name|0-255> | title clear"""
    player = session.player
    if not player:
        return
    if not args or args[0].lower() in ("show", "status"):
        session.send("Your WHO list name: " + player_display(player))
        session.send("Usage: title <words> | title set <words> | "
                     "title color <red|green|gold|purple|0-255> | title clear")
        session.send("Titles appear unbracketed in gray by default. You may type your own [brackets]. For multiple "
                     "colors: title &RFlame &CIce &[208]Storm")
        return

    action = args[0].lower()
    if action in ("clear", "off", "remove") and len(args) == 1:
        player.ooc_title = ""
        import storage
        storage.save_player(player)
        session.send("Your title is removed. Your character name is unchanged.")
        return

    if action == "color":
        if len(args) != 2 or not valid_color(args[1]):
            session.send("Choose a title color (red, green, blue, yellow, cyan, "
                         "purple, magenta, white, gray, orange, pink, gold, or 0-255).")
            return
        player.ooc_title_color = args[1].lower()
        import storage
        storage.save_player(player)
        session.send("Your WHO list name: " + player_display(player))
        return

    words = args[1:] if action == "set" else args
    title = clean_title(" ".join(words))
    if title is None:
        session.send("A title must be 1-40 visible characters: letters, numbers, "
                     "spaces, simple punctuation, and valid inline MUD color codes "
                     "(&R, &C, &[208], etc). Literal [brackets] are allowed. No terminal/control escapes. "
                     "Use TITLE COLOR <color> for its default color.")
        return
    # Replacing a title is unconditional. Players never need TITLE CLEAR
    # before choosing another one; the previous color choice persists.
    replaced = bool(player.ooc_title)
    player.ooc_title = title
    import storage
    storage.save_player(player)
    session.send(("WHO title replaced: " if replaced else "Your new WHO title: ")
                 + player_display(player))
