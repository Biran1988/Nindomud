"""Live, 250-floor Iron Ascension tower, entered through a hidden road exit.

The only physical tower exit is the floor-one return to Grassland Border
Trail; defeating all other guardians transfers challengers directly.
Saved world/area records are merged additively without replacing /data.
"""
import random
import time

AREA_NAME = "Iron Ascension"
# Existing Grassland Border Trail midway between Leaf, Grass, and Stone.
# The generated road has NW/SE highway exits; NE is the free side passage.
ROAD_ENTRANCE_VNUM = 20674
ROAD_ENTRANCE_NAME = "Grassland Border Trail - "
ROAD_EXIT_DIRECTION = "northeast"
RETURN_EXIT_DIRECTION = "southwest"
START = 30501
END = 31500
FLOORS = 250
MOB_START = 31001
HEART_VNUM = 31490
SCROLL_VNUM = 31491
HEART = "Heart of the Iron Kage"
SCROLL = "Scroll of Iron Resolve"
SKILL = "Iron Resolve"
STAGES = ("Initiate Trials", "Warrior Trials", "Veteran Trials",
          "Elite Trials", "Legendary Trials")
CLASSES = ("taijutsu", "ninjutsu", "genjutsu", "bukijutsu")


class IronAscensionError(ValueError):
    pass


def floor_number(vnum):
    return vnum - START + 1 if START <= vnum < START + FLOORS else 0


def guardian_vnum(floor):
    return MOB_START + floor - 1


def _validate_area():
    import areas
    registry = areas.all_areas()
    entry = registry.get(AREA_NAME.lower())
    if entry is None:
        # Never claim an already-reserved block owned by somebody else.
        areas.register_area(AREA_NAME, START, END, "System")
    elif (entry.get("vnum_start"), entry.get("vnum_end")) != (START, END):
        raise IronAscensionError(
            "Iron Ascension has a different saved vnum range; no rooms changed.")
    elif entry.get("prototype", False):
        # Previously saved prototypes must be enabled as a normal live area.
        # Change only the prototype flag; leave builder assignments alone.
        areas.set_prototype(AREA_NAME, False)


