"""Live global xterm-256 room UI color palette for Nindo_mud.

Admin changes update room-name, room-description and exit colors at
render time and are saved atomically to their own data/color_scheme.json.
Never mutates builder-created rooms, areas, or the world save.
"""

import json
import os
import tempfile

DEFAULT_NAME = 208            # Ember orange
DEFAULT_DESCRIPTION = 223     # Sand
DEFAULT_EXITS = None          # Original &G green until deliberately changed
DEFAULT_SCHEME = {
    "name": DEFAULT_NAME,
    "desc": DEFAULT_DESCRIPTION,
    "exits": DEFAULT_EXITS,
}

# Shared mutable state: every room display consults these live values.
ROOM_TITLE = "&[208]"
ROOM_DESCRIPTION = "&[223]"
EXIT_COLOR = "&G"


def color_code(number, default="&G"):
    """Return existing legacy exit color for None, else xterm-256 code."""
    return default if number is None else f"&[{number}]"


def _path():
    import storage
    # Resolve dynamically so temporary test directories stay isolated.
    return os.path.join(storage.DATA_DIR, "color_scheme.json")


def _validate(values):
    """Reject invalid input rather than persisting anything unrenderable."""
    if not isinstance(values, dict) or set(values) != set(DEFAULT_SCHEME):
        raise ValueError("Color scheme must define name, desc and exits.")
    for key, value in values.items():
        if key == "exits" and value is None:
            continue
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError(f"{key} must be an xterm 256 color from 0 to 255.")
    return dict(values)


def current():
    """Return live palette indices (None means legacy green exits)."""
    return {
        "name": int(ROOM_TITLE[2:-1]),
        "desc": int(ROOM_DESCRIPTION[2:-1]),
        "exits": None if EXIT_COLOR == "&G" else int(EXIT_COLOR[2:-1]),
    }


def _apply(values):
    global ROOM_TITLE, ROOM_DESCRIPTION, EXIT_COLOR
    ROOM_TITLE = color_code(values["name"])
    ROOM_DESCRIPTION = color_code(values["desc"])
    EXIT_COLOR = color_code(values["exits"])


def _write_atomic(values):
    """Write, flush and replace before a change becomes live.

    A server crash cannot leave a partially written JSON file: os.replace
    swaps in a complete file on the same filesystem. fsync protects
    against lost writes on ordinary OS crashes/power failure as possible.
    """
    path = _path()
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".color_scheme_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"version": 1, **values}, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
        # On POSIX, sync the directory metadata to make the rename durable.
        if hasattr(os, "O_DIRECTORY"):
            try:
                directory_fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
            except OSError:
                pass
            else:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                finally:
                    os.close(directory_fd)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def save(values):
    """Persist the entire new palette *before* applying it in memory."""
    values = _validate(values)
    _write_atomic(values)
    _apply(values)
    return current()


def set_color(part, color):
    """Set exactly one global part; color must be integer in 0..255."""
    if part not in DEFAULT_SCHEME:
        raise ValueError("Choose name, desc or exits.")
    values = current()
    values[part] = color
    return save(values)


def reset():
    """Restore Ember/Sand and the previous green exit style; persist it."""
    return save(DEFAULT_SCHEME)


def load():
    """Restore committed colors before players can connect.

    Invalid/incomplete files never partially override the palette.
    A missing file preserves the compiled Ember/Sand defaults.
    """
    try:
        with open(_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
        values = _validate({key: data[key] for key in DEFAULT_SCHEME})
    except FileNotFoundError:
        values = dict(DEFAULT_SCHEME)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
        # Keep last known usable live colors; don't overwrite broken data.
        return False
    _apply(values)
    return True


def color_room_name(name):
    return f"{ROOM_TITLE}{name}&x"


def color_room_description(description):
    return f"{ROOM_DESCRIPTION}{description}&x"
