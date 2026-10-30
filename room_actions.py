"""Observable same-room character actions with stealth and staff privacy.

One successful action creates one message for other occupants. No global
spam, no failed attempts, no information leak from wizinvis or camouflage.
"""
from collections import Counter


def emit(session, text, *, reveal_transition=False, exclude=()):
    """Send to observers in the actor's perceived room, never the actor."""
    player = getattr(session, "player", None)
    if player is None or not getattr(player, "name", None):
        return
    import clone_control
    import general_skills
    import staff_invisibility
    if (getattr(getattr(session, "account", None), "staff_level", "player") != "player"
            and getattr(player, "wizinvis", False)):
        return
    room = clone_control.view_room(session)
    from session import ACTIVE_SESSIONS
    for observer in list(ACTIVE_SESSIONS):
        if observer is session or any(observer is ignored for ignored in exclude):
            continue
        viewer = getattr(observer, "player", None)
        if viewer is None or clone_control.view_room(observer) != room:
            continue
        if staff_invisibility.hidden_player(viewer, player):
            continue
        if not reveal_transition and general_skills.concealed_from(viewer, player):
            continue
        observer.send(text)


def consumed(session, earlier_inventory, verb):
    """Report exactly one consumed object, even when identical items stack."""
    before = Counter(earlier_inventory)
    after = Counter(session.player.inventory)
    removed = before - after
    if not removed:
        return
    name = next(iter(removed))
    if getattr(session.player, "name", None):
        emit(session, f"{session.player.name} {verb} {name}.")


def bulk_items(session, count, action, one_item=None):
    if count == 0:
        return
    name = getattr(session.player, "name", None)
    if not name:
        return
    if count == 1 and one_item:
        emit(session, f"{name} {action} {one_item}.")
    else:
        emit(session, f"{name} {action} {count} items.")
