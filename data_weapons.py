"""
Weapon types (Section 8-9's weapon proficiency skills).

Proficiency skills are per weapon-TYPE, not per specific item -- "kunai"
is the weapon-type category name itself (covering kunai, knives, throwing
daggers, etc.), so training with any of them all advances the same
"Kunai" skill, matching how `practice`/`skill_proficiencies`
already work generically. This module is the single place that maps an
item name to its weapon type and the skill that governs it, so both
starting equipment (plain name strings) and `oset`-built object
prototypes can share it.
"""

from typing import Optional

WEAPON_TYPES = {
    "kunai": {"display_name": "Kunai", "skill": "Kunai"},
    "sword": {"display_name": "Sword", "skill": "Sword"},
    "shuriken": {"display_name": "Shuriken", "skill": "Shuriken"},
    "blunt": {"display_name": "Blunt", "skill": "Blunt Weapon"},
    "polearm": {"display_name": "Polearm", "skill": "Polearm"},
    "exotic": {"display_name": "Exotic", "skill": "Exotic Weapon"},
}

# Per-weapon-type attack verb, per explicit request -- combat messages
# previously always said "strike" regardless of what was wielded (or
# nothing at all). Chosen to read naturally in the existing "You
# {verb} {target} for {dmg} damage" sentence structure. UNARMED_VERB
# covers no weapon wielded at all (weapon_type_for_item returns None),
# and is also the fallback for any weapon type not in this dict, so a
# future weapon type added to WEAPON_TYPES without a matching entry
# here degrades to a sensible default rather than crashing.
ATTACK_VERBS = {
    "kunai": "stab",
    "sword": "slash",
    "shuriken": "pelt",
    "blunt": "bludgeon",
    "polearm": "impale",
    "exotic": "strike",
}
UNARMED_VERB = "punch"

# Third-person singular form of each verb above, for "{attacker.name}
# {verb} you" style messages (the other side of a PvP attack) --
# spelled out explicitly rather than algorithmically suffixed, since
# English conjugation isn't a uniform "+s" rule (slash/punch need
# "+es", not "+s").
ATTACK_VERBS_THIRD_PERSON = {
    "stab": "stabs",
    "slash": "slashes",
    "pelt": "pelts",
    "bludgeon": "bludgeons",
    "impale": "impales",
    "strike": "strikes",
    "punch": "punches",
}


def attack_verb_for_item(item_name: str) -> str:
    """The attack verb for whatever weapon_type_for_item resolves
    item_name to, or UNARMED_VERB if it isn't a recognized weapon at
    all (including an empty/no wielded item)."""
    if not item_name:
        return UNARMED_VERB
    weapon_type = weapon_type_for_item(item_name)
    if not weapon_type:
        return UNARMED_VERB
    return ATTACK_VERBS.get(weapon_type, UNARMED_VERB)


def attack_verb_for_item_third_person(item_name: str) -> str:
    """Third-person singular form of attack_verb_for_item, e.g. for
    '{attacker.name} slashes you' style PvP messages describing the
    other player's attack."""
    verb = attack_verb_for_item(item_name)
    return ATTACK_VERBS_THIRD_PERSON.get(verb, verb + "s")

# A weapon's own intrinsic damage contribution (Section 68) -- added
# on top of the base attack roll, so wielding a real weapon actually
# matters mechanically, not just cosmetically. A bare/unarmed attack
# (no weapon_type match at all) gets no bonus. Rough tiering: Kunai is
# the lightest, everyday tool; Sword and Exotic are solid mid-tier;
# Polearm hits hardest, reflecting its reach/heft.
WEAPON_TYPE_DAMAGE_BONUS = {
    "kunai": 0,
    "shuriken": 1,
    "blunt": 2,
    "exotic": 3,
    "sword": 3,
    "polearm": 4,
}


def weapon_damage_bonus(weapon_type: str) -> int:
    return WEAPON_TYPE_DAMAGE_BONUS.get(weapon_type, 0)


def item_base_damage(proto: dict) -> int:
    """An explicit item damage value replaces its weapon type's default."""
    damage = proto.get("damage")
    return damage if damage is not None else weapon_damage_bonus(proto.get("weapon_type", ""))


# Substring-matched against an item's (lowercased) name. First match wins,
# so put more specific keywords before generic ones if that ever matters.
ITEM_KEYWORD_TO_WEAPON_TYPE = {
    "kunai": "kunai",
    "dagger": "kunai",
    "knife": "kunai",
    "sword": "sword",
    "katana": "sword",
    "blade": "sword",
    "shuriken": "shuriken",
    "club": "blunt",
    "mace": "blunt",
    "hammer": "blunt",
    "staff": "polearm",
    "spear": "polearm",
    "naginata": "polearm",
}


def weapon_type_for_item(item_name: str) -> Optional[str]:
    """The authoritative source is the item's own registered prototype
    -- 'weapon_type_for_item' used to ONLY guess from keywords in the
    item's display name (ITEM_KEYWORD_TO_WEAPON_TYPE below), completely
    ignoring the real, already-known weapon_type field every weapon
    prototype carries. That meant any weapon whose name didn't happen
    to contain one of a small hardcoded set of English words -- and
    "exotic" had no keyword mapping at all -- silently never counted as
    that weapon type for anything reading this function, including
    which proficiency skill gets granted on wield. Now checks the real
    prototype first; keyword-guessing is kept only as a fallback for
    the rare case no prototype exists for the item at all."""
    import olc
    query = item_name.lower()
    # The exact prototype wins over broader names such as "A Basic Kunai"
    # matching a builder's distinct item named "Kunai".
    for proto in olc.OBJECT_TEMPLATES.values():
        if query == proto["short_desc"].lower():
            weapon_type = proto.get("weapon_type")
            return weapon_type if weapon_type in WEAPON_TYPES else None
    for proto in olc.OBJECT_TEMPLATES.values():
        if query in proto["short_desc"].lower() or proto["short_desc"].lower() in query:
            weapon_type = proto.get("weapon_type")
            return weapon_type if weapon_type in WEAPON_TYPES else None

    name = item_name.lower()
    for keyword, weapon_type in ITEM_KEYWORD_TO_WEAPON_TYPE.items():
        if keyword in name:
            return weapon_type
    return None


def skill_for_item(item_name: str) -> Optional[str]:
    weapon_type = weapon_type_for_item(item_name)
    if not weapon_type:
        return None
    return WEAPON_TYPES[weapon_type]["skill"]


def display_name(weapon_type: str) -> str:
    return WEAPON_TYPES.get(weapon_type, {}).get("display_name", weapon_type.title())
