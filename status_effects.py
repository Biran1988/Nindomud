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
    "barrier": {
        "display_name": "Barrier", "duration": 5,
        "message": "A chakra barrier surrounds {target}.",
        "damage_reduction_pct": 10,
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
    "chisei": {"display_name": "Chisei", "duration": 6,
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


def apply_effect(effects: Dict[str, dict], name: str, source: str = "", duration_override: int = None) -> None:
    defn = EFFECT_DEFS[name]
    duration = duration_override if duration_override is not None else defn["duration"]
    effects[name] = {"duration": duration, "source": source}


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
    if "weakened" not in effects or amount <= 0:
        return amount
    return max(1, amount * (100 - EFFECT_DEFS["weakened"]["damage_penalty_pct"]) // 100)


def tick_effects(effects: Dict[str, dict]) -> list:
    """Decrement durations by one pulse; return list of effect names that expired."""
    expired = []
    for name in list(effects.keys()):
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
