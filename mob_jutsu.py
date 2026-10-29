"""Level/class-appropriate combat jutsu for ordinary NPCs.

This is deliberately a single-target combat attack, NOT a call into the
player's command interpreter. Special modes (reaper seals, instakills,
summons, KKG, room-wide jutsu, items and player-only utility skills)
must not be cast by generic mobs without dedicated NPC implementations.
"""
import random
import time

import data_jutsu
import damage_messages
import derived_stats
import mob_balance
import status_effects


MIN_LEVEL = 10
CAST_CHANCE_PERCENT = 30
GLOBAL_CAST_DELAY_SECONDS = 8.0

# A generic NPC can safely use damaging single-target jutsu; other
# jutsu types implement player-specific state or inventory requirements.
SIMPLE_JUTSU_TYPES = frozenset((None, "attack", "ambush", "thrown", "blade_strike"))


def available_jutsu(mob, now=None):
    """Only damaging arts this mob's class, level, nature and pools permit."""
    if mob.level < MIN_LEVEL or mob.primary_class not in (
            "ninjutsu", "taijutsu", "genjutsu", "bukijutsu"):
        return []
    now = time.time() if now is None else now
    found = []
    for key, art in data_jutsu.JUTSU.items():
        if art.get("class_requirement") not in (mob.primary_class, "general"):
            continue
        if art.get("level_requirement", 251) > mob.level:
            continue
        if art.get("damage") is None or art.get("jutsu_type") not in SIMPLE_JUTSU_TYPES:
            continue
        if (art.get("kkg_gate") or art.get("scroll_only")
                or art.get("required_village") or art.get("requires_item")
                or art.get("requires_item_count")
                or art.get("required_weapon") or art.get("requires_weapon")
                or (art.get("requires_water") and mob.chakra_nature != "water")):
            continue
        weapon_types = art.get("required_weapon_types")
        if weapon_types:
            import data_weapons
            if data_weapons.weapon_type_for_item(mob.equipment.get("wielded", "")) not in weapon_types:
                continue
        element = art.get("element", "none")
        if element not in ("none", None) and element != mob.chakra_nature:
            continue
        if mob.chakra < art.get("chakra_cost", 0) or mob.stamina < art.get("stamina_cost", 0):
            continue
        if now < mob.jutsu_cooldowns.get(key, 0):
            continue
        found.append((key, art))
    return found


def try_cast(session, mob):
    """Attempt one spell instead of a physical attack. Returns True if cast.

    The NPC can spend at most one spell action per 8 real seconds, even
    when several player sessions fight it simultaneously. Successful
    cast attempts spend resources whether the spell hits or misses.
    """
    player = session.player
    if (mob.level < MIN_LEVEL or mob.health <= 0 or player.health <= 0
            or mob.room_vnum != player.room_vnum
            or getattr(mob, "shadow_clone_owner", None)
            or getattr(mob, "summon_owner", None)
            or getattr(mob, "player_shop_owner", None)):
        return False
    now = time.time()
    if now < mob.next_jutsu_at or random.randint(1, 100) > CAST_CHANCE_PERCENT:
        return False
    choices = available_jutsu(mob, now)
    if not choices:
        return False

    import combat
    import sage_mode
    import weather
    import commands

    key, art = random.choice(choices)
    mob.chakra -= art.get("chakra_cost", 0)
    mob.stamina -= art.get("stamina_cost", 0)
    mob.jutsu_cooldowns[key] = now + max(0, float(art.get("cooldown", 0)))
    mob.next_jutsu_at = now + GLOBAL_CAST_DELAY_SECONDS

    name = art["display_name"]
    hit_roll = derived_stats.hit_roll(mob) + commands.equipped_weapon_hitroll_bonus(mob)
    player_armor = (derived_stats.armor_class(player, commands.equipped_set_bonus_percent(player))
                    - commands.equipped_armor_class_bonus(player))
    chance = derived_stats.to_hit_chance(hit_roll, player_armor)
    chance += weather.combat_accuracy_modifier() - combat._accuracy_penalty_from_effects(mob)
    chance = max(derived_stats.TO_HIT_MIN_PCT,
                 min(derived_stats.TO_HIT_MAX_PCT, chance))
    if random.randint(1, 100) > chance:
        session.send(f"&C{mob.name} uses {name}, but the jutsu misses you!&x")
        return True

    if player.kamui_intangibility_rounds_left > 0:
        player.kamui_intangibility_rounds_left -= 1
        session.send(f"&C{mob.name}'s {name} passes straight through your Kamui!&x")
        return True
    dodge = (derived_stats.dodge_chance(player)
             + weather.night_dodge_bonus()
             + combat._sharingan_dodge_bonus(player)
             + combat.hyuga.dodge(player))
    if random.randint(1, 100) <= max(0, dodge):
        session.send(f"&CYou dodge {mob.name}'s {name}!&x")
        return True
    if art["class_requirement"] == "taijutsu" and combat._soto_uke_blocks(player, mob.level):
        session.send(f"&CYou counter {mob.name}'s {name} with Soto Uke!&x")
        return True

    damage, _ = combat.roll_jutsu_damage(art)
    # Player jutsu damage scales to a very high ladder; generic NPC
    # jutsu instead use the shared mob difficulty curve, at up to
    # twice this level's expected normal hit so battles remain playable.
    if art.get("jutsu_type") == "ambush":
        damage = max(1, round(damage * art.get("ambush_multiplier", 1.0)))
    damage = min(damage, max(5, mob_balance.target_damage_for_level(mob.level) * 2))
    if player.sharingan_active and player.bloodline_tomoe >= 3:
        damage = combat._sharingan_predict_and_reduce_damage(player, damage)
    damage = status_effects.reduce_outgoing_damage(mob.active_status_effects, damage)
    damage = sage_mode.incoming(
        player, status_effects.reduce_incoming_damage(player.active_status_effects, damage))
    damage = max(1, damage)
    player.health -= damage
    session.send(f"&R{mob.name} unleashes {name} for {damage_messages.describe_damage(damage)} damage!&x")

    effect = art.get("effect")
    if effect in status_effects.EFFECT_DEFS and random.randint(1, 100) <= art.get("effect_chance_pct", 100):
        genjutsu = art.get("class_requirement") == "genjutsu"
        if genjutsu and status_effects.willpower_resists(player):
            session.send("&CYour Willpower repels the Genjutsu's lingering effect!&x")
        else:
            duration = (status_effects.genjutsu_duration(effect)
                        if genjutsu else status_effects.EFFECT_DEFS[effect]["duration"])
            status_effects.apply_effect(
                player.active_status_effects, effect, source=mob.name,
                duration_override=duration, genjutsu=genjutsu)
            msg = status_effects.EFFECT_DEFS[effect].get("message")
            if msg:
                session.send(f"&R{msg.format(target='You')}&x")

    if player.health <= 0:
        if combat.try_trigger_izanagi(session):
            pass
        elif combat.is_immortal_immune_to_defeat(session):
            combat.clamp_immortal_health(session)
        else:
            combat.handle_player_defeat(session)
    elif (player.wimpy_percent > 0 and player.maximum_health > 0
          and player.health / player.maximum_health * 100 <= player.wimpy_percent):
        session.send(f"&Y(Your health has dropped to your wimpy threshold of {player.wimpy_percent}%!)&x")
        commands.cmd_flee(session, [])
    return True
