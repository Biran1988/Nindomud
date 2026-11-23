"""Player-placed room trap tags, separate from Kage territory traps.

A trap belongs to one named player and one PvP organization. Placing it
consumes a physical item; hostile entrants may auto-disarm with the existing
Trap Disabling jutsu. Active traps persist under data/room_trap_tags.json.
"""
import json
import os
import random
import time
import uuid

SKILL_KEY = "trap tag placement"
SKILL_NAME = "Trap Tag Placement"
BUKI_LEVEL = 10
SCROLL_LEVEL = 25
MAX_PER_ROOM = 3
MAX_PER_OWNER = 6
EXPIRE_SECONDS = 1800

# The first nine unassigned equipment VNUMs after Jounin stock (39-79).
TAGS = {
    "explosive": (80, "An Explosive Trap Tag", 10, 1200, "blast"),
    "snare": (81, "A Wire Snare Tag", 10, 1500, "snare"),
    "flashbang": (82, "A Flashbang Tag", 25, 2000, "blind"),
    "paralysis": (83, "A Paralysis Tag", 75, 5000, "paralyzed"),
    "drain": (84, "A Chakra Drain Tag", 75, 7500, "drained"),
    "fire": (85, "A Fire Burst Tag", 50, 4500, "burning"),
    "alarm": (86, "An Alarm Seal Tag", 25, 1800, "alarm"),
    "suppression": (87, "A Chakra Suppression Tag", 100, 15000, "silenced"),
    "disruption": (88, "A Barrier Disruption Tag", 100, 12000, "barrier"),
}
# Existing item prototypes and attached-target Bukijutsu remain unchanged.
EXISTING = {
    "note": ("An Exploding Note", "blast"),
    "smoke": ("A Smoke Bomb", "blind"),
    "gas": ("A Poison Gas Bomb", "poisoned"),
    "clay": ("A Wad of Exploding Clay", "clay"),
}
ALIASES = {"exploding": "explosive", "wire": "snare", "flash": "flashbang",
           "exploding note": "note", "smoke bomb": "smoke",
           "poison gas bomb": "gas", "exploding clay": "clay",
           "flashbang tag": "flashbang", "wire snare": "snare"}

_records = {}
_loaded_path = None


def _path():
    import storage
    return os.path.join(storage.DATA_DIR, "room_trap_tags.json")


def _persist():
    import storage
    storage.ensure_dirs()
    storage._atomic_write_json(_path(), _records)


def _expire():
    import world
    now = time.time()
    dirty = False
    for room, records in list(_records.items()):
        kept = [r for r in records if
                isinstance(r, dict)
                and r.get("type") in (*TAGS, *EXISTING)
                and isinstance(r.get("expires"), (int, float))
                and r["expires"] > now and world.WORLD.get(int(room))]
        if len(kept) != len(records):
            dirty = True
        if kept:
            _records[room] = kept
        else:
            _records.pop(room, None)
    return dirty


def load():
    global _loaded_path, _records
    path = _path()
    if _loaded_path != path:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
        else:
            saved = {}
        if not isinstance(saved, dict):
            raise ValueError("Invalid room trap ledger")
        _records = {str(int(k)): v for k, v in saved.items()
                    if str(k).isdigit() and isinstance(v, list)}
        _loaded_path = path
    if _expire():
        _persist()


def register_items():
    """Create missing prototypes only; never replace builder originals."""
    import olc
    created, collisions = [], []
    for _tag, (vnum, name, level, price, _effect) in TAGS.items():
        current = olc.OBJECT_TEMPLATES.get(vnum)
        if current is None:
            obj = olc.default_object(vnum, name)
            obj.update(item_type="misc", level=level, cost=price,
                       description=(f"A single-use level {level} trap tag. "
                                    "Use TRAP PLACE <type> after learning "
                                    "Trap Tag Placement."))
            olc.OBJECT_TEMPLATES[vnum] = obj
            created.append(vnum)
        elif (current.get("item_type") != "misc"
              or str(current.get("short_desc", "")).casefold() != name.casefold()):
            collisions.append(vnum)
    if collisions:
        print("[Room trap tags] Preserved conflicting VNUMs: " +
              ", ".join(map(str, collisions)))
    return {"created": created, "collisions": collisions}


