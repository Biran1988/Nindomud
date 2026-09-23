"""
Shop types (Section 21's future shop system).

Each shop room has a `shop_type`. `allowed_sell_categories` restricts
what item_types.classify_item() categories that shop will buy FROM a
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
}


def can_sell_here(shop_type: str, category: str) -> bool:
    allowed = SHOP_TYPES[shop_type]["allowed_sell_categories"]
    return allowed is None or category in allowed


def sell_multiplier(shop_type: str) -> float:
    return SHOP_TYPES[shop_type]["sell_multiplier"]
