"""Shared one-piece lumber fuel for portable smelting and cooking.

Only Lumberjack's actual harvests qualify. We spend the cheapest available
fuel first so high-level crafting materials such as Yew remain valuable.
Fuel must be carried in the main inventory, not nested in a backpack.
"""
from __future__ import annotations

import lumberjack

WOOD_NAMES = tuple(name.casefold() for name, *_ in lumberjack.FIND_TABLE)
LOG_NAMES = frozenset(name for name in WOOD_NAMES if name.endswith(" log"))


def find_fuel(inventory, *, logs_only: bool = False):
    """Return one inventory string or None, preferring low-grade firewood."""
    acceptable = LOG_NAMES if logs_only else frozenset(WOOD_NAMES)
    for wood in WOOD_NAMES:
        if wood not in acceptable:
            continue
        for item in inventory:
            if item.casefold() == wood:
                return item
    return None


def is_furnace(room) -> bool:
    """Builders designate free-fuel smelting via RSET FLAGS FURNACE."""
    return bool(room and any(str(flag).casefold() == "furnace"
                             for flag in getattr(room, "flags", ())))
