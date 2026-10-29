"""Calendar-based holiday loot and temporary Kage-room visitors."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import random
import time

import inventory
import storage

EVENT_ZONE = ZoneInfo("America/Detroit")
SANTA_VNUM = 999997
UNCLE_SAM_VNUM = 999995
JEDI_VNUM = 999994
FIREWORKS = "A Box of Fourth of July Fireworks"
BOMB_POP = "A Bomb Pop Popsicle"
BBQ_FOOD = "A Fourth of July BBQ Platter"
TURKEY_VNUM = 999996
TURKEY_MEAL = "A Roasted Thanksgiving Turkey"
TURKEY_FEATHER = "A Thanksgiving Turkey Feather"
TURKEY_RESPAWN_SECONDS = 15 * 60
_turkey_cooldowns = {}
EGG = "A Painted Easter Egg"
PRESENT = "A Wrapped Christmas Present"
CANDIES = {
    "A Spring Chocolate": ("health", 60),
    "A Bag of Jellybeans": ("chakra", 60),
    "A Marshmallow Chick": ("stamina", 60),
    "A Peppermint Candy Cane": ("health", 75),
}


def local_date() -> date:
    return datetime.now(EVENT_ZONE).date()


def easter_sunday(year: int) -> date:
    """Gregorian Easter date; the event runs Monday through Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def easter_active(today=None) -> bool:
    today = today or local_date()
    sunday = easter_sunday(today.year)
    return sunday - timedelta(days=6) <= today <= sunday


def christmas_active(today=None) -> bool:
    today = today or local_date()
    return today.month == 12 and 24 <= today.day <= 31


def thanksgiving_active(today=None) -> bool:
    """U.S. Thanksgiving Thursday through the following Sunday."""
    today = today or local_date()
    first = date(today.year, 11, 1)
    fourth_thursday = 1 + (3 - first.weekday()) % 7 + 21
    start = date(today.year, 11, fourth_thursday)
    return start <= today <= start + timedelta(days=3)


def july_fourth_active(today=None) -> bool:
    today = today or local_date()
    return today.month == 7 and today.day == 4


def may_fourth_active(today=None) -> bool:
    today = today or local_date()
    return today.month == 5 and today.day == 4


def hokage_room() -> int:
    import content
    return content._VILLAGE_ROOMS["leaf"]["kage"]


def mob_loot(mob, today=None) -> list:
    """Add an egg to every ordinary mob corpse without changing its template."""
    import combat
    if (easter_active(today) and not combat.is_shadow_clone(mob)
            and not getattr(mob, "tailed_beast_key", None)):
        return list(mob.loot_items) + [EGG]
    import halloween_event
    return list(mob.loot_items) + halloween_event.candy_loot(mob, today) + halloween_event.boss_loot(mob, today)


def kage_rooms() -> set:
    import content
    return {rooms["kage"] for rooms in content._VILLAGE_ROOMS.values()}


def sync_visitors(today=None) -> None:
    """Spawn Santa at all five Kage rooms during Christmas, remove him afterward."""
    import combat
    active = christmas_active(today)
    rooms = kage_rooms()
    for room_vnum, mobs in list(combat.MOBS_BY_ROOM.items()):
        mobs[:] = [mob for mob in mobs if mob.template_vnum != SANTA_VNUM or (active and room_vnum in rooms)]
    if not active:
        combat.MOB_TEMPLATES.pop(SANTA_VNUM, None)
    else:
        template = combat.default_template(SANTA_VNUM, "Santa Claus")
        template.update({"description": "Santa stands beside the Christmas tree. Ask Santa about a present.",
                         "act_flags": ["Npc", "Sentinel", "Immortal"], "respawns": False,
                         "hit_dice": "1d1+9999", "level": 1})
        combat.MOB_TEMPLATES[SANTA_VNUM] = template
        for room_vnum in rooms:
            if not any(mob.template_vnum == SANTA_VNUM for mob in combat.mobs_in_room(room_vnum)):
                combat.spawn_mob(SANTA_VNUM, room_vnum)
    sync_turkeys(today)
    sync_uncle_sam(today)
    sync_jedi(today)
    import halloween_event
    halloween_event.sync(today)


