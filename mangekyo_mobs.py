"""Mob targets and owner-controlled Amaterasu for Mangekyo techniques."""

import random
import time

import combat
import data_jutsu
import data_mangekyo
import jutsu_colors
import mangekyo
import mangekyo_discovery
import status_effects
import world

TARGETED = {"amaterasu", "tsukuyomi", "izanami", "kamui pocket dimension", "kamui limb removal"}
DELAYED = {"amaterasu", "tsukuyomi", "izanami", "kamui limb removal"}


def cast(session, key, mob):
    """Start a Mangekyo cast against an attackable mob in this room."""
    player = session.player
    jutsu = data_jutsu.JUTSU[key]
    if not combat._can_use_jutsu(player, jutsu, key):
        jutsu_colors.send(session, "You haven't learned that skill or jutsu.")
        return
    if combat.is_shopkeeper(mob) or combat.is_gambler(mob) or combat.is_teacher(mob) or combat.is_immortal_mob(mob):
        jutsu_colors.send(session, f"{mob.name.capitalize()} is protected and cannot be attacked.")
        return
    if session.pending_cast is not None:
        jutsu_colors.send(session, "You're already forming hand signs for another jutsu!")
        return
    if player.chakra < jutsu["chakra_cost"] or player.stamina < jutsu.get("stamina_cost", 0):
        jutsu_colors.send(session, "You don't have enough Chakra or Stamina.")
        return
    now = time.time()
    if now < player.cooldowns.get(key, 0):
        jutsu_colors.send(session, f"{jutsu['display_name']} is still recovering.")
        return
    if key == "kamui pocket dimension":
        try:
            mangekyo.open_mob_pocket_dimension(session, mob, world)
        except ValueError as exc:
            jutsu_colors.send(session, str(exc))
            return
    player.chakra -= jutsu["chakra_cost"]
    player.stamina -= jutsu.get("stamina_cost", 0)
    player.cooldowns[key] = now + jutsu["cooldown"]
    if key == "kamui pocket dimension":
        mangekyo_discovery.record_use(player, key)
        jutsu_colors.send(session, f"&RYou cast {mob.name} into a pocket dimension. Cast Kamui on yourself to enter it.&x")
    else:
        if key != "kamui limb removal" and "Silent Genjutsu" in player.learned_skills:
            resolve(session, key, mob)
            return
        combat.begin_pending_cast(session, key, mob, is_pvp=False)
        if key == "kamui limb removal":
            session.pending_cast.remaining_seconds = random.uniform(*data_mangekyo.KAMUI_LIMB_REMOVAL_CAST_SECONDS)


def resolve(session, key, mob):
    """Resolve a delayed mob cast only while its original target is present."""
    player = session.player
    if mob not in combat.mobs_in_room(player.room_vnum) or mob.health <= 0:
        jutsu_colors.send(session, "&DYour target is no longer there!&x")
        return
    if key == "amaterasu":
        mob.mangekyo_amaterasu_caster = player.name
        room = world.WORLD.get(mob.room_vnum)
        if room:
            room.amaterasu_fire_caster = player.name
            room.amaterasu_fire_expires_at = time.time() + data_mangekyo.AMATERASU_ROOM_FIRE_DURATION_SECONDS
        jutsu_colors.send(session, f"&RAmaterasu's black flames engulf {mob.name}!&x")
    elif key == "kamui limb removal":
        damage = random.randint(*data_mangekyo.KAMUI_LIMB_REMOVAL_DAMAGE)
        mob.health -= status_effects.reduce_incoming_damage(mob.active_status_effects, damage)
        jutsu_colors.send(session, f"&RKamui tears into {mob.name} for {damage} damage!&x")
        if mob.health <= 0:
            combat.handle_mob_defeat(session, mob)
    elif key == "tsukuyomi":
        status_effects.apply_effect(mob.active_status_effects, "genjutsu_locked",
                                    source=player.name, duration_override=10)
        jutsu_colors.send(session, f"&R{mob.name} is trapped in Tsukuyomi and cannot act for ten pulses!&x")
    elif key == "izanami":
        status_effects.apply_effect(mob.active_status_effects, "genjutsu_locked",
                                    source=player.name, duration_override=25)
        jutsu_colors.send(session, f"&R{mob.name} is caught in Izanami's repeating loop for 25 pulses!&x")
    else:
        return
    mangekyo_discovery.record_use(player, key)
    combat.grow_skill_from_usage(player, "Handsigns")


def extinguish(session, args):
    """The original Amaterasu caster may dismiss owned target and room flames."""
    import session as session_module
    caster = session.player.name
    if not args:
        jutsu_colors.send(session, "Usage: perform amaterasu extinguish <room|target|all>")
        return
    query = " ".join(args).lower()
    removed = 0
    rooms = world.WORLD.rooms.values() if query == "all" else [world.WORLD.get(session.player.room_vnum)]
    if query in ("room", "all"):
        for room in rooms:
            if room and room.amaterasu_fire_caster == caster:
                room.amaterasu_fire_caster = None
                room.amaterasu_fire_expires_at = 0.0
                removed += 1
    if query == "all":
        targets = [s.player for s in session_module.ACTIVE_SESSIONS if s.player]
        targets += [mob for mobs in combat.MOBS_BY_ROOM.values() for mob in mobs]
    elif query == "room":
        targets = []
    else:
        targets = [s.player for s in session_module.ACTIVE_SESSIONS
                   if s.player and s.player.room_vnum == session.player.room_vnum
                   and query in s.player.name.lower()]
        mob = combat.find_mob(session.player.room_vnum, query)
        if mob:
            targets.append(mob)
    for target in targets:
        if getattr(target, "mangekyo_amaterasu_caster", None) == caster:
            if hasattr(target, "mangekyo_amaterasu_burning"):
                target.mangekyo_amaterasu_burning = False
            target.mangekyo_amaterasu_caster = None
            removed += 1
    jutsu_colors.send(session, f"&YYou extinguish {removed} Amaterasu flame{'s' if removed != 1 else ''}.&x")
