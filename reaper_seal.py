"""Scroll-taught fuinjutsu and durable paired soul imprisonment."""
import json
from pathlib import Path
import random
import tempfile
import os
import time
import uuid

SEAL_KEY = "reaper death seal"
REVERSE_KEY = "reverse reaper seal"
MASK_VNUM = 9820
SCROLL_VNUM = 9821
MASK_NAME = "A Shikigami Mask"
SCROLL_NAME = "A Scroll of the Reaper Death Seal"
ROOM_BASE = 1500000
SAFE_COMMANDS = {"look", "l", "say", "ooc", "help", "score", "level", "uptime", "jinchuriki", "mastery",
                 "inventory", "inv", "equipment", "eq", "aff", "affects", "skills",
                 "who", "quit", "save", "bug", "idea"}


def jutsu_entries():
    return {key: {"jutsu_id": key.replace(" ", "_"), "display_name": name,
                  "class_requirement": "general", "level_requirement": 25,
                  "chakra_cost": 60, "stamina_cost": 0, "cooldown": 30.0,
                  "damage": None, "damage_type": None, "effect": None,
                  "tier": 3, "element": "none", "scroll_only": True, "secret": True,
                  "required_clan": "uzumaki", "required_village": "whirlpool",
                  "jutsu_type": "reaper_seal"}
            for key, name in ((SEAL_KEY, "Reaper Death Seal"),
                              (REVERSE_KEY, "Reverse Reaper Seal"))}


def eligible(player):
    return player.clan == "uzumaki" and player.village == "whirlpool" and player.level >= 25


def register_items():
    import olc
    for vnum, name, kind in ((MASK_VNUM, MASK_NAME, "armor"),
                             (SCROLL_VNUM, SCROLL_NAME, "scroll")):
        if vnum in olc.OBJECT_TEMPLATES:
            continue
        obj = olc.default_object(vnum, name)
        obj.update(item_type=kind, rarity="rare", cost=0)
        if vnum == MASK_VNUM:
            obj.update(wear_loc="head", description="An unsettling white mask bearing the visage of a death spirit.")
        else:
            obj.update(scroll_jutsu=SEAL_KEY,
                       description="Ancient fuinjutsu inscriptions bind two complementary rites within this scroll.")
        olc.OBJECT_TEMPLATES[vnum] = obj


def _path():
    import storage
    return Path(storage.DATA_DIR) / "reaper_seals.json"


def _load():
    path = _path()
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else {}


