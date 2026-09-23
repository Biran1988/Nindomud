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


def record(speaker: str, message: str) -> None:
    """Appends a new OOC message to the log and persists it
    immediately -- matching every other persistent system in this
    project (teams, spawn points), which save on every mutation
    rather than batching. The deque's own maxlen=25 handles dropping
    the oldest entry automatically once full."""
    import storage
    ENTRIES.append({"speaker": speaker, "message": message})
    storage.save_chatlog(list(ENTRIES))
