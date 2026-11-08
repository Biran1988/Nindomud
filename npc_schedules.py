"""Timed shopkeepers and gate guards driven by the shared shinobi world clock.

All schedules live on the existing persisted mob prototypes. Existing mobs
are 24-hour by default. Gate changes use the established reciprocal-door
mirror and do not add or modify any saved /data files directly.
"""
import weather


def within_hours(open_hour, close_hour, hour=None):
    """Inclusive opening time, exclusive closing time, including overnight."""
    if not (isinstance(open_hour, int) and isinstance(close_hour, int)
            and 0 <= open_hour <= 23 and 0 <= close_hour <= 23):
        return True
    hour = weather.game_hour() if hour is None else hour
    if open_hour == close_hour:
        return True  # explicit 24-hour schedule
    if open_hour < close_hour:
        return open_hour <= hour < close_hour
    return hour >= open_hour or hour < close_hour


def shop_is_open(mob, hour=None):
    """Player-owned shops keep their existing 24/7 behavior."""
    if getattr(mob, "player_shop_owner", None):
        return True
    import combat
    proto = combat.MOB_TEMPLATES.get(getattr(mob, "template_vnum", None), {})
    return within_hours(proto.get("shop_open_hour", -1),
                        proto.get("shop_close_hour", -1), hour)


def shop_closed_message(mob):
    import combat
    proto = combat.MOB_TEMPLATES.get(getattr(mob, "template_vnum", None), {})
    opening = proto.get("shop_open_hour", -1)
    closing = proto.get("shop_close_hour", -1)
    return (f"{mob.name.capitalize()} is closed. "
            f"Business hours: {hour_label(opening)} to {hour_label(closing)}.")


def hour_label(hour):
    if not isinstance(hour, int) or not 0 <= hour <= 23:
        return "any time"
    return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"


def _gate_templates():
    import combat
    for vnum, proto in combat.MOB_TEMPLATES.items():
        if (proto.get("enabled", True) and
            isinstance(proto.get("gate_room_vnum"), int)
            and proto.get("gate_direction")):
            yield vnum, proto


def _guard_present(template_vnum, room_vnum):
    import combat
    return any(mob.template_vnum == template_vnum
               for mob in combat.mobs_in_room(room_vnum))


def gate_scheduled_closed(room, direction, hour=None):
    """Block manual reopening while a scheduled guard is on duty."""
    import door_links
    hour = weather.game_hour() if hour is None else hour
    for vnum, proto in _gate_templates():
        origin = proto["gate_room_vnum"]
        facing = proto["gate_direction"]
        guard_room = __import__("world").WORLD.get(origin)
        if not guard_room or facing not in guard_room.exits:
            continue
        other, reverse = door_links.reciprocal(guard_room, facing)
        is_this_side = room.vnum == origin and direction == facing
        is_other_side = other is not None and room.vnum == other.vnum and direction == reverse
        if (is_this_side or is_other_side) and _guard_present(vnum, origin):
            if not within_hours(proto.get("gate_open_hour", 6),
                                proto.get("gate_close_hour", 18), hour):
                return True
    return False


def apply_all(*, announce=False, hour=None):
    """Reconcile all active gate guards; idempotent and safe each pulse."""
    import combat
    import door_links
    import world

    hour = weather.game_hour() if hour is None else hour
    updates = 0
    for vnum, proto in _gate_templates():
        room = world.WORLD.get(proto["gate_room_vnum"])
        direction = proto["gate_direction"]
        if (room is None or direction not in room.exits
                or "door" not in room.exit_flags.get(direction, ())
                or not _guard_present(vnum, room.vnum)):
            continue
        should_open = within_hours(proto.get("gate_open_hour", 6),
                                   proto.get("gate_close_hour", 18), hour)
        if room.exit_door_open.get(direction, False) == should_open:
            continue
        room.exit_door_open[direction] = should_open
        door_links.mirror(room, direction)
        updates += 1
        if announce:
            import session
            other, _ = door_links.reciprocal(room, direction)
            watched = {room.vnum}
            if other is not None:
                watched.add(other.vnum)
            verb = "opens" if should_open else "closes"
            message = f"&YThe gate guard {verb} the gate as the world clock strikes {weather.formatted_time()}.&x"
            for observer in list(session.ACTIVE_SESSIONS):
                if (getattr(observer, "player", None) and
                        observer.player.room_vnum in watched and
                        getattr(getattr(observer, "state", None), "name", "") == "PLAYING"):
                    observer.send(message)
                    observer.send_prompt()
    return updates
