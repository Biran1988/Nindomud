"""Durability of uniquely forged weapons and armor.

Equipment is tracked by its unique object prototype (not an item-name suffix).
Only weapons/armor forged from ingots receive wear. The prototype is already
one-per-unique-name and saved in world_state.json.
"""
import random

MATERIAL_DURABILITY = {
    "iron ingot": 2500,
    "steel ingot": 5000,
    "chakra steel ingot": 10000,
}
ARMOR_WEAR_CHANCE = 10  # one chance per landed melee attack, not per worn piece


def maximum(proto):
    materials = proto.get("craft_materials") or ()
    if proto.get("item_type") not in ("weapon", "armor") or not materials:
        return 0
    material = str(materials[0]).lower()
    return MATERIAL_DURABILITY.get(material, 0)


def state(proto):
    """(remaining, maximum), including older forged items without fields."""
    cap = maximum(proto)
    if not cap:
        return None
    top = int(proto.get("max_durability") or cap)
    remaining = int(proto.get("durability", top))
    return max(0, remaining), max(1, top)


def initialise(proto):
    maximum_uses = maximum(proto)
    if maximum_uses:
        proto["max_durability"] = maximum_uses
        proto["durability"] = maximum_uses


def _forged_item(item_name, expected_type):
    import olc
    for vnum, proto in olc.OBJECT_TEMPLATES.items():
        if (proto.get("short_desc", "").casefold() == str(item_name).casefold()
                and proto.get("item_type") == expected_type and maximum(proto)):
            return vnum, proto
    return None, None


def wear_weapon(session):
    """Wear the actually used wielded weapon once per landed attack."""
    return _wear(session, "wielded", "weapon")


def wear_armor(session):
    """A landed enemy melee hit has a 10% chance to wear one armor piece."""
    import olc
    worn = [(slot, name) for slot, name in session.player.equipment.items()
            if slot in olc.ARMOR_WEAR_LOCATIONS and name
            and _forged_item(name, "armor")[1] is not None]
    if not worn or random.randint(1, 100) > ARMOR_WEAR_CHANCE:
        return False
    slot, _ = random.choice(worn)
    return _wear(session, slot, "armor")


def _wear(session, slot, expected_type):
    import olc
    import storage
    import world_autosave
    item = session.player.equipment.get(slot)
    if not item:
        return False
    vnum, proto = _forged_item(item, expected_type)
    if proto is None:
        return False
    remaining, max_uses = state(proto)
    remaining = max(0, remaining - 1)
    proto["max_durability"] = max_uses
    proto["durability"] = remaining
    if remaining:
        if remaining <= max(10, max_uses // 20) and remaining % 10 == 0:
            session.send(f"&Y{item} is badly worn ({remaining:,} durability remaining).&x")
    else:
        # Unique-name forge prototypes normally have exactly one live item.
        # Remove both its equipment instance and its prototype. Any OSET-
        # spawned duplicates of this custom item cease to resolve as equipment.
        session.player.equipment[slot] = None
        del olc.OBJECT_TEMPLATES[vnum]
        import commands
        commands.reclaim_crafted_item_vnum(vnum)
        session.send(f"&RYour {item} breaks apart and is destroyed!&x")
    world_autosave.mark_dirty()
    storage.save_player(session.player)
    return True
