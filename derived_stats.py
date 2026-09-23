"""
Derived combat stats, computed from a character's attributes -- a
Player OR a Mob (see combat.py's own real strength/dexterity/luck
fields, added in Section 147 for full player/mob combat-math parity,
per direct confirmation: "a genuine, deep parity between mob and
player combat math, not just equipment"). Every function here only
ever reads a generic .dexterity/.strength/.luck attribute, never
anything player-specific, so accepting either type is safe -- this
was already true in spirit before Section 147: to_hit_chance's own
docstring already noted mobs "need to work symmetrically" through
this same module, since combat.py's real hit/miss math was always
attacker-type-agnostic; Section 147 is what finally gave Mob real
attribute fields to make that symmetry actually mean something.

dodge_chance, critical_chance, armor_class, and hit_roll are all
actually used in combat.py's damage resolution (see to_hit_chance()
below for the armor_class/hit_roll piece specifically -- added after
these existed as score-sheet-only display for a while). damage_roll
and initiative are still computed and displayed but not wired into
combat math beyond that.

dodge_chance and critical_chance are normalized against
config.MAX_ATTRIBUTE_VALUE (the real 40 cap on any trainable attribute)
so they scale smoothly across the entire trainable range and hit their
soft percentage caps exactly at a maxed attribute, rather than
plateauing partway there. A mob's own real attribute CAN exceed this
cap (equipment has no comparable ceiling the way player training
does) -- _scaled's own real min()/max() clamp already handles this
correctly regardless of type, since it was written to clamp any raw
value into range, not specifically a player's own capped-at-75 stat.

Every function here takes an optional bonus_percent (from
commands.equipped_set_bonus_percent() -- kept out of this module to
avoid a circular import, since that function needs equipment/oset
access). The bonus is applied AFTER the normal soft cap, so completing
an armor set is a genuine reason to exceed dodge_chance/critical_chance's
usual ceiling, not just another way to reach it. armor_class is handled
additively rather than multiplicatively -- it's a lower-is-better stat,
and multiplying a POSITIVE (bad) armor_class by a "bonus" would make it
worse, not better, which isn't what a set bonus should ever do.

All formulas are simple and intentionally tunable -- adjust the
constants here, nothing else needs to change.
"""

import config
from typing import Union
from models import Player
import combat

Character = Union[Player, "combat.Mob"]


def _with_bonus(value: int, bonus_percent: int) -> int:
    if not bonus_percent:
        return value
    return int(round(value * (1 + bonus_percent / 100)))


def armor_class(character: Character, bonus_percent: int = 0) -> int:
    """Lower (more negative) is better, matching ROM convention."""
    base = 10 - (character.dexterity * 2)
    if not bonus_percent:
        return base
    # Additive improvement (never a sign-flipping multiply) -- 10 AC
    # points per 100% bonus is the tuning constant here.
    return base - round(bonus_percent / 100 * 10)


def hit_roll(character: Character, bonus_percent: int = 0) -> int:
    return _with_bonus(character.dexterity - 10, bonus_percent)


def damage_roll(character: Character, bonus_percent: int = 0) -> int:
    return _with_bonus(character.strength - 10, bonus_percent)


def initiative(character: Character, bonus_percent: int = 0) -> int:
    return _with_bonus((character.dexterity - 10) // 2, bonus_percent)


def _scaled(value: int, base: int, span_cap: int) -> int:
    """Linearly scales `value` (10..MAX_ATTRIBUTE_VALUE) to (base..base+span_cap)."""
    attribute_span = config.MAX_ATTRIBUTE_VALUE - 10
    raw = base + (value - 10) / attribute_span * span_cap
    return int(max(0, min(base + span_cap, round(raw))))


def dodge_chance(character: Character, bonus_percent: int = 0) -> int:
    """Percent chance to fully avoid an incoming mob attack. 5% at the
    baseline Dexterity (10), up to 40% at a maxed Dexterity (40) --
    a completed armor set's bonus is applied on top and CAN push this
    past 40%, since that cap is only meant to apply to raw attribute
    training, not set bonuses."""
    return _with_bonus(_scaled(character.dexterity, base=5, span_cap=35), bonus_percent)


def critical_chance(character: Character, bonus_percent: int = 0) -> int:
    """Percent chance for a basic attack to land as a critical.
    5% at the baseline Luck (10), up to 30% at a maxed Luck (40) -- same
    past-the-cap treatment for a completed set's bonus as dodge_chance."""
    return _with_bonus(_scaled(character.luck, base=5, span_cap=25), bonus_percent)


def compute_all(character: Character, bonus_percent: int = 0) -> dict:
    return {
        "armor_class": armor_class(character, bonus_percent),
        "hit_roll": hit_roll(character, bonus_percent),
        "damage_roll": damage_roll(character, bonus_percent),
        "initiative": initiative(character, bonus_percent),
        "dodge_chance": dodge_chance(character, bonus_percent),
        "critical_chance": critical_chance(character, bonus_percent),
    }


TO_HIT_BASE_PCT = 85
TO_HIT_MIN_PCT = 10
TO_HIT_MAX_PCT = 95


def to_hit_chance(attacker_hit_roll: int, defender_armor_class: int) -> int:
    """Percent chance an attack actually lands -- the piece that was
    missing before: every attack always connected regardless of either
    side's stats. Takes raw ints rather than Player objects, since
    mobs (combat.Mob) carry their own hit_roll/armor_class fields too
    and this needs to work symmetrically for both attacker types.

    Higher attacker hit_roll improves the odds; lower (better, ROM
    convention) defender armor_class also improves them, since a
    well-defended target is harder to land a hit on. Clamped to
    [TO_HIT_MIN_PCT, TO_HIT_MAX_PCT] so no combination of stats makes
    a fight a guaranteed hit or a guaranteed miss -- there's always
    some chance either way.

    At baseline stats on both sides (hit_roll=0, armor_class=0) this
    is exactly TO_HIT_BASE_PCT (85%), matching the old always-hits
    behavior closely enough that a fresh, ungeared fight doesn't
    suddenly feel unfair -- the swing comes from actually investing in
    Dexterity (which drives both stats) or from crafted equipment
    bonuses, not from the baseline itself.
    """
    raw = TO_HIT_BASE_PCT + (attacker_hit_roll + defender_armor_class) // 2
    return max(TO_HIT_MIN_PCT, min(TO_HIT_MAX_PCT, raw))


CHAKRA_CONTROL_DISCOUNT_PER_POINT_PCT = 1  # confirmed directly: "+1% discount per point above 10"
CHAKRA_CONTROL_DISCOUNT_CAP_PCT = 50  # confirmed directly: "capped at 50% maximum"


def chakra_control_cost_discount_percent(chakra_control: int) -> int:
    """The real, linear % discount Chakra Control gives -- per direct
    request/confirmation (Section 131): "this stat also scales to
    reduce chakra usage when using genjutsu or taijutsu." Confirmed
    directly: Taijutsu costs Stamina, not Chakra, so this same real
    discount is confirmed to apply to Genjutsu's own chakra cost AND
    Taijutsu's own stamina cost, each on its own matching resource --
    this function returns the one shared percent both callers use.
    +1% per point above the baseline of 10, capped at a genuine 50%
    maximum (never fully free). 0 at or below baseline."""
    if chakra_control <= 10:
        return 0
    return min(CHAKRA_CONTROL_DISCOUNT_CAP_PCT, (chakra_control - 10) * CHAKRA_CONTROL_DISCOUNT_PER_POINT_PCT)
