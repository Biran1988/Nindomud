"""Player-owned apartments and their expansion rooms.

New expansions live in the dedicated Apartment area (32001-32500).
Existing expansions keep their original VNUMs: old player saves store only
room types, directions and costs, so moving them blindly would break exits,
locations and potentially storage. New expansions save an explicit VNUM with
the deed, surviving reboot and even future allocation-rule changes.
Previously purchased hallways remain recognized for resale and cleanup,
but no more can be bought.

Selling an expansion actually deletes the built room and its exits and
spawn placements, making the VNUM reusable. Selling an entire apartment
removes *every* player-owned expansion (including legacy placeholders),
but retains its original base room as a vacant "Empty apartment".
"""

# Keep the original type indexes to prevent changing saved expansion VNUMs.
APARTMENT_VNUM_TYPES = ("hallway", "bedroom", "kitchen", "pond", "storage", "farming")
APARTMENT_ROOM_TYPES = list(APARTMENT_VNUM_TYPES[1:])

EXPANSION_AREA_NAME = "apartment"
EXPANSION_VNUM_START = 32001
EXPANSION_VNUM_END = 32500

ROOM_TYPE_DESCRIPTIONS = {
    "hallway": "A plain connecting hallway. Nothing special here, just a place to pass through.",
    "bedroom": "A private healing bedroom: recover Health, Chakra and Stamina at village-hospital rates (10x standing, 30x sleeping) while out of combat.",
    "kitchen": "A fully stocked kitchen -- no need to hold a cooking pot here.",
    "pond": "A small outdoor pond, calm water perfect for fishing.",
    "storage": "A sturdy storage room -- whatever you leave here stays, even through a server restart.",
    "farming": "A small plot of tilled soil, ready for planting.",
}

# Used for identifying and cleaning up old sold-room placeholders.
EMPTY_ROOM_TYPE = "empty"
EMPTY_ROOM_NAME = "An Empty Room"
EMPTY_ROOM_DESCRIPTION = "A bare, unused room. It could be built into something new."
VACANT_APARTMENT_NAME = "Empty apartment"
VACANT_APARTMENT_DESCRIPTION = "An empty apartment available for purchase."


def owns_expansion_room(player, room_type: str) -> bool:
    """Check ownership before touching a deterministic VNUM on resale."""
    import world
    if player.apartment_room_vnum is None:
        return False
    room = world.WORLD.get(expansion_room_vnum(player.apartment_room_vnum, room_type, player))
    return bool(room and room.apartment and room.owner == player.name
                and room.apartment_room_type in (room_type, EMPTY_ROOM_TYPE))


def _destroy_expansion_vnum(vnum: int, fallback_vnum: int, sessions=None) -> None:
    """Delete a verified apartment expansion and remove its live references."""
    import combat
    import spawn_points
    import world

    if sessions is None:
        from session import ACTIVE_SESSIONS
        sessions = ACTIVE_SESSIONS
    for connected in sessions:
        occupant = getattr(connected, "player", None)
        if occupant is not None and occupant.room_vnum == vnum:
            occupant.room_vnum = fallback_vnum
            connected.send("&Y(The apartment room was removed. You return to the main room.)&x")

    # Drop all inbound exits AND their door/key flags. Never leave
    # a valid room pointing at a nonexistent VNUM.
    for other in world.WORLD.rooms.values():
        if other.vnum == vnum:
            continue
        for direction, destination in list(other.exits.items()):
            if destination == vnum:
                other.exits.pop(direction, None)
                for attr in ("exit_flags", "exit_door_open",
                             "exit_key_item", "exit_passcode"):
                    getattr(other, attr, {}).pop(direction, None)

    spawn_points.remove_all_spawn_points(vnum)
    combat.MOBS_BY_ROOM.pop(vnum, None)
    world.WORLD.rooms.pop(vnum, None)


def delete_expansion_room(player, room_type: str, sessions=None) -> bool:
    """Free one owned expansion VNUM, without deleting unrelated builder rooms."""
    if player.apartment_room_vnum is None or not owns_expansion_room(player, room_type):
        return False
    vnum = expansion_room_vnum(player.apartment_room_vnum, room_type, player)
    _destroy_expansion_vnum(vnum, player.apartment_room_vnum, sessions)
    return True


def clear_apartment_expansions(player, sessions=None) -> int:
    """Clear all owned slots, including legacy hallways and sold placeholders."""
    return sum(delete_expansion_room(player, room_type, sessions)
               for room_type in APARTMENT_VNUM_TYPES)


def reset_vacant_apartment(room) -> None:
    """Keep the permanent shell and its district exit available to buy."""
    room.owner = None
    room.apartment = True
    room.apartment_room_type = None
    room.name = VACANT_APARTMENT_NAME
    room.description = VACANT_APARTMENT_DESCRIPTION
    if "apartment" not in room.flags:
        room.flags.append("apartment")


def owns_room_at(player, vnum: int) -> bool:
    """True if vnum is the player's own base apartment OR any of their
    own expansion rooms -- the whole complex counts as "the player's
    own space" for buying further rooms, not just the base apartment
    specifically."""
    if player.apartment_room_vnum is None:
        return False
    if vnum == player.apartment_room_vnum:
        return True
    return any(
        expansion_room_vnum(player.apartment_room_vnum, room_type, player) == vnum
        for room_type in player.apartment_expansions
    )


