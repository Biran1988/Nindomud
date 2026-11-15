"""Flag-first room editor compatibility with existing room attributes."""
import biomes
BIOMES = {"biome_" + x: x for x in biomes.BIOME_TYPES if x != "none"}
SPECIAL = frozenset(("apartment", "player_shop", "safe", *BIOMES))

def canonical(typed):
    name = str(typed).strip().casefold().replace("-", "_").replace(" ", "_")
    if name in {"playershop", "shoproom", "shop_room", "player_shop_room"}:
        return "player_shop"
    if name in biomes.BIOME_TYPES and name != "none":
        return "biome_" + name
    if name.startswith("biome") and name[5:] in biomes.BIOME_TYPES:
        return "biome_" + name[5:]
    return name

def synchronize(room, legacy=False):
    """Mirror canonical flags into existing gameplay properties.

    Only construction/restoration migrates legacy attributes into flags;
    normal flag edits never re-enable a removed flag from a stale field.
    """
    flags = list(dict.fromkeys(canonical(x) if canonical(x) in SPECIAL else x
                               for x in (room.flags or [])))
    biome_flags = [x for x in flags if x in BIOMES]
    if legacy:
        if room.apartment and "apartment" not in flags:
            flags.append("apartment")
        if room.player_shop and "player_shop" not in flags:
            flags.append("player_shop")
        if room.safe and "safe" not in flags:
            flags.append("safe")
        if room.biome in biomes.BIOME_TYPES and room.biome != "none" and not biome_flags:
            flags.append("biome_" + room.biome)
            biome_flags = ["biome_" + room.biome]
    if biome_flags:
        first = biome_flags[0]
        flags = [x for x in flags if x not in BIOMES or x == first]
    room.flags = flags
    room.apartment = "apartment" in flags
    room.player_shop = "player_shop" in flags
    room.safe = "safe" in flags
    room.biome = BIOMES[biome_flags[0]] if biome_flags else "none"
    return room

def toggle(room, name):
    # Preserve the official spelling of non-special flags (CapturePoint,
    # etc.). Builder validation already canonicalizes these names.
    normalized = canonical(name)
    name = normalized if normalized in SPECIAL else name
    synchronize(room)
    flags = room.flags
    if name in BIOMES:
        is_active = name in flags
        room.flags = [x for x in flags if x not in BIOMES]
        if not is_active:
            room.flags.append(name)
    elif name in flags:
        flags.remove(name)
    else:
        flags.append(name)
    synchronize(room)
    return name, name in room.flags
