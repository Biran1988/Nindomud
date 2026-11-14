"""General ninja concealment, detection, quiet movement and mental discipline."""
import time

import data_jutsu
import jutsu_balance
import status_effects

CAMOUFLAGE_UPKEEP_SECONDS = 5.0
CAMOUFLAGE_UPKEEP_CHAKRA = 1

EFFECT_KEYS = {"camouflage": "camouflage", "silent movement": "silent_movement",
               "sensory detect": "sensory_detect", "focused mind": "focused_mind"}

DEFENSIVE_TOGGLES = {
    "sanctuary": ("sanctuary", 5),
    "elemental shield": ("elemental_shield", 6),
}
DEFENSIVE_UPKEEP_SECONDS = 5.0


def activate_defense(session, key, words):
    """Player-bound defensive stance; persists across movement and saves."""
    import combat
    import skill_training
    import upkeep_reports

    player = session.player
    info = data_jutsu.JUTSU[key]
    effect, upkeep_cost = DEFENSIVE_TOGGLES[key]
    if words and (len(words) != 1 or words[0].lower() not in ("on", "off")):
        session.send(f"Usage: {key} [on|off]")
        return
    mode = words[0].lower() if words else "toggle"
    if mode == "off" or (mode == "toggle" and active(player, effect)):
        player.active_status_effects.pop(effect, None)
        upkeep_reports.stop_maintaining(player, info["display_name"])
        session.send(f"{info['display_name']} is OFF.")
        return
    if active(player, effect):
        session.send(f"{info['display_name']} is already ON; use '{key} off'.")
        return
    if (not combat._can_use_jutsu(player, info, key)
            or skill_training.needs_first_practice(player, info["display_name"])):
        session.send(f"Learn and practice {info['display_name']} (level "
                     f"{info['level_requirement']}) before using it.")
        return
    if combat._is_action_blocked(player) or getattr(session, "pending_cast", None) is not None:
        session.send("You cannot concentrate right now.")
        return
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use jutsu right now!")
        return
    now = time.time()
    if now < player.cooldowns.get(key, 0):
        session.send(f"{info['display_name']} is still recovering.")
        return
    shortfall = combat.jutsu_resource_shortfall(player, info, key)
    if shortfall:
        session.send(shortfall)
        return
    player.chakra -= jutsu_balance.cast_cost(player, info, "chakra")
    player.cooldowns[key] = now + info["cooldown"]
    status_effects.apply_effect(player.active_status_effects, effect, source=key)
    player.active_status_effects[effect]["upkeep_due_at"] = now + DEFENSIVE_UPKEEP_SECONDS
    combat.grow_skill_from_usage(player, info["display_name"], session=session)
    upkeep_reports.maintain_skill(player, info["display_name"], session=session)
    if key == "elemental shield":
        nature = (getattr(player, "chakra_nature", None) or "chakra").title()
        session.send(f"&C{nature} Elemental Shield surrounds you: 30% incoming damage "
                     "reduction, +15% damage with your own element's jutsu, "
                     "+5 accuracy. Persists through movement; upkeep "
                     f"{upkeep_cost} Chakra every 5 seconds. Use '{key} off'.&x")
    else:
        session.send("&WSanctuary ON: 50% less incoming damage, even when moving. "
                     f"Upkeep {upkeep_cost} Chakra every 5 seconds. "
                     "Other shields cannot stack their damage reduction with it. "
                     "Use 'sanctuary off'.&x")


def elemental_accuracy(player) -> int:
    """Raikage-inspired agility while actively protected by Elemental Shield."""
    return 5 if active(player, "elemental_shield") else 0


def elemental_jutsu_damage(player, jutsu, damage: int) -> int:
    """Boost only a nature-matching offensive jutsu, never generic damage."""
    if not active(player, "elemental_shield") or damage <= 0:
        return damage
    element = jutsu.get("element", "none")
    natures = (getattr(player, "chakra_nature", None),
               getattr(player, "chakra_nature_secondary", None),
               getattr(player, "chakra_nature_tertiary", None))
    return damage * 115 // 100 if element not in ("none", None, "") and element in natures else damage


