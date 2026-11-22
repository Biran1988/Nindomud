"""Tactical supplies for the existing builder-owned mob 785.

Only already-functional combat consumables, the nine genuine room-trap
tags and a poison-only Antidote Pill are stocked. The installer runs
after /data builder templates have been restored and never creates a
missing NPC or overwrites a builder's occupied item prototype.
"""
from __future__ import annotations

SHOP_MOB_VNUM = 785
ANTIDOTE_VNUM = 89
ANTIDOTE_NAME = "Antidote Pill"
ANTIDOTE_LEVEL = 25
ANTIDOTE_PRICE = 750

# Existing ninja arts items, not new clones with different effects.
EXPLOSIVES = (
    (9803, "An Exploding Note"),
    (9804, "A Smoke Bomb"),
    (9805, "A Poison Gas Bomb"),
    (9806, "A Wad of Exploding Clay"),
)

# Explicit exclusions from this shop, including saved old stock.
EXCLUDED_NAMES = frozenset({
    "a pot of glue",
    "a healing salve",
    "a soldier pill",
    "medicinal herbs",
    "medicinal pill",
})


def catalog():
    """Four existing bombs, all nine room tags, and only Antidote Pill."""
    import room_trap_tags
    return (
        *EXPLOSIVES,
        *((vnum, name) for vnum, name, _level, _cost, _effect
          in room_trap_tags.TAGS.values()),
        (ANTIDOTE_VNUM, ANTIDOTE_NAME),
    )


def install():
    import combat
    import olc
    import shop_flags
    import room_trap_tags

    # Register all nine room trap item prototypes without modifying
    # pre-existing object VNUMs or other shop stock.
    room_trap_tags.register_items()

    created = []
    existing = olc.OBJECT_TEMPLATES.get(ANTIDOTE_VNUM)
    if existing is None:
        obj = olc.default_object(ANTIDOTE_VNUM, ANTIDOTE_NAME)
        obj.update({
            "item_type": "medical", "level": ANTIDOTE_LEVEL,
            "cost": ANTIDOTE_PRICE,
            "heal_amount": 0, "extra_flags": [],
            "description": ("A cure-only Antidote Pill from the Shinobi "
                            "Tactical Supply Shop. USE or EAT only while "
                            "poisoned; it restores no Health, Chakra or Stamina."),
        })
        olc.OBJECT_TEMPLATES[ANTIDOTE_VNUM] = obj
        created.append(ANTIDOTE_VNUM)

    shop = combat.MOB_TEMPLATES.get(SHOP_MOB_VNUM)
    if shop is None:
        return {"mob_exists": False, "added": (), "created": tuple(created),
                "excluded": (), "conflicts": ()}

    # A dedicated ShopTactical flag lets sell/buy use the normal
    # merchant pathway and keeps the saved NPC's other flags intact.
    shop_flags.set_type(shop, "tactical")
    stock = shop.setdefault("shop_items", [])
    if not isinstance(stock, list):
        stock = list(stock)
        shop["shop_items"] = stock

    # User explicitly excluded glue and every healing/medical supply
    # other than the antidote. Leave unrelated builder stock untouched.
    excluded = []
    kept = []
    for vnum in stock:
        obj = olc.OBJECT_TEMPLATES.get(vnum, {})
        name = str(obj.get("short_desc", "")).casefold()
        if (name in EXCLUDED_NAMES
                or (obj.get("item_type") == "medical"
                    and vnum != ANTIDOTE_VNUM)):
            excluded.append(vnum)
        else:
            kept.append(vnum)
    stock[:] = kept

    added, conflicts = [], []
    for vnum, expected in catalog():
        item = olc.OBJECT_TEMPLATES.get(vnum)
        category = "medical" if vnum == ANTIDOTE_VNUM else "misc"
        if not item or (item.get("item_type") != category
                        or str(item.get("short_desc", "")).casefold()
                        != expected.casefold()):
            conflicts.append(vnum)
            continue
        if vnum not in stock:
            stock.append(vnum)
            added.append(vnum)

    if conflicts:
        print("[Tactical shop] Occupied or missing item VNUMs "
              "were not stocked: " + ", ".join(map(str, conflicts)))
    return {"mob_exists": True, "added": tuple(added),
            "created": tuple(created), "excluded": tuple(excluded),
            "conflicts": tuple(conflicts)}
