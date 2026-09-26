"""Non-damaging Genjutsu: disguises, apparent items, Chisei, and room sleep.

Illusory items are presentation state. They never enter real inventories or
ground items, so they cannot be equipped, sold, looted, or duplicated.
"""

import random
import time

import combat
import data_jutsu
import derived_stats
import status_effects

UTILITY_TYPES = {"disguise", "item_illusion", "item_decoy", "chisei", "room_sleep"}


def apparent_name(player):
    return getattr(player, "genjutsu_disguise", "") if getattr(player, "genjutsu_disguise_pulses", 0) > 0 else player.name


def displayed_items(player):
    """Only item names change; callers keep the underlying real item."""
    illusions = getattr(player, "genjutsu_item_illusions", {})
    return [illusions.get(item, {}).get("alias", item) for item in player.inventory]


def decoys_in_room(room_vnum):
    from session import ACTIVE_SESSIONS
    for s in ACTIVE_SESSIONS:
        if s.player:
            for decoy in s.player.genjutsu_decoys:
                if decoy.get("room_vnum") == room_vnum and decoy.get("pulses", 0) > 0:
                    yield decoy


def _target_in_room(session, query):
    from session import ACTIVE_SESSIONS
    import commands
    player = session.player
    for other in ACTIVE_SESSIONS:
        if (other is not session and other.player and
                other.player.room_vnum == player.room_vnum and
                query in other.player.name.lower() and
                not commands._is_invisible_player(other.player)):
            return other.player
    mob = combat.find_mob(player.room_vnum, query)
    if mob and not commands._is_invisible_mob(mob):
        return mob
    return None


def _item_argument(player, words):
    import commands
    query = " ".join(words)
    return commands.find_indexed_item(query, player.inventory) if query else None


def begin_cast(session, key, words):
    player = session.player
    jutsu = data_jutsu.JUTSU[key]
    kind = jutsu["jutsu_type"]
    if kind == "disguise" and not words and player.genjutsu_disguise:
        player.genjutsu_disguise = ""
        player.genjutsu_disguise_pulses = 0
        session.send("You release your Henge and return to your own appearance.")
        return
    if not combat._can_use_jutsu(player, jutsu, key):
        session.send("You haven't learned that Genjutsu.")
        return
    if combat._is_action_blocked(player) or status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You cannot form that Genjutsu right now.")
        return
    if session.pending_cast is not None:
        session.send("You're already forming hand signs for another jutsu!")
        return
    if time.time() < player.cooldowns.get(key, 0):
        session.send(f"{jutsu['display_name']} is still recovering.")
        return
    cost = round(jutsu["chakra_cost"] * (100 - derived_stats.chakra_control_cost_discount_percent(player.chakra_control)) / 100)
    if player.chakra < cost:
        session.send("You don't have enough chakra.")
        return

    payload = {"kind": kind, "room_vnum": player.room_vnum}
    if kind == "disguise":
        target = _target_in_room(session, " ".join(words).lower()) if words else None
        if target is None:
            session.send(f"Use: perform {key} <person in room>. Use it without a target to end your disguise.")
            return
        payload["target"] = target
    elif kind == "item_illusion":
        if "as" not in [word.lower() for word in words]:
            session.send("Use: perform kokohi arazu <carried item> as <apparent name>.")
            return
        split = [word.lower() for word in words].index("as")
        item = _item_argument(player, words[:split])
        alias = " ".join(words[split + 1:]).strip()
        if not item or not alias or len(alias) > 40 or not alias.replace(" ", "").isalnum():
            session.send("Choose a carried item and a name of up to 40 letters or numbers.")
            return
        payload.update(item=item, alias=alias)
    elif kind == "item_decoy":
        item = _item_argument(player, words)
        if not item:
            session.send("Use: perform niju kokohi arazu <carried item>.")
            return
        payload["item"] = item
    elif kind == "chisei":
        if status_effects.has_effect(player.active_status_effects, "chisei"):
            session.send("Chisei is already active.")
            return
    elif kind == "room_sleep":
        import world
        room = world.WORLD.get(player.room_vnum)
        hostile_mobs = [m for m in combat.mobs_in_room(player.room_vnum)
                        if m.health > 0 and not (combat.is_shadow_clone(m) or combat.is_shopkeeper(m)
                        or combat.is_teacher(m) or combat.is_gambler(m) or combat.is_immortal_mob(m))]
        from session import ACTIVE_SESSIONS
        hostile_players = [s for s in ACTIVE_SESSIONS if s is not session and s.player
                           and s.player.room_vnum == player.room_vnum and s.player.health > 0]
        if not hostile_mobs and (not hostile_players or (room and room.safe)):
            session.send("There are no eligible targets here.")
            return

    import commands
    if commands.has_silent_genjutsu(player):
        resolve_cast(session, key, payload)
    else:
        combat.begin_pending_cast(session, key, payload, is_pvp=False, start_combat_on_resolve=False)


