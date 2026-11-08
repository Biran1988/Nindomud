"""Road-only, mob-free recovery missions.

Quest props are an ephemeral overlay, NOT entries in Room.ground_items.
Their durable placement lives on the mission in the owner's saved player,
so 'save world', builder edits, restarts and /data are never overwritten.
"""
import random
import time
import uuid

# Mix lost shinobi equipment with lighthearted Naruto-world errands.
RECOVERY_ITEMS = (
    ("a lost jutsu scroll", "Recover a missing jutsu scroll before its secrets spread."),
    ("a damaged sealing scroll", "Retrieve a seal master's misplaced scroll."),
    ("a forgotten mission dossier", "Locate a confidential mission report."),
    ("a missing shinobi headband", "Find an academy graduate's lost forehead protector."),
    ("a misplaced chakra research journal", "Recover a researcher's chakra notes."),
    ("the Hokage's missing underwear", "Recover the Hokage's embarrassing missing underwear discreetly."),
    ("the Hokage's secret snack stash", "Find the Hokage's suspiciously well-hidden snacks."),
    ("a ninja's forgotten lunchbox", "Track down a shinobi's abandoned lunchbox."),
    ("a legendary ramen coupon", "Find the irreplaceable ramen coupon."),
    ("a mysterious love letter", "Recover a sealed love letter before anyone reads it."),
)

# Runtime placements: mission_id => (owner casefold, room_vnum, item name).
_ITEMS = {}


def eligible_rooms():
    """Only original mainland highway rooms and rooms at roadside inns.

    A room must still have its original generated name; reused builder
    VNUMs are never considered. Country roads are distinct from village
    rooms. Inn porches, reception and tea houses are explicitly allowed.
    """
    import mainland_roads
    import roadside_encounters
    import world

    expected, _hubs = mainland_roads.build_rooms()
    choices = {
        vnum for vnum, template in expected.items()
        if (room := world.WORLD.get(vnum)) is not None
        and room.enabled and room.name == template.name
        and not room.apartment and not room.player_shop
    }
    _rooms, _links, _mobs, _spawns, details = roadside_encounters.build_plan()
    for info in details["inns"].values():
        for vnum in (info["porch"], info["lobby"], info["tea"]):
            room = world.WORLD.get(vnum)
            if (room is not None and room.enabled and
                    room.name.startswith(info["name"] + " - ") and
                    not room.apartment and not room.player_shop):
                choices.add(vnum)
    return sorted(choices)


def new_recovery(player, rank, rank_def):
    """Create exactly one recoverable object in a randomly selected road/inn."""
    import missions
    import world

    _, _, min_level, _kills, reward_xp, reward_ryo, reward_mp, cooldown = rank_def
    if player.level < min_level:
        return f"You must be at least level {min_level} to request a {rank} mission."
    key = "recovery_" + rank
    remaining = missions.cooldown_remaining(player, key)
    if remaining > 0:
        return f"Recovery missions are on cooldown for {missions._format_duration(remaining)}."
    if any((missions._resolve_mission(entry) or {}).get("rank") == rank
           and (missions._resolve_mission(entry) or {}).get("mission_type") == "retrieve"
           for entry in player.active_missions):
        return f"You already have an active {rank} recovery mission."
    choices = eligible_rooms()
    if not choices:
        return "No safe, reachable mainland road or roadside inn is available for item missions."
    vnum = random.choice(choices)
    item_name, story = random.choice(RECOVERY_ITEMS)
    now = time.time()
    mission_id = "recovery_" + uuid.uuid4().hex
    location = world.WORLD.get(vnum)
    # The named road segment / inn gives a meaningful clue without
    # exposing the precise room or a teleport shortcut.
    region = location.name.split(" - ", 1)[0]
    mission = {
        "mission_id": mission_id,
        "rank": rank,
        "mission_type": "retrieve",
        "title": "Recovery: " + item_name,
        "description": story,
        "target_count": 1,
        "quest_item_name": item_name,
        "quest_room_vnum": vnum,
        "quest_owner": player.name,
        "quest_region": region,
        "reward_xp": reward_xp,
        "reward_ryo": reward_ryo,
        "reward_mission_points": reward_mp,
        "cooldown_seconds": cooldown,
    }
    player.active_missions.append({
        "mission_id": mission_id,
        "progress": 0,
        "dynamic": mission,
        "expires_at": now + missions.MISSION_DURATION_SECONDS,
    })
    player.mission_cooldowns[key] = now + cooldown
    _ITEMS[mission_id] = (player.name.casefold(), vnum, item_name)
    return (f"Mission requested: {mission['title']} ({rank}). {story} "
            f"Last seen around {region}, somewhere on the mainland roads or at a roadside inn. "
            "Find it and GET it to finish the mission. You have 30 minutes.")


def restore_active_items():
    """Rehydrate the overlay from existing character saves at server start."""
    import missions
    import storage
    _ITEMS.clear()
    now = time.time()
    valid_rooms = set(eligible_rooms())
    for player in storage.all_players():
        for entry in player.active_missions:
            mission = missions._resolve_mission(entry)
            if (mission and mission.get("mission_type") == "retrieve"
                    and entry.get("expires_at", now + 1) > now
                    and mission.get("quest_room_vnum") in valid_rooms
                    and mission.get("quest_owner", "").casefold() == player.name.casefold()):
                _ITEMS[entry["mission_id"]] = (
                    player.name.casefold(), mission["quest_room_vnum"],
                    mission["quest_item_name"],
                )


def visible_items(room_vnum):
    """Physical-looking quest objects. Never add them to persistent world data."""
    return [name for _owner, vnum, name in _ITEMS.values() if vnum == room_vnum]


def is_quest_item(room_vnum, query):
    return any(vnum == room_vnum and all(word in name.casefold() for word in query.casefold().split())
               for _owner, vnum, name in _ITEMS.values())


def forget(mission_id):
    _ITEMS.pop(mission_id, None)


def try_pickup(session, query, *, all_mode=False):
    """Claim an item only for its assigned owner, with no NPC/turn-in.

    Returns True if a matching quest prop was handled, including a
    foreign quest that was refused. Never places the item in inventory
    where it could be sold, transferred or exploited.
    """
    import missions
    import storage
    owner = session.player.name.casefold()
    room_vnum = session.player.room_vnum
    matches = [(key, item) for key, item in list(_ITEMS.items())
               if item[1] == room_vnum and
               (not query or all(word in item[2].casefold() for word in query.casefold().split()))]
    if not matches:
        return False
    selected = matches if all_mode else matches[:1]
    handled = False
    for key, (bound_owner, _room, name) in selected:
        handled = True
        if bound_owner != owner:
            session.send("This lost item belongs to another ninja's recovery mission.")
            continue
        entry = next((e for e in session.player.active_missions if e.get("mission_id") == key), None)
        if not entry:
            forget(key)
            continue
        mission = missions._resolve_mission(entry)
        if not mission or mission.get("mission_type") != "retrieve":
            forget(key)
            continue
        # Deadline check at pickup prevents free rewards after expiration.
        expired = missions.expire_missions(session.player)
        if expired:
            for notice in expired:
                session.send(notice)
            storage.save_player(session.player)
        if entry not in session.player.active_missions:
            continue
        session.send(f"&YYou recover {name}!&x")
        forget(key)
        for notice in missions._complete_mission(session.player, mission, entry):
            session.send(notice)
        storage.save_player(session.player)
    return handled