def defense_upkeep(session):
    """Pay each toggle every 5 real seconds, in or out of combat.

    The saved effect dictionary holds the deadline so relogging cannot
    bypass upkeep. Never charge extra just because the event loop is busy.
    """
    import upkeep_reports
    player = session.player
    now = time.time()
    for key, (effect, cost) in DEFENSIVE_TOGGLES.items():
        state = player.active_status_effects.get(effect)
        if not state:
            continue
        due = state.get("upkeep_due_at", 0)
        if not due:
            state["upkeep_due_at"] = now + DEFENSIVE_UPKEEP_SECONDS
            continue
        if now < due:
            continue
        # Charge all due ticks, capped so a disconnected or lagged player
        # cannot go deeply negative or drain thousands of ticks at once.
        steps = max(1, min(12, int((now - due) // DEFENSIVE_UPKEEP_SECONDS) + 1))
        total = cost * steps
        if player.chakra < total:
            player.active_status_effects.pop(effect, None)
            upkeep_reports.stop_maintaining(player, data_jutsu.JUTSU[key]["display_name"])
            session.send(f"&R{data_jutsu.JUTSU[key]['display_name']} fades as your chakra runs out.&x")
        else:
            player.chakra -= total
            state["upkeep_due_at"] = now + DEFENSIVE_UPKEEP_SECONDS
            upkeep_reports.record(player, data_jutsu.JUTSU[key]["display_name"], total)


def active(player, effect):
    return getattr(player, "active_status_effects", {}).get(effect, {}).get("duration", 0) > 0


def concealed_from(viewer, target):
    # Staff invisibility is separate and is never defeated by Sensory Detect.
    return (viewer is not target and active(target, "camouflage")
            and not active(viewer, "sensory_detect")
            and not getattr(viewer, "_immortal_skill_mastery", False))


def break_camouflage(session):
    if session.player and session.player.active_status_effects.pop("camouflage", None):
        import upkeep_reports
        upkeep_reports.stop_maintaining(session.player, "Camouflage")
        session.player._camouflage_next_upkeep_at = 0.0
        session.send("&YCombat reveals you, breaking your camouflage.&x")
        import room_actions
        room_actions.emit(session, f"{session.player.name} is revealed as their camouflage breaks!")


def activate(session, key, words):
    if key in DEFENSIVE_TOGGLES:
        return activate_defense(session, key, words)
    import combat
    import skill_training
    player = session.player
    info = data_jutsu.JUTSU[key]
    effect = EFFECT_KEYS[key]
    if words and (len(words) != 1 or words[0].lower() not in {"on", "off"}):
        session.send(f"Usage: {key} [on|off]")
        return
    mode = words[0].lower() if words else "toggle"
    if mode == "off" or mode == "toggle" and active(player, effect):
        was_active = active(player, effect)
        player.active_status_effects.pop(effect, None)
        import upkeep_reports
        upkeep_reports.stop_maintaining(player, info["display_name"])
        if key == "camouflage":
            player._camouflage_next_upkeep_at = 0.0
        session.send(f"{info['display_name']} is off.")
        if key == "camouflage" and was_active:
            import room_actions
            room_actions.emit(session, f"{player.name} emerges from camouflage.")
        return
    if active(player, effect):
        session.send(f"{info['display_name']} is already active. Use '{key} off' to release it.")
        return
    if (not combat._can_use_jutsu(player, info, key)
            or skill_training.needs_first_practice(player, info["display_name"])):
        session.send(f"Learn and practice {info['display_name']} with a teacher before using it.")
        return
    if combat._is_action_blocked(player) or session.pending_cast is not None:
        session.send("You cannot concentrate right now.")
        return
    if key == "camouflage" and (session.combat_target is not None or session.pvp_target is not None):
        session.send("You cannot camouflage yourself during combat.")
        return
    now = time.time()
    if now < player.cooldowns.get(key, 0):
        session.send(f"{info['display_name']} is still recovering.")
        return
    shortfall = combat.jutsu_resource_shortfall(player, info, key)
    if shortfall:
        session.send(shortfall)
        return
    player.chakra -= jutsu_balance.cast_cost(player, info, "chakra")
    player.stamina -= jutsu_balance.cast_cost(player, info, "stamina")
    player.cooldowns[key] = now + info["cooldown"]
    mastery = max(0, min(100, player.skill_proficiencies.get(info["display_name"], 0)))
    toggled = status_effects.EFFECT_DEFS[effect].get("toggled", False)
    duration = None if toggled else jutsu_balance.boosted_duration(player, info, 60 + mastery)
    status_effects.apply_effect(player.active_status_effects, effect, source=key,
                                duration_override=duration)
    combat.grow_skill_from_usage(player, info["display_name"], session=session)
    import upkeep_reports
    upkeep_reports.stop_maintaining(player, info["display_name"])
    upkeep_reports.maintain_skill(player, info["display_name"], session=session)
    if key == "camouflage":
        player._camouflage_next_upkeep_at = now + CAMOUFLAGE_UPKEEP_SECONDS
        # Witnesses see the initial fading; subsequent actions stay hidden
        # unless they actively have Sensory Detect.
        import room_actions
        room_actions.emit(session, f"{player.name} blends into the surroundings and vanishes from view.", reveal_transition=True)
    descriptions = {
        "camouflage": "You blend into your surroundings. Upkeep: 1 Chakra every 5 seconds. Combat reveals you.",
        "silent movement": "You move without ordinary travel messages; each step costs 2 extra Stamina.",
        "sensory detect": "You can detect camouflaged ninja and notice silent movement. Upkeep: 1 Chakra per second.",
        "focused mind": f"You sharpen your aim: +{focused_accuracy(player)} accuracy for normal attacks and offensive techniques of every class, plus resistance to mental distractions. Each step costs 1 extra Stamina.",
    }
    state = ("is ON until released or upkeep fails" if key == "camouflage" else
             "is ON until you toggle it off or run out of Stamina") if toggled else f"is active for {duration} seconds"
    session.send(f"&G{info['display_name']} {state}.&x {descriptions[key]}")


def upkeep(session):
    defense_upkeep(session)
    player = session.player
    if active(player, "camouflage"):
        now = time.time()
        due = getattr(player, "_camouflage_next_upkeep_at", 0)
        if not due:
            player._camouflage_next_upkeep_at = now + CAMOUFLAGE_UPKEEP_SECONDS
        elif now >= due:
            if player.chakra < CAMOUFLAGE_UPKEEP_CHAKRA:
                player.active_status_effects.pop("camouflage", None)
                import upkeep_reports
                upkeep_reports.stop_maintaining(player, "Camouflage")
                player._camouflage_next_upkeep_at = 0.0
                session.send("Your Chakra runs out; Camouflage ends and you become visible.")
                import room_actions
                room_actions.emit(session, f"{player.name} emerges from camouflage as their chakra fades.")
            else:
                player.chakra -= CAMOUFLAGE_UPKEEP_CHAKRA
                player._camouflage_next_upkeep_at = now + CAMOUFLAGE_UPKEEP_SECONDS
    else:
        player._camouflage_next_upkeep_at = 0.0
    if active(player, "sensory_detect"):
        if player.chakra < 1:
            player.active_status_effects.pop("sensory_detect", None)
            session.send("Your Chakra runs out; Sensory Detect ends.")
        else:
            player.chakra -= 1


def before_move(session):
    player = session.player
    if active(player, "silent_movement"):
        if player.stamina >= 2:
            player.stamina -= 2
        else:
            player.active_status_effects.pop("silent_movement", None)
            session.send("You lack the extra Stamina for Silent Movement; your footsteps become audible.")
    if active(player, "focused_mind"):
        player.stamina = max(0, player.stamina - 1)


def broadcast_movement(session, text):
    """Filter each observer separately; no name leak via travel messages."""
    import staff_invisibility
    if staff_invisibility.is_hidden(session):
        return  # Even immortal observers cannot see wizard-invisible travel.
    player = session.player
    if not active(player, "camouflage") and not active(player, "silent_movement"):
        session.broadcast_room(text, exclude_self=True)
        return
    for observer in session.active_sessions():
        if observer is session or not observer.player or observer.player.room_vnum != player.room_vnum:
            continue
        if concealed_from(observer.player, player):
            continue
        if (active(player, "silent_movement") and not active(observer.player, "sensory_detect")
                and not getattr(observer.player, "_immortal_skill_mastery", False)):
            continue
        observer.send(text)


def focused_accuracy(player):
    """Additive hit-chance points for the ninja's own attacks of any class."""
    if not active(player, "focused_mind"):
        return 0
    mastery = max(0, min(100, getattr(player, "skill_proficiencies", {}).get("Focused Mind", 0)))
    return 5 + mastery // 20


def focused_duration(target, duration):
    if not active(target, "focused_mind"):
        return duration
    mastery = max(0, min(100, getattr(target, "skill_proficiencies", {}).get("Focused Mind", 0)))
    reduction = 10 + mastery // 5  # 10-30%, stacks with existing Sharingan resistance
    return max(1, duration * (100 - reduction) // 100)
