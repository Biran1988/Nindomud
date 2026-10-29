"""Hyuga / Byakugan combat tree.

Ordinary Byakugan uses canonical Gentle Fist and chakra pathway perception.
Celestial Byakugan and Tenseigan are deliberately rare NindoMUD endgame
adaptations, not claims that every canon Hyuga can awaken Tenseigan.
All state lives on Player and survives the normal character save.
"""
import random
import time

# name, minimum level, chakra, stamina, damage, drain %, tenketsu lock chance,
# minimum mastery fraction, minimum inherited potential.
STRIKES = (
    ("Gentle Fist: Chakra Point Strike", 50, 12, 7, (28, 40), 8, 10, 0, 0),
    ("Gentle Fist: Tenketsu Needle", 55, 18, 8, (35, 50), 10, 18, 0, 0),
    ("Eight Trigrams Sixteen Palms", 55, 22, 16, (44, 68), 12, 18, 0, 0),
    ("Eight Trigrams Thirty-Two Palms", 60, 32, 22, (63, 91), 16, 24, .12, 0),
    ("Eight Trigrams Sixty-Four Palms", 65, 46, 31, (90, 128), 22, 32, .22, 0),
    ("Eight Trigrams Vacuum Palm", 70, 38, 10, (78, 112), 12, 15, .20, 0),
    ("Gentle Fist: One Blow Body", 75, 48, 20, (108, 156), 22, 24, .35, 0),
    ("Eight Trigrams Vacuum Wall Palm", 80, 58, 18, (142, 205), 18, 22, .45, 0),
    ("Eight Trigrams One Hundred Twenty-Eight Palms", 80, 72, 47, (160, 235), 32, 42, .55, 0),
    ("Gentle Step Twin Lion Fists", 85, 65, 35, (180, 260), 32, 35, .60, 0),
    ("Eight Trigrams Mountain Crusher", 90, 84, 40, (245, 330), 36, 35, .68, 0),
    ("Eight Trigrams Three Hundred Sixty-One Palms", 95, 118, 65, (345, 470), 55, 65, .82, 80),
    ("Eight Trigrams Twin Lions Crumbling Attack", 95, 94, 48, (285, 405), 42, 45, .80, 75),
    ("Celestial Eight Trigrams Judgment", 100, 145, 60, (455, 630), 55, 60, .90, 95),
    ("Silver Wheel Reincarnation Explosion", 100, 185, 45, (550, 745), 30, 45, 1.0, 100),
    ("Golden Wheel Reincarnation Explosion", 100, 260, 80, (760, 1080), 60, 65, 1.0, 100),
)
# name, level, chakra cast, stamina cast, cooldown, mastery, potential, effect
MODES = (
    ("Byakugan", 25, 8, 0, 2, 0, 0, "byakugan"),
    ("Eight Trigrams Palms Revolving Heaven", 70, 42, 26, 30, .30, 0, "rotation"),
    ("Protecting Eight Trigrams Sixty-Four Palms", 75, 55, 30, 40, .48, 0, "protecting"),
    ("Celestial Byakugan", 100, 95, 20, 30, .90, 95, "celestial"),
    ("Fate Sight", 100, 75, 20, 55, .90, 95, "fate"),
    ("Tenseigan Chakra Mode", 100, 180, 30, 90, 1.0, 100, "tenseigan"),
)
# Passive vision only applies while a real toggled eye is active.
MASTER_GAIN_PER_TALENT_POINT = .00020


def _ratio(player):
    ceiling = max(1, int(getattr(player, "bloodline_potential", 0)))
    return min(1.0, max(0.0, getattr(player, "bloodline_mastery", 0) / ceiling))


def eligible(player):
    return (getattr(player, "bloodline_id", None) == "byakugan"
            and bool(getattr(player, "bloodline_awakened", False)))


def definition(name):
    return REGISTRY.get(name.lower())


def registry():
    return dict(REGISTRY)


