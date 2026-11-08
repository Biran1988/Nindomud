"""Conservative automatic cleanup of long-inactive character/account files.

Never edits a playing/linkdead character, staff account, or level-250
character. Use last authenticated login, not the player's frequent autosaves.
Older files lacking last_login_at use their file mtime as a conservative
migration fallback so installing this feature cannot purge recent players.
"""
import calendar
from datetime import datetime, timezone
import json
import os
import time

RETENTION_MONTHS = ((50, 6), (100, 9), (250, 12))


def months_for_level(level):
    if level >= 250:
        return None
    for upper, months in RETENTION_MONTHS:
        if level < upper:
            return months
    return None


def cutoff_for_months(now, months):
    dt = datetime.fromtimestamp(now, timezone.utc)
    month_index = dt.year * 12 + (dt.month - 1) - months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day).timestamp()


def purge_inactive(now=None):
    """Return names deleted; leave all accounts and files out of scope alone."""
    import storage
    from session import ACTIVE_SESSIONS
    storage.ensure_dirs()
    now = time.time() if now is None else float(now)
    # Protect even a player currently typing their password, before a
    # Player object has been attached to their live session.
    connected = set()
    for s in list(ACTIVE_SESSIONS):
        for name in (getattr(getattr(s, "player", None), "name", ""),
                     getattr(getattr(s, "account", None), "name", ""),
                     getattr(s, "_pending_name", "")):
            if name:
                connected.add(str(name).casefold())
    deleted = []
    for filename in sorted(os.listdir(storage.PLAYERS_DIR)):
        if not filename.endswith(".json"):
            continue
        name = filename[:-5]
        path = storage.player_path(name)
        if name.casefold() in connected or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            level = int(raw["level"])
            months = months_for_level(level)
            if months is None:
                continue
            account_name = str(raw.get("account_name", ""))
            if account_name.casefold() != name.casefold():
                continue
            account = storage.load_account(account_name)
            if account is None or account.staff_level != "player":
                continue
            last_login = float(raw.get("last_login_at", 0) or 0)
            if last_login <= 0:
                # Legacy migration: never use created_at to guess activity.
                last_login = os.path.getmtime(path)
            if last_login > cutoff_for_months(now, months):
                continue
            # A connection might have appeared during a filesystem scan.
            if any(name.casefold() in {
                    str(getattr(getattr(s, "player", None), "name", "")).casefold(),
                    str(getattr(getattr(s, "account", None), "name", "")).casefold(),
                    str(getattr(s, "_pending_name", "")).casefold(),
                    } for s in list(ACTIVE_SESSIONS)):
                continue
            storage.delete_character(name, account_name)
            deleted.append(name)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            # Invalid or inaccessible files are protected, not guessed away.
            continue
    if deleted:
        with open(os.path.join(storage.DATA_DIR, "inactive_purge.log"), "a", encoding="utf-8") as log:
            stamp = datetime.fromtimestamp(now, timezone.utc).isoformat()
            for name in deleted:
                log.write(f"{stamp} | character and account purged: {name}\n")
    return deleted
