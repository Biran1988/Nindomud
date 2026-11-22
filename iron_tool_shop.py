"""Iron-tier gathering tools sold by builder mob 779; new hoes/pots/chisels 30-38.

Reuses existing iron fishing rod, axe and pickaxe object prototypes rather
than creating ambiguous duplicate object names.  Install after persisted
builder data is restored and never overwrite a saved item or shop inventory.
"""

from __future__ import annotations

# Existing craftable iron tools (preserve original object VNUMs).
EXISTING_IRON_TOOLS = (
    (20002, "An Ironbound Oak Fishing Rod"),
    (20201, "An Ironbound Oak Axe"),
    (20101, "An Ironbound Oak Pickaxe"),
)

# New additions start directly after Chuunin armor's last VNUM (29).
# VNUM, tool kind, tier. Names, recipe prices and uses have one source of truth.
NEW_TOOLS = (
    (30, "hoe", "iron"),
    (31, "hoe", "steel"),
    (32, "hoe", "chakra"),
    (33, "pot", "iron"),
    (34, "pot", "steel"),
    (35, "pot", "chakra"),
    (36, "chisel", "iron"),
    (37, "chisel", "steel"),
    (38, "chisel", "chakra"),
)
IRON_SHOP_VNUM = 779
PREVIOUS_IRON_PRICE = 1100


def _raise_standard_iron_price(proto: dict, expected_name: str, new_price: int) -> bool:
    """Migrate only our former default price, never a builder's custom price."""
    if (proto is not None
            and proto.get("item_type") == "tool"
            and str(proto.get("short_desc", "")).casefold() == expected_name.casefold()
            and proto.get("cost") == PREVIOUS_IRON_PRICE):
        proto["cost"] = new_price
        return True
    return False


def install() -> dict:
    """Preserve builder objects; stock six iron tools if mob 779 exists."""
    import combat
    import data_crafting
    import olc
    import shop_flags

    created, preserved, collisions, repriced = [], [], [], []
    chosen = {}
    iron_price = data_crafting.TOOL_RECIPES["iron"]["price"]
    # The older three tools already exist under their original VNUMs.
    # A saved world could still retain their prior 1,100-ryo cost.
    for vnum, name in EXISTING_IRON_TOOLS:
        if _raise_standard_iron_price(olc.OBJECT_TEMPLATES.get(vnum), name, iron_price):
            repriced.append(vnum)
    # New objects use VNUMs 30-38 unless their intended prototype is
    # already present at another VNUM, in which case reuse that prototype.
    for vnum, kind, tier in NEW_TOOLS:
        name = data_crafting.job_tool_name(kind, tier)
        existing = olc.OBJECT_TEMPLATES.get(vnum)
        if existing is not None:
            if (str(existing.get("short_desc", "")).casefold() == name.casefold()
                    and existing.get("item_type") == "tool"):
                chosen[(kind, tier)] = vnum
                preserved.append(vnum)
                if tier == "iron" and _raise_standard_iron_price(existing, name, iron_price):
                    repriced.append(vnum)
            else:
                collisions.append((vnum, name, existing.get("short_desc", "")))
            continue
        matches = [(number, proto)
                   for number, proto in olc.OBJECT_TEMPLATES.items()
                   if proto.get("item_type") == "tool"
                   and str(proto.get("short_desc", "")).casefold() == name.casefold()]
        if matches:
            chosen[(kind, tier)] = matches[0][0]
            preserved.append(matches[0][0])
            if tier == "iron" and _raise_standard_iron_price(matches[0][1], name, iron_price):
                repriced.append(matches[0][0])
            continue
        recipe = data_crafting.TOOL_RECIPES[tier]
        proto = olc.default_object(vnum, name)
        proto.update({
            "item_type": "tool",
            "wear_loc": "tool",
            "cost": recipe["price"],
            "max_uses": recipe["uses"],
            "description": (f"A {tier}-tier {kind} forged from {recipe['wood']} "
                            f"and {recipe['ingot']}. Made for sustained work."),
        })
        # Keep tool crafting job-level restrictions independent of ninja level.
        # Durability uses the recipe's explicit 400/650/1000-use capacity.
        olc._auto_balance_new_equipment(proto)
        olc.OBJECT_TEMPLATES[vnum] = proto
        chosen[(kind, tier)] = vnum
        created.append(vnum)

    # Preserve any existing staff-built shop type/flags; only enable the
    # generic merchant flag if this mob wasn't already a shopkeeper.
    shop = combat.MOB_TEMPLATES.get(IRON_SHOP_VNUM)
    stock_vnums = []
    if shop is not None:
        if not shop_flags.is_shopkeeper_template(shop):
            shop_flags.enable_shopkeeper(shop)
        stock = shop.setdefault("shop_items", [])
        if not isinstance(stock, list):
            stock = list(stock)
            shop["shop_items"] = stock
        for vnum, name in EXISTING_IRON_TOOLS:
            proto = olc.OBJECT_TEMPLATES.get(vnum)
            if (proto is not None and proto.get("item_type") == "tool"
                    and str(proto.get("short_desc", "")).casefold() == name.casefold()):
                stock_vnums.append(vnum)
        for kind in ("hoe", "pot", "chisel"):
            vnum = chosen.get((kind, "iron"))
            if vnum is not None:
                stock_vnums.append(vnum)
        for vnum in stock_vnums:
            if vnum not in stock:
                stock.append(vnum)

    if collisions:
        print("[Iron tool shop] Protected occupied object VNUMs: "
              + ", ".join(str(vnum) for vnum, _name, _current in collisions))
    return {"created": created, "preserved": preserved,
            "repriced": repriced, "collisions": collisions, "stock": stock_vnums,
            "shop_exists": shop is not None}