def sync_jedi(today=None) -> None:
    import combat
    active = may_fourth_active(today)
    rooms = kage_rooms()
    for room_vnum, mobs in combat.MOBS_BY_ROOM.items():
        mobs[:] = [mob for mob in mobs if mob.template_vnum != JEDI_VNUM
                   or (active and room_vnum in rooms)]
    if not active:
        combat.MOB_TEMPLATES.pop(JEDI_VNUM, None)
        return
    template = combat.default_template(JEDI_VNUM, "a mysterious Jedi")
    template.update({"description": "A robed Jedi holds a strange metal hilt. "
                     "Ask Jedi about a lightsaber. May the 4th be with you!",
                     "act_flags": ["Npc", "Sentinel", "Immortal"], "respawns": False,
                     "hit_dice": "1d1+9999", "level": 1})
    combat.MOB_TEMPLATES[JEDI_VNUM] = template
    for room_vnum in rooms:
        if not any(mob.template_vnum == JEDI_VNUM for mob in combat.mobs_in_room(room_vnum)):
            combat.spawn_mob(JEDI_VNUM, room_vnum)


def claim_may_fourth(session, today=None) -> bool:
    today = today or local_date()
    if not may_fourth_active(today):
        return False
    import combat
    import lightsabers
    player = session.player
    if player.room_vnum not in kage_rooms() or not any(
            mob.template_vnum == JEDI_VNUM for mob in combat.mobs_in_room(player.room_vnum)):
        return False
    if player.last_may_fourth_gift_year == today.year:
        session.send("The Jedi says, 'You have already received your lightsaber this year.'")
        return True
    lightsabers.register_items()
    item = lightsabers.item_name()
    ok, reason = inventory.add_item(player.inventory, item)
    if not ok:
        session.send(inventory.full_message(reason, item))
        return True
    player.last_may_fourth_gift_year = today.year
    storage.save_player(player)
    session.send("The Jedi gives you a lightsaber hilt. May the 4th be with you! "
                 "Wield lightsaber, then activate lightsaber. Deactivate lightsaber to retract it. "
                 "Insert a cut gem into lightsaber to change its color: quartz white, sapphire blue, "
                 "ruby red, diamond cyan. The gem is consumed; the weapon stays yours after the event.")
    return True


def sync_uncle_sam(today=None) -> None:
    """Temporary, unattackable holiday visitor in all five Kage chambers."""
    import combat
    active = july_fourth_active(today)
    rooms = kage_rooms()
    for vnum, mobs in combat.MOBS_BY_ROOM.items():
        mobs[:] = [mob for mob in mobs if mob.template_vnum != UNCLE_SAM_VNUM or (active and vnum in rooms)]
    if not active:
        combat.MOB_TEMPLATES.pop(UNCLE_SAM_VNUM, None)
        return
    template = combat.default_template(UNCLE_SAM_VNUM, "Uncle Sam")
    template.update({"description": "Uncle Sam is celebrating beside the Kage. Ask Uncle Sam about gifts.",
                     "act_flags": ["Npc", "Sentinel", "Immortal"], "respawns": False,
                     "hit_dice": "1d1+9999", "level": 1})
    combat.MOB_TEMPLATES[UNCLE_SAM_VNUM] = template
    for room_vnum in rooms:
        if not any(mob.template_vnum == UNCLE_SAM_VNUM for mob in combat.mobs_in_room(room_vnum)):
            combat.spawn_mob(UNCLE_SAM_VNUM, room_vnum)


def claim_july_fourth(session, today=None) -> bool:
    today = today or local_date()
    if not july_fourth_active(today):
        return False
    import combat
    player = session.player
    if player.room_vnum not in kage_rooms() or not any(
            mob.template_vnum == UNCLE_SAM_VNUM for mob in combat.mobs_in_room(player.room_vnum)):
        return False
    if player.last_july_fourth_gift_year == today.year:
        session.send("Uncle Sam says, 'You've had your celebration gifts this year!'")
        return True
    original = list(player.inventory)
    for item in (FIREWORKS, BOMB_POP, BBQ_FOOD):
        ok, reason = inventory.add_item(player.inventory, item)
        if not ok:
            player.inventory[:] = original
            session.send(inventory.full_message(reason, item))
            return True
    player.last_july_fourth_gift_year = today.year
    storage.save_player(player)
    session.send("Uncle Sam gives you fireworks, a Bomb Pop Popsicle, and a BBQ Platter! Use fireworks and eat the food.")
    return True