def _save(records):
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".reaper-")
    try:
        with os.fdopen(fd, "w", encoding="utf8") as file:
            json.dump(records, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def imprisoned(player):
    return bool(getattr(player, "reaper_seal_id", ""))


def blocks_command(session, verb):
    if session.player and imprisoned(session.player) and verb.lower() not in SAFE_COMMANDS:
        session.send("The Reaper's seal binds your soul. You cannot act or leave this place.")
        return True
    return False


def _room(record):
    import world
    vnum = record["room"]
    if vnum not in world.WORLD.rooms:
        world.WORLD.add_room(world.Room(
            vnum, "Within the Reaper's Stomach",
            "Cold violet light reveals an endless void wrapped in chains of sealing script. "
            "Two souls are bound here beyond the reach of time. There are no exits.",
            safe=True, flags=["no_wander"], reaper_prison=True))
    return world.WORLD.get(vnum)


def _bind(player, seal_id, record):
    _room(record)
    object.__setattr__(player, "room_vnum", record["room"])
    player.reaper_seal_room_vnum = record["room"]
    player.reaper_seal_id = seal_id


def _destination(vnum, player=None):
    import world
    if world.WORLD.get(vnum) and not world.WORLD.get(vnum).reaper_prison:
        return vnum
    from data_villages import VILLAGES
    fallback = VILLAGES.get(getattr(player, "village", "leaf"), VILLAGES["leaf"])["starting_room_vnum"]
    return fallback if world.WORLD.get(fallback) else next(
        room.vnum for room in world.WORLD.rooms.values() if not room.reaper_prison)


def reconcile_player(player):
    """The journal wins over a stale character save after a crash or logout."""
    records = _load()
    for seal_id, record in records.items():
        if player.name not in record["players"]:
            continue
        if record["active"]:
            before = (player.reaper_seal_id, player.room_vnum)
            _bind(player, seal_id, record)
            return before != (player.reaper_seal_id, player.room_vnum)
    record = records.get(player.reaper_seal_id)
    if record and not record["active"]:
        player.reaper_seal_id = ""
        player.reaper_seal_room_vnum = None
        player.room_vnum = _destination(record["players"][player.name], player)
        return True
    if imprisoned(player):
        # Fail closed if the journal was lost; never silently free a soul.
        _room({"room": player.reaper_seal_room_vnum})
    return False


def restore_world():
    for record in _load().values():
        if record['active']:
            _room(record)


def _stop(session):
    import combat
    import session as sessions
    player = session.player
    for other in sessions.ACTIVE_SESSIONS:
        if other.pvp_target is session:
            other.pvp_target = None
        if other.pending_cast and other.pending_cast.target is session:
            other.pending_cast = None
    session.combat_target = session.pvp_target = session.pending_cast = None
    session.pending_action = None
    if session.controlled_clone:
        combat.remove_mob(session.controlled_clone)
    combat.dismiss_shadow_clones(player)
    combat.dismiss_summon(player)
    import genjutsu
    genjutsu.clear_chisei(player)
    player.active_status_effects.clear()
    player.mangekyo_amaterasu_burning = False
    player.mangekyo_amaterasu_caster = None
    player.rampage_until = 0
    import tracking
    tracking.stop_tracking(player)
    player.position = "standing"


def _capture(session, target_session):
    import areas
    import storage
    import world
    player = session.player
    origin = player.room_vnum
    records = _load()
    vnum = ROOM_BASE
    reserved = {r["room"] for r in records.values()}
    while vnum in world.WORLD.rooms or vnum in reserved or areas.find_area_for_vnum(vnum):
        area = areas.find_area_for_vnum(vnum)
        vnum = area.vnum_end + 1 if area else vnum + 1
    seal_id = uuid.uuid4().hex
    participants = {player.name: origin}
    participants[target_session.player.name] = target_session.player.room_vnum
    record = {"active": True, "room": vnum, "origin": origin,
              "players": participants,
              "caster": player.name, "target": target_session.player.name}
    records[seal_id] = record
    _save(records)  # commit the whole pair before either character is moved
    for trapped in [session, target_session]:
        _stop(trapped)
        _bind(trapped.player, seal_id, record)
        storage.save_player(trapped.player)
        trapped.send("&[141]The Reaper tears both souls from the world and swallows them. The seal has no end.&x")

def _reverse(session, words):
    import commands
    import storage
    import session as sessions
    import olc
    worn = session.player.equipment.get("head", "")
    proto = commands._find_object_prototype_by_name(worn) if worn else None
    if not proto or proto is not olc.OBJECT_TEMPLATES.get(MASK_VNUM):
        session.send("The reverse rite requires the Shikigami mask to be worn.")
        return
    query = " ".join(words).lower()
    records = _load()
    matches = [(key, record) for key, record in records.items() if record["active"]
               and query and any(query in name.lower() for name in (record["caster"], record["target"]))]
    if len(matches) != 1:
        session.send("Name one sealed soul unambiguously: perform reverse reaper seal <name>.")
        return
    key, record = matches[0]
    record["active"] = False
    _save(records)  # offline saves reconcile against this durable release
    for name in record["players"]:
        live = next((s for s in sessions.ACTIVE_SESSIONS if s.player and s.player.name == name), None)
        player = live.player if live else storage.load_player(name)
        if player:
            if reconcile_player(player):
                storage.save_player(player)
            if live:
                live.send("&[141]The Reaper's binding tears open. Your soul returns to the living world!&x")
    _pay(session, REVERSE_KEY)
    session.send("&[141]The Shikigami mask opens the Reaper's belly. Both bound souls are released!&x")


def _pay(session, key):
    import data_jutsu
    session.player.chakra -= data_jutsu.JUTSU[key]["chakra_cost"]
    session.player.cooldowns[key] = time.time() + data_jutsu.JUTSU[key]["cooldown"]


def cast(session, key, words):
    import combat
    import data_jutsu
    import storage
    import general_skills
    import hidden_mist
    import session as sessions
    import world
    player = session.player
    info = data_jutsu.JUTSU[key]
    if not eligible(player) or info["display_name"] not in player.learned_skills:
        session.send("You haven't learned that skill or jutsu.")
        return
    if (imprisoned(player) or player.health <= 0 or combat._is_action_blocked(player)
            or "silenced" in player.active_status_effects or session.pending_cast):
        session.send("You cannot perform the rite right now.")
        return
    if player.chakra < info["chakra_cost"] or time.time() < player.cooldowns.get(key, 0):
        session.send("You lack the Chakra or the rite is still recovering.")
        return
    if key == REVERSE_KEY:
        _reverse(session, words)
        storage.save_player(player)
        return
    room = world.WORLD.get(player.room_vnum)
    if not words or not room or room.safe or room.reaper_prison:
        session.send("The rite requires a target here, outside a safe room.")
        return
    query = " ".join(words).lower()
    target = next((s for s in sessions.ACTIVE_SESSIONS if s is not session and s.player
                   and s.player.room_vnum == player.room_vnum and query in s.player.name.lower()), None)
    if not target:
        session.send("Reaper Death Seal can bind only another player, never an NPC.")
        return
    if (target.player.health <= 0 or imprisoned(target.player)
            or combat._staff_testing_mangekyo(target.player)
            or target.player.illusion_walk_caster or target.player.tsukuyomi_frozen
            or general_skills.concealed_from(player, target.player)
            or hidden_mist.obscures(player, target.player)):
        session.send("You cannot bind that target's soul here.")
        return
    _pay(session, key)
    chance = max(5, min(100, player.skill_proficiencies.get(info["display_name"], 0)))
    if random.randint(1, 100) > chance:
        session.send("The spectral hand slips away. The Reaper's seal fails to take hold.")
        combat.grow_skill_from_usage(player, info["display_name"], session=session)
        storage.save_player(player)
        return
    _capture(session, target)
