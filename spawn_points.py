"""
Spawn point registry, per explicit request: "ability to load items and
mobs into a room and assign their there spawn point". Two distinct
capabilities, both handled here:

  - A one-time LOAD: spawn a single instance right now, no persistence
    at all. Mobs already had this ('mset spawn <vnum> <room_vnum>');
    'oset load <vnum>' (commands.cmd_oset_load) adds the equivalent
    for items, placing one onto the room's ground_items.

  - A persistent SPAWN POINT assignment ('spawnpoint add mob/item
    <vnum>', commands.cmd_spawnpoint): registers that a mob/item
    prototype should always exist in a given room, saved to
    spawn_points.json (storage.py, same shape as territory.py), and
    re-applied fresh on every server start via apply_all() (wired into
    content.py's populate(), right after all of content.py's own
    hardcoded static placement).

For MOBS specifically, "always exist" after the initial spawn is
already handled by the existing respawn queue (combat.remove_mob
re-queues a fresh instance at the same room after
config.MOB_RESPAWN_SECONDS, as long as the mob's own respawns flag is
True, which is the default) -- a spawn point just needs to place the
FIRST instance; death-to-death respawning was already automatic and
needed no new code. That mechanism doesn't survive a server restart on
its own (MOBS_BY_ROOM and the respawn queue are both in-memory), which
is exactly the gap apply_all() closes.

ITEMS have no equivalent "comes back after being taken" mechanism at
all (ground_items is a plain list with no respawn logic tied to it).
Deliberately kept simple for this first pass, per the scope actually
asked for: an item spawn point guarantees the item is there on server
start (and via 'oset load' any time staff want one restocked by hand),
not that it silently reappears the moment a player picks it up mid-
session. A restock timer for ground items would be a reasonable
follow-up if it's ever actually wanted, but isn't built here.
"""


def _key(kind: str, vnum: int, room_vnum: int) -> str:
    """Spawn points are keyed by their own (kind, vnum, room_vnum)
    triple rather than a separate generated id -- simpler, and it
    naturally prevents ever registering the exact same spawn point
    twice."""
    return f"{kind}:{vnum}:{room_vnum}"


def _save_template_snapshot(kind: str, vnum: int) -> None:
    """Persists the current template for (kind, vnum) to
    templates.json, per direct request/confirmation (Section 101:
    "make sure setspawn saves during save world so the spawnpoints
    dont disapear on reboot" -> confirmed the real fix is automatic
    persistence, no separate save world step needed). Called from
    add_spawn_point every time a spawn point is registered -- always,
    regardless of whether the template happens to already be one of
    content.py's own built-in ones or a custom one from 'mset
    create'/'oset create', since there's no clean way to distinguish
    the two at runtime, and redundantly saving a built-in template is
    completely harmless: content.py's own registration always runs
    BEFORE restore_custom_templates on the next boot (see that
    function's own docstring), so a built-in template is correctly
    overwritten by the real, current content.py code either way, not
    the possibly-stale saved copy."""
    import combat
    import olc
    import storage

    state = storage.load_custom_templates()
    if kind == "mob":
        template = combat.MOB_TEMPLATES.get(vnum)
        if template is not None:
            state.setdefault("mobs", {})[str(vnum)] = dict(template)
    else:
        template = olc.OBJECT_TEMPLATES.get(vnum)
        if template is not None:
            state.setdefault("items", {})[str(vnum)] = dict(template)
    storage.save_custom_templates(state)


def refresh_template_snapshots() -> int:
    """Refresh every spawn point's saved prototype from the live world.

    ``save world`` calls this so later shop stock, prices, programs, and
    builder edits survive a reboot even when the spawn point was originally
    registered before those edits. Returns the number of unique templates
    refreshed.
    """
    import copy
    import combat
    import olc
    import storage

    state = storage.load_custom_templates()
    refreshed = set()
    for point in list_spawn_points():
        kind, vnum = point["kind"], point["vnum"]
        if (kind, vnum) in refreshed:
            continue
        if kind == "mob" and vnum in combat.MOB_TEMPLATES:
            state.setdefault("mobs", {})[str(vnum)] = copy.deepcopy(combat.MOB_TEMPLATES[vnum])
            refreshed.add((kind, vnum))
        elif kind == "item" and vnum in olc.OBJECT_TEMPLATES:
            state.setdefault("items", {})[str(vnum)] = copy.deepcopy(olc.OBJECT_TEMPLATES[vnum])
            refreshed.add((kind, vnum))
    storage.save_custom_templates(state)
    return len(refreshed)