def refund_for_cost(cost: int) -> int:
    import config
    return int(cost * config.APARTMENT_SELL_REFUND_PERCENT)


def expansion_room_vnum(apartment_vnum: int, room_type: str, player=None) -> int:
    """Return the purchased room's VNUM, or the historical legacy VNUM.

    Old saves have no explicit VNUM and MUST retain their old identity; new
    purchases record a 32001-32500 VNUM directly on the saved expansion.
    """
    if player is not None:
        entry = getattr(player, "apartment_expansions", {}).get(room_type, {})
        if isinstance(entry, dict) and entry.get("vnum") is not None:
            return int(entry["vnum"])
    return apartment_vnum * 10 + APARTMENT_VNUM_TYPES.index(room_type)


def ensure_expansion_area() -> None:
    """Reserve Apartment 32001-32500, preserving an existing builder area.

    Prototype is an OLC *editing* designation, not a reason to discard
    player-owned rooms. We do not turn a builder's prototype flag off.
    """
    import areas
    import storage

    area = areas.find_area(EXPANSION_AREA_NAME)
    if area is not None:
        if (area.vnum_start > EXPANSION_VNUM_START
                or area.vnum_end < EXPANSION_VNUM_END):
            raise ValueError(
                f"Area '{area.name}' must cover Apartment expansion VNUMs "
                f"{EXPANSION_VNUM_START}-{EXPANSION_VNUM_END}; found "
                f"{area.vnum_start}-{area.vnum_end}.")
        return
    # Respect an explicit builder deletion rather than re-creating a removed
    # area unasked, which could silently reoccupy somebody else's VNUMs.
    for entry in storage.load_world_state().get("deleted_areas", []):
        if entry.get("start", EXPANSION_VNUM_END + 1) <= EXPANSION_VNUM_END and \
                entry.get("end", EXPANSION_VNUM_START - 1) >= EXPANSION_VNUM_START:
            raise ValueError("The Apartment expansion VNUM range was deleted; restore its area first.")
    areas.register_area(EXPANSION_AREA_NAME, EXPANSION_VNUM_START,
                        EXPANSION_VNUM_END, "system")


def allocate_expansion_vnum(player) -> int:
    """Choose an unoccupied Apartment VNUM without touching existing rooms.

    Active world rooms, stored deeds (including offline players) and saved
    world snapshots all reserve their numbers. No silent reassignment.
    """
    import storage
    import world

    ensure_expansion_area()
    used = set(world.WORLD.rooms)
    for resident in storage.all_players():
        if resident.apartment_room_vnum is None:
            continue
        for kind in resident.apartment_expansions:
            if kind in APARTMENT_VNUM_TYPES:
                used.add(expansion_room_vnum(resident.apartment_room_vnum, kind, resident))
    for kind in player.apartment_expansions:
        if kind in APARTMENT_VNUM_TYPES:
            used.add(expansion_room_vnum(player.apartment_room_vnum, kind, player))
    # Even if an OLC room was saved but not loaded into WORLD for some reason,
    # its persisted VNUM remains off-limits for new construction.
    used.update(int(v) for v in storage.load_world_state().get("rooms", {}))
    for vnum in range(EXPANSION_VNUM_START, EXPANSION_VNUM_END + 1):
        if vnum not in used:
            return vnum
    raise ValueError("Apartment expansion area 32001-32500 is full; no room can be built.")


def restore_expansion_link(parent_room, direction: str, expansion_room) -> bool:
    """Repair BOTH sides on reboot, including a missing reverse exit.

    Never overwrite an unrelated builder exit. Existing door/key flags on
    both ends remain intact; this only repairs the destination mappings.
    """
    import world
    reverse = world.OPPOSITE_DIRECTION.get(direction)
    if reverse is None:
        return False
    if parent_room.exits.get(direction) not in (None, expansion_room.vnum):
        return False
    if expansion_room.exits.get(reverse) not in (None, parent_room.vnum):
        return False
    parent_room.exits[direction] = expansion_room.vnum
    expansion_room.exits[reverse] = parent_room.vnum
    return True


def expansion_cost(rooms_already_owned: int) -> int:
    import config
    return config.APARTMENT_EXPANSION_BASE_COST * (2 ** rooms_already_owned)


def setup_expansion_room(room, room_type: str) -> None:
    """Applies the room-type-specific mechanic to a freshly created (or
    freshly reconciled) expansion room. Called from both the purchase
    command and startup reconciliation, so the two paths can't drift
    apart -- whichever one creates the room, this is what makes it
    actually behave like its type, not just display a name."""
    room.apartment_room_type = room_type
    if "apartment" not in room.flags:
        room.flags.append("apartment")
    if room_type == "bedroom":
        if "accelerated_healing" not in room.flags:
            room.flags.append("accelerated_healing")
    elif room_type == "pond":
        room.biome = "river"
    elif room_type == "farming":
        room.biome = "plains"
    # kitchen: no room flag needed -- cmd_cook checks apartment_room_type
    # directly to waive the held-tool requirement.
    # storage: no room flag needed -- its persistence comes from
    # ground_items being the SAME list object as the owning player's
    # own storage_room_items field, wired up at reconciliation/purchase
    # time, not from anything on the room itself.
