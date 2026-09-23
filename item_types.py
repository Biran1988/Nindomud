"""
Item category classification, used by shop `sell` restrictions.

Player inventory is plain name strings (no per-item object instances),
so -- matching the same pattern as data_weapons.py and consumables.py --
this classifies an item by keyword-matching its name rather than
requiring a full object-instance system. A weapon shop only buys items
that classify as "weapon" (any of data_weapons.py's weapon types), a
blacksmith only buys "armor", and a general store buys anything but
pays less for it.
"""

from typing import Optional

import consumables
import data_weapons

ARMOR_KEYWORDS = [
    "shirt", "pants", "sandals", "headband", "armor", "robe", "vest",
    "gauntlet", "helmet", "gi", "cloak", "boots", "guard",
]

# Base ryo a shop pays for an item of this category before the shop's
# own multiplier (specialty shops pay full value, general stores less).
# Only a FALLBACK now -- an item with its own registered OLC cost uses
# a fraction of that instead (see base_sell_price), so this only
# applies to items that were never registered as a prototype at all.
BASE_SELL_PRICE = {
    "weapon": 12,
    "armor": 8,
    "food": 2,
    "drink": 2,
    "medical": 6,
    "misc": 1,
}

# What fraction of an item's own registered OLC cost a shop pays for
# it -- deliberately well under 100%, or buying then immediately
# reselling would be close to free money.
PROTOTYPE_SELL_FRACTION = 0.1


def classify_item(item_name: str) -> str:
    """Returns one of: weapon, armor, food, drink, medical, misc."""
    if data_weapons.weapon_type_for_item(item_name):
        return "weapon"
    name_lower = item_name.lower()
    if any(keyword in name_lower for keyword in ARMOR_KEYWORDS):
        return "armor"
    _match_name, data = consumables.find_consumable(item_name)
    if data:
        return data["category"]  # "food" / "drink" / "medical"
    return "misc"


def _prototype_sell_price(item_name: str) -> Optional[int]:
    """A fraction of the item's OWN registered OLC cost, if a matching
    prototype exists -- e.g. a Watermelon (registered cost 130) sells
    for more than a plain Rice Ball, rather than both falling back to
    the same flat "food" category price. Bidirectional substring match,
    same convention as commands._find_object_prototype_by_name, so a
    suffixed display name (a crafted item's stat bonus, a cooked dish's
    quality tier) still resolves to its base prototype. Returns None if
    nothing matches, so the caller falls back to the flat category
    price."""
    import olc
    query = item_name.lower()
    for proto in olc.OBJECT_TEMPLATES.values():
        short_desc = proto["short_desc"].lower()
        if query in short_desc or short_desc in query:
            return max(1, int(proto["cost"] * PROTOTYPE_SELL_FRACTION))
    return None


def base_sell_price(item_name: str) -> int:
    prototype_price = _prototype_sell_price(item_name)
    if prototype_price is not None:
        return prototype_price
    return BASE_SELL_PRICE[classify_item(item_name)]