def restore_custom_templates() -> None:
    """Loads every template ever saved via _save_template_snapshot
    back into combat.MOB_TEMPLATES/olc.OBJECT_TEMPLATES, per direct
    request/confirmation. Must run BEFORE apply_all() -- a spawn
    point's own _spawn_one call silently does nothing if the template
    it needs isn't registered yet (see _spawn_one's own docstring),
    which was the actual root cause of the real bug this whole
    feature fixes: a spawn point survived a restart correctly on its
    own, but the custom template it depended on didn't, so nothing
    ever spawned.

    Spawn-point prototypes are assigned deliberately rather than loaded with
    ``setdefault``: builder-created state is authoritative, and ``save world``
    refreshes these snapshots before shutdown/reboot. This is what preserves
    a shopkeeper's later stock edits instead of reverting to the state from
    the day its spawn point was first created."""
    import combat
    import olc
    import storage

    state = storage.load_custom_templates()
    for vnum_str, template in state.get("mobs", {}).items():
        combat.MOB_TEMPLATES[int(vnum_str)] = template
    for vnum_str, template in state.get("items", {}).items():
        olc.OBJECT_TEMPLATES[int(vnum_str)] = template


def add_spawn_point(kind: str, vnum: int, room_vnum: int) -> str:
    """Registers a persistent spawn point and immediately spawns one
    instance too (per explicit request -- "assign their spawn point"
    implies it takes effect right away, not just on the next server
    restart). Returns "" on success, or a human-readable refusal
    reason (unknown kind, prototype doesn't exist, room doesn't exist,
    already registered)."""
    import combat
    import olc
    import world
    import storage

    if kind not in ("mob", "item"):
        return f"'{kind}' isn't a spawn point kind. Choose one of: mob, item."
    if room_vnum not in world.WORLD.rooms:
        return f"Room {room_vnum} doesn't exist."
    if kind == "mob" and vnum not in combat.MOB_TEMPLATES:
        return f"No mob prototype {vnum} exists."
    if kind == "item" and vnum not in olc.OBJECT_TEMPLATES:
        return f"No item prototype {vnum} exists."

    key = _key(kind, vnum, room_vnum)
    state = storage.load_spawn_points()
    state.setdefault("points", {})
    if key in state["points"]:
        return "That exact spawn point is already registered here."
    state["points"][key] = {"kind": kind, "vnum": vnum, "room_vnum": room_vnum}
    storage.save_spawn_points(state)
    _save_template_snapshot(kind, vnum)

    _spawn_one(kind, vnum, room_vnum)
    return ""


def remove_spawn_point(kind: str, vnum: int, room_vnum: int) -> bool:
    """Unregisters a spawn point. Returns False if no such spawn point
    was registered. Does not remove any already-spawned instance --
    it just stops being re-applied on future server starts; an
    existing mob will still die/respawn-elsewhere normally, an
    existing ground item still sits there until picked up."""
    import storage

    key = _key(kind, vnum, room_vnum)
    state = storage.load_spawn_points()
    if key not in state.get("points", {}):
        return False
    del state["points"][key]
    storage.save_spawn_points(state)
    return True


def remove_all_spawn_points(room_vnum: int) -> int:
    """Removes every real spawn point registered in room_vnum at
    once, per direct request ("add a remove all to spawnpoint").
    Reuses list_spawn_points to find them and remove_spawn_point to
    clear each one, rather than touching storage directly -- same
    real behavior as removing them one at a time (an already-spawned
    instance isn't removed, only the registration that would
    re-place it on a future server start). Returns how many were
    genuinely removed, 0 if the room had none registered at all."""
    points = list_spawn_points(room_vnum)
    removed = 0
    for point in points:
        if remove_spawn_point(point["kind"], point["vnum"], room_vnum):
            removed += 1
    return removed


def set_spawn_caps(kind: str, vnum: int, room_vnum: int, total_cap, per_period_cap) -> str:
    """Sets (or clears, with None) the total/per-period caps on an
    EXISTING spawn point, per direct request ("setspawn vnum 10 2"
    -- 10 total, 2 per respawn period), later merged into 'spawnpoint
    cap' as one subcommand instead of its own top-level command
    (Section 152). The spawn point itself must already be registered
    via 'spawnpoint add' (or this same command registers one on the
    fly if it doesn't exist yet -- see cmd_spawnpoint's own real
    "cap" branch). Returns "" on success, or a human-readable refusal
    reason if no matching spawn point exists."""
    import storage

    key = _key(kind, vnum, room_vnum)
    state = storage.load_spawn_points()
    if key not in state.get("points", {}):
        return "No matching spawn point registered here."
    state["points"][key]["total_cap"] = total_cap
    state["points"][key]["per_period_cap"] = per_period_cap
    storage.save_spawn_points(state)
    return ""


