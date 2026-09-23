"""
Area registry (Section 76), per explicit request. An "area" reserves
a contiguous block of ROOM vnums (matching the classic MUD convention
of one owned vnum range per area) so builders working on different
areas can't accidentally collide with each other's rooms. `area
create <name>` (see commands.cmd_area) allocates the next free block
automatically -- 1000 vnums by default, matching the size of a single
village's own existing block (see below).

Deliberately scoped to ROOM vnums only, not mobs/objects -- this
project has always used separate numbering spaces for those (rooms in
the low thousands, mobs in the 5000s/6000s, objects in the 9700s),
and unifying that into one shared vnum space per area would be a much
larger, riskier change than what was actually asked for here. A
builder creating mobs/objects for a new area still picks vnums the
same way as always (mset create/oset create); only ROOM vnum
collisions are what this system prevents.

Persisted (storage.load_areas/save_areas, the same established
pattern jackpots/bounties/auctions already use) so reservations
survive a restart -- unlike the rooms/mobs/objects themselves, which
don't. content.py's own populate() registers one broad "legacy-world"
reservation the first time it runs, covering every pre-existing room
vnum not otherwise claimed by a village -- the old (now-removed)
academy range, Main Street,
and the apartment/shop dynamic expansion range (split across two
narrower reservations, "legacy-world" and "legacy-expansions", rather
than one, so nothing needed to stay as wide as it originally was).

The 5 villages themselves each get their OWN area (see
ensure_villages_split_from_legacy below), per explicit request --
carved out of what used to be a single, much broader "legacy-world"
covering everything, including all 5 villages, at once. Verified
directly against the real, live room layout before doing this, not
assumed: every room belonging to a given village already fell
entirely within that village's own clean, non-overlapping 100-vnum
block, so splitting it out was safe. The remaining, narrower
"legacy-world"/"legacy-expansions" pair still isn't a clean
one-reservation-per-named-thing mapping for the old academy range/Main
Street/apartment content specifically -- that content predates this
system and was never built with one contiguous range per area in
mind, so a fully granular split of THAT remainder is still a
deliberate, honest limitation, just a narrower one than before.
"""

import dataclasses
from typing import Optional

DEFAULT_BLOCK_SIZE = 1000


@dataclasses.dataclass
class Area:
    name: str
    vnum_start: int
    vnum_end: int
    creator: str
    income: int = 0  # per-tick village treasury income when this area is controlled (see territory.py)
    # Area-wide atmospheric flavor line (Section: area reset messages),
    # per direct request -- shown periodically (server.py's own random-
    # trigger tick, matching the existing per-room program mechanism)
    # to a player standing in any room within this area, UNLESS that
    # specific room has its own override set via 'rset resetmsg'
    # (world.Room.reset_message), which always wins over the area-wide
    # one. None means no area-wide message has been set.
    reset_message: Optional[str] = None


def all_areas() -> dict:
    import storage
    return storage.load_areas()


def find_area(name: str) -> Optional[Area]:
    entry = all_areas().get(name.strip().lower())
    return Area(**entry) if entry else None


def find_area_for_vnum(vnum: int) -> Optional[Area]:
    for entry in all_areas().values():
        if entry["vnum_start"] <= vnum <= entry["vnum_end"]:
            return Area(**entry)
    return None


def resolve_reset_message(room) -> Optional[str]:
    """The effective reset message for a room, per direct request
    ("room overrides area"): the room's own override (room.
    reset_message) always wins if set, otherwise the message from
    whichever area contains the room (if that area has one set),
    otherwise None -- meaning no message should be shown at all.
    Takes a world.Room directly rather than a vnum, since every
    caller already has the Room object in hand."""
    if room.reset_message:
        return room.reset_message
    area = find_area_for_vnum(room.vnum)
    if area and area.reset_message:
        return area.reset_message
    return None


AREA_RESET_INTERVAL_SECONDS = 15 * 60  # 15 minutes, per explicit follow-up request


def perform_area_reset(area) -> None:
    """One area's full reset: sends the resolved reset message (see
    resolve_reset_message -- a room's own override still wins over
    the area's, per "room overrides area") to every player currently
    standing anywhere within the area, each getting the message for
    their OWN specific room rather than one blanket area-wide line,
    then sweeps for any missing mob spawn points (see spawn_points.
    respawn_missing_mobs_in_area). Called once per area every
    AREA_RESET_INTERVAL_SECONDS from server.py's own timer loop --
    replaces the old per-pulse-per-player probabilistic roll
    entirely, per direct follow-up request ("i want areas to reset
    every 15 minutes")."""
    import session as session_module
    import spawn_points
    import world

    for s in session_module.ACTIVE_SESSIONS:
        if not s.player:
            continue
        if not (area.vnum_start <= s.player.room_vnum <= area.vnum_end):
            continue
        room = world.WORLD.get(s.player.room_vnum)
        if not room:
            continue
        message = resolve_reset_message(room)
        if message:
            s.send(f"&D{message}&x")
            s.send_prompt()

    spawn_points.respawn_missing_mobs_in_area(area)


