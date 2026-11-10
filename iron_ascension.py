"""Self-contained 250-floor Iron Ascension PvE tower.

The area is deliberately unreachable from the regular world; only staff
teleports can enter until a builder deliberately adds an entrance. The
installer does not delete or replace existing /data entries.
"""
import random
import time

AREA_NAME = "Iron Ascension"
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
                "shinobi bars the staircase. Defeat the guardian to ascend."
            )
            if floor == FLOORS:
                description = (
                    "A crown of dark iron towers over the last arena. "
                    "The Iron Kage awaits; no stairs lead higher."
                )
            room = world.Room(rv, f"Iron Ascension - Floor {floor}",
                              f"Floor {floor} of 250: {stage}.\n{description}",
                              safe=True)
            world.WORLD.add_room(room)
        # Only join tower-owned rooms. Never make an external exit.
        room = world.WORLD.get(rv)
        if floor > 1:
            room.exits.setdefault("down", rv - 1)
        if floor < FLOORS:
            room.exits.setdefault("up", rv + 1)

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


def can_ascend(session, direction):
    """False only for an illegal upward step; walking DOWN remains possible."""
    if direction != "up":
        return True
    floor = floor_number(session.player.room_vnum)
    if not floor or floor >= FLOORS:
        return True
    import combat
    if session.player.iron_ascension_highest_floor < floor:
        session.send("&RThe iron staircase is sealed. Defeat this floor's ninja first.&x")
        return False
    if any(m.template_vnum == guardian_vnum(floor) and m.health > 0
           for m in combat.mobs_in_room(session.player.room_vnum)):
        session.send("&RThe guardian blocks your ascent. Defeat them before advancing.&x")
        return False
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
    """Called exactly once from ordinary mob-defeat handling."""
    floor = floor_number(mob.room_vnum)
    if not floor or mob.template_vnum != guardian_vnum(floor):
        return
    player = session.player
    if player.room_vnum != mob.room_vnum:
        return
    if floor > player.iron_ascension_highest_floor + 1:
        session.send("&RYou cannot claim a higher floor without clearing the earlier trials.&x")
        return
    player.iron_ascension_highest_floor = max(player.iron_ascension_highest_floor, floor)
    if floor < FLOORS:
        session.send(f"&YFloor {floor} cleared! The way UP to floor {floor + 1} is open.&x")
    elif not player.iron_ascension_completed:
        player.iron_ascension_completed = True
        player.mission_points += 25
        player.mission_points_earned_total += 25
        for item in (HEART, SCROLL):
            if item not in player.inventory and item not in player.equipment.values():
                player.iron_ascension_pending_items.append(item)
        session.send("&YIRON ASCENSION CONQUERED! You earn 25 mission points!&x")
        _hand_out(session)
        from session import ACTIVE_SESSIONS
        for other in ACTIVE_SESSIONS:
            if other is not session and other.player:
                other.send(f"&Y[IRON ASCENSION] {player.name} defeated the Iron Kage "
                           "and conquered all 250 floors!&x")
    else:
        session.send("&YThe Iron Kage falls again. Your legendary reward is one-time only.&x")
    import storage
    storage.save_player(player)


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
        f"&WIron Ascension:&x highest floor {player.iron_ascension_highest_floor}/250; "
        f"completed: {'yes' if player.iron_ascension_completed else 'no'}. "
        "Use UP after defeating a guardian. ASCENSION CLAIM collects pending rewards."
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
        player._iron_resolve_fired = True
        player._iron_resolve_until = now + 20.0
        session.send("&CIron Resolve activates! Your defenses harden for 20 seconds.&x")
    if now < player._iron_resolve_until:
        damage = max(1, damage * 75 // 100)
    return damage
