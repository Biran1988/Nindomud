"""Safely rehome legacy village rooms saved inside the Leaf room reservation.

The area registry was widened to 2500-room bands after old Iwa/Kiri/Kumo/
Suna rooms had already been built at 1100-1485. The saved-world overlay wins
on reboot, so changing the area metadata alone cannot relocate those rooms.

This migration moves only the known legacy room slots, never overwrites a
builder room in a target area, and records successful moves in a separate
small /data ledger. Player saves are translated on load (and written in the
new format on their next ordinary save), preserving old apartment expansion
VNUMs and all their storage. Repeated boots are safe.
"""

from copy import deepcopy
from functools import lru_cache
import json
import os

# Explicit original rooms, not a broad sweep over builder-created Leaf rooms.
VILLAGE_OFFSETS = (0, 1, 10, 20, 21, 30, 40, 50, 60, 70, 71, 72, 73, 80, 85)
# Leave each area's original canonical Kage room (2501/5001/7501/10001)
# in place. The migrated legacy village layout receives its own 100-vnum
# block, which cannot collide with those entry rooms.
VILLAGES = (
    ("Iwa", "stone", 1100, 2600, (2501, 5000)),
    ("Kiri", "water", 1200, 5100, (5001, 7500)),
    ("Kumo", "cloud", 1300, 7600, (7501, 10000)),
    ("Suna", "sand", 1400, 10100, (10001, 12500)),
)
# These two generic legacy gathering rooms also belong outside Leaf's area.
# Use spare Stone-area positions; abort rather than replacing occupied slots.
GATHERING = {2499: 2700, 2500: 2701}
LEDGER = "village_room_moves.json"


def _path():
    import storage
    return os.path.join(storage.DATA_DIR, LEDGER)


