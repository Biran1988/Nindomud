"""Observable same-room character actions with stealth and staff privacy.

One successful action creates one message for other occupants. No global
spam, no failed attempts, no information leak from wizinvis or camouflage.
"""
from collections import Counter


def emit(session, text, *, reveal_transition=False, exclude=()):
    """Send to observers in the actor's perceived room, never the actor."""
    player = getattr(session, "player", None)
    if player is None:
        return
    import clone_control
    import general_skills
    import staff_invisibility
    if staff_invisibility.is_hidden(session):
        return
    room = clone_control.view_room(session)
    for observer in session.active_sessions():
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
    emit(session, f"{session.player.name} {verb} {name}.")


def bulk_items(session, count, action, one_item=None):
    if count == 0:
        return
    name = session.player.name
    if count == 1 and one_item:
        emit(session, f"{name} {action} {one_item}.")
    else:
        emit(session, f"{name} {action} {count} items.")
