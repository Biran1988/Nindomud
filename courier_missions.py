"""Courier delivery missions: carry a mission-bound parcel to a live NPC.

All ownership and destination metadata are saved in Player.active_missions;
the unique parcel itself is carried in ordinary inventory. The server never
adds props to /data/world and never creates arbitrary recipient mobs.
"""
import random
import time
import uuid

PARCEL_PREFIX = "A Sealed Courier Parcel:"
VILLAGER_IDS = {
    "whirlpool": 6055, "leaf": 6005, "stone": 6015,
    "water": 6025, "cloud": 6035, "sand": 6045,
}
CONTENTS = (
    "Confidential Shinobi Orders",
    "Emergency Medical Supplies",
    "Sealed Intelligence Report",
    "Academy Examination Papers",
    "Village Supply Records",
    "Urgent Hokage Correspondence",
    "Replacement Chakra Paper",
    "A Carefully Wrapped Bento Box",
)


def is_parcel(item):
    return (isinstance(item, str)
            and item.casefold().startswith(PARCEL_PREFIX.casefold())
            and " [courier:" in item.casefold() and item.endswith("]"))


def cleanup(player, mission):
    """Strip only this mission's own exact parcel, never another cargo."""
    if not mission or mission.get("mission_type") != "courier":
        return
    parcel = mission.get("quest_item_name")
    if parcel:
        player.inventory[:] = [item for item in player.inventory if item != parcel]


def _reachable_from(start):
    import world
    rooms = world.WORLD
    seen = {start}
    queue = [start]
    for current in queue:
        room = rooms.get(current)
        if room is None or not room.enabled:
            continue
        for target in room.exits.values():
            if isinstance(target, int) and target not in seen:
                dest = rooms.get(target)
                if dest is not None and dest.enabled:
                    seen.add(target)
                    queue.append(target)
    return seen


def _recipients(player, rank):
    """Choose only currently spawned, reachable, noncombat village villagers."""
    import combat
    import world
    allowed = set(VILLAGER_IDS.values())
    reachable = _reachable_from(player.room_vnum)
    candidates = []
    for vnum in sorted(reachable):
        room = world.WORLD.get(vnum)
        if room is None or room.player_shop or room.apartment:
            continue
        for mob in combat.mobs_in_room(vnum):
            if mob.template_vnum in allowed and mob.health > 0:
                village = next((k for k, template in VILLAGER_IDS.items()
                                if template == mob.template_vnum), None)
                if village:
                    candidates.append((mob, vnum, room, village))
    # Some worlds have builder-placed shops and trainers but no village
    # villager spawn points. Fall back to other stationary, peaceful NPCs,
    # never a fightable mission mob, garrison, trap or player-owned shop.
    if not candidates:
        for vnum in sorted(reachable):
            room = world.WORLD.get(vnum)
            if room is None or room.player_shop or room.apartment:
                continue
            for mob in combat.mobs_in_room(vnum):
                template = combat.MOB_TEMPLATES.get(mob.template_vnum, {})
                flags = {str(flag).casefold() for flag in template.get("act_flags", ())}
                if (mob.health <= 0 or getattr(mob, "player_shop_owner", None)
                        or "sentinel" not in flags
                        or flags.intersection({"mission", "garrison", "trap", "wander"})
                        or template.get("level", 1) > 10):
                    continue
                candidates.append((mob, vnum, room, "shinobi world"))
    if rank == "D-Rank":
        preferred = [c for c in candidates if c[3] == player.village]
    else:
        preferred = [c for c in candidates if c[3] != player.village]
    return preferred or candidates


