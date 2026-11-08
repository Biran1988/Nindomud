"""The Eight Inner Gates: Taijutsu-only physical overdrive.

Ordinary Gates are sustainable only with Stamina. The Seventh Gate also
damages its user. The Eighth is a deliberately confirmed, irrevocable
sacrifice: after 30 real seconds it drops the user to defeat, even if the
user left combat. All time markers and the active gate persist in Player saves.

BATTLE READY may open the highest available SAFE Gate only (1-7), never Death.
"""
import time

# (display name, unlock level, start stamina, upkeep stamina per 3 seconds,
#  extra physical damage %, physical accuracy, self damage % of max HP/tick)
GATES = (
    ("Gate of Opening", 20, 12, 3, 10, 2, 0),
    ("Gate of Healing", 40, 20, 5, 20, 4, 0),
    ("Gate of Life", 65, 30, 8, 35, 6, 0),
    ("Gate of Pain", 90, 40, 11, 50, 8, 0),
    ("Gate of Limit", 120, 55, 15, 70, 10, 0),
    ("Gate of View", 155, 80, 20, 95, 12, 1),
    ("Gate of Wonder", 195, 115, 27, 125, 15, 3),
    ("Gate of Death", 240, 180, 42, 160, 20, 9),
)
GATE_EIGHT_SECONDS = 30
TICK_SECONDS = 3
GATE8_EXHAUSTION_SECONDS = 1200
GATE_STANCES = {
    "front lotus": (1, 25, 22, (46, 70), 8.0, None, 0),
    "reverse lotus": (3, 75, 42, (120, 165), 12.0, "off_balance", 35),
    "morning peacock": (6, 165, 85, (320, 440), 18.0, "burning", 45),
    "daytime tiger": (7, 205, 120, (465, 620), 24.0, "stunned", 20),
    "evening elephant": (8, 240, 150, (700, 980), 22.0, "off_balance", 45),
    "night guy": (8, 250, 250, (1400, 1750), 60.0, "stunned", 35),
}


