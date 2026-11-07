"""Restore damaged mainland highway links without replacing village content.

Run after saved-world loading and the legacy one-time installer. The installer
marker can survive a partial snapshot or area edit, so it cannot be the test of
whether the live road graph is actually complete.
"""
from copy import deepcopy
from dataclasses import asdict

import mainland_roads


class RoadRecoveryError(ValueError):
    """A custom occupied room/exit must be reviewed before road recovery."""


def _serialized(room):
    return {key: value for key, value in asdict(room).items()
            if key != "ground_ryo"}


def _candidate_directions(preferred, room, hub_vnum):
    """Prefer the original compass gate, or reuse an existing link to this hub."""
    from mainland_roads import HEADINGS, REVERSE
    existing = [REVERSE[d] for d, target in room.exits.items()
                if target == hub_vnum and d in REVERSE]
    return list(dict.fromkeys(existing + [preferred] + list(HEADINGS)))


def repair_missing_roads():
    """Reconcile the reserved road graph and add exits ONLY to village rooms.

    Unchanged saved village fields and exits remain untouched. A default
    Unfinished Room inside a planned highway VNUM may be replaced, but a
    genuinely custom-named road-area room is never silently overwritten.
    """
    import areas
    import storage
    import world

    area = next((entry for entry in areas.all_areas().values()
                 if entry.get("name", "").casefold() == "mainland road network"), None)
    if not area or (area["vnum_start"], area["vnum_end"]) != (
            mainland_roads.FIRST_VNUM, mainland_roads.LAST_VNUM):
        raise RoadRecoveryError(
            "Mainland Road Network area 20501-30500 is missing or mismatched.")

    expected, hubs = mainland_roads.build_rooms()
    state = storage.load_world_state()
    if not isinstance(state, dict) or not isinstance(state.get("rooms"), dict):
        raise RoadRecoveryError("Cannot repair without a valid world_state rooms map.")
    saved_rooms = state["rooms"]
    live = world.WORLD.rooms

    # No partial changes: identify any unrelated, builder-owned collision first.
    for vnum, canonical in expected.items():
        for room_name in (
                getattr(live.get(vnum), "name", None),
                (saved_rooms.get(str(vnum)) or {}).get("name")):
            if room_name is not None and room_name not in (
                    canonical.name, "An Unfinished Room"):
                raise RoadRecoveryError(
                    f"VNUM {vnum} contains {room_name!r}, not the original "
                    f"highway room; no changes made.")

    staged = {}
    new_roads = 0
    placeholders = 0
    for vnum, reference in expected.items():
        current = live.get(vnum)
        if current is None or current.name == "An Unfinished Room":
            staged[vnum] = deepcopy(reference)
            if current is None:
                new_roads += 1
            else:
                placeholders += 1
        else:
            staged[vnum] = deepcopy(current)

    # Restore each canonical corridor connection in BOTH directions.
    # The reserved road geometry takes precedence over stale/wrong links
    # within the generated road rooms, but never consumes a custom exit
    # leading to a room outside that generated corridor.
    for vnum, reference in expected.items():
        room = staged[vnum]
        for heading, destination in reference.exits.items():
            if destination not in expected:
                continue  # Entrance links are reconciled separately below.
            prior = room.exits.get(heading)
            if prior not in (None, destination) and prior not in expected:
                raise RoadRecoveryError(
                    f"Road {vnum} uses {heading} for custom room {prior}; "
                    f"cannot replace a builder exit.")
            room.exits[heading] = destination

    # The Leaf connector is room 9. Other villages connect at their
    # existing Anki/Kage rooms (2501, 7501, 10001); NEVER replace
    # those rooms, only add a missing outward exit in a free direction.
    entries = {}
    unavailable = []
    village_entries = {9, 2501, 7501, 10001}
    for title, area_name, entrance, junction, preferred, start, end in mainland_roads.DESTINATIONS:
        hub = hubs[junction]
        road = staged[hub]
        old = live.get(entrance)
        if old is None:
            if entrance in village_entries:
                unavailable.append(f"{title} {entrance}: village room missing")
                continue  # Do not fabricate a Kage/village room.
            if not areas.find_area_for_vnum(entrance):
                unavailable.append(f"{title} {entrance}: area missing")
                continue
            from world import Room
            entry = Room(entrance, f"{title} Country Entrance",
                         f"A simple entrance marks the border of {title} Country.",
                         sector="field")
        else:
            entry = deepcopy(old)

        # Remove only stale links to THIS entrance from the road hub.
        # Keep every other existing highway and roadside exit intact.
        for direction, target in list(road.exits.items()):
            if target == entrance:
                del road.exits[direction]

        chosen = None
        for direction in _candidate_directions(preferred, entry, hub):
            opposite = mainland_roads.REVERSE[direction]
            if road.exits.get(direction) not in (None, entrance):
                continue
            if entry.exits.get(opposite) not in (None, hub):
                continue
            chosen = direction
            break
        if chosen is None:
            raise RoadRecoveryError(
                f"No reciprocal free exit between {title} entrance "
                f"{entrance} and road junction {hub}; no changes made.")
        road.exits[chosen] = entrance
        entry.exits[mainland_roads.REVERSE[chosen]] = hub
        entries[entrance] = entry

    # Save a merged version of only the changed/new rooms. In particular,
    # an existing village record retains name/description/flags/programs and
    # all other saved fields byte-for-byte, except its required added exit.
    merged = deepcopy(state)
    changed = {}
    for vnum, staged_room in {**staged, **entries}.items():
        previous = live.get(vnum)
        if previous is not None and _serialized(previous) == _serialized(staged_room):
            continue
        previous_record = saved_rooms.get(str(vnum))
        if (previous is not None and previous.name != "An Unfinished Room"
                and isinstance(previous_record, dict)):
            record = deepcopy(previous_record)
            record["exits"] = deepcopy(staged_room.exits)
        else:
            record = _serialized(staged_room)
        merged["rooms"][str(vnum)] = record
        changed[vnum] = staged_room

    if changed:
        storage.save_world_state(merged)
        live.update(changed)

    return {
        "restored_rooms": new_roads, "replaced_unfinished": placeholders,
        "updated_rooms": len(changed), "entrances": len(entries),
        "unavailable": unavailable,
    }
