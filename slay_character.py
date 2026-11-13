"""Implementor-only, two-step permanent deletion of an ordinary character.

SLAY <name> arms a 60-second confirmation on the caller's live session.
The next line must be 1212. Never force or broadcast this command.
"""
import json
import time

CONFIRM_CODE = "1212"
CONFIRM_SECONDS = 60


def _authorized(session):
    import config
    account = getattr(session, "account", None)
    player = getattr(session, "player", None)
    return bool(account and player and account.staff_level == "implementor"
                and account.name.lower() == config.ADMIN_NAME.lower()
                and player.account_name.lower() == account.name.lower())


def _verify_target(name):
    """Require a matching regular player account and character on disk."""
    import config
    import storage
    if not isinstance(name, str) or not name.isascii() or not name.isalpha() or not (2 <= len(name) <= 20):
        return "Use a valid 2-20 letter character name."
    if name.lower() == config.ADMIN_NAME.lower():
        return "The primary Implementor account cannot be deleted with SLAY."
    if not storage.player_exists(name) or not storage.account_exists(name):
        return f"No complete character and account pair exists for {name}."
    try:
        account = storage.load_account(name)
        with open(storage.player_path(name), encoding="utf-8") as stream:
            character = json.load(stream)
    except (OSError, ValueError, TypeError):
        return "Saved records are unavailable or invalid; nothing was deleted."
    if not account or account.staff_level != "player":
        return "Staff accounts are protected from SLAY."
    if (not isinstance(character, dict)
            or not isinstance(character.get("name"), str)
            or not isinstance(character.get("account_name"), str)
            or account.name.lower() != name.lower()
            or character["name"].lower() != name.lower()
            or character["account_name"].lower() != name.lower()):
        return "Saved account and character do not match; nothing was deleted."
    return None


def command(session, args):
    """SLAY <name> requires a separate 1212 input to actually delete."""
    session._slay_pending = None
    if not _authorized(session):
        session.send("Only the primary Implementor may permanently delete characters.")
        return
    if len(args) != 1:
        session.send("Usage: SLAY <playername> (then type 1212 as the next command)")
        return
    name = args[0]
    error = _verify_target(name)
    if error:
        session.send(f"&R{error}&x")
        return
    if name.lower() == session.player.name.lower():
        session.send("You cannot SLAY your own character.")
        return
    session._slay_pending = (name.lower(), time.monotonic() + CONFIRM_SECONDS)
    session.send(f"&RSLAY will permanently delete {name}'s character AND login account. "
                 "This cannot be undone. Type 1212 as your NEXT command within "
                 "60 seconds to confirm. Any other input cancels.&x")


def consume_confirmation(session, line):
    """Intercept a pending reply BEFORE normal commands and immortal spying."""
    pending = getattr(session, "_slay_pending", None)
    if pending is None:
        return False
    session._slay_pending = None
    if not _authorized(session):
        session.send("SLAY cancelled: Implementor authentication required.")
        return True
    name, expires_at = pending
    if time.monotonic() > expires_at:
        session.send("SLAY confirmation expired. Nothing was deleted.")
        return True
    if line.strip() != CONFIRM_CODE:
        session.send("SLAY cancelled. Nothing was deleted.")
        return True
    error = _verify_target(name)
    if error:
        session.send(f"&R{error}&x")
        return True

    # Close any live, link-dead, or partly logged-in sessions BEFORE file
    # deletion. They cannot later autosave and resurrect deleted accounts.
    from session import ACTIVE_SESSIONS
    victims = [
        other for other in tuple(ACTIVE_SESSIONS)
        if other is not session and (
            (getattr(getattr(other, "player", None), "name", "") or "").lower() == name
            or (getattr(getattr(other, "account", None), "name", "") or "").lower() == name
            or (getattr(other, "_pending_name", "") or "").lower() == name
        )
    ]
    for victim in victims:
        victim.send("&RYour character has been permanently deleted by the Implementor.&x")
        victim.request_close()

    import storage
    try:
        storage.delete_character(name, name)
    except OSError as exc:
        session.send(f"&RSLAY could not delete both saved files: {exc}. Check the server logs.&x")
        return True

    session.send(f"&R{name.capitalize()}'s character and login account have been permanently deleted.&x")
    try:
        import olc
        olc._log(session.player.name, "player", 0, f"SLAY permanently removed character and account {name}")
    except (OSError, AttributeError):
        pass
    return True
