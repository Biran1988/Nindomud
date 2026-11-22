"""Cut gemstone inlays for uniquely forged gear and diamond-enhanced tools.

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

# Diamond doubles item durability instead of granting combat stats.
DIAMOND_DURABILITY_MULTIPLIER = 2

def strength(gem: str) -> int:
    gem = gem.lower()
    if gem in ELEMENT_GEMS:
        return ELEMENTAL_FLAT_BONUS
    if gem == "diamond":
        return 0
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
    import ninja_arts
    found = []
    import crafted_identity
    for _slot, name in getattr(actor, "equipment", {}).items():
        if not name:
            continue
        if crafted_identity.marked(name):
            linked = crafted_identity.resolve(name)
        else:
            linked = crafted_identity.legacy_match(ninja_arts.base_item(name))
        if not linked:
            continue
        gem = inlaid(linked[1])
        if gem:
            found.append(gem)
    return found

def equipment_flat_bonus(actor) -> int:
    return sum(strength(gem) for gem in equipped_gems(actor))

def elemental_jutsu_multiplier(actor, element: str) -> float:
    if element not in ELEMENT_GEMS.values():
        return 1.0
    count = sum(ELEMENT_GEMS.get(gem) == element for gem in equipped_gems(actor))
    # An equipped Jounin-shop Aura grants its own modest, matching-nature
    # jutsu boost, compatible with (and capped alongside) existing gem inlays.
    import jounin_shops
    aura_bonus = (jounin_shops.ELEMENTAL_AURA_JUTSU_PERCENT
                  if jounin_shops.equipped_aura_element(actor) == element else 0)
    boost = min(MAX_ELEMENTAL_BONUS_PERCENT,
                count * ELEMENTAL_JUTSU_BONUS_PERCENT + aura_bonus)
    return 1.0 + boost / 100.0

def reduce_counter_damage(actor, element: str, damage: int) -> int:
    """A fire inlay protects against water; other elements use the same wheel."""
    if damage <= 0 or not element:
        return damage
    count = sum(elemental_counters.ELEMENT_COUNTERS.get(ELEMENT_GEMS.get(gem)) == element
                for gem in equipped_gems(actor))
    import jounin_shops
    aura = jounin_shops.equipped_aura_element(actor)
    aura_resist = (jounin_shops.ELEMENTAL_AURA_COUNTER_RESIST_PERCENT
                   if aura and elemental_counters.ELEMENT_COUNTERS.get(aura) == element
                   else 0)
    resist = min(MAX_ELEMENTAL_RESIST_PERCENT,
                 count * ELEMENTAL_COUNTER_RESIST_PERCENT + aura_resist)
    return max(1, damage * (100 - resist) // 100) if resist else damage

def forged_prototype(name: str):
    """Resolve the exact forged VNUM, including same-name equipment."""
    import crafted_identity
    linked = (crafted_identity.resolve(name) if crafted_identity.marked(name)
              else crafted_identity.legacy_match(name))
    if not linked:
        return None
    proto = linked[1]
    return (proto if proto.get("item_type") in ("weapon", "armor")
            and proto.get("craft_materials") else None)

def diamond_tool_prototype(item_name: str):
    """Resolve one genuine tool prototype without altering all instances."""
    import olc
    import tool_durability
    base = tool_durability.base_name(item_name).casefold()
    matches = [proto for proto in olc.OBJECT_TEMPLATES.values()
               if proto.get("item_type") == "tool"
               and proto.get("short_desc", "").casefold() == base]
    return matches[0] if len(matches) == 1 else None


def available_cut_gem(player, query: str):
    from inventory import parse_indexed_query
    index, keyword = parse_indexed_query(query.casefold().strip())
    matches = [name for name in player.inventory if gem_from_cut_item(name)
               and keyword in name.casefold()]
    return matches[index - 1] if 1 <= index <= len(matches) else None