def use_fireworks(session, query: str) -> bool:
    index, words = inventory.parse_indexed_query(query)
    if not words:
        return False
    matches = [item for item in session.player.inventory if item == FIREWORKS
               and all(word in item.lower() for word in words.lower().split())]
    if not matches:
        return False
    if index > len(matches):
        session.send("You aren't carrying those fireworks.")
        return True
    session.player.inventory.remove(matches[index - 1])
    storage.save_player(session.player)
    session.send("&RRed, &Wwhite, and &Bblue fireworks burst overhead!&x")
    session.broadcast_room(f"&Y{session.player.name} lights fireworks; colorful sparks fill the sky!&x", exclude_self=True)
    return True


def eat_july_fourth_food(session, query: str) -> bool:
    index, words = inventory.parse_indexed_query(query)
    if not words:
        return False
    matches = [item for item in session.player.inventory if item in (BOMB_POP, BBQ_FOOD)
               and all(word in item.lower() for word in words.lower().split())]
    if not matches:
        return False
    if index > len(matches):
        session.send("You aren't carrying that holiday food.")
        return True
    item = matches[index - 1]
    session.player.inventory.remove(item)
    resources = {"chakra": 60, "stamina": 60} if item == BOMB_POP else {"health": 100, "stamina": 100}
    gains = []
    for resource, amount in resources.items():
        before = getattr(session.player, resource)
        setattr(session.player, resource, min(getattr(session.player, f"maximum_{resource}"), before + amount))
        gains.append(f"{getattr(session.player, resource) - before} {resource}")
    storage.save_player(session.player)
    session.send(f"You eat {item} and recover {', '.join(gains)}.")
    return True


def _area_rooms() -> dict:
    import areas
    import world
    entries = areas.all_areas()
    return {name: [vnum for vnum, room in world.WORLD.rooms.items()
                   if entry["vnum_start"] <= vnum <= entry["vnum_end"] and room.enabled
                   and not room.apartment and not room.player_shop]
            for name, entry in entries.items()}


def sync_turkeys(today=None, now=None) -> None:
    import combat
    active = thanksgiving_active(today)
    if not active:
        for mobs in combat.MOBS_BY_ROOM.values():
            mobs[:] = [mob for mob in mobs if mob.template_vnum != TURKEY_VNUM]
        combat.MOB_TEMPLATES.pop(TURKEY_VNUM, None)
        _turkey_cooldowns.clear()
        return
    now = time.time() if now is None else now
    template = combat.default_template(TURKEY_VNUM, "a Thanksgiving turkey")
    template.update({"description": "A plump wild turkey struts here, gobbling at passersby.",
                     "level": min(15, combat.MAX_KILLABLE_EVENT_MOB_LEVEL),
                     combat.EVENT_KILLABLE_TAG: True,
                     "hit_dice": "1d1+149", "damage_dice": "1d8+3",
                     "respawns": False, "loot_items": [TURKEY_MEAL, TURKEY_FEATHER, TURKEY_FEATHER]})
    combat.MOB_TEMPLATES[TURKEY_VNUM] = template
    area_rooms = _area_rooms()
    # Remove any turkey whose area or room has been deleted or disabled.
    valid_rooms = {vnum for rooms in area_rooms.values() for vnum in rooms}
    for room_vnum, mobs in combat.MOBS_BY_ROOM.items():
        if room_vnum not in valid_rooms:
            mobs[:] = [mob for mob in mobs if mob.template_vnum != TURKEY_VNUM]
    for name, rooms in area_rooms.items():
        if not rooms:
            continue
        pending = [deadline for deadline in _turkey_cooldowns.get(name, []) if deadline > now]
        _turkey_cooldowns[name] = pending
        live = sum(mob.template_vnum == TURKEY_VNUM for room in rooms for mob in combat.mobs_in_room(room))
        for _ in range(max(0, 2 - live - len(pending))):
            combat.spawn_mob(TURKEY_VNUM, random.choice(rooms))


