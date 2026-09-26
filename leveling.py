"""Leveling, experience curve, and level-based jutsu unlocking.

Ninja levels use a cumulative SMAUG-style progressive curve:
``(level - 1) ** 3 * 1000`` total experience marks the start of a level.
Existing characters are migrated once while preserving their percentage
through the level they were already working on.
"""

from typing import List

import config
import data_jutsu
import storage
from models import Player

MAX_LEVEL = 100
EXPERIENCE_CURVE_VERSION = 2
SAME_LEVEL_MOB_REWARD_PERCENT = 5
EASIER_MOB_PENALTY_PER_LEVEL = 0.10
HARDER_MOB_BONUS_PER_LEVEL = 0.03
HARDER_MOB_REWARD_CAP = 1.30

# Modest per-level resource growth; a real balance pass belongs to
# actual playtesting, not this initial slice.
HEALTH_PER_LEVEL = 8
CHAKRA_PER_LEVEL = 5
STAMINA_PER_LEVEL = 6
TRAINING_POINTS_PER_LEVEL = 6  # raised from 3 (Section 132, per direct request/confirmation): 99 level-ups x 6 = 594 total by level 100, just enough (small real surplus) to max all 9 real trainable attributes at the cap of 75 (needing 585 total: (75-10)*9)
PRACTICE_POINTS_BASE_PER_LEVEL = 3   # everyone gets at least this many

# Extra practice points per level scale with Wisdom, up to this many bonus
# points at the real attribute cap (config.MAX_ATTRIBUTE_VALUE = 40) --
# base 3 + bonus 6 = 9 pracs/level at maxed Wisdom. Below the default
# starting Wisdom (10) there's no bonus.
PRACTICE_BONUS_MAX = 6


# Extra HP/Chakra/Stamina per level scale directly and linearly with
# their own real stat, per direct request/confirmation ("Put no gain
# cap on hp chakra stamina so it can give benefit up until the max
# stat is reached" -> confirmed: a fixed, real bonus per point above
# the baseline of 10, with NO separate ceiling of its own -- the only
# real limit is the stat's own cap (config.MAX_ATTRIBUTE_VALUE, now
# 75). Confirmed directly: HP from Constitution, Stamina from
# Dexterity, Chakra from a blend of Intelligence (75%) and Wisdom
# (25%) -- all three at the same real rate, +0.5 per point.
RESOURCE_BONUS_PER_ATTRIBUTE_POINT = 0.5
CHAKRA_INTELLIGENCE_WEIGHT = 0.75  # confirmed directly: Chakra is "int + wisdom but majority int"
CHAKRA_WISDOM_WEIGHT = 0.25


def _wisdom_practice_bonus(wisdom: int) -> int:
    if wisdom <= 10:
        return 0
    span = config.MAX_ATTRIBUTE_VALUE - 10
    bonus = round((wisdom - 10) / span * PRACTICE_BONUS_MAX)
    return max(0, min(PRACTICE_BONUS_MAX, bonus))


def _constitution_health_bonus(constitution: int) -> int:
    """Genuinely uncapped, per direct confirmation -- +0.5 real HP
    per level for every point of Constitution above the baseline of
    10, with no separate ceiling of its own (only the stat's own cap
    of 75 limits this in practice)."""
    if constitution <= 10:
        return 0
    return round((constitution - 10) * RESOURCE_BONUS_PER_ATTRIBUTE_POINT)


def _dexterity_stamina_bonus(dexterity: int) -> int:
    """Genuinely uncapped, per direct confirmation -- +0.5 real
    Stamina per level for every point of Dexterity above the
    baseline of 10, same real shape as the Constitution HP bonus."""
    if dexterity <= 10:
        return 0
    return round((dexterity - 10) * RESOURCE_BONUS_PER_ATTRIBUTE_POINT)


def _chakra_gain_bonus(intelligence: int, wisdom: int) -> int:
    """Genuinely uncapped, per direct confirmation -- a blended
    Int/Wis score (Intelligence weighted at 75%, Wisdom at 25%,
    confirmed directly: "int + wisdom but majority int"), then the
    same real +0.5-per-point-above-10 rate applied to that blend,
    same shape as the Constitution HP bonus and Dexterity Stamina
    bonus."""
    blended = intelligence * CHAKRA_INTELLIGENCE_WEIGHT + wisdom * CHAKRA_WISDOM_WEIGHT
    if blended <= 10:
        return 0
    return round((blended - 10) * RESOURCE_BONUS_PER_ATTRIBUTE_POINT)


def cumulative_xp_for_level(level: int) -> int:
    """Total experience required to begin ``level`` (levels start at 1)."""
    level = max(1, min(MAX_LEVEL, int(level)))
    return (level - 1) ** 3 * 1000


def xp_for_next_level(level: int) -> int:
    """Cumulative experience required to advance from ``level``."""
    level = max(1, int(level))
    if level >= MAX_LEVEL:
        return cumulative_xp_for_level(MAX_LEVEL)
    return level ** 3 * 1000


