"""Level-75 reincarnate awakening, maintained modes and lineage techniques."""

MIN_LEVEL = 75
ACTIVATION_CHAKRA = 40
IDLE_CHAKRA = 18
COMBAT_CHAKRA = 24
COMBAT_STAMINA = 8
MODE_SKILLS = {"indra": "Six Paths Rinnegan", "ashura": "Six Paths Sage Mode"}
TECHNIQUES = {
    "indra": ("Almighty Push", "Universal Pull"),
    "ashura": ("Six Paths Vital Surge", "Truth-Seeking Orb Barrage"),
}


def jutsu_entries():
    entries = {}
    moves = {
        "indra": (("Almighty Push", (90, 130), 100, 20, "off_balance", 60),
                  ("Universal Pull", (65, 95), 75, 16, "off_balance", 75)),
        "ashura": (("Truth-Seeking Orb Barrage", (85, 125), 90, 18, "weakened", 50),),
    }
    for soul, mode in MODE_SKILLS.items():
        entries[mode.lower()] = {
            "jutsu_id": "six_paths_" + soul + "_mode", "display_name": mode,
            "class_requirement": "ninjutsu", "level_requirement": MIN_LEVEL,
            "chakra_cost": ACTIVATION_CHAKRA, "stamina_cost": 0, "cooldown": 0,
            "damage": None, "damage_type": None, "effect": None,
            "tier": 5, "element": "none", "jutsu_type": "six_paths_mode",
            "kkg_gate": "six_paths_" + soul,
        }
        for name, damage, cost, cooldown, effect, chance in moves[soul]:
            entries[name.lower()] = {
                "jutsu_id": "six_paths_" + soul + "_" + name.lower().replace(" ", "_"),
                "display_name": name, "class_requirement": "ninjutsu",
                "level_requirement": MIN_LEVEL, "chakra_cost": cost, "stamina_cost": 10,
                "cooldown": cooldown, "damage": damage, "damage_type": "chakra",
                "effect": effect, "effect_chance_pct": chance, "tier": 5,
                "element": "none", "kkg_gate": "six_paths_" + soul,
                "jutsu_type": "attack",
            }
    entries["six paths vital surge"] = {
        "jutsu_id": "six_paths_ashura_vital_surge", "display_name": "Six Paths Vital Surge",
        "class_requirement": "ninjutsu", "level_requirement": MIN_LEVEL,
        "chakra_cost": 120, "stamina_cost": 0, "cooldown": 120,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none", "kkg_gate": "six_paths_ashura",
        "jutsu_type": "six_paths_recovery", "recovery_percent": 25,
    }
    return entries


def eligible(player, soul=None):
    inherited = getattr(player, "reincarnation", "")
    return (inherited in MODE_SKILLS and getattr(player, "level", 0) >= MIN_LEVEL
            and (soul is None or soul == inherited))


def active(player):
    return (eligible(player) and getattr(player, "six_paths_active", False)
            and getattr(player, "health", 0) > 0 and not getattr(player, "sage_active_contract", ""))


def sync_skills(player):
    messages = []
    if migrate_vital_surge(player):
        messages.append("Your Six Paths Rasenshuriken has become Six Paths Vital Surge; your mastery is preserved.")
    if not eligible(player):
        return messages
    import leveling
    soul = player.reincarnation
    for name in (MODE_SKILLS[soul], *TECHNIQUES[soul]):
        if name not in player.learned_skills:
            player.learned_skills.append(name)
            player.skill_proficiencies[name] = leveling.initial_proficiency(player)
            import skill_training
            skill_training.grant_without_practice(player, name)
            messages.append(f"&[213]Your Six Paths chakra awakens: you have unlocked {name}!&x")
    return messages


def migrate_vital_surge(player):
    """Replace the retired Ashura art once, preserving trained mastery."""
    old, new = "Six Paths Rasenshuriken", "Six Paths Vital Surge"
    if player.reincarnation != "ashura" or old not in player.learned_skills:
        return False
    player.learned_skills = [new if name == old else name for name in player.learned_skills]
    player.learned_skills = list(dict.fromkeys(player.learned_skills))
    player.skill_proficiencies[new] = min(100, max(player.skill_proficiencies.get(new, 0),
                                                 player.skill_proficiencies.pop(old, 0)))
    if getattr(player, "signature_move", "") == old:
        player.signature_move = ""
    old_ready = player.cooldowns.pop("six paths rasenshuriken", 0)
    if old_ready:
        player.cooldowns["six paths vital surge"] = max(old_ready, player.cooldowns.get("six paths vital surge", 0))
    return True