@lru_cache(maxsize=16)
def _read_moves(path, stamp, size):
    with open(path, encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        return {}
    return {int(old): int(new) for old, new in payload.items()
            if str(old).isdigit() and str(new).isdigit()}


def load_moves():
    """Lightweight, cache-aware room translation for login and ground Ryo."""
    path = _path()
    try:
        stat = os.stat(path)
        return _read_moves(path, stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def remap_player(player):
    """Translate saved room references, without reassigning older housing.

    Expansion deeds from before version 15.485 did not store a `vnum`.
    Remember the original expansion VNUM before changing the main room's
    ID; otherwise the old arithmetic would silently relocate the storage
    room and disconnect its saved contents.
    """
    moves = load_moves()
    if not moves:
        return False
    import apartments
    old_base = player.apartment_room_vnum
    changed = False
    if old_base in moves:
        for kind, entry in player.apartment_expansions.items():
            if kind in apartments.APARTMENT_VNUM_TYPES and isinstance(entry, dict):
                if entry.get("vnum") is None:
                    entry["vnum"] = old_base * 10 + apartments.APARTMENT_VNUM_TYPES.index(kind)
                    changed = True
    for key, val in vars(player).items():
        if (key == "room_vnum" or key.endswith("_vnum")) and type(val) is int and val in moves:
            setattr(player, key, moves[val])
            changed = True
    for entry in player.apartment_expansions.values():
        if not isinstance(entry, dict):
            continue
        parent = entry.get("parent_vnum")
        if type(parent) is int and parent in moves:
            entry["parent_vnum"] = moves[parent]
            changed = True
    return changed


def _rewrite_spawns(spawn_data, moves):
    from spawn_points import _key
    points = spawn_data.get("points", {})
    if not isinstance(points, dict):
        return spawn_data
    remapped = {}
    original_keys = {}
    for old_key, point in points.items():
        room_vnum = point.get("room_vnum")
        new_vnum = moves.get(room_vnum, room_vnum)
        copy = dict(point)
        copy["room_vnum"] = new_vnum
        key = _key(copy["kind"], copy["vnum"], new_vnum)
        # Never discard either spawn record if both old/new positions have
        # already been configured by the builder.
        if key in remapped and original_keys[key] != old_key:
            raise ValueError(f"Spawn-point conflict relocating {old_key} -> {key}")
        remapped[key] = copy
        original_keys[key] = old_key
    state = deepcopy(spawn_data)
    state["points"] = remapped
    return state


def _save_moves(moves):
    import storage
    storage.ensure_dirs()
    storage._atomic_write_json(_path(), {str(k): v for k, v in sorted(moves.items())})
    _read_moves.cache_clear()


def relocate_saved_rooms():
    """One-time/recoverable migration after loading world but before spawns.

    All VNUMs are checked against BOTH the saved snapshot and current live
    rooms, and area reservations must be exact. A conflicting group's rooms
    stay untouched with a prominent diagnostic; no builder work is erased.
    """
    import areas
    import storage
    import world
    state = storage.load_world_state()
    saved_rooms = state.get("rooms", {})
    if not isinstance(saved_rooms, dict):
        return {}
    previously_moved = load_moves()
    moves = dict(previously_moved)
    new_moves = {}
    blocked = []
    for title, area_key, old_base, new_base, bounds in VILLAGES:
        candidates = {old_base + n: new_base + n for n in VILLAGE_OFFSETS
                      if str(old_base + n) in saved_rooms}
        if not candidates:
            continue
        area = areas.find_area(area_key)
        if area is None or (area.vnum_start, area.vnum_end) != bounds:
            blocked.append(f"{title}: destination area '{area_key}' is missing or has the wrong range")
            continue
        conflicts = [n for old, n in candidates.items()
                     if str(n) in saved_rooms or n in world.WORLD.rooms]
        if conflicts:
            blocked.append(f"{title}: target VNUMs already occupied: {conflicts}")
            continue
        new_moves.update(candidates)
    gather = {}
    for old, new in GATHERING.items():
        room = saved_rooms.get(str(old), {})
        expected_name = "a small mine" if old == 2499 else "a small forest"
        if room and room.get("name", "").casefold() == expected_name:
            gather[old] = new
    if gather:
        area = areas.find_area("stone")
        if area is None or (area.vnum_start, area.vnum_end) != (2501, 5000):
            blocked.append("Gathering: Stone area missing or incorrectly reserved")
        else:
            conflicts = [new for old, new in gather.items()
                         if str(new) in saved_rooms or new in world.WORLD.rooms]
            if conflicts:
                blocked.append(f"Gathering: target VNUMs already occupied: {conflicts}")
            else:
                new_moves.update(gather)
    # Existing mapping is replayable if a crash happened between the small
    # ledger write and the world snapshot update.
    for old, new in previously_moved.items():
        if str(old) in saved_rooms:
            if str(new) in saved_rooms or new in world.WORLD.rooms:
                # An earlier successful migration may have been followed by
                # a builder reusing the old VNUM. Never overwrite either.
                print(f"[Village VNUM migration] SKIPPED: previously moved {old} "
                      f"was reused while {new} is occupied")
            else:
                new_moves[old] = new
    for warning in blocked:
        print(f"[Village VNUM migration] SKIPPED: {warning}")
    moves.update(new_moves)
    if not new_moves and not previously_moved:
        return {}

    spawn_state = storage.load_spawn_points()
    try:
        updated_spawns = _rewrite_spawns(spawn_state, moves)
    except ValueError as error:
        print(f"[Village VNUM migration] SKIPPED: {error}")
        return {}

    if new_moves:
        updated_state = deepcopy(state)
        updated_rooms = updated_state["rooms"]
        for old, new in new_moves.items():
            room = updated_rooms.pop(str(old))
            room["vnum"] = new
            updated_rooms[str(new)] = room
        for room in updated_rooms.values():
            exits = room.get("exits", {})
            for heading, destination in list(exits.items()):
                if destination in moves:
                    exits[heading] = moves[destination]
        # Persist the translation FIRST, so an interrupted write can be
        # safely replayed on the next boot without losing owner references.
        _save_moves(moves)
        storage.save_world_state(updated_state)
        for old, new in new_moves.items():
            room = world.WORLD.rooms.pop(old, None)
            if room is not None:
                room.vnum = new
                world.WORLD.rooms[new] = room
        for room in world.WORLD.rooms.values():
            for heading, destination in list(room.exits.items()):
                if destination in moves:
                    room.exits[heading] = moves[destination]
        print(f"[Village VNUM migration] Moved {len(new_moves)} saved rooms into their registered areas.")

    if updated_spawns != spawn_state:
        storage.save_spawn_points(updated_spawns)
    return new_moves
