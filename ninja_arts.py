"""Item-bound Ninja Arts and delayed trap helpers.

The game's inventory stores item names, so an art is recorded in a suffix on
the individual item. This survives ordinary inventory/equipment save, pickup,
and trade without applying the effect to every copy of a prototype.
"""

import random
import time

import data_jutsu
import data_weapons
import status_effects
import world

PROPERTIES = ("flaming", "frost", "life", "sharp", "vorpal", "shocking", "poison")
TRAPS = {
    "exploding note": (28, 46, None),
    "smoke bomb": (5, 12, "blinded"),
    "poison gas bomb": (12, 23, "poisoned"),
    "exploding clay": (45, 70, None),
}


def property_of(item):
    for prop in PROPERTIES:
        if item.lower().endswith(" [art:" + prop + "]"):
            return prop
    return None


def base_item(item):
    prop = property_of(item)
    return item[:-(len(prop) + 7)] if prop else item


def _owned_item(player, query):
    query = query.lower()
    for item in player.inventory:
        if query in base_item(item).lower():
            return item
    return None


def _pay(session, key):
    player = session.player
    jutsu = data_jutsu.JUTSU[key]
    combat = __import__("combat")
    if combat._is_action_blocked(player):
        session.send("You are unable to act!")
        return False
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use Ninja Arts right now!")
        return False
    if not combat._can_use_jutsu(player, jutsu, key):
        session.send("You don't know that technique or lack its required element.")
        return False
    if time.time() < player.cooldowns.get(key, 0):
        session.send("That technique is still recovering.")
        return False
    if player.chakra < jutsu["chakra_cost"] or player.stamina < jutsu["stamina_cost"]:
        session.send("You need more chakra or stamina.")
        return False
    player.chakra -= jutsu["chakra_cost"]
    player.stamina -= jutsu["stamina_cost"]
    player.cooldowns[key] = time.time() + jutsu["cooldown"]
    combat.grow_skill_from_usage(player, jutsu["display_name"])
    return True


def use_weapon_art(session, key, args):
    player = session.player
    if key == "water release: glue technique":
        item = _owned_item(player, " ".join(args)) if args else None
        pot = _owned_item(player, "pot of glue")
        if not item or not pot or item == pot:
            session.send("Carry a pot of glue and specify an item to glue to yourself.")
            return
        if item.endswith(" [glued]"):
            session.send("That item is already glued to you.")
            return
        if not _pay(session, key):
            return
        player.inventory.remove(pot)
        player.inventory[player.inventory.index(item)] = item + " [glued]"
        session.send(f"You glue {item} to yourself; it cannot be dropped or traded.")
        return
    if key == "weapon enchantment":
        if len(args) < 2 or args[-1].lower() not in PROPERTIES[:-1]:
            session.send("Usage: weapon enchantment <weapon> <flaming|frost|life|sharp|vorpal|shocking>")
            return
        prop = args[-1].lower()
        query = " ".join(args[:-1])
    else:
        prop = "poison" if key == "toxin binding" else None
        query = " ".join(args)
    item = _owned_item(player, query) if query else None
    # Wielding removes the real item from inventory. Weapon arts should still
    # be usable on that same item without making the player unequip it first.
    wielded = player.equipment.get("wielded", "")
    if not item and query and query.lower() in base_item(wielded).lower():
        item = wielded
    if not item or not data_weapons.weapon_type_for_item(base_item(item)):
        session.send("Specify a weapon in your inventory.")
        return
    old = property_of(item)
    if key == "disenchantment" and not old:
        session.send("That weapon has no Ninja Art property to remove.")
        return
    if key != "disenchantment" and old:
        session.send("That weapon is already bound. Disenchant it first.")
        return
    if not _pay(session, key):
        return
    updated = base_item(item) + (f" [art:{prop}]" if prop else "")
    if item in player.inventory:
        player.inventory[player.inventory.index(item)] = updated
    else:
        player.equipment["wielded"] = updated
    session.send(f"{base_item(item)} is now {'disenchanted' if prop is None else 'permanently bound to ' + prop}.")