def _physical_item(tag):
    if tag in EXISTING:
        return EXISTING[tag][0], BUKI_LEVEL
    if tag not in TAGS:
        return None
    vnum, name, level, _price, _effect = TAGS[tag]
    import olc
    obj = olc.OBJECT_TEMPLATES.get(vnum)
    if not obj or (obj.get("item_type") != "misc"
                   or str(obj.get("short_desc", "")).casefold() != name.casefold()):
        return None
    return name, level


def command(session, words):
    import combat
    import data_jutsu
    import jutsu_balance
    import pvp_organizations
    import skill_training
    import storage
    import world
    player = getattr(session, "player", None)
    if player is None:
        return
    tag = " ".join(words).casefold().strip()
    tag = ALIASES.get(tag, tag)
    if tag not in TAGS and tag not in EXISTING:
        session.send("Usage: trap place <type>\nTypes: " +
                     ", ".join((*TAGS, *EXISTING)))
        return
    jutsu = data_jutsu.JUTSU[SKILL_KEY]
    minimum = BUKI_LEVEL if player.primary_class == "bukijutsu" else SCROLL_LEVEL
    if (player.level < minimum
            or not combat._can_use_jutsu(player, jutsu, SKILL_KEY)):
        session.send(f"You must learn Trap Tag Placement (Bukijutsu level "
                     f"{BUKI_LEVEL}; other classes scroll level {SCROLL_LEVEL}).")
        return
    if skill_training.needs_first_practice(player, SKILL_NAME):
        session.send(f"Practice {SKILL_NAME} with a teacher first.")
        return
    room = world.WORLD.get(player.room_vnum)
    if room is None or room.safe or room.apartment or room.player_shop:
        session.send("You cannot set hostile tags in PvP-safe or private rooms.")
        return
    org = pvp_organizations.membership(player)
    if not org:
        session.send("You must belong to a PvP organization to set hostile traps.")
        return
    info = _physical_item(tag)
    if info is None:
        session.send("That trap tag is not available as a genuine item.")
        return
    name, item_level = info
    if player.level < item_level:
        session.send(f"You need level {item_level} to place this tag.")
        return
    item = next((value for value in player.inventory
                 if str(value).casefold() == name.casefold()), None)
    if item is None:
        session.send(f"You need to carry {name}.")
        return
    load()
    location = str(player.room_vnum)
    here = _records.get(location, [])
    if len(here) >= MAX_PER_ROOM:
        session.send("This room has too many active trap tags.")
        return
    if any(r.get("owner", "").casefold() == player.name.casefold() for r in here):
        session.send("You already have a tag placed in this room.")
        return
    count = sum(1 for records in _records.values() for r in records
                if r.get("owner", "").casefold() == player.name.casefold())
    if count >= MAX_PER_OWNER:
        session.send("You have reached your active trap limit.")
        return
    now = time.time()
    if player.cooldowns.get(SKILL_KEY, 0) > now:
        session.send("Trap Tag Placement is on cooldown.")
        return
    chakra = jutsu_balance.cast_cost(player, jutsu, "chakra")
    stamina = jutsu_balance.cast_cost(player, jutsu, "stamina")
    if player.chakra < chakra or player.stamina < stamina:
        session.send("You lack the Chakra or Stamina to set that trap.")
        return
    entry = {"id": uuid.uuid4().hex, "type": tag, "owner": player.name,
             "org": org, "expires": now + EXPIRE_SECONDS}
    here.append(entry)
    _records[location] = here
    try:
        _persist()
    except (OSError, ValueError, TypeError):
        here.remove(entry)
        if not here:
            _records.pop(location, None)
        session.send("Unable to save the trap; the item was not consumed.")
        return
    player.inventory.remove(item)
    player.chakra -= chakra
    player.stamina -= stamina
    player.cooldowns[SKILL_KEY] = now + jutsu["cooldown"]
    storage.save_player(player)
    combat.grow_skill_from_usage(player, SKILL_NAME, session=session)
    session.send(f"&YYou conceal {name} in this room for up to 30 minutes.&x")


def _live_owner(name):
    from session import ACTIVE_SESSIONS
    return next((s for s in ACTIVE_SESSIONS
                 if getattr(s, "player", None)
                 and s.player.name.casefold() == name.casefold()
                 and getattr(getattr(s, "state", None), "name", "") == "PLAYING"), None)


