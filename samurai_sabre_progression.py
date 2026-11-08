"""Automatic Bukijutsu Samurai Sabre passive mastery tiers.

The base technique is an ordinary level-35 toggle. Tiers 2-5 are
always-on passive training milestones (no scroll, command or practice),
but add damage only while Samurai Sabre is active on a sword.
"""

BASE_LEVEL = 35
BASE_BONUS_PCT = 5
PASSIVE_TIER_BONUS_PCT = 5
PASSIVE_UNLOCKS = {
    "Samurai Sabre 2": 85,
    "Samurai Sabre 3": 140,
    "Samurai Sabre 4": 195,
    "Samurai Sabre 5": 250,
}


def sync_passives(player):
    """Return newly learned passive names; safe at level-up and login."""
    if getattr(player, "primary_class", None) != "bukijutsu":
        return []
    newly = []
    for name, needed in PASSIVE_UNLOCKS.items():
        if player.level >= needed and name not in player.learned_skills:
            player.learned_skills.append(name)
            # These are permanent passive levels, not trainable practice %.
            player.skill_proficiencies[name] = 100
            newly.append(name)
        elif name in player.learned_skills:
            player.skill_proficiencies[name] = 100
    return newly


def damage_bonus_percent(player):
    """Total Sabre bonus, 0 when inactive or not wielding a sword."""
    if (not getattr(player, "samurai_sabre_active", False)
            or getattr(player, "level", 0) < BASE_LEVEL):
        return 0
    if getattr(player, "primary_class", None) != "bukijutsu":
        return 0
    import data_weapons
    import ninja_arts
    wielded = (getattr(player, "equipment", None) or {}).get("wielded") or ""
    if data_weapons.weapon_type_for_item(ninja_arts.base_item(wielded)) != "sword":
        return 0
    total = BASE_BONUS_PCT
    for name, required_level in PASSIVE_UNLOCKS.items():
        if player.level >= required_level and name in player.learned_skills:
            total += PASSIVE_TIER_BONUS_PCT
    return total
