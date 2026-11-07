"""Individual player-authored scroll notes.

Items in NindoMUD are strings in inventories, shops, bags and room saves.
A unique marker stays with a written scroll when it is moved, traded or
dropped. The note itself is stored in a separate data/ ledger, never on
the shared object prototype, so other copies of that scroll stay blank.
"""
import json
import os
import re
import tempfile
import uuid

import storage

MAX_MESSAGE_CHARS = 2500
MAX_MESSAGE_LINES = 35
_MARKER = re.compile(r"^(?P<name>.+) \[Written #(?P<id>[0-9a-f]{20})\]$")


def identity(item_name: str):
    """Return (plain prototype name, independent scroll-note id or None)."""
    match = _MARKER.fullmatch(item_name)
    return ((match.group("name"), match.group("id"))
            if match else (item_name, None))


def plain_name(item_name: str) -> str:
    return identity(item_name)[0]


def _path():
    # Resolve the path afresh for tests and for relocated server data/.
    return os.path.join(storage.DATA_DIR, "scroll_messages.json")


def load() -> dict:
    """Read the persistent ledger without masking corruption as an empty file."""
    try:
        with open(_path(), "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Scroll message ledger is invalid; refusing to overwrite it.")
    return data


def _save(records: dict) -> None:
    storage.ensure_dirs()
    fd, temporary = tempfile.mkstemp(
        prefix=".scroll-messages-", suffix=".tmp", dir=storage.DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(records, out, ensure_ascii=True, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, _path())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def inscription(item_name: str):
    """The author's actual text for this ONE copy, or None for a blank scroll."""
    _, identifier = identity(item_name)
    if identifier is None:
        return None
    record = load().get(identifier)
    return record if isinstance(record, dict) else None


def write(item_name: str, text: str, author: str) -> str:
    """Save a message and return the string identity to carry everywhere.

    Rewriting an already inscribed scroll keeps its unique id; writing
    an ordinary scroll creates a new id without changing the prototype.
    """
    if not isinstance(text, str):
        raise ValueError("Scroll message must be text.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Never let user text inject terminal control sequences into telnet.
    text = "".join(char for char in text if char == "\n" or ord(char) >= 32)
    if not text.strip():
        raise ValueError("The scroll is blank. Write a message or use /a to cancel.")
    if len(text) > MAX_MESSAGE_CHARS or len(text.splitlines()) > MAX_MESSAGE_LINES:
        raise ValueError(
            f"Scroll messages are limited to {MAX_MESSAGE_CHARS} characters "
            f"and {MAX_MESSAGE_LINES} lines.")
    original, identifier = identity(item_name)
    records = load()
    if identifier is None:
        identifier = uuid.uuid4().hex[:20]
        while identifier in records:
            identifier = uuid.uuid4().hex[:20]
    records[identifier] = {"author": str(author), "text": text}
    _save(records)
    return f"{original} [Written #{identifier}]"