def get_spawn_caps(kind: str, vnum: int, room_vnum: int):
    """Returns (total_cap, per_period_cap) for a spawn point, each
    None if uncapped or the spawn point doesn't exist at all."""
    import storage

    key = _key(kind, vnum, room_vnum)
    entry = storage.load_spawn_points().get("points", {}).get(key, {})
    return entry.get("total_cap"), entry.get("per_period_cap")



def list_spawn_points(room_vnum: int = None) -> list:
    """Every registered spawn point, optionally filtered to one room.
    Each entry is {"kind", "vnum", "room_vnum"}."""
    import storage

    points = list(storage.load_spawn_points().get("points", {}).values())
    if room_vnum is not None:
        points = [p for p in points if p["room_vnum"] == room_vnum]
    return points


def _spawn_one(kind: str, vnum: int, room_vnum: int) -> None:
    """Actually places one instance -- a real mob for "mob", or the
    item's display name appended to the room's ground_items for
    "item". Silently does nothing if the prototype has since been
    removed (matches how content.py's own static placement already
    tolerates a since-deleted template) or the room no longer exists.

    Deliberately unconditional otherwise -- "already present" checks
    belong at the CALLER, not here, since a capped spawn point's own
    respawn_missing_mobs_in_area loop genuinely needs to call this
    several times in a row on purpose to reach its own population
    cap; putting a presence check in here would silently refuse every
    call after the first (a real regression caught during Section
    102's conversion of content.py's own hardcoded spawns to real
    spawn points, before it shipped)."""
    import combat
    import olc
    import world

    room = world.WORLD.get(room_vnum)
    if room is None:
        return
    if kind == "mob":
        if vnum in combat.MOB_TEMPLATES:
            combat.spawn_mob(vnum, room_vnum)
    elif kind == "item":
        proto = olc.OBJECT_TEMPLATES.get(vnum)
        if proto:
            room.ground_items.append(proto["short_desc"])


def respawn_missing_mobs_in_area(area) -> int:
    """Sweeps every registered MOB spawn point (kind == "mob") whose
    room falls within the given areas.Area's vnum range, and spawns
    fresh instances of any that have room to grow -- per direct
    follow-up request ("attach area reset to mobs spawns so when
    area reset message sends the mobs in that area spawn if the mob
    isnt already in the room"), extended by a later follow-up
    ("setspawn vnum 10 2" -- 10 total allowed across the area, only
    2 new ones per sweep) to support real population caps instead of
    a plain presence check. Deliberately mob-only, matching the
    original request's own wording; item spawn points have no
    comparable "missing" concept to check against (see this module's
    own docstring on ground_items having no restock timer at all, by
    design). Reuses _spawn_one -- the same function apply_all already
    uses for server-restart recovery -- rather than duplicating the
    actual spawn logic.

    For an UNCAPPED spawn point (total_cap/per_period_cap both None,
    the default for anything registered before setspawn existed),
    behavior is unchanged from before this feature: spawn exactly one
    if none currently exist anywhere in the area, otherwise do
    nothing. For a CAPPED one, spawns min(per_period_cap, total_cap -
    current_count) new instances -- never exceeding the total cap,
    never spawning more than per_period_cap in a single sweep, and
    genuinely zero if the area's already at its total cap. Returns
    how many mobs were actually respawned across every spawn point
    swept, for a caller that wants to know (or narrate) whether
    anything happened."""
    import combat

    respawned = 0
    # Cache each mob vnum's area-wide COUNT once per sweep (not just a
    # present/absent boolean, since a capped spawn point needs the
    # real number to know how much headroom is left under its total
    # cap), rather than rescanning the whole area separately for every
    # spawn point sharing the same vnum.
    count_cache: dict = {}

    def count_present_in_area(vnum: int) -> int:
        if vnum not in count_cache:
            count_cache[vnum] = sum(
                sum(1 for m in mobs if m.template_vnum == vnum)
                for room_vnum_in_area, mobs in combat.MOBS_BY_ROOM.items()
                if area.vnum_start <= room_vnum_in_area <= area.vnum_end
            )
        return count_cache[vnum]

    for point in list_spawn_points():
        if point["kind"] != "mob":
            continue
        if not (area.vnum_start <= point["room_vnum"] <= area.vnum_end):
            continue
        vnum = point["vnum"]
        room_vnum = point["room_vnum"]
        total_cap = point.get("total_cap")
        per_period_cap = point.get("per_period_cap")

        # Check the WHOLE area for this mob, not just its own spawn
        # room -- a Wander-flagged mob may have drifted elsewhere
        # within the area since it spawned, and is still very much
        # "present" even though it's no longer standing where it
        # started. Checking only the spawn room would otherwise spawn
        # a duplicate right on top of a mob that simply wandered off.
        current_count = count_present_in_area(vnum)

        if total_cap is None and per_period_cap is None:
            # Uncapped -- exact original behavior, unchanged.
            if current_count > 0:
                continue
            _spawn_one("mob", vnum, room_vnum)
            count_cache[vnum] = current_count + 1
            respawned += 1
            continue

        # Capped: figure out how many we're actually allowed to add.
        room_left_under_total = (total_cap - current_count) if total_cap is not None else float("inf")
        to_spawn = min(per_period_cap if per_period_cap is not None else float("inf"), room_left_under_total)
        to_spawn = max(0, int(to_spawn)) if to_spawn != float("inf") else 0
        for _ in range(to_spawn):
            _spawn_one("mob", vnum, room_vnum)
            respawned += 1
        count_cache[vnum] = current_count + to_spawn
    return respawned


