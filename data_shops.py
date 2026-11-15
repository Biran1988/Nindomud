"""
NPC merchant specialty rules.

A ShopX mob flag determines which rule-set applies to an NPC merchant.
`allowed_sell_categories` restricts what item_types.classify_item()
categories that shop will buy FROM a
player with `sell`; `None` means it buys anything. `sell_multiplier`
scales item_types.BASE_SELL_PRICE -- specialty shops (weapons,
blacksmith) pay full value for the category they specialize in, while
the general store buys anything but at a reduced price, matching the
brief: "General store will be anything but at a lower value."
"""

SHOP_TYPES = {
    "general": {
        "display_name": "General Store",
        "allowed_sell_categories": None,  # buys anything
        "sell_multiplier": 0.5,
    },
    "weapons": {
        "display_name": "Weapons Shop",
        "allowed_sell_categories": {"weapon"},
        "sell_multiplier": 1.0,
    },
    "blacksmith": {
        "display_name": "Blacksmith",
        "allowed_sell_categories": {"armor"},
        "sell_multiplier": 1.0,
    },
    "food": {
        "display_name": "Food Shop",
        "allowed_sell_categories": {"food"},
        "sell_multiplier": 1.0,
    },
    "mining": {
        "display_name": "Mining Supply Buyer",
        "allowed_sell_categories": {"ore"},
        "sell_multiplier": 1.5,
    },
    "farming": {
        "display_name": "Farm Produce Buyer",
        "allowed_sell_categories": {"food", "misc"},
        "sell_multiplier": 1.5,
    },
    "lumberjack": {
        "display_name": "Lumber Merchant",
        "allowed_sell_categories": {"wood"},
        "sell_multiplier": 1.5,
    },
    "gemcutter": {
        "display_name": "Gemstone Dealer",
        "allowed_sell_categories": {"gem"},
        "sell_multiplier": 1.5,
    },
    "pawnshop": {
        "display_name": "Pawnshop",
        "allowed_sell_categories": None,
        "sell_multiplier": 0.5,
    },
}


def can_sell_here(shop_type: str, category: str) -> bool:
    allowed = SHOP_TYPES[shop_type]["allowed_sell_categories"]
    return allowed is None or category in allowed


def sell_multiplier(shop_type: str) -> float:
    return SHOP_TYPES[shop_type]["sell_multiplier"]


def can_buy_item(shop_type: str, item_name: str, category: str) -> bool:
    """Check a specialty's real produce, not merely broad food keywords."""
    if shop_type == "farming":
        import farming
        farm_names = {name.casefold() for name, *_ in farming.FIND_TABLE}
        farm_names.update(name.casefold() for name in farming.EDIBLE_CROPS)
        farm_names.add("medicinal herbs")
        return item_name.casefold() in farm_names
    return can_sell_here(shop_type, category)
