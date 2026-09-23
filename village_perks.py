"""
Kage-sold village perks.

Unlike everything else purchasable in the game, these are GLOBAL: buying
one affects every player belonging to that village, not just the buyer
(bought with `buy <perk>` while standing in your own village's Kage
chamber). Priced in MISSION POINTS, not ryo -- fitting since they're a
reward for completing missions for your village, not just having ryo on
hand. State is per-village, not per-player, and lives here as plain
module-level dicts -- there's no reason to persist it to disk since a
temporary buff expiring across a server restart is fine.

Three independent categories (a village can have one active perk from
each category at once; buying a new one in the same category replaces
the old one rather than stacking):
  - "exp": scales experience gained by every player of that village.
  - "damage": scales outgoing player damage for every player of that village.
  - "ryo": scales ryo gained (mob kills and mission rewards) for every player of that village.

Every perk shares the same duration: DEFAULT_DURATION_SECONDS (1 hour).
"""

import time
from typing import List, Optional

DEFAULT_DURATION_SECONDS = 3600  # 1 hour -- applies to every perk

PERK_TYPES = {
    "double exp": {"display_name": "Double Experience", "category": "exp", "multiplier": 2.0, "cost": 5},
    "triple exp": {"display_name": "Triple Experience", "category": "exp", "multiplier": 3.0, "cost": 12},
    "double damage": {"display_name": "Double Damage", "category": "damage", "multiplier": 2.0, "cost": 8},
    "triple damage": {"display_name": "Triple Damage", "category": "damage", "multiplier": 3.0, "cost": 20},
    "double ryo": {"display_name": "Double Ryo", "category": "ryo", "multiplier": 2.0, "cost": 5},
    "triple ryo": {"display_name": "Triple Ryo", "category": "ryo", "multiplier": 3.0, "cost": 12},
}

CATEGORIES = ("exp", "damage", "ryo")


def duration_seconds(perk_key: str) -> int:
    return PERK_TYPES[perk_key].get("duration_seconds", DEFAULT_DURATION_SECONDS)


# village -> {"exp": {"perk": key, "expires_at": ts}, "damage": {...}}
_ACTIVE_PERKS: dict = {}


def _active_entry(village: str, category: str) -> Optional[dict]:
    entry = _ACTIVE_PERKS.get(village, {}).get(category)
    if not entry:
        return None
    if entry["expires_at"] <= time.time():
        return None
    return entry


def purchase(village: str, perk_key: str) -> None:
    info = PERK_TYPES[perk_key]
    _ACTIVE_PERKS.setdefault(village, {})[info["category"]] = {
        "perk": perk_key,
        "expires_at": time.time() + duration_seconds(perk_key),
    }


def xp_multiplier(village: str) -> float:
    entry = _active_entry(village, "exp")
    return PERK_TYPES[entry["perk"]]["multiplier"] if entry else 1.0


def damage_multiplier(village: str) -> float:
    entry = _active_entry(village, "damage")
    return PERK_TYPES[entry["perk"]]["multiplier"] if entry else 1.0


def ryo_multiplier(village: str) -> float:
    entry = _active_entry(village, "ryo")
    return PERK_TYPES[entry["perk"]]["multiplier"] if entry else 1.0


def active_perks_display(village: str) -> List[str]:
    lines = []
    for category in CATEGORIES:
        entry = _active_entry(village, category)
        if entry:
            info = PERK_TYPES[entry["perk"]]
            remaining = int(entry["expires_at"] - time.time())
            lines.append(f"{info['display_name']} active ({remaining // 60}m {remaining % 60}s remaining)")
    return lines
