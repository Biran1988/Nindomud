"""
Status effect engine (Section 17).

Effects are independent dict entries keyed by name on whatever entity
carries them (Player.active_status_effects, or a Mob's in-memory dict) --
deliberately NOT one shared giant script, per the brief's requirement.
Each entry is {"duration": <pulses remaining>, "strength": int,
"source": str}.
"""

import random
from typing import Dict

EFFECT_DEFS = {
    # Hyuga: finite defensive windows rather than permanent invulnerability.
    "hyuga_rotation": {"display_name": "protected by Rotation", "duration": 3,
        "damage_reduction_pct": 40, "message": None},
    "hyuga_protecting": {"display_name": "guarded by Eight Trigrams", "duration": 3,
        "damage_reduction_pct": 28, "message": None},
    "hyuga_fate": {"display_name": "peering into imminent futures", "duration": 3,
        "message": None},
    "hyuga_tenseigan": {"display_name": "surrounded by Tenseigan chakra", "duration": 5,
        "damage_reduction_pct": 20, "message": None},
    "camouflage": {"display_name": "Camouflaged", "duration": 1, "toggled": True, "message": None},
    "silent_movement": {"display_name": "Moving Silently", "duration": 1,
                        "toggled": True, "message": None},
    "sensory_detect": {"display_name": "Sensory Detect", "duration": 120, "message": None},
    "focused_mind": {"display_name": "Focused Mind", "duration": 120, "message": None},
    # Legacy saved effects can finish ticking safely after Samurai Sabre's
    # migration to a persisted upkeep toggle; new casts do not apply this.
    "samurai_sabre": {
        "display_name": "Samurai Sabre", "duration": 5,
        "message": "Chakra sharpens {target}'s sword.",
    },
    "barrier": {
        "display_name": "Barrier", "duration": 180,
        "message": "A chakra barrier surrounds {target}.",
        "damage_reduction_pct": 25,
    },
    "blinded": {
        "display_name": "Blinded", "duration": 2,
        "message": "Blinding pain disrupts {target}!",
        "accuracy_penalty": 25,
    },
    "stunned": {
        "display_name": "Stunned",
        "duration": 1,
        "message": "{target} is stunned and can't act!",
        "blocks_action": True,
    },
    "bleeding": {
        "display_name": "Bleeding",
        "duration": 3,
        "message": "{target} is bleeding.",
        "damage_per_tick": (2, 4),
    },
    "poisoned": {"display_name": "Poisoned", "duration": 3,
                 "message": "{target} is poisoned.", "damage_per_tick": (3, 5)},
    "confused": {
        "display_name": "Confused",
        "duration": 2,
        "message": "{target} looks confused.",
        "accuracy_penalty": 25,
    },
    "frightened": {
        "display_name": "Frightened",
        "duration": 2,
        "message": "{target} is frightened.",
        "damage_penalty_pct": 20,
    },
    "silenced": {
        "display_name": "Silenced",
        "duration": 2,
        "message": "{target} is silenced and cannot use jutsu!",
        "blocks_jutsu": True,
    },
    "recently defeated": {
        "display_name": "Recently Defeated",
        "duration": 45,
        "message": None,
        "protection": True,
    },
    "entangled": {
        "display_name": "Entangled",
        "duration": 15,
        "message": "{target} is entangled and can't move!",
        "blocks_movement": True,
    },
    "genjutsu_locked": {
        "display_name": "Genjutsu-Locked",
        "duration": 2,
        "message": "{target} is trapped in a genjutsu and can't act!",
        "blocks_action": True,
    },
    "narakumi": {
        "display_name": "Narakumi",
        "duration": 3,
        "message": "{target} is trapped in Narakumi's grip, their reflexes dulled.",
        "accuracy_penalty": 20,
    },
    "soundless": {"display_name": "Soundless", "duration": 3,
                  "message": "{target} loses focus in the impossible silence.", "accuracy_penalty": 12},
    "disoriented": {"display_name": "Disoriented", "duration": 2,
                    "message": "{target} is disoriented and drained.", "accuracy_penalty": 15},
    "weakened": {"display_name": "Weakened", "duration": 3,
                 "message": "{target} feels weak in the snakes' grip.", "damage_penalty_pct": 15},
    "haze": {"display_name": "Haze", "duration": 2,
             "message": "{target} loses track of the haze clones.", "accuracy_penalty": 35},
    "ringing": {"display_name": "Ringing", "duration": 2,
                "message": "{target} staggers at the sound of bells.", "accuracy_penalty": 25,
                "blocks_action": True},
    "asleep": {"display_name": "Asleep", "duration": 2,
                "message": "{target} falls asleep beneath illusory feathers.", "blocks_action": True},
    "chisei": {"display_name": "Chisei", "duration": 1, "toggled": True,
                "message": "{target}'s eyes shine with heightened focus."},
    "burning": {
        "display_name": "Burning",
        "duration": 3,
        "message": "{target} is burning.",
        "damage_per_tick": (3, 6),
    },
    "drained": {
        "display_name": "Drained",
        "duration": 3,
        "message": "{target}'s chakra is being drained away.",
        "chakra_drain_per_tick": (8, 15),
    },
    "off_balance": {
        "display_name": "Off Balance",
        "duration": 3,
        "message": "{target} is knocked off balance.",
        "stamina_drain_per_tick": (8, 15),
    },
    "paralyzed": {
        "display_name": "Paralyzed",
        "duration": 2,
        "message": "{target} is paralyzed and can't act!",
        "blocks_action": True,
    },
}

