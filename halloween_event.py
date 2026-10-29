"""Halloween Town -- a seasonal, 20-room event that NEVER rewrites builder saves.

Runtime-only rooms 100000..100019; event mobs 100200+ and items 100100+.
Permanent costume/mask item definitions are re-registered each startup to
keep earned collectibles wearable year round, but event prototypes are
excluded from save_world snapshots.
"""
from datetime import date, datetime, timedelta
import random
import time
from zoneinfo import ZoneInfo

ROOM_START = 100000
ROOM_COUNT = 20
ROOM_VNUMS = range(ROOM_START, ROOM_START + ROOM_COUNT)
TZ = ZoneInfo("America/Detroit")
TAG = "_halloween_event"
CANDY_NAMES = ("A Candy Corn Charm", "An Ectoplasm Taffy", "A Moonlight Chocolate",
               "A Jack-o'-Lantern Lollipop")
MASK = "The Pumpkin King's Cursed Mask"
MASK_CHANCE = 0.035  # A 3.5% boss-only drop: rare and genuinely powerful.
GLOBAL_CANDY_CHANCE = 0.22
MOB_RESPAWN_SECONDS = 7 * 60
FAST_MOB_RESPAWN_SECONDS = 8  # Low-level Halloween farming spawns.
BOSS_RESPAWN_SECONDS = 30 * 60
TRICK_COOLDOWN_KEY = "halloween_treat_next"
_owned_rooms = {}
_deaths = {}

