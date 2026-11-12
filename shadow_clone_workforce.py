"""Scroll-only Advanced Shadow Clone workforce.

One prepaid, room-bound worker per caster.  Work progress and acquired items
live on Player so logout/reboot cannot reset the clock or duplicate rewards.
Ordinary combat/elemental clones remain untouched.
"""
from __future__ import annotations

import random
import time

CHAKRA_PER_HALF_HOUR = 500
SECONDS_PER_CHAKRA = 1800.0 / CHAKRA_PER_HALF_HOUR
ACTION_SECONDS = 30.0
MIN_CHARGE = 100
JUTSU_KEY = "advanced shadow clone jutsu"
TASK_ALIASES = {"mine": "mining", "mining": "mining",
                "chop": "lumberjack", "lumberjack": "lumberjack",
                "fish": "fishing", "fishing": "fishing",
                "farm": "farming", "farming": "farming"}
# This list is intentionally exclusive: no smelting, cooking, crafting,
# weaponsmithing, armorsmithing or gem cutting may be delegated.
BASIC_TOOLS = {
    "mining": "a copper pickaxe",
    "lumberjack": "a copper axe",
    "fishing": "a kindling fishing rod",
    "farming": "a copper hoe",
}
ACTIVE_MOBS = {}


def _job_module(job):
    if job == "mining":
        import mining
        return mining, mining.PICKAXES, mining.can_mine_here, mining.attempt_mine
    if job == "lumberjack":
        import lumberjack
        return lumberjack, lumberjack.AXES, lumberjack.can_chop_here, lumberjack.attempt_chop
    if job == "fishing":
        import fishing
        return fishing, fishing.RODS, fishing.can_fish_here, fishing.attempt_catch
    if job == "farming":
        import farming
        return farming, farming.HOES, farming.can_farm_here, farming.attempt_farm
    raise ValueError("Only gathering professions may be delegated")


def _live(mob):
    import combat
    return mob is not None and mob.health > 0 and any(
        current is mob for current in combat.MOBS_BY_ROOM.get(mob.room_vnum, ()))


