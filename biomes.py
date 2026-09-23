"""
Elemental jutsu affinity (Section 56) -- ties a room's biome tag to a
jutsu's element, boosting or weakening damage when they interact. This
is the foundational piece of a larger planned system (fishing with
per-biome loot tables, biome ambient/reset messages) but stands on its
own: it's the first thing in this project where WHERE you fight
actually changes HOW WELL a jutsu works, not just what's in the room.

Elements are the five classic nature transformations (fire, water,
wind, earth, lightning), plus "none" for jutsu that aren't elemental
at all (taijutsu, bukijutsu, and most genjutsu -- see data_jutsu.py's
JUTSU table, where every jutsu now carries an "element" field).

Biomes are a tag on Room (world.py's `biome` field, default "none" --
plain indoor/neutral rooms are unaffected). A biome can boost some
elements and weaken others; a jutsu whose element isn't listed either
way in that biome is unaffected. "none" element and "none" biome are
both always neutral (1.0x), by construction -- there's no need to list
them in the affinity table.

This module is intentionally the neutral middle ground between
data_jutsu.py (elements) and world.py (biomes) -- both are read by
combat.py at the point of a jutsu attack, but neither of them needs to
import the other.
"""

import random

ELEMENTS = ["none", "fire", "water", "wind", "earth", "lightning"]

BIOME_TYPES = ["none", "ocean", "river", "lake", "forest", "mountain", "desert", "swamp", "plains"]

BOOST_MULTIPLIER = 1.25
WEAKEN_MULTIPLIER = 0.75

# Each biome lists which elements it boosts and which it weakens. An
# element absent from both lists for a given biome is unaffected there.
BIOME_ELEMENT_AFFINITY = {
    "ocean": {"boost": ["water"], "weaken": ["fire", "lightning"]},
    "river": {"boost": ["water"], "weaken": ["fire"]},
    "lake": {"boost": ["water"], "weaken": ["fire"]},
    "forest": {"boost": ["wind", "earth"], "weaken": []},
    "mountain": {"boost": ["earth", "lightning"], "weaken": ["wind"]},
    "desert": {"boost": ["fire", "wind"], "weaken": ["water"]},
    "swamp": {"boost": ["water", "earth"], "weaken": ["lightning"]},
    "plains": {"boost": [], "weaken": []},  # open ground -- no elemental advantage either way
}


def roll_chakra_nature() -> str:
    """Secretly resolves a freshly created character's chakra nature --
    one of the 5 real elements (never "none"), uniform odds. Called
    exactly once, at character creation (session.py), never re-rolled
    afterward -- exactly matching data_kekkei_genkai.roll_inheritance's
    own established pattern for a hidden, one-time roll.

    SECURITY: like the bloodline roll, this function only returns a
    value -- storing it on the player and never surfacing it until the
    player actually uses a Chakra Paper is entirely the caller's
    responsibility."""
    return random.choice([e for e in ELEMENTS if e != "none"])


def roll_secondary_chakra_nature(primary_element: str) -> str:
    """Secretly resolves a character's SECOND chakra nature, unlocked
    at level 100 (confirmed design: revealed through the same Chakra
    Paper flow as the primary, just gated higher) -- rolled fresh at
    the moment of that second reveal, not at character creation,
    since nobody starts the game already at level 100.

    Guaranteed to differ from primary_element: uniform odds among the
    remaining 4 real elements, with NO thematic restriction on which
    one -- confirmed design explicitly allows a directly opposing
    element ("completely random...even if they oppose each other"),
    so this does not avoid or weight against any particular pairing.

    SECURITY: like roll_chakra_nature, this function only returns a
    value -- storing it and never surfacing it until an actual second
    Chakra Paper is channeled is entirely the caller's responsibility."""
    return random.choice([e for e in ELEMENTS if e != "none" and e != primary_element])


def damage_modifier(biome: str, element: str) -> float:
    """Returns the multiplier a jutsu's damage should get for being
    used with `element` while standing in `biome`. 1.0 (no change) for
    "none" on either side, an unlisted combination, or an unrecognized
    biome/element."""
    if element == "none" or biome == "none":
        return 1.0
    affinity = BIOME_ELEMENT_AFFINITY.get(biome)
    if not affinity:
        return 1.0
    if element in affinity["boost"]:
        return BOOST_MULTIPLIER
    if element in affinity["weaken"]:
        return WEAKEN_MULTIPLIER
    return 1.0
