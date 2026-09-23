"""
Apartment room expansions (Section 72). Beyond the base apartment
(100k ryo, one room, unlocked already), an owner can buy up to 6 more
rooms -- one of each type, in a direction of their own choosing off
the base apartment room. Each purchase costs
config.APARTMENT_EXPANSION_BASE_COST (200k), DOUBLING with every
expansion already owned (200k, 400k, 800k, 1.6M, 3.2M, 6.4M for the
1st through 6th).

Selling gives back config.APARTMENT_SELL_REFUND_PERCENT (50%) of
whatever a room actually cost -- 'sell room <type>' for one expansion
room at a time (the rest of the apartment, and the room's own vnum/
link, stay intact -- just reset to an empty, reusable placeholder), or
'sell apartment' for everything at once (base apartment plus every
expansion, ownership released so a future owner can claim the shell
fresh). Player.apartment_expansions tracks the ryo cost paid per room,
not just the room count, so a refund is always exactly half of what
THAT room cost even after a sell/rebuy cycle changes what the "next"
room would cost today.

Rooms aren't persisted to disk (the whole world is rebuilt fresh from
content.py every startup -- see world.reconcile_apartment_ownership's
own docstring for the established reasoning this follows), so each
expansion room's vnum is DETERMINISTIC (derived from the apartment's
own vnum + a fixed per-type offset) rather than tracked separately,
and Player.apartment_expansions (room_type -> {"direction", "cost"})
is the durable source of truth used to recreate these rooms at
startup.
"""

APARTMENT_ROOM_TYPES = ["hallway", "bedroom", "kitchen", "pond", "storage", "farming"]

ROOM_TYPE_DESCRIPTIONS = {
    "hallway": "A plain connecting hallway. Nothing special here, just a place to pass through.",
    "bedroom": "A cozy bedroom, well-suited for resting and recovering faster than anywhere else.",
    "kitchen": "A fully stocked kitchen -- no need to hold a cooking pot here.",
    "pond": "A small outdoor pond, calm water perfect for fishing.",
    "storage": "A sturdy storage room -- whatever you leave here stays, even through a server restart.",
    "farming": "A small plot of tilled soil, ready for planting.",
}

# A sentinel apartment_room_type (not a real buyable type -- deliberately
# absent from APARTMENT_ROOM_TYPES) marking a slot that's been sold and
# reset, but still exists/still linked -- safe to reconfigure into a
# fresh purchase later rather than permanently blocking that direction.
EMPTY_ROOM_TYPE = "empty"
EMPTY_ROOM_NAME = "An Empty Room"
EMPTY_ROOM_DESCRIPTION = "A bare, unused room. It could be built into something new."


def reset_room_to_empty(room, clear_owner: bool = False, parent_vnum=None, direction=None) -> None:
    """Strips a room back to a neutral placeholder, and disconnects it
    if parent_vnum/direction are given -- called when a room expansion
    is sold, whether individually ('sell room', clear_owner=False
    since the rest of the apartment is still owned) or as part of
    selling the whole apartment ('sell apartment', clear_owner=True so
    a future owner can claim the shell fresh). Per a direct bug
    report: the exit used to stay connected to the reset room instead
    of being removed, so 'buy room' needed special-case logic to
    detect and reuse an "empty" placeholder -- now the exit is
    unlinked outright (world.WORLD.unlink) for expansion rooms, so a
    sold room's direction is simply free again, the same as if it had
    never been built. parent_vnum/direction are left out entirely for
    the BASE apartment room itself -- it's a pre-existing static unit
    (one of a village's fixed apartment slots), not something the
    player built, so it must stay linked to its district for the next
    owner to find, unlike an expansion the player actually
    constructed. The room object itself still exists (nothing deletes
    Room instances in this project) but an unlinked one is
    unreachable -- harmless, since nothing can navigate to it
    anymore."""
    if parent_vnum is not None and direction is not None:
        import world
        world.WORLD.unlink(parent_vnum, direction)
    room.apartment_room_type = EMPTY_ROOM_TYPE
    room.name = EMPTY_ROOM_NAME
    room.description = EMPTY_ROOM_DESCRIPTION
    room.biome = "none"
    if "accelerated_healing" in room.flags:
        room.flags.remove("accelerated_healing")
    room.ground_items = []
    if clear_owner:
        room.owner = None


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
        expansion_room_vnum(player.apartment_room_vnum, room_type) == vnum
        for room_type in player.apartment_expansions
    )


def refund_for_cost(cost: int) -> int:
    import config
    return int(cost * config.APARTMENT_SELL_REFUND_PERCENT)


def expansion_room_vnum(apartment_vnum: int, room_type: str) -> int:
    """Deterministic: apartment vnum (e.g. 1071) * 10 + the room
    type's fixed index in APARTMENT_ROOM_TYPES (e.g. bedroom=1) gives
    10711 -- safely outside the 4-digit range every other room in the
    game uses, so no collision risk, and always the SAME vnum for the
    SAME apartment+type pair, which is what makes reconciliation at
    startup work without tracking vnums separately."""
    return apartment_vnum * 10 + APARTMENT_ROOM_TYPES.index(room_type)


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
    if room_type == "bedroom":
        if "accelerated_healing" not in room.flags:
            room.flags.append("accelerated_healing")
    elif room_type == "pond":
        room.biome = "river"
    elif room_type == "farming":
        room.biome = "plains"
    # hallway: no special mechanic at all, "a basic room" as requested.
    # kitchen: no room flag needed -- cmd_cook checks apartment_room_type
    # directly to waive the held-tool requirement.
    # storage: no room flag needed -- its persistence comes from
    # ground_items being the SAME list object as the owning player's
    # own storage_room_items field, wired up at reconciliation/purchase
    # time, not from anything on the room itself.
