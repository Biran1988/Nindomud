"""Level-75 reincarnate awakening, maintained modes and lineage techniques."""

MIN_LEVEL = 75
ACTIVATION_CHAKRA = 40
IDLE_CHAKRA = 18
COMBAT_CHAKRA = 24
COMBAT_STAMINA = 8
MODE_SKILLS = {"indra": "Six Paths Rinnegan", "ashura": "Six Paths Sage Mode"}
TECHNIQUES = {
    "indra": ("Almighty Push", "Universal Pull"),
    "ashura": ("Six Paths Rasenshuriken", "Truth-Seeking Orb Barrage"),
}


def jutsu_entries():
    entries = {}
    moves = {
        "indra": (("Almighty Push", (90, 130), 100, 20, "off_balance", 60),
                  ("Universal Pull", (65, 95), 75, 16, "off_balance", 75)),
        "ashura": (("Six Paths Rasenshuriken", (110, 150), 110, 24, "weakened", 40),
                   ("Truth-Seeking Orb Barrage", (85, 125), 90, 18, "weakened", 50)),
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
    return entries


def eligible(player, soul=None):
    inherited = getattr(player, "reincarnation", "")
    return (inherited in MODE_SKILLS and getattr(player, "level", 0) >= MIN_LEVEL
            and (soul is None or soul == inherited))


def active(player):
    return (eligible(player) and getattr(player, "six_paths_active", False)
            and getattr(player, "health", 0) > 0 and not getattr(player, "sage_active_contract", ""))


def sync_skills(player):
    if not eligible(player):
        return []
    import leveling
    soul = player.reincarnation
    messages = []
    for name in (MODE_SKILLS[soul], *TECHNIQUES[soul]):
        if name not in player.learned_skills:
            player.learned_skills.append(name)
            player.skill_proficiencies[name] = leveling.initial_proficiency(player)
            messages.append(f"&[213]Your Six Paths chakra awakens: you have unlocked {name}!&x")
    return messages


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