def turkey_defeated(mob, now=None) -> None:
    if mob.template_vnum != TURKEY_VNUM:
        return
    import areas
    area = areas.find_area_for_vnum(mob.room_vnum)
    if area:
        _turkey_cooldowns.setdefault(area.name.lower(), []).append(
            (time.time() if now is None else now) + TURKEY_RESPAWN_SECONDS)


def eat_turkey(session, query: str) -> bool:
    index, words = inventory.parse_indexed_query(query)
    matches = [item for item in session.player.inventory if item == TURKEY_MEAL
               and all(word in item.lower() for word in words.lower().split())]
    if not words or not matches:
        return False
    if index > len(matches):
        session.send("You aren't carrying that turkey meal.")
        return True
    player = session.player
    player.inventory.remove(matches[index - 1])
    gains = []
    for resource in ("health", "chakra", "stamina"):
        before = getattr(player, resource)
        setattr(player, resource, min(getattr(player, f"maximum_{resource}"), before + 100))
        gains.append(f"{getattr(player, resource) - before} {resource}")
    player.holiday_xp_boost_until = max(player.holiday_xp_boost_until, time.time() + 1800)
    storage.save_player(player)
    session.send("You feast on roasted turkey and recover " + ", ".join(gains)
                 + ". Sugar Rush grants +10% mob experience for 30 minutes (does not stack).")
    return True


def tree_visible(room_vnum: int, today=None) -> bool:
    return christmas_active(today) and room_vnum in kage_rooms()


def claim_present(session, today=None) -> bool:
    today = today or local_date()
    if not christmas_active(today):
        return False
    import combat
    if not any(mob.template_vnum == SANTA_VNUM for mob in combat.mobs_in_room(session.player.room_vnum)):
        return False
    if session.player.last_christmas_present_year == today.year:
        session.send("Santa says, 'I already gave you a present this Christmas!'")
        return True
    ok, reason = inventory.add_item(session.player.inventory, PRESENT)
    if not ok:
        session.send(inventory.full_message(reason, PRESENT))
        return True
    session.player.last_christmas_present_year = today.year
    storage.save_player(session.player)
    session.send("Santa hands you a wrapped Christmas present! Use present to open it.")
    return True


def use_holiday_item(session, query: str) -> bool:
    """Open eggs/presents and eat candy through the existing use command."""
    index, words = inventory.parse_indexed_query(query)
    words = words.lower().split()
    if not words:
        return False
    matches = [item for item in session.player.inventory
               if (item in (EGG, PRESENT) or item in CANDIES)
               and all(word in item.lower() for word in words)]
    if not matches:
        return False
    if index > len(matches):
        session.send("You aren't carrying that holiday item.")
        return True
    item = matches[index - 1]
    if item in (EGG, PRESENT):
        choices = list(CANDIES)[:3] if item == EGG else list(CANDIES)
        prize = random.choice(choices)
        session.player.inventory.remove(item)
        ok, reason = inventory.add_item(session.player.inventory, prize)
        if not ok:
            session.player.inventory.append(item)
            session.send(inventory.full_message(reason, prize))
            return True
        session.send(f"You open {item} and find {prize}!")
    else:
        resource, amount = CANDIES[item]
        player = session.player
        before = getattr(player, resource)
        setattr(player, resource, min(getattr(player, f"maximum_{resource}"), before + amount))
        player.holiday_xp_boost_until = max(player.holiday_xp_boost_until, datetime.now().timestamp() + 900)
        player.inventory.remove(item)
        session.send(f"You enjoy {item} and recover {getattr(player, resource) - before} {resource}. Sugar Rush grants +10% mob experience for 15 minutes (does not stack).")
    storage.save_player(session.player)
    return True
