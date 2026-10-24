"""Water Release: Hidden Mist Jutsu's room-bound combat concealment."""

import time

import data_jutsu
import derived_stats
import world


JUTSU_KEY = "hidden mist jutsu"
DEFENSE_PENALTY = 15  # points added to the caster's hit chance, removed from target dodge
UPKEEP_CHAKRA = 1
UPKEEP_SECONDS = 5.0


def room_active(room) -> bool:
    return bool(room and getattr(room, "hidden_mist_caster", None)
                and (getattr(room, "hidden_mist_toggled", False)
                     or getattr(room, "hidden_mist_expires_at", 0) > time.time()))


def owned_room(player):
    return next((room for room in world.WORLD.rooms.values()
                 if room.hidden_mist_caster == player.name and room_active(room)), None)


def _clear(room, sessions):
    import upkeep_reports
    for owner in sessions:
        if owner.player and owner.player.name == room.hidden_mist_caster:
            upkeep_reports.stop_maintaining(owner.player, "Hidden Mist Jutsu")
    room.hidden_mist_caster = None
    room.hidden_mist_expires_at = 0.0
    room.hidden_mist_toggled = False
    room.hidden_mist_next_upkeep_at = 0.0
    for observer in sessions:
        if observer.player and observer.player.room_vnum == room.vnum:
            observer.send("&CThe hidden mist thins and the room comes back into view.&x")


def dismiss(session):
    import session as sessions
    ended = False
    pending = getattr(session, "pending_cast", None)
    if pending and pending.jutsu_key == JUTSU_KEY:
        session.pending_cast = None
        ended = True
    for room in world.WORLD.rooms.values():
        if room.hidden_mist_caster == session.player.name:
            _clear(room, sessions.ACTIVE_SESSIONS)
            ended = True
    session.send("Hidden Mist Jutsu is OFF." if ended else "Your Hidden Mist Jutsu is already off.")


def active(player) -> bool:
    room = world.WORLD.get(player.room_vnum)
    return bool(getattr(player, "health", 1) > 0 and room_active(room)
                and room.hidden_mist_caster == player.name)


def obscures(attacker, target) -> bool:
    """A caster cannot be selected by anyone else in the same room."""
    return (attacker is not target and active(target)
            and attacker.room_vnum == target.room_vnum)


def conceals_from_view(viewer, target) -> bool:
    """The room's mist also hides its caster from adjacent scans."""
    return viewer is not target and active(target)


def advantage(attacker, target) -> int:
    return DEFENSE_PENALTY if active(attacker) and attacker.room_vnum == target.room_vnum else 0


def cast(session) -> bool:
    import combat
    player = session.player
    jutsu = data_jutsu.JUTSU[JUTSU_KEY]
    if not combat._can_use_jutsu(player, jutsu, JUTSU_KEY):
        session.send("You have not learned Hidden Mist Jutsu or lack the water element.")
        return False
    if combat._is_action_blocked(player) or "silenced" in player.active_status_effects:
        session.send("You cannot form the mist right now.")
        return False
    if owned_room(player):
        session.send("You already maintain hidden mist. Use 'perform hidden mist jutsu off' to release it.")
        return False
    now = time.time()
    if now < player.cooldowns.get(JUTSU_KEY, 0):
        session.send(f"Hidden Mist Jutsu is still recovering ({player.cooldowns[JUTSU_KEY] - now:.1f}s).")
        return False
    cost = round(jutsu["chakra_cost"] * (100 - derived_stats.chakra_control_cost_discount_percent(player.chakra_control)) / 100)
    if player.chakra < cost:
        session.send("You don't have enough chakra.")
        return False
    room = world.WORLD.get(player.room_vnum)
    if room is None:
        session.send("There is nowhere for the mist to gather.")
        return False
    if room_active(room):
        session.send("Another ninja's mist already fills this room.")
        return False
    player.chakra -= cost
    player.cooldowns[JUTSU_KEY] = now + jutsu["cooldown"]
    room.hidden_mist_caster = player.name
    room.hidden_mist_expires_at = 0.0
    room.hidden_mist_toggled = True
    room.hidden_mist_next_upkeep_at = now + UPKEEP_SECONDS
    session.send("&CHidden Mist Jutsu is ON. A thick mist spreads through this room; maintain it for 1 Chakra every 5 seconds. Toggle it off to release it.&x")
    session.broadcast_room(f"&CThick mist rolls across the room around {player.name}.&x", exclude_self=True)
    combat.grow_skill_from_usage(player, jutsu["display_name"], session=session)
    import upkeep_reports
    upkeep_reports.stop_maintaining(player, jutsu["display_name"])
    upkeep_reports.maintain_skill(player, jutsu["display_name"], session=session)
    return True


def process_rooms(sessions) -> None:
    """Bill the connected owner for maintained room mist, including from afar."""
    now = time.time()
    for room in world.WORLD.rooms.values():
        if not room.hidden_mist_caster:
            continue
        owner = next((s for s in sessions if s.player and s.player.name == room.hidden_mist_caster
                      and getattr(getattr(s, "state", None), "name", "PLAYING") != "CLOSED"), None)
        if not owner or owner.player.health <= 0 or owner.player.reaper_seal_id:
            _clear(room, sessions)
            continue
        if not room.hidden_mist_toggled:
            if not room_active(room):
                _clear(room, sessions)
                continue
            room.hidden_mist_toggled = True
            room.hidden_mist_expires_at = 0.0
            room.hidden_mist_next_upkeep_at = now + UPKEEP_SECONDS
        if now < room.hidden_mist_next_upkeep_at:
            continue
        if owner.player.chakra < UPKEEP_CHAKRA:
            owner.send("&YYou lack the Chakra to maintain Hidden Mist Jutsu; the mist fades.&x")
            _clear(room, sessions)
            continue
        owner.player.chakra -= UPKEEP_CHAKRA
        room.hidden_mist_next_upkeep_at = now + UPKEEP_SECONDS
        import upkeep_reports
        upkeep_reports.maintain_skill(owner.player, "Hidden Mist Jutsu", session=owner)
