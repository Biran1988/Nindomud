"""Whirlpool / Uzumaki fuinjutsu: real target seals and persistent exit barriers.

No wall mutates a builder's exits. The journal is separate, crash-safe, and
read on demand; fixed/imbued seals outlive their caster's location/logout.
Flowing barriers have remote upkeep while their caster remains connected.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

SEAL_PREFIX = "fuinjutsu_"
ACTIVE_SEAL_KEYS = {
    "chakra suppression seal": "fuinjutsu_no_ninjutsu",
    "mind suppression seal": "fuinjutsu_no_genjutsu",
    "hand sign suppression seal": "fuinjutsu_no_handsigns",
    "binding formula seal": "fuinjutsu_rooted",
    "chakra lock seal": "fuinjutsu_chakra_locked",
    "teleportation anchor seal": "fuinjutsu_teleport_anchor",
    "summoning contract seal": "fuinjutsu_summon_locked",
}
BARRIERS = {
    "flowing barrier seal": {"level": 35, "cost": 36, "cooldown": 25, "mode": "upkeep"},
    "timed barrier seal": {"level": 75, "cost": 75, "cooldown": 35, "mode": "timed"},
    "imbued barrier seal": {"level": 135, "cost": 0, "cooldown": 45, "mode": "imbued"},
    "multi exit barrier": {"level": 180, "cost": 120, "cooldown": 120, "mode": "timed"},
}
SEALS = {
    "chakra suppression seal": (25, 42, 35, 18),
    "mind suppression seal": (45, 46, 35, 18),
    "chakra siphon seal": (65, 50, 30, 0),
    "hand sign suppression seal": (110, 70, 50, 11),
    "binding formula seal": (55, 34, 30, 10),
    "chakra lock seal": (95, 55, 45, 20),
    "seal release": (120, 40, 10, 0),
    "teleportation anchor seal": (155, 72, 50, 35),
    "summoning contract seal": (200, 85, 50, 45),
}
MAX_BARRIERS_PER_CASTER = 3
MULTI_EXIT_SECONDS = 240
CONTRACT_BREAK_LEVEL = 230
CONTRACT_BREAK_COST = 240
CONTRACT_BREAK_COOLDOWN = 3600
CONTRACT_CONSENT_SECONDS = 120
# In-memory requests; intentionally not persisted. Reconnect/reboot cancels consent.
_PENDING_BREAKS = {}
UPKEEP_INTERVAL = 5.0
UPKEEP_COST = 6
TIMED_SECONDS = 180
MIN_IMBUE = 50
MAX_IMBUE = 1000
MAX_IMBUED_SECONDS = 1800


def jutsu_entries():
    entries = {}
    for key, (level, cost, cooldown, _duration) in SEALS.items():
        entries[key] = _entry(key, level, cost, cooldown)
    for key, spec in BARRIERS.items():
        entries[key] = _entry(key, spec["level"], spec["cost"], spec["cooldown"])
    entries["summoning contract break"] = _entry(
        "summoning contract break", CONTRACT_BREAK_LEVEL, CONTRACT_BREAK_COST, CONTRACT_BREAK_COOLDOWN)
    return entries


def _entry(key, level, cost, cooldown):
    return {"jutsu_id": "whirlpool_" + key.replace(" ", "_"),
            "display_name": key.title(), "class_requirement": "general",
            "level_requirement": level, "chakra_cost": cost, "stamina_cost": 0,
            "cooldown": float(cooldown), "damage": None, "damage_type": None,
            "effect": None, "tier": 2 if level < 50 else 4,
            "element": "none", "jutsu_type": "whirlpool_seal",
            "required_village": "whirlpool", "required_clan": "uzumaki",
            "secret": True}


def eligible(player):
    return getattr(player, "village", "") == "whirlpool" and getattr(player, "clan", "") == "uzumaki"


def sync_skills(player):
    """Grant rank-appropriate arts, including older Whirlpool characters."""
    if not eligible(player):
        return []
    gained = []
    for key, info in jutsu_entries().items():
        name = info["display_name"]
        if player.level >= info["level_requirement"] and name not in player.learned_skills:
            player.learned_skills.append(name)
            player.skill_proficiencies[name] = 0
            gained.append(name)
    return gained


def _path():
    import storage
    return Path(storage.DATA_DIR) / "whirlpool_barriers.json"


def _load():
    path = _path()
    if not path.exists():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf8"))
        return loaded if isinstance(loaded, list) else []
    except (OSError, ValueError):
        # Fail closed for corrupted data: do not overwrite it automatically.
        return []


def _save(items):
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".barriers-")
    try:
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(items, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _playing_caster(name, sessions=None):
    if sessions is None:
        from session import ACTIVE_SESSIONS
        sessions = ACTIVE_SESSIONS
    return next((s for s in sessions if getattr(s, "player", None)
                 and s.player.name.casefold() == name.casefold()
                 and getattr(getattr(s, "state", None), "name", "") == "PLAYING"), None)


def _valid_wall(record, now, sessions=None):
    if record.get("expires_at", 0) <= now:
        return False
    if record.get("mode") == "upkeep" and not _playing_caster(record.get("caster", ""), sessions):
        return False
    # A builder may delete/repoint an exit while a wall is active. An old
    # wall may never unexpectedly block a completely different destination.
    import world
    room = world.WORLD.get(record.get("room"))
    return bool(room and room.exits.get(record.get("direction")) == record.get("destination"))


def current_barrier(room_vnum, direction, *, now=None, sessions=None):
    now = time.time() if now is None else now
    return next((r for r in _load()
                 if r.get("room") == room_vnum and r.get("direction") == direction
                 and _valid_wall(r, now, sessions)), None)


def check_movement(player, room_vnum, direction, *, now=None):
    """Return movement refusal or None; no chakra/stamina spent for denial."""
    record = current_barrier(room_vnum, direction, now=now)
    if record:
        return f"&RA glowing Whirlpool {record['mode']} seal blocks the {direction} exit.&x"
    return None


def is_active(player, key, *, now=None):
    entry = getattr(player, "active_status_effects", {}).get(key)
    if not entry:
        return False
    now = time.time() if now is None else now
    if entry.get("expires_at", now + 1) <= now:
        player.active_status_effects.pop(key, None)
        return False
    return True


def blocked_jutsu(player, jutsu, *, now=None):
    """Ninjutsu and genjutsu locks are independent; a hand-sign lock stops both."""
    category = jutsu.get("class_requirement")
    if is_active(player, "fuinjutsu_no_handsigns", now=now) and (
        category in ("ninjutsu", "genjutsu") or jutsu.get("jutsu_type") == "whirlpool_seal"):
        return "A Whirlpool binding prevents you from forming the necessary hand signs."
    if category == "ninjutsu" and is_active(player, "fuinjutsu_no_ninjutsu", now=now):
        return "A Whirlpool seal has shut down your ninjutsu for now."
    if category == "genjutsu" and is_active(player, "fuinjutsu_no_genjutsu", now=now):
        return "A Whirlpool seal has shut down your genjutsu for now."
    return None


def blocks_teleport(player, *, now=None):
    return is_active(player, "fuinjutsu_teleport_anchor", now=now)


def blocks_summoning(player, *, now=None):
    return is_active(player, "fuinjutsu_summon_locked", now=now)


def blocks_chakra_regen(player, *, now=None):
    return is_active(player, "fuinjutsu_chakra_locked", now=now)


def _target(session, words):
    query = " ".join(words).strip().casefold()
    if not query:
        other = getattr(session, "pvp_target", None)
        if other and other.player and other.player.room_vnum == session.player.room_vnum:
            return other
        return None
    matches = [s for s in session.active_sessions()
               if s is not session and s.player and s.player.room_vnum == session.player.room_vnum
               and query in s.player.name.casefold()]
    return matches[0] if len(matches) == 1 else None


def _ready(session, key, *, amount=None):
    player = session.player
    info = jutsu_entries()[key]
    if not eligible(player):
        session.send("Only ninja of the Whirlpool village's Uzumaki clan can use these fuinjutsu.")
        return False
    if player.level < info["level_requirement"] or info["display_name"] not in player.learned_skills:
        session.send("You have not learned this Whirlpool sealing art yet.")
        return False
    import skill_training
    if skill_training.needs_first_practice(player, info["display_name"]):
        session.send(f"Practice {info['display_name']} with a teacher once before using it.")
        return False
    now = time.time()
    if player.cooldowns.get(key, 0) > now:
        session.send(f"{info['display_name']} is recovering for {player.cooldowns[key] - now:.0f}s.")
        return False
    cost = info["chakra_cost"] if amount is None else amount
    if player.chakra < cost:
        session.send(f"You need {cost} chakra for this seal.")
        return False
    if getattr(session, "pending_cast", None) or getattr(session, "pending_action", None):
        session.send("You cannot inscribe a seal while already performing another action.")
        return False
    import status_effects
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You cannot channel chakra while silenced.")
        return False
    blocked = blocked_jutsu(player, info)
    if blocked:
        session.send(blocked)
        return False
    return True


def _pay(session, key, *, amount=None):
    info = jutsu_entries()[key]
    session.player.chakra -= info["chakra_cost"] if amount is None else amount
    session.player.cooldowns[key] = time.time() + info["cooldown"]
    import general_skills
    general_skills.break_camouflage(session)
    import combat
    combat.grow_skill_from_usage(session.player, info["display_name"])


def _cast_wall(session, key, words):
    import world
    import storage
    player = session.player
    if key == "multi exit barrier":
        _cast_multi_wall(session, words)
        return
    if key == "imbued barrier seal":
        if len(words) != 2 or not words[1].isdigit():
            session.send("Usage: perform imbued barrier seal <direction> <chakra 50-1000>")
            return
        amount = int(words[1])
        if not MIN_IMBUE <= amount <= MAX_IMBUE:
            session.send("Imbue between 50 and 1000 chakra.")
            return
    else:
        amount = None
        if len(words) != 1:
            session.send(f"Usage: perform {key} <direction>")
            return
    direction = world.normalize_direction(words[0])
    room = world.WORLD.get(player.room_vnum)
    destination = world.WORLD.get(room.exits.get(direction)) if room and direction else None
    if not room or not direction or not destination:
        session.send("A seal requires a real exit in that direction.")
        return
    if room.safe or destination.safe or room.reaper_prison or destination.reaper_prison:
        session.send("Sealing a safe area or soul prison's passage is forbidden.")
        return
    if not _ready(session, key, amount=amount):
        return
    now = time.time()
    existing = [record for record in _load() if _valid_wall(record, now)]
    if any(r["room"] == room.vnum and r["direction"] == direction for r in existing):
        session.send("A Whirlpool barrier already seals that exit.")
        return
    if sum(1 for r in existing if r["caster"].casefold() == player.name.casefold()) >= MAX_BARRIERS_PER_CASTER:
        session.send("You can maintain no more than three barriers at once. Use Seal Release to dismiss them.")
        return
    mode = BARRIERS[key]["mode"]
    # An upkeep barrier has no natural timer: only Chakra, logout,
    # the caster's remote release, or a builder changing the exit ends it.
    expiry = (1e20 if mode == "upkeep" else
              now + TIMED_SECONDS if mode == "timed" else
              now + min(MAX_IMBUED_SECONDS, amount * 3))
    new = {"caster": player.name, "room": room.vnum, "direction": direction,
           "destination": destination.vnum, "mode": mode, "expires_at": expiry,
           "next_upkeep_at": now + UPKEEP_INTERVAL,
           "imbued_chakra": amount or 0}
    _save(existing + [new])
    _pay(session, key, amount=amount)
    lifetime = ("as long as you remain online and maintain its chakra upkeep"
                if mode == "upkeep" else f"up to {int(expiry - now)} seconds")
    session.send(f"&CWhirlpool sealing script closes the {direction} exit for {lifetime}. "
                 "You may leave this room; the barrier remains.&x")
    session.broadcast_room(f"&CA spiral of fuinjutsu seals the {direction} exit!&x", exclude_self=True)
    storage.save_player(player)


def _cast_multi_wall(session, words):
    """One paid cast, 2-3 independent directional seals, persisted atomically."""
    import world
    import storage
    key = "multi exit barrier"
    if not 2 <= len(words) <= 3:
        session.send("Usage: perform multi exit barrier <direction1> <direction2> [direction3]")
        return
    directions = [world.normalize_direction(word) for word in words]
    if any(not d for d in directions) or len(set(directions)) != len(directions):
        session.send("Specify two or three different valid directions.")
        return
    player = session.player
    room = world.WORLD.get(player.room_vnum)
    if not room or room.safe or room.reaper_prison:
        session.send("You cannot seal exits from a safe area or soul prison.")
        return
    destinations = [world.WORLD.get(room.exits.get(d)) for d in directions]
    if any(d is None or d.safe or d.reaper_prison for d in destinations):
        session.send("Every selected exit must lead to a real, unprotected room.")
        return
    now = time.time()
    existing = [r for r in _load() if _valid_wall(r, now)]
    if any(r.get("room") == room.vnum and r.get("direction") in directions for r in existing):
        session.send("One of those exits is already sealed.")
        return
    owned = sum(r["caster"].casefold() == player.name.casefold() for r in existing)
    if owned + len(directions) > MAX_BARRIERS_PER_CASTER:
        session.send("You may only maintain three sealed exits at once. Release older barriers first.")
        return
    if not _ready(session, key):
        return
    records = [{"caster": player.name, "room": room.vnum,
                "direction": direction, "destination": dest.vnum,
                "mode": "timed", "expires_at": now + MULTI_EXIT_SECONDS,
                "next_upkeep_at": now + UPKEEP_INTERVAL, "imbued_chakra": 0}
               for direction, dest in zip(directions, destinations)]
    _save(existing + records)
    _pay(session, key)
    session.send("&CAn array of Whirlpool seals blocks " + ", ".join(directions)
                 + f" for {MULTI_EXIT_SECONDS} seconds. The seals persist after you leave or log out.&x")
    session.broadcast_room("&CA multiple-exit sealing array erupts across the passages!&x", exclude_self=True)
    storage.save_player(player)


def _player_in_room(session, name):
    """Exact names only: no partial-name consent ambiguities."""
    return next((s for s in session.active_sessions()
                 if s is not session and getattr(s, "player", None)
                 and getattr(getattr(s, "state", None), "name", "") == "PLAYING"
                 and s.player.room_vnum == session.player.room_vnum
                 and s.player.name.casefold() == name.casefold()), None)


def _break_is_valid(request, now):
    if now >= request["expires"]:
        return False
    caster = request["caster"]
    a, b = request["participants"]
    from session import ACTIVE_SESSIONS
    if any(s not in ACTIVE_SESSIONS or not s.player or s.state.name != "PLAYING"
           for s in (caster, a, b)):
        return False
    if any(s.player.room_vnum != request["room"] or s.combat_target or s.pvp_target
           or s.player.health <= 0 or getattr(s.player, "downed_by", None)
           for s in (caster, a, b)):
        return False
    import sage_mode
    return (eligible(caster.player)
            and all(sage_mode.chosen_contract(s.player) for s in (a, b))
            and tuple(s.player.name.casefold() for s in (a, b)) == request["names"]
            and tuple(sage_mode.chosen_contract(s.player) for s in (a, b)) == request["contracts"])


def _purge_expired_breaks(*, now=None):
    now = time.time() if now is None else now
    for caster, request in list(_PENDING_BREAKS.items()):
        if not _break_is_valid(request, now):
            del _PENDING_BREAKS[caster]
            for s in request["participants"]:
                if getattr(s, "player", None):
                    s.send("The summoning contract dissolution request has expired or been cancelled.")


def _request_contract_break(session, words):
    """The caster is a third party; never a consenting contract holder."""
    _purge_expired_breaks()
    if len(words) != 2 or words[0].casefold() == words[1].casefold():
        session.send("Usage: perform summoning contract break <player1> <player2>")
        return
    a, b = (_player_in_room(session, name) for name in words)
    if not a or not b or a is b:
        session.send("Two different contract holders must be present in your room.")
        return
    import sage_mode
    if not all(sage_mode.chosen_contract(s.player) for s in (a, b)):
        session.send("Both players must have a signed summoning contract.")
        return
    if any(s.combat_target or s.pvp_target for s in (session, a, b)):
        session.send("Everyone must be out of combat to dissolve a contract.")
        return
    if any(s in req["participants"] for req in _PENDING_BREAKS.values() for s in (a,b)):
        session.send("A participant already has a pending contract request.")
        return
    if session in _PENDING_BREAKS:
        session.send("You already have a pending contract dissolution request.")
        return
    if not _ready(session, "summoning contract break"):
        return
    request = {"caster": session, "participants": (a, b), "room": session.player.room_vnum,
               "approved": set(), "expires": time.time() + CONTRACT_CONSENT_SECONDS,
               "names": (a.player.name.casefold(), b.player.name.casefold()),
               "contracts": (sage_mode.chosen_contract(a.player), sage_mode.chosen_contract(b.player))}
    _PENDING_BREAKS[session] = request
    session.send(f"You ask {a.player.name} and {b.player.name} to consent to dissolving their own summoning contracts. No chakra charged yet.")
    for target in (a, b):
        target.send(f"&Y{session.player.name} offers to dissolve your summoning contract along with the contract of "
                    f"{(b if target is a else a).player.name}. This will dismiss your summon and end your Sage Mode, "
                    "and remove your current signed contract. Type 'yes' to approve or 'no' to decline (or use 'sealconsent yes/no') "
                    f"to decline within {CONTRACT_CONSENT_SECONDS} seconds.&x")


def has_pending_consent(session):
    _purge_expired_breaks()
    return any(session in req["participants"] for req in _PENDING_BREAKS.values())


def contract_consent(session, args):
    """Both target players must individually opt in; refusal is final."""
    _purge_expired_breaks()
    answer = args[0].lower() if len(args) == 1 else ""
    if answer not in {"yes", "no"}:
        session.send("Usage: sealconsent yes|no")
        return
    matches = [(caster, req) for caster, req in _PENDING_BREAKS.items() if session in req["participants"]]
    if not matches:
        session.send("You have no pending contract dissolution request.")
        return
    caster, req = matches[0]
    if answer == "no":
        del _PENDING_BREAKS[caster]
        caster.send(f"{session.player.name} declined. Neither contract was changed.")
        for person in req["participants"]:
            person.send("The contract dissolution has been cancelled. Your contract remains intact.")
        return
    req["approved"].add(session)
    session.send("You consent to the contract dissolution. " +
                 ("Waiting for the other player's approval." if len(req["approved"]) != 2 else "Both approvals received."))
    if len(req["approved"]) < 2:
        return
    del _PENDING_BREAKS[caster]
    if not _break_is_valid(req, time.time()) or not _ready(caster, "summoning contract break"):
        for person in req["participants"]:
            person.send("The contract dissolution could not complete; no contracts were changed.")
        return
    import combat
    import storage
    import sage_mode
    # No cost and no mutation before both unique, live approvals.
    _pay(caster, "summoning contract break")
    for person in req["participants"]:
        character = person.player
        contract = sage_mode.chosen_contract(character)
        combat.dismiss_summon(character)
        character.signed_summoning_contracts = []
        character.sage_active_contract = ""
        character.sage_preferred_contract = ""
        character.sage_mastery.pop(contract, None)
        character.sage_training_ready_at.pop(contract, None)
        storage.save_player(character)
        person.send(f"&YYour {contract.title()} summoning contract is dissolved by mutual agreement.&x")
    storage.save_player(caster.player)
    caster.send("&GThe two agreed summoning contracts are dissolved. Your own abilities are unchanged.&x")


def _release(session, words):
    import storage
    player = session.player
    if not words:
        session.send("Usage: perform seal release <self|player|barriers> (barriers dismisses your seals remotely)")
        return
    query = " ".join(words).strip().casefold()
    other = _target(session, words) if query not in {"barriers", "all", "self", "me"} else None
    if query in ("barriers", "all"):
        records = _load()
        owned = [r for r in records if r["caster"].casefold() == player.name.casefold()]
        if not owned:
            session.send("You have no barriers to release.")
            return
        if not _ready(session, "seal release"):
            return
        _save([r for r in records if r not in owned])
        _pay(session, "seal release")
        session.send(f"You release {len(owned)} of your barriers from afar.")
        storage.save_player(player)
        return
    target = player if query in {"self", "me"} else other.player if other else None
    if target is None:
        session.send("Name a player here, yourself, or 'barriers'.")
        return
    active = [k for k in ACTIVE_SEAL_KEYS.values() if is_active(target, k)]
    if not active:
        session.send("No Whirlpool suppression seals are active on that target.")
        return
    if not _ready(session, "seal release"):
        return
    for k in active:
        target.active_status_effects.pop(k, None)
    _pay(session, "seal release")
    session.send(f"You unravel {len(active)} suppression seals from {target.name}.")
    if other:
        other.send("&GWhirlpool seals unravel around you.&x")
    storage.save_player(player)
    if other:
        storage.save_player(target)


def cast(session, key, words):
    """Command dispatcher; all validation happens before charging chakra."""
    import status_effects
    import world
    if key == "summoning contract break":
        _request_contract_break(session, words)
        return
    if key in BARRIERS:
        _cast_wall(session, key, words)
        return
    if key == "seal release":
        _release(session, words)
        return
    target_session = _target(session, words)
    room = world.WORLD.get(session.player.room_vnum)
    if not target_session:
        session.send(f"Usage: perform {key} <player in this room> (or fight the player first)")
        return
    if room is None or room.safe or target_session.player.health <= 0:
        session.send("You cannot apply a hostile seal in a safe room or to a defeated player.")
        return
    if not _ready(session, key):
        return
    target = target_session.player
    duration = SEALS[key][3]
    effect_key = ACTIVE_SEAL_KEYS.get(key)
    if effect_key and is_active(target, effect_key):
        session.send(f"{target.name} is already under that seal.")
        return
    if key == "chakra siphon seal":
        drained = min(target.chakra, max(1, target.maximum_chakra // 5))
        _pay(session, key)
        target.chakra -= drained
        gain = min(drained // 2, session.player.maximum_chakra - session.player.chakra)
        session.player.chakra += gain
        session.send(f"&BYou siphon {drained} chakra from {target.name} and recover {gain}.&x")
        target_session.send(f"&RA Whirlpool siphoning formula steals {drained} of your chakra!&x")
    else:
        _pay(session, key)
        status_effects.apply_effect(target.active_status_effects, effect_key, source=session.player.name,
                                    duration_override=duration)
        target.active_status_effects[effect_key]["expires_at"] = time.time() + duration
        if key == "chakra lock seal" and target_session.chakra_charge is not None:
            target_session.chakra_charge = None
        session.send(f"&CYour {key.title()} takes hold of {target.name} for {duration} seconds.&x")
        target_session.send(f"&R{session.player.name}'s Whirlpool {key} binds your chakra for {duration} seconds!&x")
    import storage
    storage.save_player(session.player)
    storage.save_player(target)


def process_barriers(*, now=None, sessions=None):
    """Called each server pulse; running caster need not be in barrier room."""
    now = time.time() if now is None else now
    if sessions is None:
        from session import ACTIVE_SESSIONS
        sessions = ACTIVE_SESSIONS
    _purge_expired_breaks(now=now)
    existing = _load()
    active = []
    changed = False
    for record in existing:
        if not _valid_wall(record, now, sessions):
            changed = True
            continue
        if record["mode"] == "upkeep" and record.get("next_upkeep_at", 0) <= now:
            owner = _playing_caster(record["caster"], sessions)
            if not owner:
                changed = True
                continue
            # Late pulses do not allow unlimited retroactive free upkeep.
            payments = int((now - record["next_upkeep_at"]) // UPKEEP_INTERVAL) + 1
            cost = payments * UPKEEP_COST
            if owner.player.chakra < cost:
                owner.send("&RYour distant Whirlpool barrier dissolves as your chakra fails.&x")
                changed = True
                continue
            owner.player.chakra -= cost
            record["next_upkeep_at"] += payments * UPKEEP_INTERVAL
            changed = True
        active.append(record)
    if changed:
        _save(active)
