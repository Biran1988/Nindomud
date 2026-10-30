"""Immortal-only wizard invisibility; no player-side detection override.

This is not the ordinary Invisible effect: it has no duration or Chakra
cost and cannot be bypassed by Sharingan, Byakugan or Sensory Detect.
"""
import storage


def is_hidden(session):
    return bool(
        getattr(session, "player", None)
        and getattr(session, "account", None)
        and session.account.staff_level != "player"
        and getattr(session.player, "wizinvis", False)
    )


def hidden_player(viewer, target):
    """Whether a character disappears from another person's perception."""
    return bool(viewer is not target and getattr(target, "wizinvis", False))


def visible_to(viewer_session, other_session):
    return viewer_session is other_session or not is_hidden(other_session)


def command(session, args):
    if not session.player or not session.account or session.account.staff_level == "player":
        session.send("Only immortals may use wizinvis.")
        return
    if len(args) > 1 or args and args[0].casefold() not in ("on", "off", "status"):
        session.send("Usage: wizinvis [on|off|status]")
        return
    mode = args[0].casefold() if args else ("off" if session.player.wizinvis else "on")
    if mode == "status":
        session.send(f"Wizard invisibility is {'ON' if session.player.wizinvis else 'OFF'}.")
        return
    desired = mode == "on"
    if session.player.wizinvis == desired:
        session.send(f"Wizard invisibility is already {'ON' if desired else 'OFF'}.")
        return
    session.player.wizinvis = desired
    try:
        storage.save_player(session.player)
    except OSError as error:
        session.player.wizinvis = not desired
        session.send(f"Could not save wizard invisibility: {error}")
        return
    if desired:
        session.send("&GYou fade out of sight. You no longer appear in WHO, WHOIS, IMMS, look or scan, and your movement is silent.&x")
    else:
        session.send("&YYou become visible to the ninja world again.&x")
