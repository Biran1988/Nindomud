"""Bukijutsu pills with per-unit metadata in the legacy string inventory."""

import re

HERB_NAME = "Medicinal Herbs"
MIN_CRAFTER_LEVEL = 25
PILL_PATTERN = re.compile(r"^(Antidote|Medicinal) Pill\x1e\{pill_level:([1-9][0-9]{0,2})\}$", re.I)
PILL_DATA_SUFFIX = re.compile(r"\x1e\{pill_level:[1-9][0-9]{0,2}\}")


def pill_name(kind: str) -> str:
    return f"{kind} Pill"


def encode_pill(kind: str, level: int) -> str:
    return f"{pill_name(kind)}\x1e{{pill_level:{level}}}"


def display_name(item_name: str) -> str:
    return PILL_DATA_SUFFIX.sub("", item_name)


def pill_data(item_name: str):
    """Decode an inventory string; its selected strength survives saves/trades."""
    match = PILL_PATTERN.fullmatch(item_name)
    if not match:
        return None
    kind, raw_level = match.groups()
    level = int(raw_level)
    if not 1 <= level <= 100:
        return None
    if kind.lower() == "antidote":
        return {
            "category": "medical", "level": level, "resources": ["health"],
            "amount": 50 + 2 * level, "heal_duration": 30,
            "cures": ["poisoned"],
            "message": "You swallow {item}. The poison leaves your body.",
        }
    return {
        "category": "medical", "level": level, "resources": ["health", "chakra", "stamina"],
        "amount": 100 + 6 * level, "heal_duration": 30,
        "cures": ["bleeding", "silenced"],
        "message": "You swallow {item}. Its potent herbs begin restoring you.",
    }