def _trigger(session, trap):
    import status_effects
    player = session.player
    tag = trap["type"]
    name = _physical_item(tag)[0] if _physical_item(tag) else tag
    effect = TAGS[tag][4] if tag in TAGS else EXISTING[tag][1]
    msg = [f"&RYou trigger {name}!&x"]
    hits = {"blast": (28, 46), "clay": (45, 70),
            "blind": (5, 12), "poisoned": (12, 23),
            "snare": (8, 16), "burning": (15, 25)}
    if effect in hits:
        low, high = hits[effect]
        rolled = status_effects.reduce_incoming_damage(
            player.active_status_effects, random.randint(low, high))
        # Single-use, non-lethal PvP trap: no uncredited offline kills.
        damage = min(max(0, player.health - 1), rolled)
        player.health = max(1, player.health - damage)
        msg.append(f"{damage} damage.")
    statuses = {"blind": "blinded", "snare": "entangled",
                "poisoned": "poisoned", "paralyzed": "paralyzed",
                "burning": "burning", "drained": "drained",
                "silenced": "silenced"}
    if effect in statuses:
        status_effects.apply_effect(
            player.active_status_effects, statuses[effect],
            source=f"Trap Tag by {trap['owner']}")
        msg.append(f"Status: {statuses[effect]}.")
    if effect == "drained":
        loss = min(player.chakra, random.randint(25, 50))
        player.chakra -= loss
        msg.append(f"{loss} Chakra lost.")
    if effect == "barrier":
        removed = [name for name in (
            "barrier", "reinforced_barrier", "fortress_barrier",
            "sanctuary", "elemental_shield")
            if name in player.active_status_effects]
        for name in removed:
            player.active_status_effects.pop(name, None)
        msg.append("Your protective barrier collapses!" if removed
                   else "No protective barrier was active.")
    if effect == "alarm":
        owner = _live_owner(trap["owner"])
        if owner is not None and owner is not session:
            owner.send(f"&YYour alarm tag detected {player.name} in room "
                       f"{player.room_vnum}.&x")
    session.send(" ".join(msg))



def staff_room_lines(room_vnum):
    """Reveal active hidden player-set traps to immortals during LOOK.

    This never exposes the trap ledger to ordinary players, and it reads the
    live persisted entries so triggered, disarmed and expired tags disappear.
    """
    load()
    now = time.time()
    lines = []
    for trap in _records.get(str(room_vnum), ()):
        details = _physical_item(trap["type"])
        name = details[0] if details else trap["type"].title() + " trap"
        minutes = max(1, int((trap["expires"] - now + 59) // 60))
        lines.append(
            f"  &Y[IMM TRAP]&x {name} "
            f"&D[Owner: {trap['owner']} | {minutes}m remaining]&x"
        )
    return lines


def on_enter(session):
    """Disarm with existing skill automatically, or spring an enemy's tag."""
    import combat
    import pvp_organizations
    import storage
    import world
    player = getattr(session, "player", None)
    if player is None:
        return
    room = world.WORLD.get(player.room_vnum)
    if room is None or room.safe or combat.is_immortal_immune_to_defeat(session):
        return
    load()
    here = str(player.room_vnum)
    organization = pvp_organizations.membership(player)
    for trap in list(_records.get(here, ())):
        # Entering players spring traps unless they placed the tag or share
        # its organization. Unaffiliated players are not silently skipped.
        if (trap["owner"].casefold() == player.name.casefold()
                or (organization and trap["org"] == organization)):
            continue
        original = _records.get(here, [])
        if not any(item.get("id") == trap.get("id") for item in original):
            continue
        original.remove(trap)
        if not original:
            _records.pop(here, None)
        _persist()  # One-shot even if room programs teleport during messaging.
        if "Trap Disabling" in player.learned_skills:
            mastery = max(0, min(100, int(
                player.skill_proficiencies.get("Trap Disabling", 0))))
            chance = min(90, 25 + 65 * mastery // 100)
            if random.randint(1, 100) <= chance:
                session.send(f"&GYou automatically disarm a hidden {trap['type']} tag!&x")
                combat.grow_skill_from_usage(
                    player, "Trap Disabling", session=session)
                storage.save_player(player)
                continue
            session.send("&RYou spot a hidden trap but fail to disarm it!&x")
        _trigger(session, trap)
        storage.save_player(player)
