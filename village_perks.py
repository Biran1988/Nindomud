"""
Kage-sold village perks.

Unlike everything else purchasable in the game, these are GLOBAL: buying
one affects every player belonging to that village, not just the buyer
(bought with `buy <perk>` while standing in your own village's Kage
chamber). Priced in MISSION POINTS, not ryo -- fitting since they're a
reward for completing missions for your village, not just having ryo on
hand. State is per-village, not per-player. Kage-bought perks remain temporary;
immortal-activated MUD-wide 24-hour overrides are separately persisted to disk so
reboots cannot prematurely end an event perk.

Three independent categories (a village can have one active perk from
each category at once; buying a new one in the same category replaces
the old one rather than stacking):
  - "exp": scales experience gained by every player of that village.
  - "damage": scales outgoing player damage for every player of that village.
  - "ryo": scales ryo gained (mob kills and mission rewards) for every player of that village.

Every perk shares the same duration: DEFAULT_DURATION_SECONDS (1 hour).
"""

import json
import os
import time
from typing import List, Optional

import storage
from data_villages import VILLAGES

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

# Immortal event perks are GLOBAL across the entire MUD: all villages,
# including any new villages, use the same category records under "all".
# They override (but never erase) normal Kage-purchased village perks.
# Independent 24-hour staff timers are persisted across reboots.
STAFF_DURATION_SECONDS = 24 * 60 * 60
_STAFF_PERKS: dict = {}
_STAFF_LOADED_PATH: Optional[str] = None


def _staff_file_path() -> str:
    # Resolve lazily so patched storage.DATA_DIR and deployments work.
    return os.path.join(storage.DATA_DIR, "village_perks.json")


def _load_staff_perks() -> None:
    global _STAFF_LOADED_PATH
    path = _staff_file_path()
    if path == _STAFF_LOADED_PATH:
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            records = json.load(handle)
    except (FileNotFoundError, ValueError, OSError):
        records = {}
    # Never apply unknown or corrupted categories/keys from save data.
    valid = {}
    now = time.time()
    if isinstance(records, dict):
        for village, categories in records.items():
            if village != "all" or not isinstance(categories, dict):
                continue
            for category, entry in categories.items():
                if category not in CATEGORIES or not isinstance(entry, dict):
                    continue
                key = entry.get("perk")
                expiry = entry.get("expires_at")
                if (key not in PERK_TYPES or
                        PERK_TYPES[key]["category"] != category or
                        not isinstance(expiry, (int, float)) or expiry <= now):
                    continue
                valid.setdefault(village, {})[category] = {
                    "perk": key, "expires_at": expiry,
                }
    _STAFF_PERKS.clear()
    _STAFF_PERKS.update(valid)
    _STAFF_LOADED_PATH = path


def _save_staff_perks() -> None:
    _load_staff_perks()
    storage.ensure_dirs()
    path = _staff_file_path()
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(_STAFF_PERKS, handle, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def set_staff_perk(village: str, perk_key: str) -> float:
    """Activate a free, 24-hour global perk, saved across reboots."""
    if village != "all" or perk_key not in PERK_TYPES:
        raise ValueError("Invalid village or perk.")
    _load_staff_perks()
    info = PERK_TYPES[perk_key]
    category = info["category"]
    previous = _STAFF_PERKS.get(village, {}).get(category)
    expiry = time.time() + STAFF_DURATION_SECONDS
    _STAFF_PERKS.setdefault(village, {})[category] = {
        "perk": perk_key, "expires_at": expiry,
    }
    try:
        _save_staff_perks()
    except OSError:
        if previous is None:
            del _STAFF_PERKS[village][category]
            if not _STAFF_PERKS[village]:
                del _STAFF_PERKS[village]
        else:
            _STAFF_PERKS[village][category] = previous
        raise
    return expiry


def clear_staff_perk(village: str, perk_key: str) -> bool:
    """Disable exactly this staff perk without affecting Kage purchases."""
    if village != "all" or perk_key not in PERK_TYPES:
        raise ValueError("Invalid village or perk.")
    _load_staff_perks()
    category = PERK_TYPES[perk_key]["category"]
    previous = _STAFF_PERKS.get(village, {}).get(category)
    if not previous or previous["perk"] != perk_key:
        return False
    del _STAFF_PERKS[village][category]
    if not _STAFF_PERKS[village]:
        del _STAFF_PERKS[village]
    try:
        _save_staff_perks()
    except OSError:
        _STAFF_PERKS.setdefault(village, {})[category] = previous
        raise
    return True


def _staff_entry(village: str, category: str) -> Optional[dict]:
    _load_staff_perks()
    entry = _STAFF_PERKS.get("all", {}).get(category)
    if entry and entry["expires_at"] > time.time():
        return entry
    return None


def _active_entry(village: str, category: str) -> Optional[dict]:
    staff_entry = _staff_entry(village, category)
    if staff_entry:
        return staff_entry
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


def staff_perks_display(village: str) -> List[str]:
    """Administrative view of global 24-hour overrides and their remaining time."""
    lines = []
    for category in CATEGORIES:
        entry = _staff_entry(village, category)
        if entry:
            remaining = max(0, int(entry["expires_at"] - time.time()))
            hours, leftover = divmod(remaining, 3600)
            minutes = leftover // 60
            name = PERK_TYPES[entry["perk"]]["display_name"]
            lines.append(f"{name}: {hours}h {minutes}m remaining")
    return lines


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