def perform_all_area_resets() -> None:
    """Runs perform_area_reset for every registered area, in one
    sweep -- called once every AREA_RESET_INTERVAL_SECONDS from
    server.py's own timer loop."""
    for entry in all_areas().values():
        perform_area_reset(Area(**entry))


def next_free_block(size: int = DEFAULT_BLOCK_SIZE) -> int:
    """Returns the start vnum of the next completely free block of the
    given size -- scans every registered area's reserved range (not
    existing rooms directly) for the first gap big enough, starting
    from vnum 1."""
    areas_sorted = sorted(all_areas().values(), key=lambda e: e["vnum_start"])
    candidate = 1
    for entry in areas_sorted:
        if candidate + size - 1 < entry["vnum_start"]:
            return candidate
        candidate = max(candidate, entry["vnum_end"] + 1)
    return candidate


def register_area(name: str, vnum_start: int, vnum_end: int, creator: str) -> Area:
    """Registers a new reservation directly at a specific range --
    used by content.py's own startup "legacy" registration and by
    create_area below. Raises ValueError on a name collision or a
    vnum range overlapping an existing area."""
    areas = all_areas()
    key = name.strip().lower()
    if key in areas:
        raise ValueError(f"An area named '{name}' already exists.")
    for entry in areas.values():
        if vnum_start <= entry["vnum_end"] and entry["vnum_start"] <= vnum_end:
            raise ValueError(
                f"Vnums {vnum_start}-{vnum_end} overlap the existing area "
                f"'{entry['name']}' ({entry['vnum_start']}-{entry['vnum_end']})."
            )
    areas[key] = {
        "name": name, "vnum_start": vnum_start, "vnum_end": vnum_end, "creator": creator,
    }
    import storage
    storage.save_areas(areas)
    return Area(name=name, vnum_start=vnum_start, vnum_end=vnum_end, creator=creator)


def create_area(name: str, creator: str, size: int = DEFAULT_BLOCK_SIZE) -> Area:
    """Allocates the next free block automatically and registers it."""
    start = next_free_block(size)
    return register_area(name, start, start + size - 1, creator)


def set_income(name: str, income: int) -> Optional[Area]:
    """Sets an existing area's per-tick territory income (see
    territory.py). Returns the updated Area, or None if no area with
    that name exists."""
    import storage

    areas = all_areas()
    key = name.strip().lower()
    if key not in areas:
        return None
    areas[key]["income"] = income
    storage.save_areas(areas)
    return Area(**areas[key])


def set_reset_message(name: str, message: Optional[str]) -> Optional[Area]:
    """Sets (or clears, if message is None/empty) an existing area's
    reset_message (Section: area reset messages) -- see areas.py's own
    docstring on resolve_reset_message for how this interacts with a
    room's own override. Returns the updated Area, or None if no area
    with that name exists."""
    import storage

    areas = all_areas()
    key = name.strip().lower()
    if key not in areas:
        return None
    areas[key]["reset_message"] = message if message else None
    storage.save_areas(areas)
    return Area(**areas[key])


def remove_area(name: str) -> bool:
    """Removes an area's reservation entirely. Returns False if no
    area by that name exists. Doesn't touch any room actually built
    within its old range -- purely a registry-bookkeeping operation."""
    import storage

    areas = all_areas()
    key = name.strip().lower()
    if key not in areas:
        return False
    del areas[key]
    storage.save_areas(areas)
    return True


def ensure_legacy_area_registered() -> None:
    """Called once from content.py's populate() every startup --
    idempotent (does nothing if already registered), so it's safe to
    call every time rather than needing a separate one-time setup
    step. Covers every room vnum the pre-existing content already
    uses, so 'area create' never allocates something that collides
    with it."""
    if find_area("legacy-world"):
        return
    try:
        register_area("legacy-world", 1, 10999, "system")
    except ValueError:
        pass  # created by a concurrent/earlier call in the same startup


