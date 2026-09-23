"""Live administrative actions; never writes saved world or area data."""


def restore_online():
    import session
    count = 0
    seen = set()
    for connection in list(session.ACTIVE_SESSIONS):
        player = connection.player
        if player is None or connection.state == session.State.CLOSED:
            continue
        if id(player) in seen:
            continue
        seen.add(id(player))
        player.health = player.maximum_health
        player.chakra = player.maximum_chakra
        player.stamina = player.maximum_stamina
        connection.send("&GYour HP, chakra, and stamina have been fully restored.&x")
        if connection.state == session.State.PLAYING:
            connection.send_prompt()
        count += 1
    return count


def respawn_missing():
    """Fill configured populations immediately; count wanderers within their area.

    Manual refill honors total caps but bypasses per-period limits. Uncapped
    populations mean one per template/area, matching normal area resets.
    Rooms outside registered areas use their own room as the population scope.
    Pending timer spawns are also handled; unused prototypes are never spawned.
    """
    import areas
    import combat
    import spawn_points
    import world

    registry = list(areas.all_areas().values())

    def scope(room):
        for area in registry:
            if area["vnum_start"] <= room <= area["vnum_end"]:
                return area["vnum_start"], area["vnum_end"]
        return room, room

    targets = {}
    for point in spawn_points.list_spawn_points():
        if point["kind"] != "mob":
            continue
        room, vnum = point["room_vnum"], point["vnum"]
        if world.WORLD.get(room) is None:
            continue
        key = (vnum, scope(room))
        cap = point.get("total_cap")
        desired = max(0, int(cap)) if cap is not None else 1
        previous = targets.get(key)
        if previous is None or desired > previous[1]:
            targets[key] = (room, desired)

    for _, vnum, room in combat._respawn_queue:
        if world.WORLD.get(room) is not None:
            targets.setdefault((vnum, scope(room)), (room, 1))

    spawned = 0
    handled = set()
    for (vnum, bounds), (room, desired) in targets.items():
        template = combat.MOB_TEMPLATES.get(vnum)
        if not template or not template.get("enabled", True):
            continue
        current = sum(
            1 for location, mobs in combat.MOBS_BY_ROOM.items()
            if bounds[0] <= location <= bounds[1]
            for mob in mobs if mob.template_vnum == vnum
        )
        for _ in range(max(0, desired - current)):
            mob = combat.spawn_mob(vnum, room)
            if mob is not None:
                spawned += 1
        handled.add((vnum, bounds))

    # Remove satisfied timers so they cannot spawn duplicates on the next pulse.
    combat._respawn_queue[:] = [
        entry for entry in combat._respawn_queue
        if (entry[1], scope(entry[2])) not in handled
    ]
    return spawned
