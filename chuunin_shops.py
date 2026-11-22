"""Chuunin weapon and armor stock for builder-owned shopkeeper mobs 775/776.

Weapon objects occupy VNUMs 6-17; armor objects occupy VNUMs 18-29.
Install *after* the persisted world and custom templates load. This keeps
existing /data and builder edits authoritative. Occupied object IDs are
never overwritten, and a conflicting item is never accidentally sold.
"""

from __future__ import annotations

# (object VNUM, short description, required level, cost in ryo, weapon type)
WEAPONS = (
    (6, "Reinforced Kunai", 15, 750, "kunai"),
    (7, "Balanced Shuriken", 15, 650, "shuriken"),
    (8, "Steel Tanto", 18, 1200, "kunai"),
    (9, "Twin Kunai", 20, 1600, "kunai"),
    (10, "Iron Nunchaku", 20, 1500, "blunt"),
    (11, "Chuunin Short Sword", 22, 2200, "sword"),
    (12, "Weighted Kusarigama", 25, 3000, "exotic"),
    (13, "Shinobi Spear", 25, 2800, "polearm"),
    (14, "Chakra-Conductive Tanto", 28, 4500, "kunai"),
    (15, "Reinforced Katana", 30, 5000, "sword"),
    (16, "Windmill Shuriken", 32, 5800, "shuriken"),
    (17, "Chuunin Elite Blade", 35, 7500, "sword"),
)

# (object VNUM, short description, required level, cost in ryo, wear slot)
ARMOR = (
    (18, "Reinforced Shinobi Vest", 15, 900, "body"),
    (19, "Reinforced Shinobi Trousers", 15, 800, "legs"),
    (20, "Hardened Shinobi Sandals", 18, 1150, "feet"),
    (21, "Reinforced Combat Gloves", 18, 1250, "hands"),
    (22, "Steel Forearm Guards", 20, 1650, "wrist"),
    (23, "Leather Shinobi Hood", 20, 1450, "head"),
    (24, "Chuunin Utility Belt", 22, 2200, "waist"),
    (25, "Chuunin Field Cloak", 25, 3200, "back"),
    (26, "Chakra-Woven Bracers", 25, 3300, "wrist"),
    (27, "Reinforced Battle Leggings", 28, 4400, "legs"),
    (28, "Chakra-Weave Combat Vest", 30, 5200, "body"),
    (29, "Chuunin Elite Battle Armor", 35, 7600, "body"),
)

SHOPS = (
    (775, "weapons", WEAPONS),
    (776, "blacksmith", ARMOR),
)


def install() -> dict:
    """Safely register absent objects and append stock to existing mob prototypes.

    This runs at startup after builder data restoration. It never creates a
    replacement for an absent builder-owned mob or overwrites an occupied
    object VNUM. Only matching weapon/armor prototypes can be stocked.
    """
    import combat
    import olc
    import shop_flags

    created = []
    already_present = []
    collisions = []
    updated_shops = []

    for mob_vnum, specialty, catalog in SHOPS:
        category = "weapon" if specialty == "weapons" else "armor"
        for vnum, name, level, cost, sub_type in catalog:
            proto = olc.OBJECT_TEMPLATES.get(vnum)
            if proto is None:
                proto = olc.default_object(vnum, name)
                proto.update({
                    "item_type": category,
                    "level": level,
                    "cost": cost,
                    "wear_loc": "wielded" if category == "weapon" else sub_type,
                    "description": (
                        f"A sturdy level {level} Chuunin-grade "
                        f"{'weapon' if category == 'weapon' else 'piece of armor'} "
                        "made for active shinobi."
                    ),
                })
                if category == "weapon":
                    proto["weapon_type"] = sub_type
                # No explicit damage/AC: global AutoBalance scales to level.
                olc._auto_balance_new_equipment(proto)
                olc.OBJECT_TEMPLATES[vnum] = proto
                created.append(vnum)
            elif (str(proto.get("short_desc", "")).casefold() == name.casefold()
                  and proto.get("item_type") == category):
                already_present.append(vnum)  # preserve all saved builder edits
            else:
                collisions.append((vnum, name, proto.get("short_desc", "")))

        shop = combat.MOB_TEMPLATES.get(mob_vnum)
        if shop is None:
            continue  # mob is built/placed by staff; never synthesize it

        shop_flags.set_type(shop, specialty)
        stock = shop.setdefault("shop_items", [])
        if not isinstance(stock, list):
            stock = list(stock)
            shop["shop_items"] = stock
        for vnum, name, _level, _cost, _slot in catalog:
            proto = olc.OBJECT_TEMPLATES.get(vnum)
            if (proto is not None
                    and str(proto.get("short_desc", "")).casefold() == name.casefold()
                    and proto.get("item_type") == category
                    and vnum not in stock):
                stock.append(vnum)
        updated_shops.append(mob_vnum)

    if collisions:
        print("[Chuunin shops] Occupied object VNUMs preserved; "
              "conflicting entries were not added to the shop: "
              + ", ".join(str(vnum) for vnum, _expected, _actual in collisions))
    return {"created": created, "preserved": already_present,
            "collisions": collisions, "shops": updated_shops}
