"""
Minimal room/world model.

Rooms are addressed by VNUM, as required by the design brief. This is a
plain in-memory table for now; Phase 6 (Online Creation) would replace
`build_world()`'s hardcoded dict with data loaded from rset-authored
area files, without needing to change anything that *reads* WORLD.ROOMS.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

OPPOSITE_DIRECTION = {
    "north": "south", "south": "north",
    "east": "west", "west": "east",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
    "up": "down", "down": "up",
    "inside": "outside", "outside": "inside",
}

DIRECTION_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest",
    "se": "southeast", "sw": "southwest",
    "u": "up", "d": "down",
}


def normalize_direction(word: str) -> Optional[str]:
    word = word.lower()
    if word in OPPOSITE_DIRECTION:
        return word
    return DIRECTION_ALIASES.get(word)


@dataclass
class Room:
    vnum: int
    name: str
    description: str
    sector: str = "inside"
    exits: Dict[str, int] = field(default_factory=dict)
    flags: list = field(default_factory=list)
    enabled: bool = True  # immortal-only toggle -- disabled rooms can't be entered
    # Player housing (Section 52) -- apartment=True marks this room as an
    # available/claimed home shell; owner is the player name who claimed
    # it (None = unclaimed, purchasable). Non-owners (other than staff)
    # cannot move into an owned apartment -- see commands.cmd_move.
    apartment: bool = False
    owner: Optional[str] = None
    # Which apartment expansion type this room is (Section 72) --
    # "hallway"/"bedroom"/"kitchen"/"pond"/"storage"/"farming", or None
    # for the base apartment room itself and every other room.
    apartment_room_type: Optional[str] = None
    # Player shops (Section 75) -- a shop-slot room along Main Street.
    # owner (already above) doubles as "who claimed this shop", same
    # as it does for apartment.
    player_shop: bool = False
    # Declarative programs (see programs.py) -- enter/random triggers
    # only, no arbitrary code. Each entry: {"trigger", "action", "args"}.
    programs: list = field(default_factory=list)
    # Elemental jutsu affinity (biomes.py) -- "none" (the default) means
    # no elemental effect either way, matching plain indoor/neutral rooms.
    biome: str = "none"
    # Per-room override of the area-wide reset message (Section: area
    # reset messages), per direct request ("room overrides area") --
    # None means this room has no override of its own, so the area's
    # own areas.Area.reset_message (if any) is shown instead. Set via
    # 'rset resetmsg <text>'.
    reset_message: Optional[str] = None
    # Amaterasu's own real room-fire (Section 140, if rolled) --
    # confirmed directly: casting Amaterasu on a player ALSO sets
    # their current room ablaze, burning everyone in it except the
    # caster, lasting a real 30 minutes from the cast (or until
    # sealed early by a scroll-taught sealing jutsu, not yet built).
    # Genuinely separate from a player's own real burn (mangekyo_
    # amaterasu_burn_until on Player) -- if the original target
    # leaves, this stays behind and would burn anyone else who walks
    # in, exactly as confirmed.
    amaterasu_fire_caster: Optional[str] = None  # the caster's own name, exempt from this room's burn
    amaterasu_fire_expires_at: float = 0.0
    # Kekkei no Me ("Barrier Eye", Section 140, if rolled) -- real,
    # confirmed to transform the CURRENT room in place (no one moves
    # anywhere). Tagged with the caster's own name (exempt from the
    # real drain) and the element their own chakra nature already is
    # at cast time, lasting a real 90 seconds.
    kekkei_no_me_caster: Optional[str] = None
    kekkei_no_me_element: Optional[str] = None
    kekkei_no_me_expires_at: float = 0.0
    # PvP safe zone -- False (the default) means PvP is allowed here;
    # True blocks initiating an attack on another player and auto-
    # disengages any ongoing PvP the moment either combatant is in a
    # safe room. content.py flags villages/shops/hospitals/
    # apartments safe=True; "Outskirts" areas are left PvP-enabled.
    safe: bool = False
    # Items dropped on the ground (commands.cmd_drop/cmd_get) -- plain
    # strings, same shape as player.inventory, so the same stacking
    # rules (inventory.py) apply when picking something back up.
    ground_items: list = field(default_factory=list)
    # Per-exit flags (Section 64) -- direction -> list of flag names, so
    # a single exit can combine multiple at once (e.g. a locked door
    # that also needs a specific key item). Valid flags: "door",
    # "locked", "keyitem", "passcode", "hidden". See
    # olc.EXIT_FLAG_NAMES for the canonical set and olc.py's
    # `rset exitflag` for how builders set them.
    exit_flags: Dict[str, List[str]] = field(default_factory=dict)
    # Whether a "door"-flagged exit is currently open (direction ->
    # bool). Only meaningful when "door" is in that direction's
    # exit_flags -- a door starts closed the moment the flag is set.
    exit_door_open: Dict[str, bool] = field(default_factory=dict)
    # The required key item's name for a "keyitem"-flagged exit, and
    # the required passcode string for a "passcode"-flagged exit.
    exit_key_item: Dict[str, str] = field(default_factory=dict)
    exit_passcode: Dict[str, str] = field(default_factory=dict)
    # Elemental jutsu collision effects (Section 97, per direct
    # request/confirmation: "The counter jutsu hit eachother if cast
    # finishes within 1 second of the other...a water jutsu hitting a
    # fire jutsu will create steam in the room. A earth hitting water
    # might make the room muddy temporarily"). Real Unix timestamp,
    # matching the established pattern for other time-based fields
    # (Player.silenced_until/jailed_until) -- 0.0 means no active
    # override. temp_description_text is APPENDED to the room's own
    # real description when shown (see commands.cmd_look), never a
    # replacement, so the room's genuine identity is never lost, just
    # temporarily supplemented while the effect lasts.
    temp_description_until: float = 0.0
    temp_description_text: str = ""


class World:
    def __init__(self):
        self.rooms: Dict[int, Room] = {}

    def add_room(self, room: Room):
        self.rooms[room.vnum] = room

    def link(self, a_vnum: int, direction: str, b_vnum: int, bidirectional=True):
        """Equivalent to `rset bexit` -- creates the exit and its reverse."""
        self.rooms[a_vnum].exits[direction] = b_vnum
        if bidirectional:
            rev = OPPOSITE_DIRECTION[direction]
            self.rooms[b_vnum].exits[rev] = a_vnum

    def unlink(self, a_vnum: int, direction: str, bidirectional=True):
        """The reverse of link() -- removes the exit (and, by default,
        its reverse) rather than just leaving it pointing at a
        placeholder room. a_vnum must still exist and have that exit;
        does nothing if either isn't true, so callers don't need to
        guard against an already-missing link."""
        room = self.rooms.get(a_vnum)
        if not room or direction not in room.exits:
            return
        b_vnum = room.exits.pop(direction)
        if bidirectional:
            rev = OPPOSITE_DIRECTION[direction]
            b_room = self.rooms.get(b_vnum)
            if b_room and b_room.exits.get(rev) == a_vnum:
                del b_room.exits[rev]

    def get(self, vnum: int) -> Optional[Room]:
        return self.rooms.get(vnum)


def build_world() -> World:
    w = World()

    # Per direct confirmation (Section 143): every village's own real
    # room layout (now a genuinely single Kage/Hokage room per
    # village) is built entirely by content.py's own populate()
    # instead -- these 10 hardcoded rooms (the OLD village square/
    # hospital vnums) used to exist here independently of populate()
    # entirely, and would have directly conflicted with the new,
    # confirmed layout if left in place.

    return w


WORLD = build_world()


def reconcile_apartment_ownership() -> None:
    """Rooms aren't persisted to disk (the whole world is rebuilt fresh
    from content.py + any rset-created rooms every startup), so
    Room.owner (and any name/description customization) has to be
    reconstructed from each player's saved apartment fields, which ARE
    persisted. Call once at startup, after the world (including any
    apartment room shells) is built.

    Also rebuilds every apartment expansion room (Section 72) from
    each player's saved apartment_expansions dict, same reasoning --
    and for a storage room specifically, restores its contents by
    pointing its ground_items at the SAME list object as the player's
    own storage_room_items field (not a copy), so a later drop/get
    there keeps mutating that field directly with no separate sync
    step, exactly like the purchase path in commands.cmd_buy does.

    Also rebuilds every owned player shop (Section 75) from each
    player's saved shop_room_vnum/shop_name/shop_description, spawning
    a fresh shopkeeper mob tagged with player_shop_owner -- the shop's
    actual stock/prices live on the player (shop_stock), not the mob,
    so there's nothing to restore on the mob itself beyond its
    existence and ownership tag."""
    import apartments
    import storage
    for player in storage.all_players():
        if player.apartment_room_vnum is not None:
            room = WORLD.get(player.apartment_room_vnum)
            if room and room.apartment:
                room.owner = player.name
                if player.apartment_name:
                    room.name = player.apartment_name
                if player.apartment_description:
                    room.description = player.apartment_description

                # Multi-pass rather than a single iteration: a child's
                # parent might not be created yet on the first pass if
                # dict order doesn't happen to match parent-before-child
                # purchase order (e.g. a parent room type was sold and
                # later rebought, re-inserting it at the end of the
                # dict after a child that depends on it). Repeats until
                # nothing more can be resolved.
                remaining = dict(player.apartment_expansions)
                while remaining:
                    made_progress = False
                    for room_type, entry in list(remaining.items()):
                        parent_vnum = entry.get("parent_vnum", player.apartment_room_vnum)
                        if WORLD.get(parent_vnum) is None:
                            continue  # parent not built yet this pass -- try again next pass
                        direction = entry["direction"]
                        new_vnum = apartments.expansion_room_vnum(player.apartment_room_vnum, room_type)
                        new_room = Room(
                            new_vnum, f"{player.name}'s {room_type.capitalize()}",
                            apartments.ROOM_TYPE_DESCRIPTIONS[room_type],
                        )
                        new_room.apartment = True
                        new_room.owner = player.name
                        new_room.safe = True
                        WORLD.add_room(new_room)
                        apartments.setup_expansion_room(new_room, room_type)
                        parent_room = WORLD.get(parent_vnum)
                        if direction not in parent_room.exits:
                            WORLD.link(parent_vnum, direction, new_vnum)
                        if room_type == "storage":
                            new_room.ground_items = player.storage_room_items
                        del remaining[room_type]
                        made_progress = True
                    if not made_progress:
                        break  # a parent vnum doesn't exist at all -- give up on the rest, not an infinite loop

        if player.shop_room_vnum is not None:
            shop_room = WORLD.get(player.shop_room_vnum)
            if shop_room and shop_room.player_shop:
                shop_room.owner = player.name
                if player.shop_name:
                    shop_room.name = player.shop_name
                if player.shop_description:
                    shop_room.description = player.shop_description
                import combat
                import playershops
                shopkeeper = combat.spawn_mob(playershops.SHOPKEEPER_TEMPLATE_VNUM, shop_room.vnum)
                if shopkeeper:
                    shopkeeper.player_shop_owner = player.name
                    shopkeeper.name = f"{player.name}'s shopkeeper"
