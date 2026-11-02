"""Safe, persistent player-selected titles for the OOC channel only.

The title is cosmetic metadata. It never replaces the actual character
name, account name or in-character identity. Escape sequences and MUD color
codes cannot be injected by players into global chat.
"""
import re

MAX_TITLE_LENGTH = 40
_TITLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ',.!?_-]*$")
COLOR_CHOICES = {
    "red": "&r", "green": "&g", "yellow": "&y", "blue": "&b",
    "cyan": "&c", "magenta": "&m", "purple": "&m",
    "white": "&w", "gray": "&D", "grey": "&D",
    "orange": "&O", "pink": "&[213]", "gold": "&[220]",
}
DEFAULT_COLOR = "gold"


def clean_title(text):
    """Return valid plain title or None; never accept custom escape codes."""
    if not isinstance(text, str):
        return None
    value = " ".join(text.split())
    if not 1 <= len(value) <= MAX_TITLE_LENGTH or not _TITLE_RE.fullmatch(value):
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
    """Formatted chat speaker with independently colored title, if valid."""
    title = clean_title(title)
    if not title:
        return name
    return f"{name} {color_code(color)}[{title}]&x"


def player_display(player):
    return display_name(player.name, getattr(player, "ooc_title", ""),
                        getattr(player, "ooc_title_color", DEFAULT_COLOR))


def command(session, args):
    """title [text] | title set <text> | title color <name|0-255> | title clear"""
    player = session.player
    if not player:
        return
    if not args or args[0].lower() in ("show", "status"):
        session.send("Your OOC name: " + player_display(player))
        session.send("Usage: title <words> | title set <words> | "
                     "title color <red|green|gold|purple|0-255> | title clear")
        return

    action = args[0].lower()
    if action in ("clear", "off", "remove") and len(args) == 1:
        player.ooc_title = ""
        import storage
        storage.save_player(player)
        session.send("Your OOC title is removed. Your character name is unchanged.")
        return

    if action == "color":
        if len(args) != 2 or not valid_color(args[1]):
            session.send("Choose a title color (red, green, blue, yellow, cyan, "
                         "purple, magenta, white, gray, orange, pink, gold, or 0-255).")
            return
        player.ooc_title_color = args[1].lower()
        import storage
        storage.save_player(player)
        session.send("Your OOC name: " + player_display(player))
        return

    words = args[1:] if action == "set" else args
    title = clean_title(" ".join(words))
    if title is None:
        session.send("A title must be 1-40 characters: letters, numbers, spaces "
                     "and simple punctuation only. No color/escape codes. "
                     "Use 'title color <color>' for its color.")
        return
    player.ooc_title = title
    import storage
    storage.save_player(player)
    session.send("Your new OOC name: " + player_display(player))
