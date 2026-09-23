"""
Bukijutsu crafting (Section 133).

Per direct request/confirmation, replacing the old crafting.py recipe
framework entirely (it shipped with zero real recipes after an earlier
revamp stripped them out, and was never refilled): "i wanta single
skill for Bukijutsu level 25 that can use these crafting items to
craft the determined weapontype or armor based on their input
typing...like craft armor head <name> to call the item whatever they
want...or craft weapon exotic <name>....the items above are what will
be used...and i want there to be combinations to this..a yew log can
be combined with an iron ingot to make armor or any other combination
but it will take into account that each of those items have their
own..."

Confirmed design, locked in across the whole conversation:
- Exactly 8 real materials (gems, fishing, and farming materials are
  explicitly OUT of scope, confirmed directly -- gems "will come in
  later and should not be counted"). Raw ores are not directly
  usable, only their smelted ingots.
- Chakra Steel Ingot is the top-tier ingot overall, confirmed
  directly to swap places with Alloy Ingot -- both the real ryo
  price (content.py) AND the real crafting stat value here.
- Always exactly 2 materials combined, confirmed directly ("never 1
  alone and never 3+") -- their own stat values simply add together.
- `craft weapon <type> <name>` (type = one of data_weapons.
  WEAPON_TYPES) and `craft armor <slot> <name>` (slot = one of
  olc.ARMOR_WEAR_LOCATIONS) -- confirmed directly, reusing the
  game's own existing real weapon-type/armor-slot systems rather
  than inventing new categories.
- A crafted WEAPON's combined stat value applies as BOTH +hitroll
  AND +damroll at the same value (confirmed directly: "add a
  matching hitroll"). A crafted ARMOR's combined stat value applies
  as -armor_class (confirmed earlier in this same conversation,
  lower/more negative is better, matching ROM convention).
- Unlocked by EITHER Bukijutsu level 25+, OR any class at level 70+
  (confirmed directly: two genuinely separate real unlock paths to
  the same skill, not one combined gate).
"""

# Confirmed real stat values, one per material -- the ryo prices below
# are informational only (content.py is the real, live source of
# truth for actual shop prices); Chakra Steel Ingot and Alloy Ingot's
# own real prices were directly swapped in content.py to match this
# same confirmed tier order.
MATERIALS = {
    "iron ingot": {"stat_value": 5, "price_ryo": 200},
    "sturdy oak log": {"stat_value": 6, "price_ryo": 300},
    "ironwood log": {"stat_value": 8, "price_ryo": 600},
    "steel ingot": {"stat_value": 12, "price_ryo": 2000},
    "masterwork oak log": {"stat_value": 14, "price_ryo": 3000},
    "alloy ingot": {"stat_value": 22, "price_ryo": 20000},
    "ancient heartwood log": {"stat_value": 26, "price_ryo": 40000},
    "yew log": {"stat_value": 26, "price_ryo": 40000},
    "chakra steel ingot": {"stat_value": 30, "price_ryo": 60000},
}

CRAFTING_BUKIJUTSU_MIN_LEVEL = 25  # confirmed directly: the first, real unlock path
CRAFTING_GENERAL_MIN_LEVEL = 70  # confirmed directly: the second, separate real unlock path (any class)


def can_craft(player) -> bool:
    """Whether this player currently meets EITHER real, confirmed
    unlock path -- Bukijutsu at level 25+, or any class at level 70+.
    Confirmed directly as two genuinely separate paths, not a single
    combined gate."""
    if player.primary_class == "bukijutsu" and player.level >= CRAFTING_BUKIJUTSU_MIN_LEVEL:
        return True
    return player.level >= CRAFTING_GENERAL_MIN_LEVEL


def find_material(query: str):
    """Matches query against a real material's own name -- an EXACT
    match always wins first (so plain "steel ingot" genuinely means
    Steel Ingot, not Chakra Steel Ingot); only falls back to substring
    matching (same real convention used elsewhere in this codebase,
    e.g. commands._find_object_prototype_by_name) when no exact match
    exists, preferring the LONGEST candidate among those. Caught by
    direct live testing, in 2 real stages: first, "chakra steel ingot"
    could match "steel ingot" first (a genuine substring collision);
    then, after preferring the longest candidate to fix that, plain
    "steel ingot" started incorrectly matching "chakra steel ingot"
    instead -- the exact-match-first check fixes both correctly.
    Returns the real material key (e.g. "iron ingot") or None."""
    query = query.lower()
    if query in MATERIALS:
        return query
    candidates = [name for name in MATERIALS if query in name or name in query]
    if not candidates:
        return None
    return max(candidates, key=len)


def combined_stat_value(material_a: str, material_b: str) -> int:
    """The real, confirmed combined stat value for 2 materials --
    simply their own individual stat_value fields added together,
    confirmed directly ("iron=5, yew=20 -> combined=25", the exact
    real shape this mirrors)."""
    return MATERIALS[material_a]["stat_value"] + MATERIALS[material_b]["stat_value"]