REGISTRY = {}
for name, level, chakra, stamina, damage, drain, lock, mastery, potential in STRIKES:
    key = name.lower()
    REGISTRY[key] = {
        "jutsu_id": "hyuga_" + key.replace(" ", "_").replace(":", ""),
        "display_name": name, "class_requirement": "taijutsu",
        "level_requirement": level, "chakra_cost": chakra, "stamina_cost": stamina,
        "cooldown": 7.0 + max(0, level-65)/3, "damage": damage, "damage_type": "physical",
        "effect": None, "tier": 5 if level >= 95 else 4 if level >= 80 else 3,
        "element": "none", "jutsu_type": "hyuga_strike", "kkg_gate": "byakugan",
        "hyuga_drain_pct": drain, "hyuga_lock_pct": lock,
        "hyuga_mastery": mastery, "hyuga_potential": potential,
    }
for name, level, chakra, stamina, cooldown, mastery, potential, effect in MODES:
    key = name.lower()
    REGISTRY[key] = {
        "jutsu_id": "hyuga_" + key.replace(" ", "_"),
        "display_name": name, "class_requirement": "taijutsu",
        "level_requirement": level, "chakra_cost": chakra, "stamina_cost": stamina,
        "cooldown": cooldown, "damage": None, "damage_type": None, "effect": None,
        "tier": 5 if level >= 100 else 3, "element": "none",
        "jutsu_type": "hyuga_mode", "kkg_gate": "byakugan",
        "hyuga_mastery": mastery, "hyuga_potential": potential,
        "hyuga_effect": effect,
    }


def unlocked(player, key):
    spec = REGISTRY.get(key)
    if spec is None or not eligible(player):
        return False
    if player.level < spec["level_requirement"]:
        return False
    if player.bloodline_potential < spec.get("hyuga_potential", 0):
        return False
    return _ratio(player) + 1e-9 >= spec.get("hyuga_mastery", 0)


def can_use(player, key):
    if not unlocked(player, key):
        return False
    if key not in {"byakugan", "celestial byakugan", "tenseigan chakra mode"}:
        if not player.byakugan_active:
            return False
    if key in {"silver wheel reincarnation explosion", "golden wheel reincarnation explosion"}:
        return bool(player.tenseigan_active)
    if key == "fate sight" and not player.celestial_byakugan_active:
        return False
    return True


def sync(player):
    """Bring old/returning players up to date without rerolling bloodlines."""
    if not eligible(player):
        player.byakugan_active = False
        player.celestial_byakugan_active = False
        player.tenseigan_active = False
        return []
    learned = []
    for key, spec in REGISTRY.items():
        if unlocked(player, key) and spec["display_name"] not in player.learned_skills:
            player.learned_skills.append(spec["display_name"])
            player.skill_proficiencies.setdefault(spec["display_name"], 0)
            learned.append(spec["display_name"])
    return learned


def accuracy(player):
    if not eligible(player) or not player.byakugan_active:
        return 0
    return 3 + int(_ratio(player)*8) + (8 if player.celestial_byakugan_active else 0)


def dodge(player):
    if not eligible(player) or not player.byakugan_active:
        return 0
    return 3 + int(_ratio(player)*7) + (9 if player.celestial_byakugan_active else 0) + (10 if player.tenseigan_active else 0) + (12 if "hyuga_fate" in player.active_status_effects else 0)


def tick_upkeep(session):
    player = session.player
    if not player.byakugan_active:
        return
    if not eligible(player):
        player.byakugan_active = player.celestial_byakugan_active = player.tenseigan_active = False
        return
    if player.tenseigan_active and "hyuga_tenseigan" not in player.active_status_effects:
        player.tenseigan_active = False
    cost = 2 + (7 if player.celestial_byakugan_active else 0) + (12 if player.tenseigan_active else 0)
    if player.chakra < cost:
        player.byakugan_active = player.celestial_byakugan_active = player.tenseigan_active = False
        session.send("&DYour Byakugan fades as your chakra runs dry.&x")
    else:
        player.chakra -= cost


