"""
OOC chat log (Section 93), per direct request:

"add a command in game that shows the last 25 ooc chats by typing
chatlog"

Confirmed persisted to disk -- survives a server restart, matching
teams.json's own established save/load pattern (storage.load_chatlog/
save_chatlog). A genuine collections.deque(maxlen=25) enforces the
"last 25" cap automatically: once full, adding a 26th entry silently
drops the oldest one, so the log can never grow unbounded.

Loaded once at startup (content.populate(), matching teams.load_all's
own pattern) into the module-level ENTRIES deque, then every new OOC
message appends to it and re-saves. Each entry is a plain
{"speaker": str, "message": str} dict -- no timestamp requested,
kept minimal per what was actually asked for.
"""

from collections import deque

MAX_ENTRIES = 25

ENTRIES: deque = deque(maxlen=MAX_ENTRIES)


def load_all() -> None:
    """Loads the persisted chat log from disk into ENTRIES, matching
    teams.load_all()'s own established startup pattern. Called once
    from content.populate()."""
    import storage
    ENTRIES.clear()
    for entry in storage.load_chatlog():
        ENTRIES.append(entry)


def record(speaker: str, message: str, *, title: str = "", title_color: str = "gold") -> None:
    """Save message and a snapshot of the speaker's OOC title if present.

    Old log entries with only speaker/message continue to render normally.
    """
    import storage
    import ooc_titles
    entry = {"speaker": speaker, "message": message}
    safe_title = ooc_titles.clean_title(title)
    if safe_title:
        entry["title"] = safe_title
        entry["title_color"] = title_color if ooc_titles.valid_color(title_color) else "gold"
    ENTRIES.append(entry)
    storage.save_chatlog(list(ENTRIES))
