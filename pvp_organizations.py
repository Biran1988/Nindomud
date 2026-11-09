"""Opt-in PvP organizations, independent of clan, village rank and grouping.

Players outside a registered organization are immune to player-origin PvP.
Members can fight members of *other* organizations, never their own allies.
Safe-room protections still apply. Consensual accepted duels are exempt.
"""

import time

import storage


# One character may belong to one PvP organization at a time.
# Village restrictions are entry requirements, not changes to clan or bloodline.
ORGANIZATIONS = {
    "anbu": ("ANBU", ("leaf",), "Hidden Leaf's elite covert operatives."),
    "root": ("Root", ("leaf",), "The Leaf's underground intelligence division."),
    "akatsuki": ("Akatsuki", (), "Rogue shinobi from any village."),
    "mist_hunters": ("Mist Hunter-nin", ("water",), "Specialists in tracking rogue ninja."),
    "seven_swordsmen": ("Seven Ninja Swordsmen", ("water",), "The Hidden Mist's notorious blade wielders."),
    "sand_anbu": ("Sand ANBU", ("sand",), "The Sand's covert shinobi corps."),
    "cloud_anbu": ("Cloud ANBU", ("cloud",), "The Cloud's covert shinobi corps."),
    "stone_anbu": ("Stone ANBU", ("stone",), "The Stone's covert shinobi corps."),
}
CHANGE_COOLDOWN_SECONDS = 24 * 60 * 60


def resolve(name):
    """Accept IDs, readable names, and common dash/space variants."""
    key = "_".join(name.strip().lower().replace("-", " ").split())
    if key in ORGANIZATIONS:
        return key
    for org, (display, _, _) in ORGANIZATIONS.items():
        if key == "_".join(display.lower().replace("-", " ").split()):
            return org
    return ""


def membership(player):
    """Ignore invalid or legacy saved values; never infer from clan/village."""
    key = getattr(player, "pvp_organization", "")
    return key if key in ORGANIZATIONS else ""


def display_name(key):
    return ORGANIZATIONS[key][0] if key in ORGANIZATIONS else "None (PvP protected)"


def denial_reason(attacker, defender):
    """Pure, centralized opt-in requirement for every hostile PvP path."""
    attacking = membership(attacker) if attacker is not None else ""
    defending = membership(defender) if defender is not None else ""
    if not attacking:
        return "You must join a PvP organization before attacking other players. Type 'organization list'."
    if not defending:
        return "That player is not in a PvP organization and is protected from PvP."
    if attacking == defending:
        return "Members of the same PvP organization cannot attack each other."
    return ""


def allowed(attacker, defender):
    return not denial_reason(attacker, defender)


def is_accepted_duel(session, opponent):
    """A consensual arena duel is allowed even for unaffiliated players."""
    duel = getattr(session, "duel", None)
    return (duel is not None and duel is getattr(opponent, "duel", None)
            and getattr(duel, "accepted", False)
            and duel.other(session) is opponent)


def allowed_sessions(session, opponent):
    return is_accepted_duel(session, opponent) or allowed(
        getattr(session, "player", None), getattr(opponent, "player", None))


def check(session, opponent):
    """Send the denial to the attacker; avoid modifying combat state."""
    if is_accepted_duel(session, opponent):
        return True
    reason = denial_reason(getattr(session, "player", None),
                           getattr(opponent, "player", None))
    if reason:
        session.send(reason)
        return False
    return True


def _busy(session):
    """Prevent opting out of a live duel, incoming attack or hostile cast."""
    if (getattr(session, "pvp_target", None) is not None
            or getattr(session, "duel", None) is not None
            or getattr(getattr(session, "pending_cast", None), "is_pvp", False)
            or getattr(session.player, "tsukuyomi_active_target_name", "")):
        return True
    for other in session.active_sessions():
        if other is session:
            continue
        pending = getattr(other, "pending_cast", None)
        if (getattr(other, "pvp_target", None) is session
                or (getattr(pending, "is_pvp", False) and getattr(pending, "target", None) is session)
                or getattr(getattr(other, "player", None), "tsukuyomi_active_target_name", "") == session.player.name):
            return True
    return False


def _cooldown_left(player, now):
    last = float(getattr(player, "pvp_organization_changed_at", 0) or 0)
    return max(0, int(last + CHANGE_COOLDOWN_SECONDS - now)) if last else 0


def command(session, args):
    """organization [list|status|join <name>|leave|members <name>]"""
    player = session.player
    action = args[0].lower() if args else "status"
    if action in ("list", "help"):
        lines = ["&C-- PvP organizations (opt-in) --&x"]
        for key, (title, villages, description) in ORGANIZATIONS.items():
            requirement = ", ".join(villages).title() if villages else "Any village"
            lines.append(f"  &W{title}&x ({key}) - {description} [{requirement}]")
        lines += [
            "&YJoining enables PvP against members of other organizations only.&x",
            "Unaffiliated players are protected in open-world PvP. Same-organization attacks are blocked.",
            "Safe rooms remain safe; consensual arena duels remain open to everyone. Changes have a 24-hour cooldown.",
            "Use 'organization join <name>', 'organization leave', or 'organization status'.",
        ]
        session.send("\n".join(lines))
        return

    if action in ("status", "info"):
        session.send(f"&CPvP organization:&x {display_name(membership(player))}")
        if membership(player):
            session.send("&YPvP active:&x You may fight members of rival organizations outside safe rooms.")
        else:
            session.send("&GPvP protected:&x You cannot attack or be attacked by other players outside accepted duels.")
        remaining = _cooldown_left(player, time.time())
        if remaining:
            hours, minutes = divmod((remaining + 59) // 60, 60)
            session.send(f"&DNext organization change available in {hours}h {minutes}m.&x")
        session.send("Commands: organization list | join <name> | leave | members <name>")
        return

    if action == "members":
        key = resolve(" ".join(args[1:])) if len(args) > 1 else membership(player)
        if not key:
            session.send("Usage: organization members <organization>")
            return
        online = sorted(s.player.name for s in session.active_sessions()
                        if getattr(s, "player", None) and membership(s.player) == key)
        session.send(f"&C{display_name(key)} online:&x " + (", ".join(online) if online else "No online members"))
        return

    if action not in ("join", "leave"):
        session.send("Usage: organization list | status | join <name> | leave | members <name>")
        return

    if _busy(session):
        session.send("You cannot change PvP organization while a duel, hostile cast or PvP fight is active.")
        return

    current = membership(player)
    if action == "leave" and not current:
        session.send("You are not currently part of a PvP organization.")
        return

    key = resolve(" ".join(args[1:])) if action == "join" else ""
    if action == "join":
        if not key:
            session.send("Specify an organization from 'organization list'.")
            return
        if key == current:
            session.send(f"You already belong to {display_name(key)}.")
            return
        if current:
            session.send(f"Leave {display_name(current)} before joining another organization.")
            return
        villages = ORGANIZATIONS[key][1]
        if villages and player.village not in villages:
            session.send(f"{display_name(key)} only accepts shinobi from: {', '.join(villages)}.")
            return

    remaining = _cooldown_left(player, time.time())
    if remaining:
        session.send("You must wait 24 hours between joining or leaving PvP organizations.")
        return

    player.pvp_organization = key
    player.pvp_organization_changed_at = time.time()
    storage.save_player(player)
    if key:
        session.send(f"&RYou joined {display_name(key)}. You are now eligible for PvP against rival organizations.&x")
    else:
        session.send("&GYou left your PvP organization. You are now protected from player attacks.&x")