def ensure_villages_split_from_legacy() -> None:
    """Called once from content.py's populate(), right after
    ensure_legacy_area_registered() -- per explicit request, carves
    each of the 5 villages out of the single broad "legacy-world"
    reservation into its own named area. Idempotent, same pattern as
    ensure_legacy_area_registered itself: checks whether "leaf" (the
    first village) is already registered as its own area and does
    nothing if so, so this migration only ever actually runs once,
    the very first startup after this feature was added.

    Safe because it was verified directly against the real, live room
    layout first, not assumed: every room belonging to a given village
    (including its Outskirts, shops, gambling den, and any Leaf-only
    gathering locations) already falls entirely within that village's
    own clean, non-overlapping 100-vnum block (1000-1099 for Leaf,
    1100-1199 for Iwa, and so on) -- nothing spills into another
    village's range or vice versa. The two small ranges outside all 5
    village blocks (the old, now-removed academy range at 100-106, and the dynamic
    player-shop slots at 10901-10942) stay covered by two narrower
    replacement reservations instead of the single wide one."""
    import data_villages

    if find_area("leaf"):
        return

    remove_area("legacy-world")

    for village_key, village_info in data_villages.VILLAGES.items():
        start = village_info["starting_room_vnum"]
        try:
            register_area(village_key, start, start + 99, "system")
        except ValueError:
            pass  # already registered by a concurrent/earlier call this startup

    for name, start, end in [
        ("legacy-world", 1, 999),
        ("legacy-expansions", 1500, 10999),
    ]:
        try:
            register_area(name, start, end, "system")
        except ValueError:
            pass


def ensure_village_expansion_areas() -> None:
    """Called once from content.py's populate(), right after
    ensure_villages_split_from_legacy() -- per explicit request
    ("make the village vnum range bigger so each village has 1000
    vnums to build with"). Idempotent, same check-first pattern as the
    other two ensure_* functions here.

    Each village's ORIGINAL 100-vnum core block (1000-1099 for Leaf,
    and so on) is packed directly against the next village's, only
    100 vnums apart -- there's no room to simply widen it in place
    without relocating already-built rooms and breaking every existing
    saved player's room_vnum, apartment ownership, and any other
    persisted reference to those exact vnums. Far too risky for a
    live, persisted game, so nothing about any existing room moves.

    Instead, each village gets a SECOND, separate area -- a genuinely
    fresh, empty 1000-vnum block for new building, placed in confirmed
    -clean space starting right after legacy-expansions (which ends at
    10999) and stopping well short of the next real reservation
    (forest-of-death, at 60000): 11000-11999 for the first village in
    data_villages.VILLAGES, 12000-12999 for the second, and so on.
    Named "<village>-expansion" (e.g. "leaf-expansion") so it's
    unmistakable which is the original core and which is the new room
    to grow into -- both show up under 'area list'."""
    import data_villages

    if find_area("leaf-expansion"):
        return

    for index, village_key in enumerate(data_villages.VILLAGES):
        start = 11000 + index * 1000
        try:
            register_area(f"{village_key}-expansion", start, start + 999, "system")
        except ValueError:
            pass  # already registered by a concurrent/earlier call this startup


def ensure_single_village_areas() -> None:
    """Called once from content.py's own populate(), REPLACING the 3
    older ensure_legacy_area_registered/ensure_villages_split_from_
    legacy/ensure_village_expansion_areas calls entirely -- per direct
    request/confirmation (Section 143): "convert these into 1 leaf
    village not expansions...give each area 2500 vnums to work with
    no expansions so that they are single areas." Confirmed directly
    it's genuinely fine to wipe every old room in this one instance,
    and that the new, single areas should reuse the SAME low vnum
    range the old ones occupied, packed contiguously starting at
    vnum 1 (rather than reserving a genuinely separate new block),
    since the old areas are being purged as part of this same change.

    Idempotent, same check-first pattern as the functions it replaces:
    does nothing if "leaf" is already registered with the new, real
    2500-vnum range. Every OTHER real reservation that used to occupy
    this same low range (legacy-world, legacy-expansions, the 5
    original 100-vnum village blocks, the 5 later expansion blocks)
    is genuinely removed here too, since they'd otherwise overlap the
    new, wider village blocks."""
    import data_villages

    existing = find_area("leaf")
    if existing and existing.vnum_start == 1 and existing.vnum_end == 2500:
        return

    for name in [
        "legacy-world", "legacy-expansions",
        "leaf", "stone", "water", "cloud", "sand",
        "leaf-expansion", "stone-expansion", "water-expansion", "cloud-expansion", "sand-expansion",
    ]:
        remove_area(name)

    for index, village_key in enumerate(data_villages.VILLAGES):
        start = 1 + index * 2500
        try:
            register_area(village_key, start, start + 2499, "system")
        except ValueError:
            pass  # already registered by a concurrent/earlier call this startup