def _spawn(player):
    """Create a harmless room-local NPC, not a normal combat clone/summon."""
    import combat
    state = player.work_clone
    if not state:
        return
    owner = player.name.casefold()
    mob = ACTIVE_MOBS.get(owner)
    if _live(mob):
        return
    import world
    if not world.WORLD.get(state["room"]):
        return
    mob = combat.Mob(
        instance_id=-time.monotonic_ns(), template_vnum=-1000001,
        name=f"{player.name}'s working shadow clone",
        level=player.level, health=max(1, player.maximum_health // 4),
        max_health=max(1, player.maximum_health // 4),
        room_vnum=state["room"], experience_reward=0, ryo_reward=0,
        damage_dice="0d1+0", attacks=0, respawns=False, loot_items=[],
    )
    mob.work_clone_owner = player.name
    combat.MOBS_BY_ROOM.setdefault(mob.room_vnum, []).append(mob)
    ACTIVE_MOBS[owner] = mob


def _remove_mob(player):
    import combat
    mob = ACTIVE_MOBS.pop(player.name.casefold(), None)
    if mob is not None:
        room_mobs = combat.MOBS_BY_ROOM.get(mob.room_vnum, [])
        if mob in room_mobs:
            room_mobs.remove(mob)


def _training_skill(player, name):
    import data_jutsu
    import combat
    import skill_training
    for key, technique in data_jutsu.JUTSU.items():
        display = technique["display_name"]
        if name.casefold() not in (key.casefold(), display.casefold()):
            continue
        if (display not in player.learned_skills
                or technique.get("damage") is None
                or not combat._can_use_jutsu(player, technique, key)
                or skill_training.needs_first_practice(player, display)):
            return None
        return display
    return None


def _take_tool(player, job, query):
    """Validate a specific player-supplied tool before removing it."""
    import commands
    import jobs
    _module, choices, _biome, _attempt = _job_module(job)
    if not query:
        return "", BASIC_TOOLS[job]
    query = query.casefold().strip()
    candidates = []
    if player.equipment.get("tool"):
        candidates.append(("equipment", player.equipment["tool"]))
    candidates.extend(("inventory", item) for item in player.inventory)
    for location, item in candidates:
        if query not in item.casefold():
            continue
        base = commands.strip_crafted_suffix(item).casefold()
        spec = choices.get(base)
        if spec is None:
            continue
        if jobs.get_job_level(player, job) < spec["required_level"]:
            raise ValueError(f"That tool requires {job.capitalize()} level {spec['required_level']}.")
        import tool_durability
        if tool_durability.uses_left(item)[0] <= 0:
            raise ValueError("That tool is already broken.")
        if location == "equipment":
            # Work clones cannot duplicate a tool still held by their owner.
            commands._apply_equipment_stat_bonuses(player, item, sign=-1)
            del player.equipment["tool"]
        else:
            player.inventory.remove(item)
        return item, base
    raise ValueError("You must carry or hold a valid tool matching that name.")


def _split_request(args):
    """Accept 'mine 500 [with iron... ]' and 'train Rasengan 500'."""
    if not args:
        return None
    words = list(args)
    task = TASK_ALIASES.get(words[0].casefold())
    if task:
        if len(words) < 2 or not words[1].isdigit():
            return None
        tool_words = words[2:]
        if tool_words and tool_words[0].casefold() == "with":
            tool_words = tool_words[1:]
        return task, int(words[1]), "", " ".join(tool_words)
    if words[0].casefold() == "train" and len(words) >= 3 and words[-1].isdigit():
        return "train", int(words[-1]), " ".join(words[1:-1]), ""
    return None


def _message_status(session, state):
    remaining = max(0, int(state["ends_at"] - time.time()))
    mins, secs = divmod(remaining, 60)
    job = state["skill"] if state["task"] == "train" else state["task"]
    session.send(f"&CWorking clone: {job} in room {state['room']}. "
                 f"{mins}m {secs}s remaining; {state['funded']} Chakra committed; "
                 f"{len(state['items'])} item(s) gathered.&x")


def command(session, args):
    """Handler for PERFORM ADVANCED SHADOW CLONE JUTSU.

    The normal PERFORM pipeline resolves the learned scroll technique first.
    """
    import combat
    import data_jutsu
    import storage
    import world

    player = session.player
    if player is None:
        return
    if not args or args[0].casefold() in ("help", "?"):
        session.send("Syntax: PERFORM ADVANCED SHADOW CLONE JUTSU MINE|CHOP|FISH|FARM <chakra> [WITH <tool>]\n"
                     "        PERFORM ADVANCED SHADOW CLONE JUTSU TRAIN <known attack jutsu> <chakra>\n"
                     "        PERFORM ADVANCED SHADOW CLONE JUTSU STATUS|RETURN\n"
                     "500 Chakra = 30 real minutes; one worker, summoned at its work site.")
        return
    action = args[0].casefold()
    if action == "status":
        if player.work_clone:
            _message_status(session, player.work_clone)
        else:
            session.send("You have no active working clone.")
        return
    if action in ("return", "dismiss", "dispel"):
        if not player.work_clone:
            session.send("You have no working clone to recall.")
        else:
            finish(session, reason="recalled")
        return

    jutsu = data_jutsu.JUTSU[JUTSU_KEY]
    if not combat._can_use_jutsu(player, jutsu, JUTSU_KEY):
        session.send("You must learn Advanced Shadow Clone Jutsu from its scroll first.")
        return
    if player.level < jutsu["level_requirement"] and not combat._staff_testing_mangekyo(player):
        session.send(f"You must reach level {jutsu['level_requirement']} to use this advanced scroll jutsu.")
        return
    if (getattr(session, "combat_target", None) or getattr(session, "pvp_target", None)
            or getattr(session, "pending_cast", None) or session.is_busy()
            or player.health <= 0):
        session.send("You must be conscious, out of combat and free to summon a worker.")
        return
    if player.work_clone:
        session.send("You already have a working clone. Use 'perform advanced shadow clone jutsu status' or 'perform advanced shadow clone jutsu return'.")
        return
    parsed = _split_request(args)
    if not parsed:
        session.send("Use 'perform advanced shadow clone jutsu help' for the task and Chakra syntax.")
        return
    task, chakra, skill_query, tool_query = parsed
    if chakra < MIN_CHARGE:
        session.send(f"Commit at least {MIN_CHARGE} Chakra per work session.")
        return
    if chakra > player.chakra:
        session.send("You do not have enough Chakra to fund that many minutes.")
        return
    room = world.WORLD.get(player.room_vnum)
    if not room or not room.enabled:
        session.send("You cannot summon a working clone here.")
        return
    if task == "train":
        if not any(combat.is_training_dummy(m) for m in combat.mobs_in_room(room.vnum)):
            session.send("Summon a training clone in a room with a training dummy (mob vnum 6).")
            return
        skill = _training_skill(player, skill_query)
        if skill is None:
            session.send("Choose a known, currently usable attack jutsu to train at the dummy.")
            return
        tool, tool_base = "", ""
    else:
        import jobs
        _module, _tools, permitted, _attempt = _job_module(task)
        if not permitted(room.biome):
            session.send(f"This room's biome does not support {task}. Summon the clone at the work site.")
            return
        try:
            tool, tool_base = _take_tool(player, task, tool_query)
        except ValueError as exc:
            session.send(str(exc))
            return
        skill = ""
    now = time.time()
    player.chakra -= chakra
    player.work_clone = {
        "task": task, "skill": skill, "room": room.vnum,
        "started_at": now, "next_at": now + ACTION_SECONDS,
        "ends_at": now + chakra * SECONDS_PER_CHAKRA,
        "funded": chakra, "items": [], "xp": 0, "gains": 0,
        "tool": tool, "tool_base": tool_base,
    }
    _spawn(player)
    storage.save_player(player)
    session.send(f"&CYou summon one advanced shadow clone to {('practice ' + skill) if task == 'train' else task} "
                 f"here. It will work for {chakra * SECONDS_PER_CHAKRA / 60:g} real minutes "
                 f"before returning to you.&x")


def _work_step(session, state):
    player = session.player
    if state["task"] == "train":
        import data_jutsu
        import signature_moves
        skill = state["skill"]
        if skill not in player.learned_skills:
            return
        current = player.skill_proficiencies.get(skill, 0)
        cap = signature_moves.SIGNATURE_CAP if signature_moves.selected_name(player) == skill else 100
        if current >= cap:
            return
        # Match live combat's percentage curve: mastery gets harder with use.
        if random.randint(1, 100) <= cap - current:
            player.skill_proficiencies[skill] = current + 1
            state["gains"] += 1
            import elemental_mastery
            technique = next((j for j in data_jutsu.JUTSU.values()
                              if j["display_name"] == skill), None)
            if technique:
                elemental_mastery.record_use(player, technique)
        return

    import jobs
    import commands
    import tool_durability
    import gems
    task = state["task"]
    _module, _choices, _permitted, attempt = _job_module(task)
    tool = state["tool"]
    base = state["tool_base"] if tool else BASIC_TOOLS[task]
    if tool:
        updated = tool_durability.spend_use(tool)
        state["tool"] = updated or ""
        if updated is None:
            state["tool_base"] = BASIC_TOOLS[task]
            session.send("&YYour working clone's upgraded tool broke. It continues with basic gathering.&x")
    # The basic virtual tool is deliberate: workers need no purchased copper kit.
    result = attempt(jobs.get_job_level(player, task), base)
    if result["failed"]:
        return
    prototype = commands._find_object_prototype_by_name(result["name"])
    state["items"].append(prototype["short_desc"] if prototype else result["name"])
    state["xp"] += result["xp"]
    if task == "mining":
        bonus = gems.roll_bonus_gem()
        if bonus:
            gem_proto = commands._find_object_prototype_by_name(bonus[0])
            state["items"].append(gem_proto["short_desc"] if gem_proto else bonus[0])


def tick(session, now=None):
    """One-second pulse; catch up wall-clock work after offline sessions/reboot."""
    import storage
    state = getattr(session.player, "work_clone", {})
    if not state:
        return
    now = time.time() if now is None else now
    player = session.player
    current_mob = ACTIVE_MOBS.get(player.name.casefold())
    if current_mob is not None and not _live(current_mob):
        finish(session, reason="dispersed", now=now)
        return
    if current_mob is None:
        _spawn(player)
    deadline = min(now, state["ends_at"])
    changed = False
    steps = 0
    while state["next_at"] <= deadline and steps < 120:
        _work_step(session, state)
        state["next_at"] += ACTION_SECONDS
        changed = True
        steps += 1
    if state["next_at"] > state["ends_at"] and now >= state["ends_at"]:
        finish(session, reason="completed", now=now)
        return
    if changed:
        storage.save_player(player)
    if now >= state["ends_at"] and state["next_at"] > deadline:
        finish(session, reason="completed", now=now)


def _destination(player):
    """Apartment-owned storage if built, otherwise the owned base room."""
    import world
    import apartments
    base = getattr(player, "apartment_room_vnum", None)
    room = world.WORLD.get(base) if base is not None else None
    if room and room.apartment and room.owner == player.name:
        if apartments.owns_expansion_room(player, "storage"):
            storage = world.WORLD.get(apartments.expansion_room_vnum(base, "storage"))
            if storage and storage.owner == player.name and storage.apartment_room_type == "storage":
                # Storage room's ground_items is already player-backed and saved.
                return storage, True
        return room, True
    return world.WORLD.get(player.room_vnum), False


def finish(session, reason="completed", now=None):
    import inventory
    import jobs
    import storage
    import leveling
    import village_perks
    import world_autosave
    player = session.player
    state = player.work_clone
    if not state:
        return
    _remove_mob(player)
    # Clear and save first, so disconnects can never claim the same haul twice.
    player.work_clone = {}
    storage.save_player(player)
    destination, apartment = _destination(player)
    materials = list(state["items"])
    if state["tool"]:
        materials.append(state["tool"])
    delivered = dropped = 0
    for item in materials:
        if apartment and destination is not None:
            destination.ground_items.append(item)
            dropped += 1
        else:
            ok, _why = inventory.add_item(player.inventory, item)
            if ok:
                delivered += 1
            elif destination is not None:
                destination.ground_items.append(item)
                dropped += 1
    if dropped and destination is not None and not (
            destination.apartment_room_type == "storage" and apartment):
        world_autosave.mark_dirty()
    if state["task"] == "train":
        gained = state["gains"]
        if gained:
            before = player.experience
            messages = leveling.grant_experience(player, gained * 10)
            earned = max(0, player.experience - before)
            session.send(f"&CYour clone returns and reports {state['skill']}: "
                         f"+{gained}% mastery ({player.skill_proficiencies[state['skill']]}% total), "
                         f"+{earned} experience.&x")
            for message in messages:
                session.send(message)
        else:
            session.send(f"&CYour clone returns from training {state['skill']}; no mastery gains this session.&x")
    else:
        multiplied = int(state["xp"] * village_perks.xp_multiplier(player.village))
        before = jobs.get_job_xp(player, state["task"])
        messages = jobs.add_job_xp(player, state["task"], multiplied)
        earned = jobs.get_job_xp(player, state["task"]) - before
        session.send(f"&CYour working clone returns ({reason}) with {len(state['items'])} "
                     f"materials. {delivered} went into your inventory, {dropped} "
                     f"were dropped {'in your apartment' if apartment else 'at your feet'}. "
                     f"+{earned} {state['task'].capitalize()} XP.&x")
        for message in messages:
            session.send(message)
    session.send("&DThe advanced shadow clone dispels, sharing its experience with you.&x")
    storage.save_player(player)
