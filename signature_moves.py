"""One player-chosen learned skill; signature mastery works for active and passive skills."""

import math


SIGNATURE_CAP = 150
SIGNATURE_BONUS = 1.25


def eligible(jutsu):
    """All learned jutsu qualify, including passive and later-unlocked types.

    The command also accepts learned class skills outside the JUTSU table
    (weapon skills, multi-attacks, sword styles and passive progressions).
    """
    return bool(jutsu.get("display_name"))


def eligible_names(player):
    """The character's actual learned skills are the source of truth.

    Do not restrict signatures to a small hard-coded set of starter jutsu.
    Learned bloodline, scroll, class, utility and passive skills all count.
    """
    return sorted({name for name in getattr(player, "learned_skills", ())
                   if isinstance(name, str) and name.strip()}, key=str.casefold)


def selected_name(player):
    return getattr(player, "signature_move", "") or ""


def mastered(player, skill_name):
    """Only the single chosen skill receives signature effects at 150%."""
    return (bool(skill_name) and selected_name(player) == skill_name
            and skill_name in getattr(player, "learned_skills", ())
            and player.skill_proficiencies.get(skill_name, 0) >= SIGNATURE_CAP)


def multiplier(player, skill_name):
    return SIGNATURE_BONUS if mastered(player, skill_name) else 1.0


def empowered(player, jutsu):
    return eligible(jutsu) and mastered(player, jutsu.get("display_name", ""))


def amount(player, jutsu, amount):
    return max(1, round(amount * SIGNATURE_BONUS)) if empowered(player, jutsu) else amount


def duration(player, jutsu, duration):
    return max(1, math.ceil(duration * SIGNATURE_BONUS)) if empowered(player, jutsu) else duration
