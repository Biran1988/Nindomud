"""General ninja concealment, detection, quiet movement and mental discipline."""
import time

import data_jutsu
import status_effects

CAMOUFLAGE_UPKEEP_SECONDS = 5.0
CAMOUFLAGE_UPKEEP_CHAKRA = 1

EFFECT_KEYS = {"camouflage": "camouflage", "silent movement": "silent_movement",
               "sensory detect": "sensory_detect", "focused mind": "focused_mind"}


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


def activate(session, key, words):
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
        player.active_status_effects.pop(effect, None)
        import upkeep_reports
        upkeep_reports.stop_maintaining(player, info["display_name"])
        if key == "camouflage":
            player._camouflage_next_upkeep_at = 0.0
        session.send(f"{info['display_name']} is off.")
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
    player.chakra -= info["chakra_cost"]
    player.stamina -= info["stamina_cost"]
    player.cooldowns[key] = now + info["cooldown"]
    mastery = max(0, min(100, player.skill_proficiencies.get(info["display_name"], 0)))
    toggled = status_effects.EFFECT_DEFS[effect].get("toggled", False)
    duration = None if toggled else 60 + mastery
    status_effects.apply_effect(player.active_status_effects, effect, source=key,
                                duration_override=duration)
    combat.grow_skill_from_usage(player, info["display_name"], session=session)
    import upkeep_reports
    upkeep_reports.stop_maintaining(player, info["display_name"])
    upkeep_reports.maintain_skill(player, info["display_name"], session=session)
    if key == "camouflage":
        player._camouflage_next_upkeep_at = now + CAMOUFLAGE_UPKEEP_SECONDS
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