def xp_band_for_level(level: int) -> int:
    """Experience contained in the level's current progression band."""
    if level >= MAX_LEVEL:
        return 0
    return xp_for_next_level(level) - cumulative_xp_for_level(level)


def mob_base_experience(mob_level: int) -> int:
    """Reward before player/mob level-difference scaling.

    A same-level kill is worth five percent of that level's XP band,
    producing roughly twenty even-level kills per level before bonuses.
    """
    mob_level = max(1, min(MAX_LEVEL - 1, int(mob_level)))
    return max(1, round(xp_band_for_level(mob_level) * SAME_LEVEL_MOB_REWARD_PERCENT / 100))


def mob_kill_experience(player_level: int, mob_level: int) -> int:
    """Level-scaled XP for one player killing one mob.

    Easier enemies lose ten percent per level and reach zero at ten levels
    below the player. Harder enemies gain three percent per level, capped at
    130 percent. Group callers apply this independently for every member.
    """
    difference = int(mob_level) - int(player_level)
    if difference < 0:
        multiplier = max(0.0, 1.0 + difference * EASIER_MOB_PENALTY_PER_LEVEL)
    else:
        multiplier = min(HARDER_MOB_REWARD_CAP, 1.0 + difference * HARDER_MOB_BONUS_PER_LEVEL)
    return max(0, round(mob_base_experience(mob_level) * multiplier))


def migrate_experience_curve(player: Player) -> bool:
    """Move one legacy character to curve v2 without changing their level.

    The old curve used 1,000 XP bands. The fraction already completed in
    the current band is carried into the new cubic band. Returns whether the
    player changed so storage can persist the migration once.
    """
    if getattr(player, "experience_curve_version", 1) >= EXPERIENCE_CURVE_VERSION:
        return False

    level = max(1, min(MAX_LEVEL, int(player.level)))
    if level >= MAX_LEVEL:
        player.experience = cumulative_xp_for_level(MAX_LEVEL)
    else:
        old_floor = (level - 1) * 1000
        old_progress = max(0, min(1000, int(player.experience) - old_floor))
        progress_ratio = old_progress / 1000
        new_floor = cumulative_xp_for_level(level)
        player.experience = new_floor + round(xp_band_for_level(level) * progress_ratio)
    player.experience_curve_version = EXPERIENCE_CURVE_VERSION
    return True


def grant_experience(player: Player, amount: int) -> List[str]:
    """Apply experience, handle any level-ups, return messages to show the player."""
    if player.level >= MAX_LEVEL:
        return []

    lines = []
    player.experience += amount

    while player.level < MAX_LEVEL and player.experience >= xp_for_next_level(player.level):
        player.level += 1
        health_gain = HEALTH_PER_LEVEL + _constitution_health_bonus(player.constitution)
        chakra_gain = CHAKRA_PER_LEVEL + _chakra_gain_bonus(player.intelligence, player.wisdom)
        stamina_gain = STAMINA_PER_LEVEL + _dexterity_stamina_bonus(player.dexterity)
        training_gain = TRAINING_POINTS_PER_LEVEL
        practice_gain = PRACTICE_POINTS_BASE_PER_LEVEL + _wisdom_practice_bonus(player.wisdom)

        player.maximum_health += health_gain
        player.maximum_chakra += chakra_gain
        player.maximum_stamina += stamina_gain
        player.health = player.maximum_health
        player.chakra = player.maximum_chakra
        player.stamina = player.maximum_stamina
        player.training_points += training_gain
        player.practice_points += practice_gain

        lines.append(f"&YYou have reached level {player.level}!&x")
        lines.append(
            f"  &R+{health_gain} Max Health&x  &B+{chakra_gain} Max Chakra&x  "
            f"&G+{stamina_gain} Max Stamina&x  &C+{training_gain} Training Point(s)&x  "
            f"&W+{practice_gain} Practice Point(s)&x"
        )

        unlocked = data_jutsu.jutsu_for_class_at_level(player.primary_class, player.level)
        for key in unlocked:
            display = data_jutsu.JUTSU[key]["display_name"]
            if display not in player.learned_skills:
                player.learned_skills.append(display)
                player.skill_proficiencies[display] = 0
                lines.append(f"You have unlocked:\n  {display}")

        if player.level >= data_jutsu.APPRAISAL_LEVEL_REQUIREMENT and "Examine" not in player.learned_skills:
            player.learned_skills.append("Examine")
            player.skill_proficiencies["Examine"] = 0
            lines.append("You have unlocked:\n  Examine")

        import data_handsigns
        if player.level >= data_handsigns.HANDSIGNS_MIN_LEVEL and "Handsigns" not in player.learned_skills:
            player.learned_skills.append("Handsigns")
            player.skill_proficiencies["Handsigns"] = 0
            lines.append("You have unlocked:\n  Handsigns")

        for skill_name, level_req, required_class in data_jutsu.MULTI_ATTACK_SKILLS:
            if required_class and player.primary_class != required_class:
                continue
            if player.level >= level_req and skill_name not in player.learned_skills:
                player.learned_skills.append(skill_name)
                player.skill_proficiencies[skill_name] = 0
                lines.append(f"You have unlocked:\n  {skill_name}")

        # Save immediately -- a crash right after a level-up shouldn't cost
        # the player the level they just earned.
        storage.save_player(player)

    return lines