def reload_room(room_vnum: int) -> dict:
    """Spawns back any mob or item spawn point registered in
    room_vnum that's genuinely missing right now, per direct
    request/confirmation ("add a command reload that reloads all
    items and mobs set to spawn in that room" -> confirmed items get
    the same real "only spawn what's missing" check mobs already have
    via respawn_missing_mobs_in_area, a deliberate extension since the
    existing area-reset logic was mob-only by design). Unlike that
    area-wide sweep, this is genuinely scoped to ONE room -- a mob
    that wandered off to an adjacent room still counts as "missing"
    here, matching the confirmed scope of the command itself (this
    room's own spawn points, not the whole area).

    Mob presence is checked by template_vnum among mobs currently
    standing in this exact room (combat.mobs_in_room). Item presence
    is checked by matching the item's own display name against
    room.ground_items, since that list stores names, not vnums --
    genuinely all ground_items has ever stored.

    Returns {"mobs": <count spawned>, "items": <count spawned>}, for
    the caller to report exactly what happened."""
    import combat
    import olc
    import world

    room = world.WORLD.get(room_vnum)
    if room is None:
        return {"mobs": 0, "items": 0}

    present_mob_vnums = {m.template_vnum for m in combat.mobs_in_room(room_vnum)}
    spawned_mobs = 0
    spawned_items = 0

    for point in list_spawn_points(room_vnum):
        vnum = point["vnum"]
        if point["kind"] == "mob":
            if vnum in present_mob_vnums:
                continue
            _spawn_one("mob", vnum, room_vnum)
            present_mob_vnums.add(vnum)
            spawned_mobs += 1
        else:
            proto = olc.OBJECT_TEMPLATES.get(vnum)
            if not proto:
                continue
            if proto["short_desc"] in room.ground_items:
                continue
            _spawn_one("item", vnum, room_vnum)
            spawned_items += 1

    return {"mobs": spawned_mobs, "items": spawned_items}


def apply_all() -> None:
    """Called once from content.py's populate(), right after all of
    content.py's own hardcoded static placement -- spawns one fresh
    instance for every registered spawn point that doesn't already
    have one present. This is what makes a spawn point survive a
    server restart: MOBS_BY_ROOM and ground_items are both purely
    in-memory, so without this, every staff-assigned spawn point
    would silently vanish the moment the server restarted, even
    though it's still sitting in spawn_points.json.

    The "already present" check for mobs is a real, genuine fix
    (caught by direct testing during Section 102's conversion of
    every hardcoded content.py spawn to a real spawn point): without
    it, a spawn point registered via add_spawn_point during THIS SAME
    content.populate() call -- which already spawns one instance
    immediately, per its own docstring -- would get a second,
    duplicate instance the moment apply_all() ran right after it,
    every single time the server started, not just on a genuine
    restart. A true reboot starts with MOBS_BY_ROOM completely empty
    regardless, so this check is a pure no-op difference in that
    case -- it only matters for the same-process, same-populate()-call
    scenario. Items have no comparable check, matching this module's
    own long-established, deliberate design (ground items have no
    "already present" concept at all)."""
    import combat

    for point in list_spawn_points():
        if point["kind"] == "mob":
            if any(m.template_vnum == point["vnum"] for m in combat.mobs_in_room(point["room_vnum"])):
                continue
        _spawn_one(point["kind"], point["vnum"], point["room_vnum"])
