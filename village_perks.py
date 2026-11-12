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

Kage purchases normally last one hour. Automatic MUD-wide perks run for
30 minutes each, with one window per category in every 24-hour cycle.
"""

import json
import logging
import os
import random
import time
from functools import lru_cache
from typing import List, Optional

import storage

DEFAULT_DURATION_SECONDS = 3600  # 1 hour for Kage purchases
AUTOMATIC_DURATION_SECONDS = 30 * 60
AUTOMATIC_CYCLE_SECONDS = 24 * 60 * 60
_AUTOMATIC_SLOT_COUNT = AUTOMATIC_CYCLE_SECONDS // AUTOMATIC_DURATION_SECONDS
LOG = logging.getLogger(__name__)

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
    _save_perk_records(_staff_file_path(), _STAFF_PERKS)


def _save_perk_records(path: str, records: dict) -> None:
    storage.ensure_dirs()
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _load_automatic_schedule(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            schedule = json.load(handle)
    except (FileNotFoundError, ValueError):
        return None
    if not isinstance(schedule, dict):
        return None
    cycle_start = schedule.get("cycle_start")
    slots = schedule.get("slots")
    if type(cycle_start) is not int or not isinstance(slots, dict) or len(slots) != len(CATEGORIES):
        return None
    if any(key not in PERK_TYPES or type(slot) is not int or not 0 <= slot < _AUTOMATIC_SLOT_COUNT
           for key, slot in slots.items()):
        return None
    if (len(set(slots.values())) != len(CATEGORIES) or
            {PERK_TYPES[key]["category"] for key in slots} != set(CATEGORIES)):
        return None
    return schedule


def _roll_automatic_schedule(cycle_start: int) -> dict:
    slots = random.sample(range(_AUTOMATIC_SLOT_COUNT), len(CATEGORIES))
    keys = [
        random.choice([key for key, info in PERK_TYPES.items() if info["category"] == category])
        for category in CATEGORIES
    ]
    return {"cycle_start": cycle_start, "slots": dict(zip(keys, slots))}


class _AutomaticPerks:
    def __init__(self, path: str):
        self.path = path
        self.schedule: Optional[dict] = None
        self.announced_start: Optional[int] = None
        self.retry_at = 0.0

    def _refresh(self, now: float) -> None:
        if self.schedule is None:
            self.schedule = _load_automatic_schedule(self.path)
        cycle_start = self.schedule["cycle_start"] if self.schedule else int(now)
        elapsed_cycles = (int(now) - cycle_start) // AUTOMATIC_CYCLE_SECONDS
        if self.schedule is not None and elapsed_cycles < 1:
            return

        # Skip elapsed cycles when the server has been down.
        schedule = _roll_automatic_schedule(cycle_start + elapsed_cycles * AUTOMATIC_CYCLE_SECONDS)
        _save_perk_records(self.path, schedule)
        self.schedule = schedule

    def active(self, now: float) -> Optional[dict]:
        if self.schedule is None:
            return None
        cycle_start = self.schedule["cycle_start"]
        for key, slot in self.schedule["slots"].items():
            start = cycle_start + slot * AUTOMATIC_DURATION_SECONDS
            expiry = start + AUTOMATIC_DURATION_SECONDS
            if start <= now < expiry:
                return {"perk": key, "starts_at": start, "expires_at": expiry}
        return None

    def tick(self) -> Optional[str]:
        now = time.time()
        if now < self.retry_at:
            return None
        try:
            self._refresh(now)
        except OSError as error:
            self.retry_at = now + 60
            LOG.warning("Could not update automatic village perks: %s", error)
            return None

        active = self.active(now)
        if active and active["starts_at"] != self.announced_start:
            self.announced_start = active["starts_at"]
            return f"&Y[Global village perk]&x {_display_active(active, now)}"
        return None


@lru_cache(maxsize=1)
def _automatic_perks(data_dir: str) -> _AutomaticPerks:
    return _AutomaticPerks(os.path.join(data_dir, "village_perk_schedule.json"))


def tick_automatic_perks() -> Optional[str]:
    return _automatic_perks(storage.DATA_DIR).tick()


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
    now = time.time()
    purchased = _ACTIVE_PERKS.get(village, {}).get(category)
    if purchased and purchased["expires_at"] <= now:
        purchased = None
    automatic = _automatic_perks(storage.DATA_DIR).active(now)
    if automatic is None or PERK_TYPES[automatic["perk"]]["category"] != category:
        return purchased
    if purchased is None:
        return automatic
    return max((purchased, automatic), key=lambda entry: (
        PERK_TYPES[entry["perk"]]["multiplier"], entry["expires_at"],
    ))


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


def _display_active(entry: dict, now: float) -> str:
    name = PERK_TYPES[entry["perk"]]["display_name"]
    minutes, seconds = divmod(max(0, int(entry["expires_at"] - now)), 60)
    return f"{name} active ({minutes}m {seconds}s remaining)"


def automatic_perk_display() -> Optional[str]:
    now = time.time()
    entry = _automatic_perks(storage.DATA_DIR).active(now)
    return _display_active(entry, now) if entry else None


def active_perks_display(village: str) -> List[str]:
    lines = []
    for category in CATEGORIES:
        entry = _active_entry(village, category)
        if entry:
            lines.append(_display_active(entry, time.time()))
    return lines