def resolve_cast(session, key, payload):
    player = session.player
    jutsu = data_jutsu.JUTSU[key]
    kind = payload["kind"]
    if player.room_vnum != payload["room_vnum"]:
        session.send("Your illusion fades before it takes hold; you left the room.")
        return
    if kind == "disguise":
        target = payload["target"]
        if target is player or target.room_vnum != player.room_vnum or getattr(target, "health", 1) <= 0:
            session.send("That person is no longer here.")
            return
    if kind in ("item_illusion", "item_decoy") and payload["item"] not in player.inventory:
        session.send("You are no longer carrying that item.")
        return
    if kind == "chisei" and status_effects.has_effect(player.active_status_effects, "chisei"):
        session.send("Chisei is already active.")
        return
    cost = round(jutsu["chakra_cost"] * (100 - derived_stats.chakra_control_cost_discount_percent(player.chakra_control)) / 100)
    if player.chakra < cost or not combat._can_use_jutsu(player, jutsu, key):
        session.send("You can no longer complete that Genjutsu.")
        return
    player.chakra -= cost
    player.cooldowns[key] = time.time() + jutsu["cooldown"]

    if kind == "disguise":
        player.genjutsu_disguise = payload["target"].name
        player.genjutsu_disguise_pulses = jutsu["duration"]
        session.send(f"You assume the appearance of {player.genjutsu_disguise} for {jutsu['duration']} pulses.")
    elif kind == "item_illusion":
        player.genjutsu_item_illusions[payload["item"]] = {"alias": payload["alias"], "pulses": jutsu["duration"]}
        session.send(f"{payload['item']} now appears as {payload['alias']}; its real properties are unchanged.")
    elif kind == "item_decoy":
        player.genjutsu_decoys.append({"name": payload["item"], "room_vnum": player.room_vnum, "pulses": jutsu["duration"]})
        session.send(f"A false {payload['item']} appears on the ground. It cannot be taken or used.")
    elif kind == "chisei":
        bonus = max(20, 10 + player.intelligence // 2)
        player.chisei_chakra_bonus = bonus
        player.maximum_chakra += bonus
        player.chakra += bonus
        status_effects.apply_effect(player.active_status_effects, "chisei", source=key)
        session.send(f"Chisei sharpens your Genjutsu and grants {bonus} temporary maximum Chakra for six pulses.")
    elif kind == "room_sleep":
        import world
        from session import ACTIVE_SESSIONS
        room = world.WORLD.get(player.room_vnum)
        affected = 0
        for mob in list(combat.mobs_in_room(player.room_vnum)):
            if mob.health <= 0 or any((combat.is_shadow_clone(mob), combat.is_shopkeeper(mob),
                combat.is_teacher(mob), combat.is_gambler(mob), combat.is_immortal_mob(mob))):
                continue
            chance = max(25, min(85, 70 + (player.level - mob.level) * 2))
            if random.randint(1, 100) <= chance:
                status_effects.apply_effect(mob.active_status_effects, "asleep", source=key)
                affected += 1
        if not (room and room.safe):
            import data_kekkei_genkai
            for other in ACTIVE_SESSIONS:
                if (other is session or not other.player or other.player.room_vnum != player.room_vnum
                        or other.player.health <= 0):
                    continue
                chance = max(25, min(85, 70 + (player.level - other.player.level) * 2))
                if random.randint(1, 100) <= chance:
                    duration = 2
                    if data_kekkei_genkai.sharingan_genjutsu_resistant(other.player):
                        duration = data_kekkei_genkai.reduced_genjutsu_duration(duration)
                    status_effects.apply_effect(other.player.active_status_effects, "asleep", source=key, duration_override=duration)
                    other.send("Illusory feathers drift down; you fall asleep and cannot act!")
                    affected += 1
        session.send(f"Nehan Shōja sends {affected} target(s) to sleep; others resist the illusion.")
    combat.grow_skill_from_usage(player, jutsu["display_name"])


def tick_player(session):
    player = session.player
    if player.genjutsu_disguise_pulses > 0:
        player.genjutsu_disguise_pulses -= 1
        if player.genjutsu_disguise_pulses == 0:
            player.genjutsu_disguise = ""
            session.send("Your Henge wears off.")
    for item, state in list(player.genjutsu_item_illusions.items()):
        state["pulses"] -= 1
        if state["pulses"] <= 0 or item not in player.inventory:
            del player.genjutsu_item_illusions[item]
    for decoy in list(player.genjutsu_decoys):
        decoy["pulses"] -= 1
        if decoy["pulses"] <= 0:
            player.genjutsu_decoys.remove(decoy)
