"""Item-bound Ninja Arts and delayed trap helpers.

The game's inventory stores item names, so an art is recorded in a suffix on
the individual item. This survives ordinary inventory/equipment save, pickup,
and trade without applying the effect to every copy of a prototype.
"""

import jutsu_colors
import random
import time

import data_jutsu
import jutsu_balance
import data_weapons
import status_effects
import world
import samurai_sabre_progression

PROPERTIES = ("flaming", "frost", "life", "sharp", "vorpal", "shocking", "poison")
# Permanent *item-bound* chakra imbuements use the same inventory/equipment
# name persistence as older Ninja Arts, not per-character or prototype state.
ELEMENTAL_WEAPON_JUTSU = {
    "fire": "fireball jutsu", "water": "water dragon jutsu",
    "wind": "wind blade jutsu", "lightning": "lightning strike jutsu",
    "earth": "earth wall crusher",
}
ELEMENTAL_WEAPON_DAMAGE_PERCENT = 50
EARTH_SWORD_IMPACT_PERCENT = 25  # Earth Wall Crusher: greater direct damage, no status

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


def element_of(item):
    """Identify a permanent single-element sword enchantment, if any."""
    if not item:
        return None
    for element in ELEMENTAL_WEAPON_JUTSU:
        if item.lower().endswith(f" [element:{element}]"):
            return element
    return None


def base_item(item):
    element = element_of(item)
    if element:
        return item[:-len(f" [element:{element}]")]
    prop = property_of(item)
    return item[:-(len(prop) + 7)] if prop else item


def is_chakra_steel_weapon(item: str) -> bool:
    """Only a *genuinely forged* Chakra Steel weapon is enchantable.

    Item names are player-controlled. Never trust the displayed name or an
    appended suffix as proof of materials. Match the exact saved item
    prototype first and inspect its original crafting record. Legacy
    forged prototypes used only a generated description; accept that
    canonical format for existing saved weapons. A developer-made item
    can also declare explicit material provenance on its own prototype.
    """
    import olc
    original_name = base_item(item)
    if not original_name:
        return False
    for proto in olc.OBJECT_TEMPLATES.values():
        if proto.get("short_desc", "").casefold() != original_name.casefold():
            continue
        if proto.get("item_type") != "weapon" or proto.get("weapon_type") not in data_weapons.WEAPON_TYPES:
            return False
        materials = proto.get("craft_materials")
        if isinstance(materials, (tuple, list)) and materials:
            return "chakra steel ingot" in {str(x).casefold() for x in materials}
        description = str(proto.get("description", "")).casefold()
        # Only the specific canonical forging statement, not a player's
        # custom display name or description with incidental keywords.
        import re
        legacy = re.fullmatch(
            r"a crafted weapon named .+, forged from ([a-z ]+) and ([a-z ]+)\.",
            description,
        )
        return bool(legacy and "chakra steel ingot" in legacy.groups())
    return False