# Cost, equipment slot, armor perks. These are genuine standard OLC items:
# wear to apply the stats; remove to reverse them, usable after the holiday.
COSTUMES = (
    (100100, "A Pumpkin-Head Costume", 1000, "head", {"max_health": 30, "constitution": 1}),
    (100101, "A Witchlight Robe", 2600, "body", {"max_chakra": 55, "intelligence": 2}),
    (100102, "A Skeleton Shinobi Suit", 3300, "body", {"max_health": 65, "strength": 2}),
    (100103, "A Phantom Cloak", 4800, "back", {"max_stamina": 70, "dexterity": 2}),
    (100104, "A Vampire Lord's Cape", 7000, "back", {"max_health": 75, "max_chakra": 50, "damroll": 3}),
)
CANDY_STOCK = (
    (100110, CANDY_NAMES[0], 80),
    (100111, CANDY_NAMES[1], 120),
    (100112, CANDY_NAMES[2], 200),
    (100113, CANDY_NAMES[3], 300),
)
MASK_VNUM = 100120
MOB_BASE = 100200
COSTUME_MERCHANT = 100220
CANDY_MERCHANT = 100221
TRICK_NPC = 100222
BOSS_VNUM = 100230
# Only enemies in combat rooms: the scarecrow in the safe entrance cannot be farmed.
FAST_RESPAWN_VNUMS = frozenset({MOB_BASE + 1, MOB_BASE + 2, MOB_BASE + 3})
ROOMS = [
  {
    "name": "The Crooked Pumpkin Gate",
    "description": "A crooked arch of living pumpkin vines opens onto a city lit by jack-o'-lanterns. A grinning wooden sign reads: EVERY NIGHT IS HALLOWEEN.",
    "sector": "forest"
  },
  {
    "name": "Eternal October Town Square",
    "description": "Cobblestones twist around an enormous smiling pumpkin clock. Masked townsfolk trade ghost stories beneath floating lanterns.",
    "sector": "city"
  },
  {
    "name": "The Costume Cauldron",
    "description": "Racks of capes, enchanted robes, and skeletal armor hang in a converted witch's cottage. A costume vendor watches with an enormous grin.",
    "sector": "inside"
  },
  {
    "name": "The Witch's Candy Cauldron",
    "description": "Candy jars levitate beside steaming kettles. Chocolate bats and glowing sweets tumble across the counter.",
    "sector": "inside"
  },
  {
    "name": "Lantern-Fire Promenade",
    "description": "A thousand carved pumpkins whisper riddles from crooked windows. Music from nowhere drifts between the lanterns.",
    "sector": "city"
  },
  {
    "name": "Grinning Graveyard",
    "description": "Ancient shinobi headstones lean toward the living. Clawed hands reach up through disturbed earth.",
    "sector": "forest"
  },
  {
    "name": "Broomstick Alley",
    "description": "Witch brooms sweep this alley by themselves. Zombies stagger beneath twisted rooftops.",
    "sector": "city"
  },
  {
    "name": "The Phantom Theater",
    "description": "Spectral actors perform beneath a broken moon. Every mirror reflects a different dead ninja.",
    "sector": "inside"
  },
  {
    "name": "The Vampire's Parlor",
    "description": "Purple curtains shroud a ballroom where pale nobles drain the light from every flame.",
    "sector": "inside"
  },
  {
    "name": "Howling Moon Bridge",
    "description": "A silver bridge crosses a river of black mist. Distant wolves howl from a mountain that isn't there.",
    "sector": "city"
  },
  {
    "name": "Crypt of the Lost Genin",
    "description": "Moss-covered academy headbands decorate the walls of this abandoned training crypt.",
    "sector": "inside"
  },
  {
    "name": "The Zombie Marketplace",
    "description": "Shambling merchants stagger past empty stalls, still searching for a final sale.",
    "sector": "city"
  },
  {
    "name": "Specter Lantern Grove",
    "description": "Floating blue lanterns illuminate a grove of whispering ghosts and cursed ninja silhouettes.",
    "sector": "forest"
  },
  {
    "name": "The Haunted Academy",
    "description": "Broken desks, ghostly chalk writing, and empty headbands mark a school abandoned long ago.",
    "sector": "inside"
  },
  {
    "name": "Mayor's Trick-or-Treat Porch",
    "description": "A friendly pumpkin-faced mayor hands candy to polite visitors. Something else sometimes answers the door.",
    "sector": "city"
  },
  {
    "name": "The Forbidden Corn Maze",
    "description": "Corn stalks rise like walls around hollow-eyed scarecrows and the rustle of hidden footsteps.",
    "sector": "field"
  },
  {
    "name": "Witchlight Swamp",
    "description": "Green flame dances on stagnant water. Rotten shinobi drift just beneath the surface.",
    "sector": "swamp"
  },
  {
    "name": "The Cursed Pumpkin Patch",
    "description": "Every giant pumpkin is carved with a terrified face. Roots pulse as if something beneath is breathing.",
    "sector": "field"
  },
  {
    "name": "The Pumpkin King's Stairway",
    "description": "A winding staircase climbs a black tower under a red harvest moon. Undead royal guards refuse passage lightly.",
    "sector": "inside"
  },
  {
    "name": "The Pumpkin King's Throne",
    "description": "Beneath a colossal blood-orange moon, the Pumpkin King waits on a throne of bones and lanterns. The rarest prize is his cursed mask.",
    "sector": "inside"
  }
]
# Five columns by four rows. Bidirectional corridors connect all 20 rooms.
MOB_SPAWNS = (
    (0, MOB_BASE, 7, "a pumpkin scarecrow", 85, "1d7+5", 30, 25),
    (5, MOB_BASE + 1, 15, "a reanimated genin", 200, "1d9+9", 75, 40),
    (6, MOB_BASE + 2, 22, "a shambling zombie shinobi", 300, "1d12+10", 125, 50),
    (7, MOB_BASE + 3, 28, "a phantom swordsman", 390, "1d15+15", 180, 75),
    (8, MOB_BASE + 4, 33, "a vampire rogue ninja", 475, "1d18+17", 240, 90),
    (9, MOB_BASE + 5, 40, "a howling werewolf shinobi", 575, "1d20+20", 350, 110),
    (10, MOB_BASE + 6, 44, "a cursed academy instructor", 700, "1d23+21", 420, 150),
    (11, MOB_BASE + 7, 48, "a skeletal merchant", 775, "1d23+24", 475, 170),
    (12, MOB_BASE + 8, 50, "a vengeful shinobi spirit", 890, "1d26+26", 620, 190),
    (13, MOB_BASE + 9, 50, "a ghostly chunin examiner", 1080, "1d30+27", 750, 230),
    (15, MOB_BASE + 10, 50, "a possessed straw guardian", 1400, "1d33+31", 850, 275),
    (16, MOB_BASE + 11, 50, "a swamp-drowned jonin", 1800, "1d36+35", 1150, 325),
    (17, MOB_BASE + 12, 50, "an ancient pumpkin revenant", 2200, "1d40+40", 1450, 400),
    (18, MOB_BASE + 13, 50, "an undead royal shinobi", 2800, "1d43+43", 1850, 550),
    (19, BOSS_VNUM, 50, "The Pumpkin King", 9500, "2d35+65", 8000, 2500),
)