def combat_tick(player):
    if not eligible(player) or not player.byakugan_active:
        return []
    if player.bloodline_mastery >= player.bloodline_potential:
        return []
    if random.random() >= player.bloodline_talent * MASTER_GAIN_PER_TALENT_POINT:
        return []
    before = _ratio(player)
    player.bloodline_mastery += 1
    new = sync(player)
    msg = []
    if new:
        msg.append("&CYour Byakugan has grown sharper! New techniques: " + ", ".join(new) + ".&x")
    elif int(before * 10) < int(_ratio(player) * 10):
        msg.append("&CYour chakra vision deepens as your Byakugan mastery advances.&x")
    return msg


def on_strike(session, target, spec):
    if spec.get("jutsu_type") != "hyuga_strike" or not can_use(session.player, spec["display_name"].lower()):
        return
    import status_effects
    drain = spec["hyuga_drain_pct"]
    pool = "chakra" if getattr(target, "chakra", None) is not None else "stamina"
    if getattr(target, pool, None) is not None:
        available = max(0, getattr(target, pool))
        amount = min(available, max(2, int(available * drain / 100)))
        setattr(target, pool, available - amount)
        if amount:
            session.send(f"&CYour Gentle Fist seals {amount} {pool} from {target.name}'s pathways.&x")
    chance = spec["hyuga_lock_pct"]
    # Only combatants with normal status effects can be suppressed. Apply
    # finite, expiring 1-2 pulse silence, never a permanent chakra lock.
    if random.randint(1, 100) <= chance and hasattr(target, "active_status_effects"):
        status_effects.apply_effect(target.active_status_effects, "silenced",
                                    source="hyuga_tenketsu", duration_override=1 if chance < 40 else 2)
        session.send(f"&C{target.name}'s tenketsu close: jutsu are briefly disrupted!&x")


def _scout(session, direction):
    import world
    import combat
    import commands
    player = session.player
    direction = world.normalize_direction(direction)
    if not direction:
        session.send("Usage: byakugan scan <direction>")
        return
    current = world.WORLD.get(player.room_vnum)
    if not current:
        return
    sight = 2 + round(_ratio(player) * 8) + (8 if player.celestial_byakugan_active else 0)
    lines = ["&CYour Byakugan peers into distant chakra pathways:&x"]
    for index in range(1, sight+1):
        if direction not in current.exits or "hidden" in current.exit_flags.get(direction, []):
            break
        if "door" in current.exit_flags.get(direction, []) and not current.exit_door_open.get(direction, False):
            break
        target = world.WORLD.get(current.exits[direction])
        if not target or not target.enabled or (target.apartment and target.owner and target.owner != player.name):
            break
        lines.append(f" &W{index} {direction}: {target.name}&x")
        for mob in combat.mobs_in_room(target.vnum):
            if not commands._is_invisible_mob(mob):
                lines.append(f"  &G{mob.name}&x [chakra signature]")
        for other in session.active_sessions():
            if (other is not session and other.player
                    and other.player.room_vnum == target.vnum
                    and not commands._player_hidden_from(player, other.player)):
                lines.append(f"  &G{other.player.name}&x [chakra: {other.player.chakra}/{other.player.maximum_chakra}]")
        current = target
    session.send("\n".join(lines) if len(lines) > 1 else "Your Byakugan finds no open path in that direction.")


