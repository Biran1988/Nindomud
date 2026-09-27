"""Water Release: Hidden Mist Jutsu's room-bound combat concealment."""

import time

import data_jutsu
import derived_stats
import world


JUTSU_KEY = "hidden mist jutsu"
DEFENSE_PENALTY = 15  # points added to the caster's hit chance, removed from target dodge
MIST_DURATION_SECONDS = 12.0


def room_active(room) -> bool:
    return bool(room and getattr(room, "hidden_mist_caster", None)
                and getattr(room, "hidden_mist_expires_at", 0) > time.time())


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
    if active(player):
        session.send("Your mist already fills this room.")
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
    player.chakra -= cost
    player.cooldowns[JUTSU_KEY] = now + jutsu["cooldown"]
    room.hidden_mist_caster = player.name
    room.hidden_mist_expires_at = now + MIST_DURATION_SECONDS
    session.send("&CA thick mist spreads through the room. Enemies lose sight of you; their defenses open to your attacks.&x")
    session.broadcast_room(f"&CThick mist rolls across the room around {player.name}.&x", exclude_self=True)
    combat.grow_skill_from_usage(player, jutsu["display_name"])
    return True


def process_rooms(sessions) -> None:
    """Clear expired room mist and tell occupants when visibility returns."""
    for room in world.WORLD.rooms.values():
        if room.hidden_mist_caster and not room_active(room):
            room.hidden_mist_caster = None
            room.hidden_mist_expires_at = 0.0
            for session in sessions:
                if session.player and session.player.room_vnum == room.vnum:
                    session.send("&CThe hidden mist thins and the room comes back into view.&x")
