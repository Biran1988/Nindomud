"""
World persistence -- 'save world' (Section 77), per direct request
("how do we make it so when you package up the newest version it
does not effect area files ever again so i can start 'building' the
mud").

The real problem this solves: every room, mob prototype, and item
prototype in the entire game is built purely in memory by
content.py's own populate() function, called fresh on every single
server start. There has never been any separate persistence layer
for world data at all -- anything created in-game via 'rset create'/
'oset create'/'mset create' (or edited on an existing one) only ever
lived in memory, so it was silently discarded the moment the server
restarted, whether that restart came from a crash, a reboot, or
deploying a newly packaged version of the code. Player accounts and
characters were always saved properly (storage.py's save_player/
save_account) -- it was specifically the WORLD itself that had no
persistence at all.

Three design decisions were confirmed directly rather than assumed,
each a real fork with a meaningfully different outcome:

1. A FULL snapshot, not just new additions -- 'save world' captures
   the CURRENT STATE of every room/mob/item live in memory at the
   moment it's run, built-in content.py content and player-built
   content alike, not just what's new since the code was last
   deployed. This is the safest option: it means a future content.py
   change can never silently alter something already saved (even a
   room that originally came from content.py itself), at the cost of
   a future genuine content.py improvement to an untouched area not
   taking effect until that area is explicitly re-saved or reset.

2. Saved data always WINS on restart -- applied in content.populate()
   strictly AFTER every one of content.py's own hardcoded rooms/mobs/
   items are registered, so a saved room/mob/item vnum always
   overwrites whatever content.py would have built at that same
   vnum, never the other way around.

3. MANUAL save, not automatic -- a real 'save world' command a staff
   member runs when ready, not an autosave firing on every single
   edit. Matches the classic ROM-style 'asave'/'osave' convention
   this whole project is deliberately modeled on, and avoids writing
   to disk constantly while actively mid-build.

Registered as world_state.json (storage.save_world_state/
load_world_state) -- a single flat file holding every room, mob
template, and item template as plain, directly JSON-serializable
data (Room is a dataclass -> dataclasses.asdict(); MOB_TEMPLATES/
OBJECT_TEMPLATES are already plain dicts, no conversion needed at
all). Deliberately NOT split per-area or per-file -- the user has
separately asked for that as a future improvement (see README), but
that's an organizational nicety on top of this, not a prerequisite
for solving the actual problem here.
"""

import dataclasses


def snapshot_world() -> dict:
    """Builds the full save payload from whatever's CURRENTLY live in
    memory -- every room in world.WORLD.rooms, every mob prototype in
    combat.MOB_TEMPLATES, every item prototype in olc.OBJECT_TEMPLATES.
    Deliberately snapshots PROTOTYPES only, never live spawned mob
    instances (those are transient combat state -- health, position,
    an active fight -- and were never meant to persist; only the
    TEMPLATE a fresh instance gets spawned from matters here, the same
    prototype/instance split combat.py already draws everywhere else)."""
    import world
    import combat
    import olc

    return {
        "rooms": {
            str(vnum): dataclasses.asdict(room)
            for vnum, room in world.WORLD.rooms.items()
        },
        "mobs": {
            str(vnum): dict(template)
            for vnum, template in combat.MOB_TEMPLATES.items()
        },
        "items": {
            str(vnum): dict(template)
            for vnum, template in olc.OBJECT_TEMPLATES.items()
        },
    }


def apply_saved_world() -> int:
    """Loads the saved snapshot (if one exists at all -- a brand new
    install with nothing ever saved is a normal, expected case, not
    an error) and applies it on top of whatever content.py's own
    populate() has already built. Called strictly LAST from
    content.populate(), after every hardcoded room/mob/item already
    exists AND after spawn_points.apply_all() has already registered
    and spawned everything a builder has set up.

    ROOMS and every ORDINARY mob/item template (content.py's own
    built-ins, or an existing one edited via mset/oset): a saved
    vnum always overwrites what's already there -- confirmed design
    ("the saved snapshot always wins over what content.py would
    normally build"), unchanged from the original behavior.

    Per direct confirmation (Section 159 -- a real, live bug report:
    "is spawnpoint cap overiding spawnpoint set in save world making
    the spawn disapear in reboot"), the ONE real exception: a mob/
    item template specifically registered via a real spawn point
    (tracked in templates.json -- see spawn_points.
    _save_template_snapshot, the exact, existing, real marker of
    which vnums came from 'spawnpoint add') is never overwritten
    here, even if an OLDER 'save world' snapshot also happens to
    contain that same vnum. The real, confirmed root cause this
    fixes: a 'save world' snapshot captures templates at ONE moment
    in time; any spawn point added or edited AFTER that snapshot was
    taken would still get correctly registered and spawned on a
    fresh boot by spawn_points.apply_all() (which runs first), only
    for THIS function -- which ran last, straight after, and
    originally used direct overwrite for everything -- to then
    silently clobber that newer, correct template with the older,
    stale one saved before, on every single future reboot. An
    earlier attempt at this fix used a blanket "skip if the vnum
    already exists" check instead, which incorrectly ALSO protected
    content.py's own built-in templates and broke the legitimate case
    of 'save world' restoring a genuine mset/oset edit to an existing
    mob/item -- corrected here to check the real, specific spawn-
    point marker instead of a generic existence check.

    Returns how many total rooms/mobs/items were restored, for a
    caller that wants to report it (e.g. a startup log line)."""
    import storage
    import world
    import combat
    import olc

    state = storage.load_world_state()
    if not state:
        return 0

    custom_templates = storage.load_custom_templates()
    spawn_point_mob_vnums = {int(v) for v in custom_templates.get("mobs", {})}
    spawn_point_item_vnums = {int(v) for v in custom_templates.get("items", {})}

    import dataclasses
    valid_room_fields = {f.name for f in dataclasses.fields(world.Room)}
    restored = 0
    for vnum_str, room_data in state.get("rooms", {}).items():
        vnum = int(vnum_str)
        filtered = {k: v for k, v in room_data.items() if k in valid_room_fields}
        world.WORLD.rooms[vnum] = world.Room(**filtered)
        restored += 1

    for vnum_str, mob_data in state.get("mobs", {}).items():
        vnum = int(vnum_str)
        if vnum in spawn_point_mob_vnums:
            continue
        combat.MOB_TEMPLATES[vnum] = mob_data
        restored += 1

    for vnum_str, item_data in state.get("items", {}).items():
        vnum = int(vnum_str)
        if vnum in spawn_point_item_vnums:
            continue
        olc.OBJECT_TEMPLATES[vnum] = item_data
        restored += 1

    return restored


def save_world() -> dict:
    """Writes the current live world state to disk, per the 'save
    world' staff command -- everything currently in memory becomes
    what gets restored on every future restart from here on, until
    the next 'save world'. Returns the same counts snapshot_world's
    payload holds, so the caller can report exactly how much was
    saved (e.g. "Saved 214 rooms, 58 mobs, 130 items.")."""
    import spawn_points
    import storage

    payload = snapshot_world()
    storage.save_world_state(payload)
    # A shopkeeper/item can be edited after its spawn point was created.
    # Refresh those durable template copies at the same moment as the world
    # snapshot so stock, prices, programs, and other builder changes cannot
    # roll back on the next reboot.
    spawn_points.refresh_template_snapshots()
    return {
        "rooms": len(payload["rooms"]),
        "mobs": len(payload["mobs"]),
        "items": len(payload["items"]),
    }
