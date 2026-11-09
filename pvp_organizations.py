"""Opt-in PvP organizations, independent of clan, village rank and grouping.

Players outside a registered organization are immune to player-origin PvP.
Members can fight members of *other* organizations, never their own allies.
Safe-room protections remain in place; mutually accepted arena duels are open to all.
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
    """Only a mutual, accepted arena challenge bypasses organization membership."""
    duel = getattr(session, "duel", None)
    return (duel is not None and duel is getattr(opponent, "duel", None)
            and getattr(duel, "accepted", False) and duel.other(session) is opponent)


def allowed_sessions(session, opponent):
    """Member-versus-rival combat or an accepted consensual duel."""
    return is_accepted_duel(session, opponent) or allowed(
        getattr(session, "player", None), getattr(opponent, "player", None))


def check(session, opponent):
    """Reject nonmember attacks, except accepted consensual duels."""
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
    """Manage immortal-appointed, invitation-only organizations."""
    from organization_leaders import command as organization_command
    return organization_command(session, args)
