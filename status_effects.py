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