def _known_elements(player):
    """Only the player's revealed, owned natures may be used for enchanting."""
    return {nature for nature, revealed in (
        (getattr(player, "chakra_nature", None), getattr(player, "chakra_nature_revealed", False)),
        (getattr(player, "chakra_nature_secondary", None), getattr(player, "chakra_nature_secondary_revealed", False)),
        (getattr(player, "chakra_nature_tertiary", None), getattr(player, "chakra_nature_tertiary_revealed", False)),
    ) if revealed and nature in ELEMENTAL_WEAPON_JUTSU}


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
    chakra_cost = jutsu_balance.cast_cost(player, jutsu, "chakra")
    stamina_cost = jutsu_balance.cast_cost(player, jutsu, "stamina")
    if player.chakra < chakra_cost or player.stamina < stamina_cost:
        session.send("You need more chakra or stamina.")
        return False
    player.chakra -= chakra_cost
    player.stamina -= stamina_cost
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
        available = "flaming|frost|life|sharp|vorpal|shocking|fire|water|wind|lightning|earth"
        if len(args) < 2 or args[-1].lower() not in (*PROPERTIES[:-1], *ELEMENTAL_WEAPON_JUTSU):
            session.send(f"Usage: weapon enchantment <weapon> <{available}>")
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
    element = element_of(item)
    if key == "disenchantment" and not (old or element):
        session.send("That weapon has no Ninja Art property to remove.")
        return
    if key != "disenchantment" and (old or element):
        session.send("That weapon is already bound. Disenchant it first.")
        return
    is_elemental = prop in ELEMENTAL_WEAPON_JUTSU
    if is_elemental:
        if player.primary_class != "bukijutsu":
            session.send("Only Bukijutsu users can imbue elemental weapons.")
            return
        if not is_chakra_steel_weapon(item):
            session.send("Elemental enchantments require a weapon forged with a Chakra Steel Ingot.")
            return
        if prop not in _known_elements(player):
            session.send("You must first discover and possess that chakra nature to enchant a sword with it.")
            return
    if not _pay(session, key):
        return
    suffix = f" [element:{prop}]" if is_elemental else f" [art:{prop}]" if prop else ""
    updated = base_item(item) + suffix
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
    """Toggle an ongoing chakra edge on a wielded sword."""
    player = session.player
    if player.samurai_sabre_active:
        import upkeep_reports
        for message in upkeep_reports.flush(player, "Samurai Sabre"):
            session.send(message)
        upkeep_reports.stop_maintaining(player, "Samurai Sabre")
        player.samurai_sabre_active = False
        jutsu_colors.send(session, "&CYou release Samurai Sabre's chakra edge.&x")
        return
    if data_weapons.weapon_type_for_item(base_item(player.equipment.get("wielded", ""))) != "sword":
        jutsu_colors.send(session, "Wield a sword to use Samurai Sabre.")
        return
    if not _pay(session, "samurai sabre"):
        return
    player.active_status_effects.pop("samurai_sabre", None)
    player.samurai_sabre_active = True
    bonus = samurai_sabre_progression.damage_bonus_percent(player)
    jutsu_colors.send(session, f"&CChakra envelops your sword. Sword strikes deal {bonus}% more damage while you sustain Samurai Sabre. Use it again to turn it off.&x")


SABRE_IDLE_CHAKRA_UPKEEP = 4
SABRE_COMBAT_CHAKRA_UPKEEP = 6
SABRE_COMBAT_STAMINA_UPKEEP = 2


def tick_samurai_sabre(session, combat=False):
    """Charge while active; return whether player-visible output was sent."""
    player = session.player
    if not player.samurai_sabre_active:
        return False
    import upkeep_reports
    if data_weapons.weapon_type_for_item(base_item(player.equipment.get("wielded", ""))) != "sword":
        for message in upkeep_reports.flush(player, "Samurai Sabre"):
            session.send(message)
        upkeep_reports.stop_maintaining(player, "Samurai Sabre")
        player.samurai_sabre_active = False
        jutsu_colors.send(session, "&YSamurai Sabre fades when you stop wielding a sword.&x")
        return True
    chakra = SABRE_COMBAT_CHAKRA_UPKEEP if combat else SABRE_IDLE_CHAKRA_UPKEEP
    stamina = SABRE_COMBAT_STAMINA_UPKEEP if combat else 0
    if player.chakra < chakra or player.stamina < stamina:
        for message in upkeep_reports.flush(player, "Samurai Sabre"):
            session.send(message)
        upkeep_reports.stop_maintaining(player, "Samurai Sabre")
        player.samurai_sabre_active = False
        jutsu_colors.send(session, "&YYou can no longer sustain Samurai Sabre.&x")
        return True
    player.chakra -= chakra
    player.stamina -= stamina
    messages = upkeep_reports.record(player, "Samurai Sabre", chakra, stamina)
    for message in messages:
        session.send(message)
    upkeep_reports.maintain_skill(player, "Samurai Sabre")
    return bool(messages)


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


def _enchantment_feedback(session, message, *, target_session=None, target_message=None):
    """A small combat line only after a weapon effect really activates."""
    if session is not None:
        session.send(f"&C{message}&x")
    if target_session is not None and target_message:
        target_session.send(f"&R{target_message}&x")


