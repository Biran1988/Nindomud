"""Special Jounin / Jounin gear for builder-owned mobs 784 (weapons) and 786 (armor).

Object VNUMs start at 39, directly after the iron-tool VNUMs 30-38.
Installed only after saved builder templates load. Never replace a builder
prototype, delete prior merchant stock or create absent builder mobs.
Elemental equipment carries a deliberately modest native elemental perk.
"""

from __future__ import annotations

WEAPON_MOB_VNUM = 784
ARMOR_MOB_VNUM = 786
ELEMENTS = ("fire", "water", "wind", "lightning", "earth")

# (VNUM, name, ninja level, ryo, weapon type, elemental nature or None)
WEAPONS = (
    (39, "Special Jounin Tanto", 70, 14000, "kunai", None),
    (40, "Silent Step Shuriken", 75, 16000, "shuriken", None),
    (41, "Ironwood Nunchaku", 85, 19000, "blunt", None),
    (42, "Shadow Reed Naginata", 90, 22000, "polearm", None),
    (43, "Twin Fang Kunai", 100, 25000, "kunai", None),
    (44, "Crescent Moon Blade", 110, 28000, "sword", None),
    (45, "Whirling Chain Sickle", 125, 34000, "exotic", None),
    (46, "Stormguard Spear", 140, 40000, "polearm", None),
    (47, "Blacksteel War Hammer", 155, 48000, "blunt", None),
    (48, "Jounin Tactical Katana", 175, 58000, "sword", None),
    (49, "Cyclone Shuriken", 185, 64000, "shuriken", None),
    (50, "Jounin Assassin Dagger", 200, 72000, "kunai", None),
    (51, "Dragonfang Odachi", 210, 88000, "sword", None),
    (52, "ANBU Executioner Blade", 225, 110000, "sword", None),
    (53, "Master Shinobi Kusarigama", 240, 150000, "exotic", None),
    (54, "Supreme Jounin War Spear", 250, 200000, "polearm", None),
    (55, "Emberfang Katana", 175, 70000, "sword", "fire"),
    (56, "Tidal Crescent Blade", 175, 70000, "sword", "water"),
    (57, "Gale-Edge Naginata", 175, 70000, "polearm", "wind"),
    (58, "Thunderclap Kunai", 175, 70000, "kunai", "lightning"),
    (59, "Stonebreaker Hammer", 175, 70000, "blunt", "earth"),
)

# (VNUM, name, ninja level, ryo, wear slot, elemental nature or None)
ARMOR = (
    (60, "Special Jounin Assault Vest", 70, 17000, "body", None),
    (61, "Special Jounin Shin Guards", 75, 15000, "legs", None),
    (62, "Reinforced ANBU Mask", 85, 18000, "head", None),
    (63, "Hunter-Nin Silent Boots", 95, 20000, "feet", None),
    (64, "Chakra-Lined Gloves", 105, 23000, "hands", None),
    (65, "Tactical Seal Belt", 115, 28000, "waist", None),
    (66, "Jounin Guard Bracers", 135, 33000, "wrist", None),
    (67, "Jounin Field Cloak", 150, 40000, "back", None),
    (68, "Chakra Channel Necklace", 160, 48000, "neck", None),
    (69, "Steelguard Leg Armor", 175, 55000, "legs", None),
    (70, "Jounin Battle Vest", 200, 75000, "body", None),
    (71, "Jounin War Helm", 210, 92000, "head", None),
    (72, "Jounin Battle Sandals", 225, 100000, "feet", None),
    (73, "Jounin Elite Combat Gloves", 235, 120000, "hands", None),
    (74, "Jounin Supreme Battle Armor", 250, 180000, "body", None),
    (75, "Fire Release Chakra Aura", 160, 62000, "chakra aura", "fire"),
    (76, "Water Release Chakra Aura", 160, 62000, "chakra aura", "water"),
    (77, "Wind Release Chakra Aura", 160, 62000, "chakra aura", "wind"),
    (78, "Lightning Release Chakra Aura", 160, 62000, "chakra aura", "lightning"),
    (79, "Earth Release Chakra Aura", 160, 62000, "chakra aura", "earth"),
)

ELEMENTAL_WEAPON_DAMAGE_PERCENT = 10
ELEMENTAL_AURA_JUTSU_PERCENT = 10
ELEMENTAL_AURA_COUNTER_RESIST_PERCENT = 10