def week_bounds(year):
    """Halloween's Monday-through-Sunday week, containing October 31."""
    halloween = date(year, 10, 31)
    start = halloween - timedelta(days=halloween.weekday())
    return start, start + timedelta(days=6)


def active(today=None):
    today = today or datetime.now(TZ).date()
    start, end = week_bounds(today.year)
    return start <= today <= end


def owns_room(vnum, room=None):
    """Only our own actual runtime room objects; never builder rooms."""
    owned = _owned_rooms.get(vnum)
    if owned is None:
        return False
    return room is None or owned is room


def is_event_mob(vnum):
    return vnum in {entry[1] for entry in MOB_SPAWNS}


def decorate_village(vnum, today=None):
    if not active(today):
        return ""
    import content
    if any(vnum in mapping.values() for mapping in content._VILLAGE_ROOMS.values()):
        return "&[208]Jack-o'-lanterns grin from the rooftops. A crooked sign whispers: teleport halloween!&x"
    return ""


def register_collectibles():
    """Persisted character items keep their prototypes out of season."""
    import olc
    for vnum, name, price, slot, stats in COSTUMES + (
        (MASK_VNUM, MASK, 0, "head",
         {"max_health": 175, "max_chakra": 175, "max_stamina": 175,
          "strength": 5, "dexterity": 5, "intelligence": 5,
          "hitroll": 12, "damroll": 12}),):
        existing = olc.OBJECT_TEMPLATES.get(vnum)
        if existing is not None:
            if not existing.get(TAG):
                continue  # Never overwrite a builder-created prototype.
            continue
        obj = olc.default_object(vnum, name)
        obj.update({"item_type": "armor", "cost": price, "wear_loc": slot,
                    "rarity": "legendary" if vnum == MASK_VNUM else "rare",
                    "stat_bonuses": stats, TAG: True,
                    "description": ("A terrible prize torn from Halloween Town's ruler."
                                    if vnum == MASK_VNUM else
                                    "An enchanted Halloween Town souvenir, wearable year-round.")})
        olc.OBJECT_TEMPLATES[vnum] = obj
    for vnum, name, cost in CANDY_STOCK:
        existing = olc.OBJECT_TEMPLATES.get(vnum)
        if existing is not None:
            if not existing.get(TAG):
                continue
            continue
        obj = olc.default_object(vnum, name)
        obj.update({"item_type": "food", "cost": cost, TAG: True,
                    "description": "Halloween Town candy. Eat it for recovery and a timed experience boost."})
        olc.OBJECT_TEMPLATES[vnum] = obj