def weapon_hit(attacker, victim, damage, *, session=None, target_session=None):
    """Apply a weapon property to a landed hit and report successful procs.

    This remains callable without a session by tests or other combat helpers.
    Only the live combat callers supply session, so no effect is announced on
    a miss or when a non-matching elemental wielder cannot activate the art.
    """
    wielded = attacker.equipment.get("wielded", "")
    prop = property_of(wielded)
    sabre_bonus = samurai_sabre_progression.damage_bonus_percent(attacker)
    if damage > 0 and sabre_bonus:
        damage = max(1, damage * (100 + sabre_bonus) // 100)
    element = element_of(wielded)
    # The elemental bonus is usable only by a Bukijutsu wielder whose
    # own revealed chakra nature matches the enchantment.
    if (damage > 0 and element and getattr(attacker, "primary_class", None) == "bukijutsu"
            and element in _known_elements(attacker)
            and is_chakra_steel_weapon(wielded)):
        damage = max(1, damage * (100 + ELEMENTAL_WEAPON_DAMAGE_PERCENT) // 100)
        jutsu = data_jutsu.JUTSU[ELEMENTAL_WEAPON_JUTSU[element]]
        effect = jutsu.get("effect")
        if element == "earth":
            damage = max(1, damage * (100 + EARTH_SWORD_IMPACT_PERCENT) // 100)
            _enchantment_feedback(session, f"Earth chakra crashes into {victim.name}!")
        elif effect and random.randint(1, 100) <= jutsu.get("effect_chance_pct", 0):
            status_effects.apply_effect(
                victim.active_status_effects, effect,
                source=f"{element} chakra weapon")
            messages = {
                "fire": f"Your blade ignites {victim.name}!",
                "water": f"Water chakra drains {victim.name}!",
                "wind": f"Wind chakra throws {victim.name} off balance!",
                "lightning": f"Lightning chakra paralyzes {victim.name}!",
            }
            target_messages = {
                "fire": f"{attacker.name}'s enchanted weapon sets you ablaze!",
                "water": f"{attacker.name}'s enchanted weapon drains your chakra!",
                "wind": f"{attacker.name}'s enchanted weapon throws you off balance!",
                "lightning": f"{attacker.name}'s enchanted weapon paralyzes you!",
            }
            _enchantment_feedback(session, messages.get(element, f"{element.title()} chakra strikes {victim.name}!"),
                                  target_session=target_session, target_message=target_messages.get(element))
        return damage
    if prop is None or damage <= 0:
        return damage
    if prop == "poison" and random.randint(1, 100) <= 30:
        status_effects.apply_effect(victim.active_status_effects, "poisoned", source="toxin binding")
        _enchantment_feedback(session, f"Your poisoned blade poisons {victim.name}!",
                              target_session=target_session,
                              target_message=f"{attacker.name}'s poisoned weapon infects you!")
    elif prop == "flaming" and random.randint(1, 100) <= 25:
        status_effects.apply_effect(victim.active_status_effects, "burning", source="weapon enchantment")
        _enchantment_feedback(session, f"Your enchanted blade burns {victim.name}!",
                              target_session=target_session,
                              target_message=f"{attacker.name}'s burning enchantment ignites you!")
    elif prop == "frost" and random.randint(1, 100) <= 25:
        status_effects.apply_effect(victim.active_status_effects, "off_balance", source="weapon enchantment")
        _enchantment_feedback(session, f"Frost chills {victim.name}, throwing them off balance!",
                              target_session=target_session,
                              target_message=f"{attacker.name}'s frost enchantment throws you off balance!")
    elif prop == "shocking" and random.randint(1, 100) <= 20:
        status_effects.apply_effect(victim.active_status_effects, "stunned", source="weapon enchantment")
        _enchantment_feedback(session, f"Your weapon shocks and stuns {victim.name}!",
                              target_session=target_session,
                              target_message=f"{attacker.name}'s shocking enchantment stuns you!")
    elif prop == "life":
        maximum = getattr(attacker, "maximum_health", getattr(attacker, "max_health", 1))
        old_health = attacker.health
        attacker.health = min(maximum, attacker.health + max(1, damage // 10))
        healed = attacker.health - old_health
        if healed > 0:
            _enchantment_feedback(session, f"Your blade drains {healed} HP from {victim.name}!")
    elif prop == "sharp":
        bonus = max(1, damage // 10)
        _enchantment_feedback(session, f"Your sharp enchantment cuts {victim.name} deeper!")
        return damage + bonus
    elif prop == "vorpal":
        bonus = max(1, damage // 6)
        _enchantment_feedback(session, f"Your vorpal enchantment cuts into {victim.name}!")
        return damage + bonus
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
