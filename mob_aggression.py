"""Autonomous NPC aggression, chosen by editable mobile prototype flags.

AggressiveEveryone = attack any ordinary player.
aggressive_village = attack only players of configured aggro_village.
aggressive_clan = attack only players of configured aggro_clan.
Flags can coexist and combine as an OR. A village/clan flag with no
target configured remains inert, never attacking unrelated players.

NPC aggression starts ordinary PvE combat and is resolved by the existing
combat loop. When scouting via a physical elemental clone, the live clone
can separately be attacked and destroyed by hostile local NPCs.
"""
import time

AGGRESSION_FLAGS = {"aggressive_village", "aggressive_clan", "aggressive_everyone"}
CLONE_ATTACK_SECONDS = 5.0
_clone_attack_due = {}


def targets_player(template, player):
    flags = set(template.get("act_flags") or ())
    if "aggressive_everyone" in flags:
        return True
    if ("aggressive_village" in flags and template.get("aggro_village", "") and
            str(template["aggro_village"]).casefold() == str(player.village or "").casefold()):
        return True
    if ("aggressive_clan" in flags and template.get("aggro_clan", "") and
            str(template["aggro_clan"]).casefold() == str(player.clan or "").casefold()):
        return True
    return False


def _valid_attacker(mob, room):
    import combat
    if not mob or mob.health <= 0 or not room or not room.enabled:
        return False
    if room.safe or room.apartment or room.player_shop:
        return False
    if (mob.shadow_clone_owner or mob.summon_owner or
            combat.is_shopkeeper(mob) or combat.is_teacher(mob) or
            combat.is_gambler(mob) or combat.is_immortal_mob(mob)):
        return False
    return True


def _clone_target_and_owner(clone):
    import session as session_module
    for session in list(session_module.ACTIVE_SESSIONS):
        if (session.player and getattr(session, "controlled_clone", None) is clone and
                session.player.name.casefold() == clone.shadow_clone_owner.casefold()):
            return session
    return None


def process_aggression(now=None):
    """One server pulse: select valid enemy players, then damage live scouts.

    Initial attacks only start PvE via combat.start_attack so player combat
    resolution, XP, death, spells and the normal fight rules stay unchanged.
    A controlled scout clone has HP separate from its owner and cannot
    fight back in reconnaissance mode; real attacks can disperse it.
    """
    import combat
    import session as session_module
    import world
    if now is None:
        now = time.time()
    connected = list(session_module.ACTIVE_SESSIONS)
    for session in connected:
        player = getattr(session, "player", None)
        if (not player or getattr(getattr(session, "state", None), "name", "") != "PLAYING" or
                getattr(getattr(session, "account", None), "staff_level", "player") != "player" or
                player.health <= 0 or getattr(player, "downed_by", None)):
            continue
        if session.combat_target or session.pvp_target:
            continue
        room = world.WORLD.get(player.room_vnum)
        if not room or room.safe:
            continue
        for mob in list(combat.mobs_in_room(player.room_vnum)):
            template = combat.MOB_TEMPLATES.get(mob.template_vnum, {})
            import general_skills
            if general_skills.concealed_from(mob, player):
                continue
            if (_valid_attacker(mob, room) and targets_player(template, player)):
                combat.start_attack(session, mob)
                session.send(f"&R{mob.name} recognizes you and attacks without warning!&x")
                break

    # Scouts remain their own mob objects, even though their owner's
    # physical body stays in a different room. Attack only once per
    # attacker every CLONE_ATTACK_SECONDS. No rewards or corpse for clones.
    live_ids = set()
    for session in connected:
        clone = getattr(session, "controlled_clone", None)
        if not clone or not getattr(session, "player", None) or clone.health <= 0:
            continue
        room = world.WORLD.get(clone.room_vnum)
        if not room:
            continue
        for mob in list(combat.mobs_in_room(clone.room_vnum)):
            if mob is clone or not _valid_attacker(mob, room):
                continue
            template = combat.MOB_TEMPLATES.get(mob.template_vnum, {})
            if not targets_player(template, session.player):
                continue
            key = (mob.instance_id, clone.instance_id)
            live_ids.add(key)
            if now < _clone_attack_due.get(key, 0):
                continue
            _clone_attack_due[key] = now + CLONE_ATTACK_SECONDS
            damage = max(1, combat._mob_attack_damage(mob))
            clone.health -= damage
            session.send(f"&R{mob.name} attacks your {clone.clone_element} clone for {damage} damage "
                         f"({max(0, clone.health)}/{clone.max_health} HP remaining)!&x")
            if clone.health <= 0:
                session.send(f"&RYour clone is defeated by {mob.name}!&x")
                combat.remove_mob(clone)
                break
    # Prevent dangling references to old mob ids.
    if len(_clone_attack_due) > 400:
        for key in list(_clone_attack_due):
            if key not in live_ids:
                del _clone_attack_due[key]