def _register_mob(vnum, name, level, hp, damage, xp, ryo, *, shop=None, stock=None, hostile=False):
    import combat
    old = combat.MOB_TEMPLATES.get(vnum)
    if old is not None and not old.get(TAG):
        return False
    t = combat.default_template(vnum, name)
    t.update({TAG: True, "level": min(level, combat.MAX_KILLABLE_EVENT_MOB_LEVEL)
              if hostile else level,
              combat.EVENT_KILLABLE_TAG: bool(hostile),
              "hit_dice": f"1d1+{hp-1}",
              "damage_dice": damage, "experience_reward": xp,
              "ryo_reward": ryo, "respawns": False,
              "act_flags": ["Npc", "Sentinel"] + (["aggressive_everyone"] if hostile else []),
              "description": f"{name.capitalize()} stirs in the cursed streets of Halloween Town."})
    if shop:
        t.update({"shopkeeper": True, "shop_items": list(stock or ()),
                  "shop_type": shop, "shop_buys_categories": []})
    if vnum == TRICK_NPC:
        t.update({"act_flags": ["Npc", "Sentinel", "Immortal"],
                  "description": "The pumpkin-headed Mayor invites you to type 'trickortreat' once each day."})
    if vnum == BOSS_VNUM:
        t["description"] = "The ancient Pumpkin King reigns over the cursed town. His mask holds terrifying power."
    combat.MOB_TEMPLATES[vnum] = t
    return True


def _register_enemies():
    for room_idx, vnum, level, name, hp, damage, xp, ryo in MOB_SPAWNS:
        _register_mob(vnum, name, level, hp, damage, xp, ryo,
                      hostile=True)
    _register_mob(COSTUME_MERCHANT, "Morgana the Costume Witch", 1, 9999,
                  "1d1+1", 0, 0, shop="general",
                  stock=[vnum for vnum, *_ in COSTUMES])
    _register_mob(CANDY_MERCHANT, "Gourdie the Candy Merchant", 1, 9999,
                  "1d1+1", 0, 0, shop="food",
                  stock=[vnum for vnum, *_ in CANDY_STOCK])
    _register_mob(TRICK_NPC, "Mayor Jack Lantern", 1, 9999, "1d1+1", 0, 0)


def _spawn_population(now, fast_only=False):
    import combat
    for index, vnum, *_rest in MOB_SPAWNS:
        if fast_only and vnum not in FAST_RESPAWN_VNUMS:
            continue
        rv = ROOM_START + index
        if not owns_room(rv):
            continue
        if vnum not in combat.MOB_TEMPLATES or not combat.MOB_TEMPLATES[vnum].get(TAG):
            continue
        if any(m.template_vnum == vnum for m in combat.mobs_in_room(rv)):
            continue
        delay = (BOSS_RESPAWN_SECONDS if vnum == BOSS_VNUM else
                 FAST_MOB_RESPAWN_SECONDS if vnum in FAST_RESPAWN_VNUMS else MOB_RESPAWN_SECONDS)
        if now < _deaths.get(vnum, -1e20) + delay:
            continue
        combat.spawn_mob(vnum, rv)
    for idx, vnum in ((2, COSTUME_MERCHANT), (3, CANDY_MERCHANT), (14, TRICK_NPC)):
        rv = ROOM_START + idx
        if (owns_room(rv) and combat.MOB_TEMPLATES.get(vnum, {}).get(TAG)
                and not any(m.template_vnum == vnum for m in combat.mobs_in_room(rv))):
            combat.spawn_mob(vnum, rv)


def process_fast_respawns(now=None):
    """Pulse-driven fast respawns; normal undead and the boss keep longer timers."""
    if not _owned_rooms or not active():
        return
    _spawn_population(time.time() if now is None else now, fast_only=True)


def _fallback_room(player):
    import world
    import content
    vnum = getattr(player, "halloween_return_vnum", 0)
    if vnum and world.WORLD.get(vnum) and not owns_room(vnum):
        return vnum
    village = content._VILLAGE_ROOMS.get(player.village, {})
    return village.get("kage") if world.WORLD.get(village.get("kage")) else next(iter(world.WORLD.rooms))


def _send_home(session, message):
    p = session.player
    p.room_vnum = _fallback_room(p)
    p.halloween_return_vnum = 0
    session.combat_target = None
    session.pvp_target = None
    session.send(message)
    import storage
    storage.save_player(p)
    import commands
    commands.cmd_look(session, [])


