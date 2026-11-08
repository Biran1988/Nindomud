"""Retire the original village mission mobs without resetting player or world data.

The six legacy bandits and four old rank tiers per village were once the
built-in quest targets. Modern missions use builder-marked Mission mobs instead.
This migration deletes only their 30 reserved mob IDs and their saved spawns.
It never wipes /data or touches unrelated mob, room, object or player records.
"""
LEGACY_BASE_VNUMS = (5001, 5002, 5003, 5004, 5005, 5006)
LEGACY_MOB_VNUMS = frozenset(
    base + offset for base in LEGACY_BASE_VNUMS
    for offset in (0, 100, 200, 300, 400)
)


def is_legacy_mob(vnum):
    return isinstance(vnum, int) and vnum in LEGACY_MOB_VNUMS


def retire_saved_mobs():
    """Remove retired IDs from the *specific* persisted registries that respawn them.

    Existing unrelated data is retained verbatim in each loaded registry,
    and files without retired records are not rewritten. Run after applying
    world and custom-template snapshots but before restoring live spawns.
    """
    import combat
    import storage

    point_state = storage.load_spawn_points()
    points = point_state.get("points", {})
    doomed_points = [
        key for key, point in points.items()
        if point.get("kind") == "mob" and is_legacy_mob(point.get("vnum"))
    ]
    if doomed_points:
        for key in doomed_points:
            del points[key]
        storage.save_spawn_points(point_state)

    template_state = storage.load_custom_templates()
    saved_templates = template_state.get("mobs", {})
    doomed_templates = [key for key in saved_templates if key.isdigit() and is_legacy_mob(int(key))]
    if doomed_templates:
        for key in doomed_templates:
            del saved_templates[key]
        storage.save_custom_templates(template_state)

    world_state = storage.load_world_state()
    saved_mobs = world_state.get("mobs", {})
    doomed_world = [key for key in saved_mobs if key.isdigit() and is_legacy_mob(int(key))]
    if doomed_world:
        for key in doomed_world:
            del saved_mobs[key]
        storage.save_world_state(world_state)

    # Clear any already-present legacy instances (including on in-process
    # content repopulation) and any queued death respawns.
    for vnum in LEGACY_MOB_VNUMS:
        combat.MOB_TEMPLATES.pop(vnum, None)
    for room_vnum, mobs in list(combat.MOBS_BY_ROOM.items()):
        combat.MOBS_BY_ROOM[room_vnum] = [
            mob for mob in mobs if not is_legacy_mob(mob.template_vnum)
        ]
    combat._respawn_queue[:] = [
        row for row in combat._respawn_queue if not is_legacy_mob(row[1])
    ]
    return len(doomed_points), len(doomed_templates), len(doomed_world)