def vital_surge(session, target_words):
    """Self recovery usable during combat; ordinary control and resource gates apply."""
    import time
    import combat
    import data_jutsu
    import derived_stats
    import status_effects
    import storage
    player = session.player
    key = "six paths vital surge"
    jutsu = data_jutsu.JUTSU[key]
    if target_words and " ".join(target_words).lower() not in ("self", "me", player.name.lower()):
        session.send("Vital Surge restores only you. Usage: perform six paths vital surge")
        return
    if not eligible(player, "ashura") or not combat._can_use_jutsu(player, jutsu, key):
        session.send("Vital Surge requires a level-75 Ashura reincarnation with Six Paths mode active.")
        return
    if combat._is_action_blocked(player) or status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You cannot channel Vital Surge while unable to act or silenced.")
        return
    if getattr(session, "pending_cast", None) is not None:
        session.send("Finish your current hand signs before channeling Vital Surge.")
        return
    now = time.time()
    if now < player.cooldowns.get(key, 0):
        session.send("Vital Surge is still recovering.")
        return
    cost = round(jutsu["chakra_cost"] * (100 - derived_stats.chakra_control_cost_discount_percent(player.chakra_control)) / 100)
    if player.chakra < cost:
        session.send(f"You need {cost} Chakra to channel Vital Surge.")
        return
    ailments = [effect for effect in ("poisoned", "weakened") if effect in player.active_status_effects]
    health_gain = min(max(0, player.maximum_health - player.health), max(1, player.maximum_health * jutsu["recovery_percent"] // 100))
    stamina_gain = min(max(0, player.maximum_stamina - player.stamina), max(1, player.maximum_stamina * jutsu["recovery_percent"] // 100))
    if not health_gain and not stamina_gain and not ailments:
        session.send("You are already healthy and refreshed; Vital Surge is unnecessary.")
        return
    player.chakra -= cost
    player.health += health_gain
    player.stamina += stamina_gain
    for effect in ailments:
        player.active_status_effects.pop(effect, None)
    player.cooldowns[key] = now + jutsu["cooldown"]
    combat.grow_skill_from_usage(player, jutsu["display_name"])
    storage.save_player(player)
    cleared = "; cleared " + ", ".join(ailments) if ailments else ""
    session.send(f"&GYour Six Paths Vital Surge restores {health_gain} Health and {stamina_gain} Stamina{cleared}.&x")
    session.broadcast_room(f"&G{player.name}'s Six Paths chakra surges with renewed vitality!&x", exclude_self=True)


def mastery(player):
    return max(0, min(100, player.skill_proficiencies.get(MODE_SKILLS.get(player.reincarnation, ""), 0)))


def bonuses(player):
    pct = mastery(player) if active(player) else 0
    return (10 + pct // 10, 5 + pct // 10, 5 + pct // 20) if active(player) else (0, 0, 0)


def outgoing(player, damage):
    bonus = bonuses(player)[0]
    return max(0, damage * (100 + bonus) // 100)


def incoming(player, damage):
    return max(0, damage * (100 - bonuses(player)[1]) // 100)


def accuracy(player):
    return bonuses(player)[2]


def stop(session, message="Your Six Paths power fades."):
    import storage
    import upkeep_reports
    player = session.player
    if not player.six_paths_active:
        return False
    player.six_paths_active = False
    skill = MODE_SKILLS.get(player.reincarnation, "Six Paths")
    upkeep_reports.stop_maintaining(player, skill)
    for line in upkeep_reports.flush(player, skill):
        session.send(line)
    session.send(message)
    storage.save_player(player)
    return True


def _pay_upkeep(session, chakra, stamina):
    import upkeep_reports
    player = session.player
    if not player.six_paths_active:
        return False
    if not active(player) or player.chakra < chakra or player.stamina < stamina:
        return stop(session, "Your Six Paths power fades: you can no longer sustain it.")
    player.chakra -= chakra
    player.stamina -= stamina
    skill = MODE_SKILLS[player.reincarnation]
    lines = upkeep_reports.record(player, skill, chakra, stamina)
    upkeep_reports.maintain_skill(player, skill)
    for line in lines:
        session.send(line)
    return bool(lines)


def combat_pulse(session):
    return _pay_upkeep(session, COMBAT_CHAKRA, COMBAT_STAMINA)


def idle_upkeep(session):
    return _pay_upkeep(session, IDLE_CHAKRA, 0)


def command(session, args):
    import combat
    import storage
    player = session.player
    action = args[0].lower() if len(args) == 1 else "toggle" if not args else "invalid"
    if action == "status":
        if not eligible(player):
            session.send("Six Paths powers awaken at level 75, only for Indra or Ashura reincarnations.")
            return
        offense, defense, hit = bonuses(player)
        session.send(f"{MODE_SKILLS[player.reincarnation]}: {'active' if active(player) else 'inactive'}, "
                     f"mastery {mastery(player)}%. Current bonuses: +{offense}% damage, "
                     f"{defense}% incoming damage reduction, +{hit} accuracy. "
                     f"Techniques: {', '.join(TECHNIQUES[player.reincarnation])}.")
        return
    if action == "off" or (action == "toggle" and player.six_paths_active):
        if not stop(session):
            session.send("Your Six Paths power is already inactive.")
        return
    if action not in ("on", "toggle"):
        session.send("Usage: sixpaths [on|off|status]")
        return
    if not eligible(player):
        session.send("Only Indra or Ashura reincarnations can awaken Six Paths powers at level 75.")
        return
    if player.six_paths_active:
        session.send("Your Six Paths power is already active.")
        return
    if player.sage_active_contract:
        session.send("Release your summon Sage Mode before entering Six Paths mode.")
        return
    if player.health <= 0 or combat._is_action_blocked(player):
        session.send("You cannot awaken Six Paths power while down or unable to act.")
        return
    if player.chakra < ACTIVATION_CHAKRA:
        session.send(f"You need {ACTIVATION_CHAKRA} Chakra to activate Six Paths power.")
        return
    sync_skills(player)
    player.chakra -= ACTIVATION_CHAKRA
    player.six_paths_active = True
    storage.save_player(player)
    session.send(f"&[213]You awaken {MODE_SKILLS[player.reincarnation]}! Use sixpaths off to release it.&x")
    session.broadcast_room(f"&[213]{player.name} awakens an overwhelming Six Paths chakra!&x", exclude_self=True)
