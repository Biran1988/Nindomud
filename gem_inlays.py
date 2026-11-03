"""Cut gemstone inlays for uniquely forged weapons and armor.

Only genuinely forged prototype records may accept an inlay. The inlay is
stored on the saved object prototype (never in the visible item name).
Every elemental gem has identical stats; its offensive nature and protective
counter-element are determined by the existing elemental counter wheel.
"""
from __future__ import annotations

import elemental_counters

ELEMENT_GEMS = {
    "ruby": "fire", "sapphire": "water", "emerald": "earth",
    "amethyst": "wind", "topaz": "lightning",
}
LOWER_GEMS = {"quartz": 2, "jade": 3, "amber": 3, "garnet": 3}
CUT_GEMS = tuple(LOWER_GEMS) + tuple(ELEMENT_GEMS) + ("diamond",)
ELEMENTAL_FLAT_BONUS = 10
ELEMENTAL_JUTSU_BONUS_PERCENT = 15
ELEMENTAL_COUNTER_RESIST_PERCENT = 15
MAX_ELEMENTAL_BONUS_PERCENT = 30
MAX_ELEMENTAL_RESIST_PERCENT = 30

def strength(gem: str) -> int:
    gem = gem.lower()
    if gem in ELEMENT_GEMS:
        return ELEMENTAL_FLAT_BONUS
    if gem == "diamond":
        return 12
    return LOWER_GEMS.get(gem, 0)

def cut_name(gem: str) -> str:
    return "A Cut " + gem.title()

def gem_from_cut_item(name: str) -> str | None:
    candidate = name.strip().casefold()
    for gem in CUT_GEMS:
        if candidate == cut_name(gem).casefold():
            return gem
    return None

def inlaid(proto: dict) -> str | None:
    gem = proto.get("gem_inlay")
    return gem if gem in CUT_GEMS else None

def equipped_gems(actor) -> list:
    import olc
    found = []
    for _slot, name in getattr(actor, "equipment", {}).items():
        if not name:
            continue
        matches = [p for p in olc.OBJECT_TEMPLATES.values()
                   if p.get("short_desc", "").casefold() == name.casefold()]
        # Name-only inventory means ambiguously named prototypes are unsafe.
        if len(matches) != 1:
            continue
        gem = inlaid(matches[0])
        if gem:
            found.append(gem)
    return found

def equipment_flat_bonus(actor) -> int:
    return sum(strength(gem) for gem in equipped_gems(actor))

def elemental_jutsu_multiplier(actor, element: str) -> float:
    if element not in ELEMENT_GEMS.values():
        return 1.0
    count = sum(ELEMENT_GEMS.get(gem) == element for gem in equipped_gems(actor))
    boost = min(MAX_ELEMENTAL_BONUS_PERCENT, count * ELEMENTAL_JUTSU_BONUS_PERCENT)
    return 1.0 + boost / 100.0

def reduce_counter_damage(actor, element: str, damage: int) -> int:
    """A fire inlay protects against water; other elements use the same wheel."""
    if damage <= 0 or not element:
        return damage
    count = sum(elemental_counters.ELEMENT_COUNTERS.get(ELEMENT_GEMS.get(gem)) == element
                for gem in equipped_gems(actor))
    resist = min(MAX_ELEMENTAL_RESIST_PERCENT, count * ELEMENTAL_COUNTER_RESIST_PERCENT)
    return max(1, damage * (100 - resist) // 100) if resist else damage

def forged_prototype(name: str):
    """Refuse duplicate names so an inlay cannot silently modify other items."""
    import olc
    matches = [p for p in olc.OBJECT_TEMPLATES.values()
               if p.get("short_desc", "").casefold() == name.casefold()]
    if len(matches) != 1:
        return None
    proto = matches[0]
    return (proto if proto.get("item_type") in ("weapon", "armor")
            and proto.get("craft_materials") else None)

def available_cut_gem(player, query: str):
    from inventory import parse_indexed_query
    index, keyword = parse_indexed_query(query.casefold().strip())
    matches = [name for name in player.inventory if gem_from_cut_item(name)
               and keyword in name.casefold()]
    return matches[index - 1] if 1 <= index <= len(matches) else None