def cast(session, key, args):
    import combat
    import skill_training
    import status_effects
    player = session.player
    spec = REGISTRY[key]
    effect = spec["hyuga_effect"]
    if not eligible(player):
        session.send("You haven't learned that skill or jutsu.")
        return
    if not unlocked(player, key):
        session.send("You haven\'t unlocked that technique.")
        return
    sync(player)
    if effect == "byakugan":
        if args and args[0].lower() == "scan":
            if not player.byakugan_active:
                session.send("Activate Byakugan before scanning.")
            elif len(args) != 2:
                session.send("Usage: byakugan scan <direction>")
            else:
                _scout(session, args[1])
            return
        if len(args) > 1 or (args and args[0].lower() not in {"on", "off", "status"}):
            session.send("Usage: byakugan [on|off|status|scan <direction>]")
            return
        mode = args[0].lower() if args else ("off" if player.byakugan_active else "on")
        if mode == "status":
            session.send(f"&CByakugan: {'ON' if player.byakugan_active else 'OFF'}; mastery {_ratio(player):.0%}; Celestial: {'ON' if player.celestial_byakugan_active else 'OFF'}; Tenseigan: {'ON' if player.tenseigan_active else 'OFF'}.&x")
            return
        if mode == "off":
            player.byakugan_active = player.celestial_byakugan_active = player.tenseigan_active = False
            session.send("&CThe veins around your eyes soften; Byakugan fades.&x")
            return
        if player.byakugan_active:
            session.send("Byakugan is already active.")
            return
    else:
        if not can_use(player, key):
            session.send("Your Byakugan has not unlocked this technique or its required form.")
            return
        if args and (len(args) != 1 or args[0].lower() not in {"on", "off"}):
            session.send(f"Usage: perform {key} [on|off]")
            return
        if effect == "celestial" and args and args[0].lower() == "off":
            player.celestial_byakugan_active = player.tenseigan_active = False
            session.send("&CYour celestial sight subsides.&x")
            return
        if effect == "tenseigan" and args and args[0].lower() == "off":
            player.tenseigan_active = False
            session.send("&CYour Tenseigan chakra cloak fades.&x")
            return
    if effect != "byakugan" and skill_training.needs_first_practice(player, spec["display_name"]) and not combat._staff_testing_mangekyo(player):
        session.send(f"Practice {spec['display_name']} with a teacher at least once before using it.")
        return
    if combat._is_action_blocked(player) or status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are unable to channel chakra.")
        return
    now = time.time()
    if now < player.cooldowns.get(key, 0):
        session.send(f"{spec['display_name']} is recovering.")
        return
    if player.chakra < spec["chakra_cost"] or player.stamina < spec["stamina_cost"]:
        session.send("Not enough chakra or stamina.")
        return
    if effect == "celestial" and not player.byakugan_active:
        session.send("Activate Byakugan first.")
        return
    if effect == "tenseigan" and not player.celestial_byakugan_active:
        session.send("Activate Celestial Byakugan first.")
        return
    player.chakra -= spec["chakra_cost"]
    player.stamina -= spec["stamina_cost"]
    player.cooldowns[key] = now + spec["cooldown"]
    if effect == "byakugan":
        player.byakugan_active = True
        session.send("&CByakugan! Veins rise around your eyes as the world opens to chakra sight.&x")
    elif effect == "celestial":
        player.celestial_byakugan_active = True
        session.send("&WYour Byakugan reaches a celestial clarity; fate itself flickers at the edge of sight.&x")
    elif effect == "tenseigan":
        player.tenseigan_active = True
        status_effects.apply_effect(player.active_status_effects, "hyuga_tenseigan", source=key, duration_override=4)
        session.send("&WThe Tenseigan chakra mantle surrounds you -- an almost mythical awakening!&x")
    else:
        status_key = {"rotation": "hyuga_rotation", "protecting": "hyuga_protecting", "fate": "hyuga_fate"}[effect]
        status_effects.apply_effect(player.active_status_effects, status_key, source=key, duration_override=3)
        session.send(f"&C{spec['display_name']} unfolds, protecting you against incoming attacks.&x")
    combat.grow_skill_from_usage(player, spec["display_name"], session=session)


def cmd_byakugan(session, args):
    cast(session, "byakugan", args)


def cmd_hyuga(session, args):
    player = session.player
    if not eligible(player):
        session.send("You have not awakened the Byakugan.")
        return
    newly = sync(player)
    if not args or args[0].lower() == "list":
        lines = ["&CHyuga Bloodline Techniques&x", f"Mastery: {_ratio(player):.0%}; Level: {player.level}",
                 "Use 'byakugan on', 'byakugan scan <direction>' or any listed jutsu shortcut."]
        for key, spec in sorted(REGISTRY.items(), key=lambda pair: (pair[1]["level_requirement"], pair[0])):
            if player.bloodline_potential >= spec.get("hyuga_potential", 0):
                state = "learned" if unlocked(player, key) else f"requires mastery {spec.get('hyuga_mastery', 0):.0%}"
                lines.append(f" Lv {spec['level_requirement']:3} {spec['display_name']} - {state}")
        session.send("\n".join(lines))
        return
    session.send("Usage: hyuga list")
