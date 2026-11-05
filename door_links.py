"""Keep a physical doorway's two reciprocal exits in the same state.

Only actual reverse links are mirrored. A missing reverse can be created when
a builder adds a door, but an existing exit to a third room is never replaced.
The hidden flag remains directional; door/lock/key/passcode are shared.
"""

import world

SHARED_FLAGS = ("door", "locked", "keyitem", "passcode")


def reciprocal(room, direction):
    """Return (other_room, opposite_direction) only for a true two-way link."""
    target = room.exits.get(direction)
    opposite = world.OPPOSITE_DIRECTION.get(direction)
    other = world.WORLD.get(target) if target is not None else None
    if other is not None and opposite and other.exits.get(opposite) == room.vnum:
        return other, opposite
    return None, None


def ensure_reciprocal(room, direction):
    """Safely add an absent reverse link. Never overwrite a third-room exit."""
    target = room.exits.get(direction)
    opposite = world.OPPOSITE_DIRECTION.get(direction)
    if target is None or not opposite:
        return False, "There is no valid exit in that direction."
    other = world.WORLD.get(target)
    if other is None:
        return False, f"Destination room {target} does not exist."
    existing = other.exits.get(opposite)
    if existing is not None and existing != room.vnum:
        return False, (
            f"Room {target} already has a {opposite} exit to room {existing}. "
            "Use rset bexit with force to resolve the conflicting link first."
        )
    other.exits[opposite] = room.vnum
    return True, ""


def mirror(room, direction):
    """Copy all shared door properties from one exit to its reverse."""
    other, opposite = reciprocal(room, direction)
    if other is None:
        return False
    source_flags = room.exit_flags.get(direction, [])
    other_flags = other.exit_flags.setdefault(opposite, [])
    for flag in SHARED_FLAGS:
        if flag in source_flags and flag not in other_flags:
            other_flags.append(flag)
        elif flag not in source_flags and flag in other_flags:
            other_flags.remove(flag)

    for attr in ("exit_key_item", "exit_passcode"):
        source = getattr(room, attr)
        dest = getattr(other, attr)
        if direction in source:
            dest[opposite] = source[direction]
        else:
            dest.pop(opposite, None)

    if "door" in source_flags:
        other.exit_door_open[opposite] = room.exit_door_open.get(direction, False)
    else:
        room.exit_door_open.pop(direction, None)
        other.exit_door_open.pop(opposite, None)
    return True


def reconcile_pair(room, direction):
    """Repair a one-sided legacy door without discarding its existing state."""
    other, opposite = reciprocal(room, direction)
    if other is None:
        return False
    if "door" in room.exit_flags.get(direction, []):
        return mirror(room, direction)
    if "door" in other.exit_flags.get(opposite, []):
        return mirror(other, opposite)
    return False


def reconcile_all():
    """Normalize old world snapshots that stored a door on only one side.

    Also creates missing reverse exits for doors when there is no conflict.
    Does not replace an occupied reverse exit or change unrelated non-doors.
    """
    visited = set()
    for room in sorted(world.WORLD.rooms.values(), key=lambda item: item.vnum):
        for direction in sorted(room.exits):
            if "door" not in room.exit_flags.get(direction, []):
                continue
            ok, _ = ensure_reciprocal(room, direction)
            if not ok:
                continue
            other, opposite = reciprocal(room, direction)
            pair = frozenset(((room.vnum, direction), (other.vnum, opposite)))
            if pair in visited:
                continue
            visited.add(pair)
            mirror(room, direction)