def sync_universal_skills(player: Player) -> List[str]:
    """Called once at login (both a returning player AND an immortal --
    every account has a Player underneath) to bring an older character
    up to date with anything added or renamed since they were created:
    a skill renamed since (data_jutsu.SKILL_RENAMES) is migrated in
    place, keeping its current proficiency; any universal starting
    skill (data_jutsu.UNIVERSAL_STARTING_SKILLS) the character doesn't
    have yet -- because it was added to the game after their character
    was made -- is granted at 0%; and (Section 135, per direct
    request/confirmation: "make sure that all skills that have been
    added are being allocated when a player logs in") any class jutsu
    the player's CURRENT level already qualifies for, added to the
    game since their last login, is granted the same way -- catching
    what the ordinary level-up mechanism (data_jutsu.
    jutsu_for_class_at_level) can never retroactively catch on its
    own, since it only fires on an active level-up event. Kekkei
    Genkai-gated jutsu are deliberately excluded from this last check.
    Returns messages to show the player; empty if nothing changed. A
    freshly-created character already has everything, so this is a
    harmless no-op for them."""
    lines = []
    player.learned_skills = [skill for skill in player.learned_skills
                             if skill.lower() != "sharingan genjutsu"]
    player.skill_proficiencies.pop("Sharingan Genjutsu", None)

    for old_name, new_name in data_jutsu.SKILL_RENAMES.items():
        if old_name in player.learned_skills:
            idx = player.learned_skills.index(old_name)
            player.learned_skills[idx] = new_name
            if old_name in player.skill_proficiencies:
                player.skill_proficiencies[new_name] = player.skill_proficiencies.pop(old_name)

    for skill in data_jutsu.UNIVERSAL_STARTING_SKILLS:
        # Resolve through any rename first -- UNIVERSAL_STARTING_SKILLS
        # might still list the pre-rename name if it wasn't updated
        # alongside SKILL_RENAMES; without this, a just-renamed skill
        # would look "missing" under its old name and get re-granted,
        # undoing the rename above.
        current_name = data_jutsu.SKILL_RENAMES.get(skill, skill)
        if current_name not in player.learned_skills:
            player.learned_skills.append(current_name)
            player.skill_proficiencies[current_name] = 0
            lines.append(f"&Y(New since your last login: you have learned {current_name}!)&x")

    if (
        player.level >= data_jutsu.APPRAISAL_LEVEL_REQUIREMENT
        and "Examine" not in player.learned_skills
    ):
        player.learned_skills.append("Examine")
        player.skill_proficiencies["Examine"] = 0
        lines.append("&Y(New since your last login: you have learned Examine!)&x")

    for skill_name, level_req, required_class in data_jutsu.MULTI_ATTACK_SKILLS:
        if required_class and player.primary_class != required_class:
            continue
        if player.level >= level_req and skill_name not in player.learned_skills:
            player.learned_skills.append(skill_name)
            player.skill_proficiencies[skill_name] = 0
            lines.append(f"&Y(New since your last login: you have learned {skill_name}!)&x")

    # Per direct request/confirmation (Section 135): "make sure that
    # all skills that have been added are being allocated when a
    # player logs in." A real, genuine gap found here: any jutsu with
    # a real level_requirement is correctly auto-granted the moment a
    # matching-class player LEVELS UP into it (data_jutsu.
    # jutsu_for_class_at_level, called from an active level-up event)
    # -- but a returning player whose level ALREADY qualifies for a
    # jutsu added to the game since their last login (e.g. Silent
    # Genjutsu, Counter Kunai) never received it at all, since that
    # function is never called at login, only on an actual level-up.
    # all_unlocked_for_class uses <= rather than ==, so it correctly
    # catches every such jutsu regardless of when the player first
    # crossed that level threshold.
    for jutsu_key in data_jutsu.all_unlocked_for_class(player.primary_class, player.level):
        jutsu_data = data_jutsu.JUTSU[jutsu_key]
        if jutsu_data.get("kkg_gate"):
            # A Kekkei Genkai-gated jutsu (e.g. Mangekyo techniques) is
            # deliberately excluded from learned_skills entirely, per
            # its own real, existing design -- gated by the bloodline
            # ability itself, not a normal class/level unlock.
            continue
        display_name = jutsu_data["display_name"]
        if display_name not in player.learned_skills:
            player.learned_skills.append(display_name)
            player.skill_proficiencies[display_name] = 0
            lines.append(f"&Y(New since your last login: you have learned {display_name}!)&x")

    if lines:
        storage.save_player(player)

    return lines