def entries():
    """Public skill definitions: level-up and retroactive unlock use normal paths."""
    result = {}
    for index, (name, level, start, _upkeep, _power, _accuracy, _pain) in enumerate(GATES, 1):
        result[name.casefold()] = {
            "jutsu_id": "taijutsu_inner_gate_" + str(index),
            "display_name": name, "class_requirement": "taijutsu",
            "level_requirement": level, "chakra_cost": 0, "stamina_cost": start,
            "cooldown": 0.0, "damage": None, "damage_type": None, "effect": None,
            "tier": min(5, (index + 1) // 2), "element": "none",
            "jutsu_type": "eight_gate", "required_gate": index,
        }
    for name, (gate, level, cost, damage, cooldown, effect, chance) in GATE_STANCES.items():
        result[name] = {
            "jutsu_id": "taijutsu_gate_strike_" + name.replace(" ", "_"),
            "display_name": name.title(), "class_requirement": "taijutsu",
            "level_requirement": level, "chakra_cost": 0, "stamina_cost": cost,
            "cooldown": cooldown, "damage": damage, "damage_type": "physical",
            "effect": effect, "effect_chance_pct": chance,
            "tier": min(5, gate), "element": "none",
            "jutsu_type": "gate_strike", "required_gate": gate,
        }
    return result


def qualified(player, gate, *, practiced=True):
    if not 1 <= gate <= 8:
        return False
    import combat
    if combat._staff_testing_mangekyo(player):
        return True
    name, level, *_ = GATES[gate - 1]
    if player.primary_class != "taijutsu" or player.level < level:
        return False
    if name.casefold() not in {skill.casefold() for skill in player.learned_skills}:
        return False
    if practiced:
        import skill_training
        if skill_training.needs_first_practice(player, name):
            return False
    return True


def highest_safe(player):
    return next((gate for gate in range(7, 0, -1) if qualified(player, gate)), 0)


def active(player):
    return max(0, min(8, int(getattr(player, "gates_open", 0) or 0)))


def accuracy(player):
    gate = active(player)
    return GATES[gate - 1][5] if gate else 0


def physical_damage(player, amount, jutsu=None):
    """Gate power affects normal strikes and Taijutsu, not unrelated Ninjutsu."""
    gate = active(player)
    if not gate:
        return amount
    if jutsu is not None and (jutsu.get("class_requirement") != "taijutsu"
                              and jutsu.get("jutsu_type") != "kkgk_taijutsu_strike"):
        return amount
    return max(1, int(amount * (100 + GATES[gate - 1][4]) / 100))


def strike_unlocked(player, jutsu):
    gate = int(jutsu.get("required_gate", 0))
    return (active(player) >= gate and
            (player.primary_class == "taijutsu" or _staff(player)))


def _staff(player):
    import combat
    return combat._staff_testing_mangekyo(player)


def end(player, *, forced=False):
    """Clear any active gate and apply exhaustion; defeat invokes forced=True."""
    gate = active(player)
    if not gate:
        return False
    if gate == 8 and not forced:
        return False
    player.gates_open = 0
    player.gates_eighth_expires_at = 0.0
    cooldown = GATE8_EXHAUSTION_SECONDS if gate == 8 else 180 if gate >= 6 else 90 if gate >= 4 else 45
    player.gates_cooldown_until = max(getattr(player, "gates_cooldown_until", 0.0),
                                      time.time() + cooldown)
    return True


def open_gate(session, gate, *, confirm=False):
    player = session.player
    from combat import _is_action_blocked
    if player is None or not 1 <= gate <= 8:
        session.send("Choose a Gate from 1 through 8.")
        return False
    if _is_action_blocked(player) or "silenced" in player.active_status_effects:
        session.send("You cannot focus your chakra and body right now.")
        return False
    if getattr(session, "pending_cast", None) is not None or getattr(session, "pending_action", None) is not None:
        session.send("Finish your current action before opening a Gate.")
        return False
    if not qualified(player, gate):
        session.send(f"Gate {gate} requires Taijutsu, level {GATES[gate - 1][1]}, and one teacher practice of {GATES[gate - 1][0]}.")
        return False
    current = active(player)
    if current >= gate:
        session.send(f"{GATES[current - 1][0]} is already open.")
        return True
    if current == 8:
        session.send("The final Gate cannot be contained.")
        return False
    if gate == 8 and not confirm:
        session.send("&RThe Eighth Gate will inevitably defeat you after 30 seconds, with normal defeat penalties. Type 'gates 8 confirm' to make this irreversible choice.&x")
        return False
    now = time.time()
    if current == 0 and now < getattr(player, "gates_cooldown_until", 0):
        session.send(f"Your body is still recovering from the Gates ({int(player.gates_cooldown_until - now) + 1}s).")
        return False
    _name, _level, cost, *_ = GATES[gate - 1]
    if player.stamina < cost:
        session.send(f"You need {cost} Stamina to open Gate {gate}.")
        return False
    if gate == 8 and player.health < player.maximum_health * 0.75:
        session.send("You must have at least 75% Health to withstand the final Gate's opening.")
        return False
    player.stamina -= cost
    player.gates_open = gate
    player.gates_last_upkeep_at = now
    player.gates_eighth_expires_at = now + GATE_EIGHT_SECONDS if gate == 8 else 0.0
    import combat
    combat.grow_skill_from_usage(player, GATES[gate - 1][0], session=session)
    session.send(f"&RYou tear open the {GATES[gate - 1][0]}! Your physical strength and speed surge.&x")
    if gate == 8:
        session.send("&RThe Gate of Death cannot be closed. Your life burns away for 30 seconds.&x")
    return True


def tick(session, *, now=None):
    """Called once per second for online players, outside AND inside combat."""
    player = session.player
    gate = active(player)
    if not gate:
        return
    now = time.time() if now is None else now
    if gate == 8 and now >= player.gates_eighth_expires_at:
        end(player, forced=True)
        player.health = 0
        session.send("&RThe Gate of Death consumes your final heartbeat. You collapse!&x")
        return
    if now - getattr(player, "gates_last_upkeep_at", now) < TICK_SECONDS:
        return
    player.gates_last_upkeep_at = now
    cost = GATES[gate - 1][3]
    if player.stamina < cost:
        end(player, forced=True)
        session.send("&YYour Stamina gives out. The Inner Gates slam shut; exhaustion follows.&x")
        return
    player.stamina -= cost
    wound_pct = GATES[gate - 1][6]
    if wound_pct:
        wound = max(1, player.maximum_health * wound_pct // 100)
        # In the eighth gate even self-healing cannot avert eventual defeat.
        player.health = max(0, player.health - wound)
        session.send(f"&RThe {GATES[gate - 1][0]} tears through your body for {wound} Health!&x")
        if player.health <= 0:
            end(player, forced=True)


def command(session, args):
    """GATES [status|safe|off|1..8 [confirm]|open <number> [confirm]]."""
    player = session.player
    words = [str(word).casefold() for word in args]
    if not words or words == ["status"] or words == ["list"]:
        gate = active(player)
        title = GATES[gate - 1][0] if gate else "none"
        session.send(f"&WInner Gates:&x {title}. Stamina {player.stamina}/{player.maximum_stamina}.")
        for idx, (name, level, *_rest) in enumerate(GATES, 1):
            state = "OPEN" if gate == idx else "learned" if qualified(player, idx) else "locked"
            session.send(f"  {idx}. {name} (level {level}) - {state}")
        session.send("Usage: gates safe | gates <1..8> | gates 8 confirm | gates off. Eighth Gate cannot be closed.")
        return
    if words in (["off"], ["close"], ["stop"]):
        if active(player) == 8:
            session.send("&RThe Gate of Death cannot be closed.&x")
        elif end(player):
            session.send("&YYou release the Inner Gates. Your body needs time to recover.&x")
        else:
            session.send("No Inner Gate is open.")
        return
    if words == ["safe"]:
        chosen = highest_safe(player)
        if not chosen:
            session.send("You have not learned and practiced any safe Inner Gate.")
        else:
            open_gate(session, chosen)
        return
    if words[0] in ("open", "on"):
        words = words[1:]
    if words and words[0] in ("8", "eight", "death"):
        requested = 8
    elif words and words[0].isdigit():
        requested = int(words[0])
    else:
        session.send("Usage: gates [status|safe|off|1..8 [confirm]].")
        return
    open_gate(session, requested, confirm=len(words) > 1 and words[1] == "confirm")