def sync(today=None):
    """Minute-tick and startup. No side effects on reserved vnum collisions."""
    import combat
    import world
    import corpses
    register_collectibles()
    if not active(today):
        import session as session_module
        for s in list(session_module.ACTIVE_SESSIONS):
            if getattr(s, "player", None) and owns_room(s.player.room_vnum):
                _send_home(s, "&YHalloween Town fades away. You awaken safely back home.&x")
        for rv, room in list(_owned_rooms.items()):
            if world.WORLD.get(rv) is not room:
                _owned_rooms.pop(rv, None)
                continue
            for mob in combat.MOBS_BY_ROOM.pop(rv, []):
                # Seasonal templates never use generic respawn.
                pass
            corpses.CORPSES_BY_ROOM.pop(rv, None)
            del world.WORLD.rooms[rv]
            _owned_rooms.pop(rv, None)
        for vnum, t in list(combat.MOB_TEMPLATES.items()):
            if t.get(TAG):
                combat.MOB_TEMPLATES.pop(vnum, None)
        return
    # Refuse the entire event if ANY room is already a builder's creation.
    if any(world.WORLD.get(rv) is not None and not owns_room(rv)
           for rv in ROOM_VNUMS):
        return
    # Refuse spawns if existing custom mobs/items occupy event vnums.
    used_mobs = [row[1] for row in MOB_SPAWNS] + [
        COSTUME_MERCHANT, CANDY_MERCHANT, TRICK_NPC]
    used_items = [r[0] for r in COSTUMES] + [
        r[0] for r in CANDY_STOCK] + [MASK_VNUM]
    import olc
    if any(combat.MOB_TEMPLATES.get(vnum) is not None and
           not combat.MOB_TEMPLATES[vnum].get(TAG) for vnum in used_mobs):
        return
    if any(olc.OBJECT_TEMPLATES.get(vnum) is not None and
           not olc.OBJECT_TEMPLATES[vnum].get(TAG) for vnum in used_items):
        return
    if not _owned_rooms:
        from world import Room
        for idx, description in enumerate(ROOMS):
            vnum = ROOM_START + idx
            room = Room(vnum, description["name"], description["description"],
                        sector=description["sector"], safe=idx in {0, 1, 2, 3, 4},
                        flags=[TAG, "no_wander"])
            world.WORLD.add_room(room)
            _owned_rooms[vnum] = room
        for idx in range(ROOM_COUNT):
            row, col = divmod(idx, 5)
            if col < 4:
                world.WORLD.link(ROOM_START + idx, "east", ROOM_START + idx + 1)
            if row < 3:
                world.WORLD.link(ROOM_START + idx, "south", ROOM_START + idx + 5)
    _register_enemies()
    _spawn_population(time.time())


def command_teleport(session, args):
    """teleport halloween; teleport return safely leaves the event."""
    if len(args) != 1 or args[0].lower() not in {"halloween", "return"}:
        session.send("Usage: teleport halloween | teleport return")
        return
    player = session.player
    if session.combat_target or session.pvp_target or getattr(player, "jailed_until", 0) > time.time():
        session.send("You cannot teleport during combat or while jailed.")
        return
    if args[0].lower() == "return":
        if not owns_room(player.room_vnum):
            session.send("You are not in Halloween Town.")
            return
        _send_home(session, "&[208]The town's jack-o'-lantern portal carries you back home!&x")
        return
    if not active():
        session.send("&YThe Halloween Town portal opens only during Halloween week (Monday through Sunday around October 31).&x")
        return
    sync()
    if not owns_room(ROOM_START):
        session.send("Halloween Town cannot open: its reserved vnums are already in use. Contact an administrator.")
        return
    if owns_room(player.room_vnum):
        session.send("You are already in Halloween Town. Use 'teleport return' to leave.")
        return
    player.halloween_return_vnum = player.room_vnum
    player.room_vnum = ROOM_START
    import storage
    storage.save_player(player)
    session.send("&[208]Pumpkin-orange sparks swirl around you. You arrive in Halloween Town!&x")
    import commands
    commands.cmd_look(session, [])
    commands._fire_enter_triggers(session)