# Permanent shop ID map, not a dynamic name-based trust shortcut. An
# unrelated object with the same name cannot impersonate a shop element.
_WEAPON_ELEMENT_BY_NAME = {
    name.casefold(): (vnum, element)
    for vnum, name, _level, _cost, _kind, element in WEAPONS if element
}
_AURA_ELEMENT_BY_NAME = {
    name.casefold(): (vnum, element)
    for vnum, name, _level, _cost, _slot, element in ARMOR if element
}


def _verified_element(equipped_name: str, category: str) -> str | None:
    """Only a genuine registered vendor item provides its elemental perk."""
    import olc
    import crafted_identity
    import tool_durability
    import ninja_arts

    if not equipped_name or crafted_identity.marked(equipped_name):
        return None
    base = tool_durability.base_name(ninja_arts.base_item(equipped_name))
    mapping = _WEAPON_ELEMENT_BY_NAME if category == "weapon" else _AURA_ELEMENT_BY_NAME
    record = mapping.get(base.casefold())
    if record is None:
        return None
    vnum, element = record
    prototype = olc.OBJECT_TEMPLATES.get(vnum)
    if (not prototype or prototype.get("item_type") != category
            or str(prototype.get("short_desc", "")).casefold() != base.casefold()):
        return None
    if category == "armor" and prototype.get("wear_loc") != "chakra aura":
        return None
    if category == "weapon" and prototype.get("wear_loc") != "wielded":
        return None
    # Do not infer powers from a renamed builder item; only the original,
    # verified item's own explicit element metadata grants this effect.
    return element if prototype.get("shop_element") == element else None


def weapon_element(equipped_name: str) -> str | None:
    return _verified_element(equipped_name, "weapon")


def equipped_aura_element(actor) -> str | None:
    return _verified_element(
        getattr(actor, "equipment", {}).get("chakra aura", ""), "armor")


def install() -> dict:
    """Register nonconflicting gear and append stock to existing 784/786."""
    import combat
    import olc
    import shop_flags

    created, preserved, collisions, shops = [], [], [], []
    for mob_vnum, specialty, category, catalog in (
        (WEAPON_MOB_VNUM, "weapons", "weapon", WEAPONS),
        (ARMOR_MOB_VNUM, "blacksmith", "armor", ARMOR),
    ):
        for vnum, name, level, cost, subtype, element in catalog:
            proto = olc.OBJECT_TEMPLATES.get(vnum)
            if proto is None:
                proto = olc.default_object(vnum, name)
                proto.update({
                    "item_type": category,
                    "level": level,
                    "cost": cost,
                    "wear_loc": "wielded" if category == "weapon" else subtype,
                    "description": (
                        f"{name}, equipment for Special Jounin and Jounin shinobi. "
                        + (f"Channels the {element.title()} chakra element. " if element else "")
                        + ("Its power scales with the user's ninja level requirements.")
                    ),
                })
                if category == "weapon":
                    proto["weapon_type"] = subtype
                if element:
                    proto["shop_element"] = element
                # Keep strength on the same existing global AutoBalance
                # scaling path as the Chuunin vendors.
                olc._auto_balance_new_equipment(proto)
                olc.OBJECT_TEMPLATES[vnum] = proto
                created.append(vnum)
            elif (str(proto.get("short_desc", "")).casefold() == name.casefold()
                  and proto.get("item_type") == category):
                preserved.append(vnum)
            else:
                collisions.append((vnum, name, proto.get("short_desc", "")))

        shop = combat.MOB_TEMPLATES.get(mob_vnum)
        if shop is None:
            continue  # Do not invent or replace a builder-owned shopkeeper.
        shop_flags.set_type(shop, specialty)
        stock = shop.setdefault("shop_items", [])
        if not isinstance(stock, list):
            stock = list(stock)
            shop["shop_items"] = stock
        for vnum, name, _level, _cost, _subtype, _element in catalog:
            obj = olc.OBJECT_TEMPLATES.get(vnum)
            if (obj is not None
                    and str(obj.get("short_desc", "")).casefold() == name.casefold()
                    and obj.get("item_type") == category
                    and vnum not in stock):
                stock.append(vnum)
        shops.append(mob_vnum)

    if collisions:
        print("[Jounin shops] Preserved occupied object VNUMs: "
              + ", ".join(str(vnum) for vnum, _name, _actual in collisions))
    return {"created": created, "preserved": preserved,
            "collisions": collisions, "shops": shops}