def use_disable(session, target):
    effects = target.active_status_effects
    names = [name for name in TRAPS if name in effects]
    if not names:
        session.send("That target has no attached traps to disable.")
        return
    if not _pay(session, "trap disabling"):
        return
    if random.randint(1, 100) <= max(25, session.player.skill_proficiencies.get("Trap Disabling", 0)):
        for name in names:
            effects.pop(name, None)
        session.send("You safely disable the attached trap(s).")
    else:
        session.send("You fumble the trap! It detonates against you.")
        for name in names:
            effects.pop(name, None)
            lo, hi, effect = TRAPS[name]
            session.player.health = max(1, session.player.health - random.randint(lo, hi))
            if effect:
                status_effects.apply_effect(session.player.active_status_effects, effect, source=name)


def use_samurai_sabre(session):
    """Flow chakra through a wielded sword for five effect pulses."""
    if data_weapons.weapon_type_for_item(session.player.equipment.get("wielded", "")) != "sword":
        session.send("Wield a sword to use Samurai Sabre.")
        return
    if not _pay(session, "samurai sabre"):
        return
    status_effects.apply_effect(session.player.active_status_effects, "samurai_sabre", source="samurai sabre")
    session.send("&CChakra envelops your sword. Sword strikes deal 20% more damage for five pulses.&x")


def attach_trap(target, key, attacker_name):
    effects = target.active_status_effects
    if key in effects:
        return False
    effects[key] = {"duration": 2, "source": attacker_name}
    return True


def detonate_trap(target, name):
    lo, hi, effect = TRAPS[name]
    damage = random.randint(lo, hi)
    damage = status_effects.reduce_incoming_damage(target.active_status_effects, damage)
    target.health = max(0, target.health - damage)
    if effect:
        status_effects.apply_effect(target.active_status_effects, effect, source=name)
    return damage


def weapon_hit(attacker, victim, damage):
    """Apply the wielded weapon's item-specific combat property on hit."""
    wielded = attacker.equipment.get("wielded", "")
    prop = property_of(wielded)
    if damage > 0 and "samurai_sabre" in attacker.active_status_effects and data_weapons.weapon_type_for_item(base_item(wielded)) == "sword":
        damage = max(1, damage * 120 // 100)
    if prop is None or damage <= 0:
        return damage
    if prop == "poison" and random.randint(1, 100) <= 30:
        status_effects.apply_effect(victim.active_status_effects, "poisoned", source="toxin binding")
    elif prop == "flaming" and random.randint(1, 100) <= 25:
        status_effects.apply_effect(victim.active_status_effects, "burning", source="weapon enchantment")
    elif prop == "frost" and random.randint(1, 100) <= 25:
        status_effects.apply_effect(victim.active_status_effects, "off_balance", source="weapon enchantment")
    elif prop == "shocking" and random.randint(1, 100) <= 20:
        status_effects.apply_effect(victim.active_status_effects, "stunned", source="weapon enchantment")
    elif prop == "life":
        attacker.health = min(getattr(attacker, "maximum_health", getattr(attacker, "max_health", 1)), attacker.health + max(1, damage // 10))
    elif prop == "sharp":
        return damage + max(1, damage // 10)
    elif prop == "vorpal":
        return damage + max(1, damage // 6)
    return damage


def fan_push(session, target, direction, target_session=None):
    """Drive a target through a real open exit; never bypass doors or hidden exits."""
    room = world.WORLD.get(target.room_vnum)
    if not room or direction not in room.exits or world.WORLD.get(room.exits[direction]) is None:
        session.send("The slicing wind strikes, but there is nowhere to push the target.")
        return False
    flags = room.exit_flags.get(direction, [])
    if "hidden" in flags or ("door" in flags and not room.exit_door_open.get(direction, False)):
        session.send("The gust cannot carry the target through that exit.")
        return False
    old = target.room_vnum
    target.room_vnum = room.exits[direction]
    if target_session:
        if session.pvp_target is target_session:
            session.pvp_target = None
        if target_session.pvp_target is session:
            target_session.pvp_target = None
        target_session.send(f"&CThe fan's gust sends you {direction}!&x")
    else:
        import combat
        if target in combat.MOBS_BY_ROOM.get(old, []):
            combat.MOBS_BY_ROOM[old].remove(target)
            combat.MOBS_BY_ROOM.setdefault(target.room_vnum, []).append(target)
        if session.combat_target is target:
            session.combat_target = None
    session.send(f"&CThe fan's gust sends {target.name} {direction}!&x")
    return True