def install():
    """Idempotently build the area from source without overwriting builder data."""
    import world
    import combat
    import olc

    _validate_area()
    # Validate first: a partially installed area must not appear on collision.
    for floor in range(1, FLOORS + 1):
        rv = START + floor - 1
        room = world.WORLD.get(rv)
        if room and not room.name.startswith("Iron Ascension - Floor "):
            raise IronAscensionError(f"Room {rv} is already in use; tower unchanged.")
        mv = guardian_vnum(floor)
        template = combat.MOB_TEMPLATES.get(mv)
        if template and template.get("iron_ascension_floor") != floor:
            raise IronAscensionError(f"Mob {mv} is already in use; tower unchanged.")
    for vnum, label in ((HEART_VNUM, HEART), (SCROLL_VNUM, SCROLL)):
        obj = olc.OBJECT_TEMPLATES.get(vnum)
        if obj and obj.get("short_desc") != label:
            raise IronAscensionError(f"Item {vnum} is already in use; tower unchanged.")

    for floor in range(1, FLOORS + 1):
        rv = START + floor - 1
        if world.WORLD.get(rv) is None:
            stage = STAGES[(floor - 1) // 50]
            description = (
                "Black iron walls surround a narrow fighting platform. A lone "
                "shinobi guards this platform. Defeat them to advance by transfer."
            )
            if floor == FLOORS:
                description = (
                    "A crown of dark iron towers over the last arena. "
                    "The Iron Kage awaits the final challenger."
                )
            room = world.Room(rv, f"Iron Ascension - Floor {floor}",
                              f"Floor {floor} of 250: {stage}.\n{description}",
                              safe=True)
            world.WORLD.add_room(room)
        # Transfer-only tower: remove legacy UP/DOWN exits, including
        # saved layouts from the previous challenge implementation.
        room = world.WORLD.get(rv)
        room.exits.clear()
        room.exit_flags.clear()
        room.exit_door_open.clear()

        mv = guardian_vnum(floor)
        if mv not in combat.MOB_TEMPLATES:
            name = ("the Iron Kage" if floor == FLOORS else
                    f"an Iron Ascension floor {floor} shinobi")
            template = combat.default_template(mv, name)
            template.update({
                "level": floor,
                "primary_class": CLASSES[(floor - 1) % len(CLASSES)],
                "iron_ascension_floor": floor,
                "auto_balance": True,
                "respawns": True,
                "act_flags": ["Npc", "Sentinel"],
                "no_wander": True,
                "experience_reward": floor * 5,
                "ryo_reward": floor * 2,
                "loot_items": [],
                "description": (
                    "The final guardian of the Iron Ascension." if floor == FLOORS
                    else f"The appointed challenger for Iron Ascension floor {floor}."),
            })
            combat.MOB_TEMPLATES[mv] = template

    if HEART_VNUM not in olc.OBJECT_TEMPLATES:
        heart = olc.default_object(HEART_VNUM, HEART)
        heart.update({
            "item_type": "armor", "wear_loc": "neck",
            "level": 250, "cost": 0, "rarity": "legendary",
            "extra_flags": ["bound", "nodrop", "notrade"],
            "stat_bonuses": {
                "hitroll": 25, "damroll": 25, "max_health": 500,
                "max_chakra": 500, "max_stamina": 250,
            },
            "description": (
                "A legendary relic of the tower's Iron Kage. While worn, "
                "it reduces incoming damage by 5%, with a 5% chance "
                "to negate a direct attack entirely."),
        })
        olc.OBJECT_TEMPLATES[HEART_VNUM] = heart
    if SCROLL_VNUM not in olc.OBJECT_TEMPLATES:
        scroll = olc.default_object(SCROLL_VNUM, SCROLL)
        scroll.update({
            "item_type": "scroll", "scroll_jutsu": "",
            "level": 250, "cost": 0, "rarity": "legendary",
            "extra_flags": ["bound", "nodrop", "notrade"],
            "description": (
                "Study with READ to learn Iron Resolve, a once-per-fight "
                "defensive instinct triggered near defeat."),
        })
        olc.OBJECT_TEMPLATES[SCROLL_VNUM] = scroll

    # Guards are deliberately sourced from code, not saved /data spawnpoints:
    # restarts regenerate one per floor and normal death respawn handles retries.
    for floor in range(1, FLOORS + 1):
        rv = START + floor - 1
        if not any(m.template_vnum == guardian_vnum(floor)
                   for m in combat.mobs_in_room(rv)):
            combat.spawn_mob(guardian_vnum(floor), rv)



def install_entrance():
    """Persist a hidden Grass Road entrance without touching unrelated rooms.

    Unlike transfer-only combat floors, floor one has a normal exit back to
    the trail. Only the single chosen exit and flag are merged into /data.
    """
    from copy import deepcopy
    from dataclasses import asdict
    import storage
    import world

    road = world.WORLD.get(ROAD_ENTRANCE_VNUM)
    first = world.WORLD.get(START)
    if road is None or first is None or not road.name.startswith(ROAD_ENTRANCE_NAME):
        raise IronAscensionError(
            f"Entrance unavailable: expected Grassland Border Trail at {ROAD_ENTRANCE_VNUM}.")
    if (road.exits.get(ROAD_EXIT_DIRECTION) not in (None, START)
            or first.exits.get(RETURN_EXIT_DIRECTION) not in (None, ROAD_ENTRANCE_VNUM)):
        raise IronAscensionError("Entrance would overwrite a builder's existing road or tower exit.")
    old_flags = road.exit_flags.get(ROAD_EXIT_DIRECTION, [])
    if old_flags not in ([], ["hidden"]):
        raise IronAscensionError("Entrance has custom exit flags; existing builder settings retained.")

    state = storage.load_world_state()
    if not isinstance(state, dict):
        raise IronAscensionError("Saved world state could not be read.")
    saved = state.get("rooms", {})
    if saved is not None and not isinstance(saved, dict):
        raise IronAscensionError("Saved world rooms are invalid; no changes made.")
    record = (saved or {}).get(str(ROAD_ENTRANCE_VNUM))
    if record is None:
        record = {key: value for key, value in asdict(road).items() if key != "ground_ryo"}
    if not isinstance(record, dict) or record.get("name") != road.name:
        raise IronAscensionError("Saved road room does not match the current Grassland Trail.")
    if record.get("exits", {}).get(ROAD_EXIT_DIRECTION) not in (None, START):
        raise IronAscensionError("Saved road has a conflicting entrance; nothing overwritten.")
    if record.get("exit_flags", {}).get(ROAD_EXIT_DIRECTION, []) not in ([], ["hidden"]):
        raise IronAscensionError("Saved road has conflicting entrance flags; nothing overwritten.")

    # Save the road's new hidden exit atomically BEFORE exposing it live.
    if (record.get("exits", {}).get(ROAD_EXIT_DIRECTION) != START
            or record.get("exit_flags", {}).get(ROAD_EXIT_DIRECTION) != ["hidden"]):
        merged = deepcopy(state)
        saved_rooms = merged.setdefault("rooms", {})
        merged_record = deepcopy(record)
        merged_record.setdefault("exits", {})[ROAD_EXIT_DIRECTION] = START
        merged_record.setdefault("exit_flags", {})[ROAD_EXIT_DIRECTION] = ["hidden"]
        saved_rooms[str(ROAD_ENTRANCE_VNUM)] = merged_record
        storage.save_world_state(merged)

    road.exits[ROAD_EXIT_DIRECTION] = START
    road.exit_flags[ROAD_EXIT_DIRECTION] = ["hidden"]
    # No links among levels; the only reverse route is floor one's way out.
    first.exits[RETURN_EXIT_DIRECTION] = ROAD_ENTRANCE_VNUM
    return ROAD_ENTRANCE_VNUM


def ensure_guardian(floor):
    """Maintain a living opponent in a room entered mid-respawn."""
    if not 1 <= floor <= FLOORS:
        return
    import combat
    rv, mv = START + floor - 1, guardian_vnum(floor)
    if mv not in combat.MOB_TEMPLATES:
        return
    if not any(m.template_vnum == mv and m.health > 0 for m in combat.mobs_in_room(rv)):
        combat.spawn_mob(mv, rv)
        # Replacing the guardian now must not duplicate it when the old
        # delayed respawn timer fires.
        combat._respawn_queue[:] = [
            entry for entry in combat._respawn_queue
            if not (entry[1] == mv and entry[2] == rv)
        ]


def reset_run_on_login(session):
    """A new authenticated session always restarts a tower visit at floor 1."""
    player = getattr(session, "player", None)
    if player is None or not floor_number(player.room_vnum):
        return False
    import world
    if world.WORLD.get(START) is None:
        return False
    player.room_vnum = START
    ensure_guardian(1)
    session.send("&Y[Iron Ascension] The tower resets your challenge to floor 1.&x")
    return True


def _transfer(session, floor):
    """Transfer to a sealed arena room without using any room exits."""
    import world
    import commands
    rv = START + floor - 1
    if world.WORLD.get(rv) is None:
        session.send("&RThe next Iron Ascension arena is unavailable.&x")
        return False
    ensure_guardian(floor)
    session.player.room_vnum = rv
    session.send(f"&CIron Ascension transports you to floor {floor} of {FLOORS}!&x")
    import storage
    storage.save_player(session.player)
    commands.cmd_look(session, [])
    return True


def _hand_out(session):
    """Give pending one-time rewards, preserving unclaimed items if full."""
    import inventory
    import storage
    player = session.player
    pending = list(player.iron_ascension_pending_items)
    for item in pending:
        success, reason = inventory.add_item(player.inventory, item)
        if success:
            player.iron_ascension_pending_items.remove(item)
            session.send(f"&YYou receive {item}!&x")
        else:
            session.send(f"&Y{item} is awaiting collection. "
                         "Free an inventory slot, then type ASCENSION CLAIM.&x")
    storage.save_player(player)


def defeated(session, mob):
    """Advance the killer after ALL ordinary kill rewards have been processed."""
    floor = floor_number(mob.room_vnum)
    if not floor or mob.template_vnum != guardian_vnum(floor):
        return False
    player = session.player
    if player.room_vnum != mob.room_vnum:
        return False
    if floor < FLOORS:
        session.send(f"&YFloor {floor} defeated! The tower seal advances you.&x")
        return _transfer(session, floor + 1)

    # The only persistent tower state is the one-time reward entitlement.
    if not player.iron_ascension_completed:
        player.iron_ascension_completed = True
        player.mission_points += 25
        player.mission_points_earned_total += 25
        for item in (HEART, SCROLL):
            if item not in player.inventory and item not in player.equipment.values():
                if item not in player.iron_ascension_pending_items:
                    player.iron_ascension_pending_items.append(item)
        session.send("&YIRON ASCENSION CONQUERED! You earn 25 mission points!&x")
        _hand_out(session)
        from session import ACTIVE_SESSIONS
        for other in ACTIVE_SESSIONS:
            if other is not session and other.player:
                other.send(f"&Y[IRON ASCENSION] {player.name} defeated the Iron Kage "
                           "and conquered all 250 floors!&x")
    else:
        session.send("&YThe Iron Kage falls again. Legendary rewards are one-time only.&x")
    session.send("&YThe Iron Kage's final seal returns you to the first arena.&x")
    return _transfer(session, 1)


def command(session, args):
    player = session.player
    if args and args[0].lower() == "claim":
        if not player.iron_ascension_completed:
            session.send("You have no Iron Ascension rewards to claim.")
            return
        if not player.iron_ascension_pending_items:
            session.send("You have no unclaimed Iron Ascension items.")
            return
        _hand_out(session)
        return
    session.send(
        f"&WIron Ascension:&x current floor {floor_number(player.room_vnum) or 'outside tower'}/250; "
        f"final reward claimed: {'yes' if player.iron_ascension_completed else 'no'}. "
        "Defeating a guardian transfers you directly to the next floor. "
        "Logging back in restarts at floor 1. "
        "ASCENSION CLAIM collects pending one-time items."
    )


def read_scroll(session, item):
    """Return True when this specialized scroll has been handled."""
    if item != SCROLL:
        return False
    import storage
    player = session.player
    if SKILL in player.learned_skills:
        session.send("You already know Iron Resolve.")
        return True
    player.learned_skills.append(SKILL)
    player.skill_proficiencies[SKILL] = 100
    import skill_training
    skill_training.grant_without_practice(player, SKILL)
    player.inventory.remove(item)
    storage.save_player(player)
    session.send("&YYou study the Scroll of Iron Resolve and master Iron Resolve!&x")
    return True


def reduce_incoming(session, mob, damage):
    """Per-hit Heart defenses and once-per-fight Iron Resolve trigger."""
    player = session.player
    damage = max(0, int(damage))
    if not damage:
        return 0
    if HEART in player.equipment.values():
        if random.randint(1, 100) <= 5:
            session.send("&YIron Will! The Heart of the Iron Kage negates the attack.&x")
            return 0
        damage = max(1, damage * 95 // 100)

    if SKILL not in player.learned_skills:
        return damage
    # Fresh target means a fresh encounter. No wall-clock cooldown can
    # accidentally allow a second Iron Resolve during the same long fight.
    fight_id = getattr(mob, "instance_id", id(mob))
    if getattr(player, "_iron_resolve_fight_id", None) != fight_id:
        player._iron_resolve_fight_id = fight_id
        player._iron_resolve_fired = False
        player._iron_resolve_until = 0.0
    now = time.time()
    if (not player._iron_resolve_fired
            and player.health - damage <= max(1, player.maximum_health // 5)):
        import signature_moves
        duration = round(20 * signature_moves.multiplier(player, SKILL))
        player._iron_resolve_fired = True
        player._iron_resolve_until = now + duration
        session.send(f"&CIron Resolve activates! Your defenses harden for {duration} seconds.&x")
    if now < player._iron_resolve_until:
        import signature_moves
        reduction = round(25 * signature_moves.multiplier(player, SKILL))
        damage = max(1, damage * (100 - reduction) // 100)
    return damage