def command_trickortreat(session, args):
    """One treat per character per Detroit calendar day; occasional trick."""
    if args:
        session.send("Usage: trickortreat")
        return
    if not active() or not owns_room(session.player.room_vnum):
        session.send("Trick-or-treating is only available inside Halloween Town during Halloween week.")
        return
    import combat
    if not any(m.template_vnum == TRICK_NPC
               for m in combat.mobs_in_room(session.player.room_vnum)):
        session.send("Find Mayor Jack Lantern at the Trick-or-Treat Porch first.")
        return
    from datetime import datetime
    now = time.time()
    until = session.player.cooldowns.get(TRICK_COOLDOWN_KEY, 0)
    if until > now:
        session.send("The Mayor smiles: 'One trick or treat each day. Come back tomorrow!'")
        return
    # Save the next local midnight, including the daylight-saving offset.
    local = datetime.fromtimestamp(now, TZ)
    next_day = local.date() + timedelta(days=1)
    session.player.cooldowns[TRICK_COOLDOWN_KEY] = datetime(
        next_day.year, next_day.month, next_day.day, tzinfo=TZ).timestamp()
    if random.random() < 0.18:
        session.send("&RTrick! The Mayor whistles and a scarecrow lunges at you from the dark!&x")
        if combat.MOB_TEMPLATES.get(MOB_BASE, {}).get(TAG):
            combat.spawn_mob(MOB_BASE, session.player.room_vnum)
    else:
        import inventory
        gift = random.choice(CANDY_NAMES)
        ok, reason = inventory.add_item(session.player.inventory, gift)
        if ok:
            session.send(f"&G'Treat!' The Mayor gives you {gift}. Eat it to claim its perks.&x")
        else:
            session.send(inventory.full_message(reason, gift))
    import storage
    storage.save_player(session.player)


def candy_loot(mob, today=None):
    """Independent random Halloween candy roll on regular mob kills."""
    import combat
    if (not active(today) or combat.is_shadow_clone(mob)
            or getattr(mob, "tailed_beast_key", None)
            or getattr(mob, "template_vnum", None) in {
                COSTUME_MERCHANT, CANDY_MERCHANT, TRICK_NPC}
            or not getattr(mob, "experience_reward", 0)):
        return []
    return [random.choice(CANDY_NAMES)] if random.random() < GLOBAL_CANDY_CHANCE else []


def boss_loot(mob, today=None):
    if (active(today) and mob.template_vnum == BOSS_VNUM
            and owns_room(mob.room_vnum) and
            random.random() < MASK_CHANCE):
        return [MASK]
    return []


def mob_defeated(mob, now=None):
    if is_event_mob(mob.template_vnum) and owns_room(mob.room_vnum):
        _deaths[mob.template_vnum] = time.time() if now is None else now


def consume_candy(session, query):
    """Eat seasonal candy even after the week ends."""
    import inventory
    index, key = inventory.parse_indexed_query(query)
    words = key.lower().split()
    if not words:
        return False
    matches = [item for item in session.player.inventory
               if item in CANDY_NAMES and all(w in item.lower() for w in words)]
    if not matches:
        return False
    if index < 1 or index > len(matches):
        session.send("You don't have that Halloween candy.")
        return True
    item = matches[index - 1]
    resources = {CANDY_NAMES[0]: ("health", 100),
                 CANDY_NAMES[1]: ("chakra", 100),
                 CANDY_NAMES[2]: ("stamina", 100),
                 CANDY_NAMES[3]: ("health", 175)}
    field, amount = resources[item]
    p = session.player
    previous = getattr(p, field)
    setattr(p, field, min(getattr(p, "maximum_" + field), previous + amount))
    p.holiday_xp_boost_until = max(p.holiday_xp_boost_until, time.time() + 15 * 60)
    p.inventory.remove(item)
    session.send(f"&[208]You devour {item}, recovering {getattr(p, field)-previous} "
                 f"{field}. Sugar Rush grants +10% XP from mob kills for 15 minutes!&x")
    import storage
    storage.save_player(p)
    return True
