"""Kai (Genjutsu Release): controlled escape from ordinary illusions only.

No damage, medical healing, poison/physical stun purge, Mangekyo escape,
Izanami loop escape, reaper-seal escape or permanent player stat changes.
"""
import time

import combat
import data_jutsu
import jutsu_balance
import status_effects


KEY = "kai"


def _has_ordinary_illusion(player):
    return (any(isinstance(state, dict) and state.get("genjutsu")
                for state in player.active_status_effects.values())
            or bool(getattr(player, "illusion_walk_caster", None)))


def _blocked_by_physical_condition(player):
    for name, state in player.active_status_effects.items():
        props = status_effects.EFFECT_DEFS.get(name, {})
        if (props.get("blocks_action") or props.get("blocks_jutsu")) and not (
                isinstance(state, dict) and state.get("genjutsu")):
            return True
    return False


def _release(player):
    removed = status_effects.dispel_genjutsu_effects(player.active_status_effects)
    escaped_walk = bool(getattr(player, "illusion_walk_caster", None))
    if escaped_walk:
        player.illusion_walk_caster = None
        player.illusion_walk_real_room_vnum = None
        player.illusion_walk_range = 0
        player.illusion_walk_steps_taken = 0
    return removed, escaped_walk


def cast(session, words):
    """Perform Kai on self, or one visible player in the same room."""
    caster = session.player
    target_session = session
    if words:
        import session as session_module
        query = " ".join(words).casefold()
        candidates = [
            other for other in session_module.ACTIVE_SESSIONS
            if other.player and other.player.room_vnum == caster.room_vnum
            and other.player.health > 0
            and other.player.name.casefold() == query
        ]
        if len(candidates) != 1:
            session.send("Kai can only release yourself or a player in this room. Usage: kai [player].")
            return
        target_session = candidates[0]
    victim = target_session.player
    art = data_jutsu.JUTSU[KEY]
    if not combat._can_use_jutsu(caster, art, KEY):
        session.send("You must learn and practice Kai before using it.")
        return
    if _blocked_by_physical_condition(caster):
        session.send("A physical restraint or non-Genjutsu silence prevents Kai.")
        return
    if getattr(session, "pending_cast", None) is not None:
        session.send("Finish or interrupt your current hand signs first.")
        return
    if getattr(caster, "tsukuyomi_frozen", False):
        session.send("Kai cannot break Tsukuyomi.")
        return
    if not _has_ordinary_illusion(victim):
        session.send("There is no ordinary Genjutsu to release.")
        return
    now = time.time()
    if now < caster.cooldowns.get(KEY, 0):
        session.send(f"Kai is recovering ({caster.cooldowns[KEY] - now:.1f}s).")
        return
    cost = jutsu_balance.cast_cost(caster, art, "chakra")
    if caster.chakra < cost:
        session.send(f"You need {cost} Chakra to perform Kai.")
        return
    caster.chakra -= cost
    caster.cooldowns[KEY] = now + art["cooldown"]
    removed, escaped_walk = _release(victim)
    if target_session is session:
        session.send("&CYou focus your Chakra and release Kai, shattering the ordinary Genjutsu!&x")
    else:
        session.send(f"&CYou pulse your Chakra into {victim.name}, releasing their Genjutsu!&x")
        target_session.send(f"&C{caster.name} channels Kai through you, breaking the ordinary illusion!&x")
    import combat as _combat
    _combat.grow_skill_from_usage(caster, art["display_name"])
    if escaped_walk:
        import commands
        commands.cmd_look(target_session, [])
    return removed