def request(player, rank, definition):
    """Create one parcel-and-recipient mission for any D-S difficulty."""
    import missions
    import inventory
    _, _, min_level, _count, reward_xp, reward_ryo, reward_mp, cooldown = definition
    if player.level < min_level:
        return f"You must be at least level {min_level} for a {rank} delivery mission."
    key = "courier_" + rank
    remaining = missions.cooldown_remaining(player, key)
    if remaining:
        return f"Delivery missions are on cooldown for {missions._format_duration(remaining)}."
    if any((missions._resolve_mission(entry) or {}).get("mission_type") == "courier"
           and (missions._resolve_mission(entry) or {}).get("rank") == rank
           for entry in player.active_missions):
        return f"You already have an active {rank} courier mission."
    candidates = _recipients(player, rank)
    if not candidates:
        return "No reachable village courier recipient is currently present; try again when the village NPCs have spawned."
    mob, vnum, room, village = random.choice(candidates)
    nonce = uuid.uuid4().hex
    mission_id = f"dynamic_{rank}_courier_{nonce}"
    cargo = random.choice(CONTENTS)
    parcel = f"{PARCEL_PREFIX} {cargo} [courier:{nonce}]"
    ok, reason = inventory.add_item(player.inventory, parcel)
    if not ok:
        return "You need room in your inventory for the sealed parcel before accepting a delivery mission."
    mission = {
        "mission_id": mission_id, "rank": rank, "mission_type": "courier",
        "title": "Courier: " + cargo,
        "description": f"Deliver the sealed parcel to {mob.name} in {room.name} ({village.title()}).",
        "quest_item_name": parcel, "quest_owner": player.name,
        "delivery_mob_template": mob.template_vnum,
        "delivery_room_vnum": vnum, "delivery_room_name": room.name,
        "delivery_mob_name": mob.name, "target_count": 1,
        "reward_xp": reward_xp, "reward_ryo": reward_ryo,
        "reward_mission_points": reward_mp, "cooldown_seconds": cooldown,
    }
    now = time.time()
    player.active_missions.append({
        "mission_id": mission_id, "progress": 0, "dynamic": mission,
        "expires_at": now + missions.MISSION_DURATION_SECONDS,
    })
    player.mission_cooldowns[key] = now + cooldown
    return (f"Mission requested: {mission['title']} ({rank}). "
            f"You receive {parcel}. {mission['description']} "
            "Use 'deliver' beside the recipient or 'give parcel <npc>'. "
            "You have 30 minutes.")


def try_deliver(session, target_query=""):
    """Return True if a carried mission parcel was handled.

    A mission only rewards its exact owner, exact parcel and correct
    live NPC template at the original assigned destination.
    """
    import combat
    import missions
    import storage

    player = session.player
    if not any(is_parcel(item) for item in player.inventory):
        return False
    candidates = []
    for entry in player.active_missions:
        mission = missions._resolve_mission(entry)
        if (mission and mission.get("mission_type") == "courier"
                and mission.get("quest_owner", "").casefold() == player.name.casefold()
                and mission.get("quest_item_name") in player.inventory):
            candidates.append((entry, mission))
    if not candidates:
        session.send("This parcel no longer has a valid active courier mission.")
        return True
    # Handle expired deliveries before accepting any handover.
    expired = missions.expire_missions(player)
    if expired:
        for line in expired:
            session.send(line)
        storage.save_player(player)
        return True
    for entry, mission in candidates:
        if mission["delivery_room_vnum"] != player.room_vnum:
            continue
        recipient = next((mob for mob in combat.mobs_in_room(player.room_vnum)
                          if mob.template_vnum == mission["delivery_mob_template"]
                          and mob.health > 0 and
                          (not target_query or target_query.casefold() in mob.name.casefold())), None)
        if recipient is None:
            continue
        cleanup(player, mission)
        entry["progress"] = 1
        session.send(f"&GYou hand the sealed parcel to {recipient.name}. Delivery confirmed!&x")
        for line in missions._complete_mission(player, mission, entry):
            session.send(line)
        storage.save_player(player)
        return True
    target = candidates[0][1]
    session.send(f"Deliver this parcel to {target['delivery_mob_name']} in {target['delivery_room_name']} (room {target['delivery_room_vnum']}).")
    return True