# A pulse is one second. These durations apply only when the status comes
# from Genjutsu; other attacks using the same status keep EFFECT_DEFS timing.
GENJUTSU_DURATIONS = {
    "frightened": 20, "narakumi": 24, "soundless": 24,
    "disoriented": 20, "confused": 20, "weakened": 24,
    "haze": 24, "blinded": 20,
    "stunned": 10, "paralyzed": 10, "ringing": 10,
    "asleep": 12, "genjutsu_locked": 10,
}


def genjutsu_duration(name: str) -> int:
    """Status lifetime in seconds when inflicted by a Genjutsu technique."""
    return GENJUTSU_DURATIONS.get(name, EFFECT_DEFS[name]["duration"])


# Willpower is trainable from 10 to 75. At maximum Willpower, ordinary
# Genjutsu has a 30% chance to fail on application and a 13% chance to
# break on each later one-second pulse. Neither roll negates direct jutsu
# damage, and neither bypasses Mangekyo's unique puzzle/dimension rules.
WILLPOWER_BASE = 10
WILLPOWER_RESIST_CAP = 30
WILLPOWER_ESCAPE_CAP = 13


def willpower_resist_chance(willpower: int) -> int:
    """Percentage chance to shrug off an ordinary Genjutsu status on cast."""
    return min(WILLPOWER_RESIST_CAP, max(0, (willpower - WILLPOWER_BASE) // 2))


def willpower_escape_chance(willpower: int) -> int:
    """Per-second chance to force an ordinary active Genjutsu effect off."""
    return min(WILLPOWER_ESCAPE_CAP, max(0, (willpower - WILLPOWER_BASE) // 5))


def willpower_resists(player) -> bool:
    chance = willpower_resist_chance(getattr(player, "willpower", WILLPOWER_BASE))
    return chance > 0 and random.randint(1, 100) <= chance


def willpower_breaks(player) -> bool:
    chance = willpower_escape_chance(getattr(player, "willpower", WILLPOWER_BASE))
    return chance > 0 and random.randint(1, 100) <= chance


def break_genjutsu_effects(effects: Dict[str, dict], player) -> list:
    """Remove ONLY statuses explicitly tagged as ordinary Genjutsu.

    Never free a target from Mangekyo-specific frozen/loop states or
    natural sleep, poison, ordinary non-Genjutsu stuns, or physical traps.
    """
    broken = []
    for name, state in list(effects.items()):
        if state.get("genjutsu") and willpower_breaks(player):
            effects.pop(name, None)
            broken.append(name)
    return broken


def apply_effect(effects: Dict[str, dict], name: str, source: str = "",
                 duration_override: int = None, *, genjutsu: bool = False) -> None:
    defn = EFFECT_DEFS[name]
    duration = duration_override if duration_override is not None else defn["duration"]
    effects[name] = {"duration": duration, "source": source}
    if genjutsu:
        effects[name]["genjutsu"] = True


def has_effect(effects: Dict[str, dict], name: str) -> bool:
    return name in effects


def reduce_incoming_damage(effects: Dict[str, dict], amount: int) -> int:
    """Barrier mitigates damage after other defenses, for any incoming hit."""
    if amount <= 0:
        return amount
    reduction = max((EFFECT_DEFS.get(name, {}).get("damage_reduction_pct", 0)
                     for name in effects), default=0)
    return max(1, amount * (100 - reduction) // 100)


def reduce_outgoing_damage(effects: Dict[str, dict], amount: int) -> int:
    if amount <= 0:
        return amount
    for name in ("weakened", "frightened"):
        if name in effects:
            amount = max(1, amount * (100 - EFFECT_DEFS[name]["damage_penalty_pct"]) // 100)
    return amount


def tick_effects(effects: Dict[str, dict]) -> list:
    """Tick timed effects; toggles stay on until explicitly removed."""
    expired = []
    for name in list(effects.keys()):
        if (EFFECT_DEFS.get(name, {}).get("toggled")
                and effects[name].get("duration", 0) > 0):
            continue
        effects[name]["duration"] -= 1
        if effects[name]["duration"] <= 0:
            del effects[name]
            expired.append(name)
    return expired


def bleeding_damage() -> int:
    lo, hi = EFFECT_DEFS["bleeding"]["damage_per_tick"]
    return random.randint(lo, hi)


def burning_damage() -> int:
    lo, hi = EFFECT_DEFS["burning"]["damage_per_tick"]
    return random.randint(lo, hi)


def drained_chakra_loss() -> int:
    lo, hi = EFFECT_DEFS["drained"]["chakra_drain_per_tick"]
    return random.randint(lo, hi)


def off_balance_stamina_loss() -> int:
    lo, hi = EFFECT_DEFS["off_balance"]["stamina_drain_per_tick"]
    return random.randint(lo, hi)
