"""
Personality trait trade-offs (Section 124).

Per direct request/confirmation: "lets discuss personality traits and
their bonus to characters" -> "trade off" confirmed as the real design
shape. Every trait (see data_appearance.PERSONALITY_TRAITS) pairs one
real, meaningful upside with one real, meaningful downside -- not a
free stat bump. Chosen once at character creation and permanent,
exactly like the class stat bonus (Section 123) this mirrors in spirit.

7 of the 8 traits work through the same real bonus_percent parameter
every derived_stats.py combat formula already accepts (the same
mechanism an equipment set bonus already uses) -- see
personality_bonus_percent() below, the single real source every combat
call site checks. The 8th, Loyal, is a genuinely different kind of
bonus (XP, not a combat number) and is checked directly in combat.py's
own XP-award logic instead (see LOYAL_GROUP_XP_BONUS_PCT).

Confirmed trade-offs, one pair per trait:
    Reckless:   +damage,        -armor class   (hits harder, easier to hit)
    Confident:  +hit roll,      -dodge          (lands more, doesn't flinch away)
    Loyal:      +10% XP in any real group fight (not just a formal Team);
                completely ordinary, unmodified XP solo -- confirmed
                explicitly NOT a penalty below the normal rate.
                Stacks with the existing Team XP bonus (teams.py).
    Reserved:   +dodge,         -damage         (evasive, but pulls punches)
    Calm:       +armor class,   -hit roll       (composed defense, less aggressive offense)
    Hot-headed: +critical,      -hit roll       (swings for the kill, less precise)
    Cunning:    +critical,      -armor class    (opportunistic, exposed while hunting the opening)
    Cheerful:   +dodge,         -critical       (light on their feet, doesn't press an advantage)
"""

LOYAL_GROUP_XP_BONUS_PCT = 10  # matches teams.TEAM_XP_BONUS_PCT for consistency, confirmed directly to STACK with it

# Each combat trait maps to a dict of {stat_name: signed_percent}, where
# stat_name matches the real derived_stats.py formula it modifies:
# "hit_roll", "damage_roll", "armor_class", "dodge_chance", "critical_chance".
# A negative percent for armor_class is a real PENALTY (worse armor,
# matching ROM convention that lower is better -- so a "-armor class"
# trade-off is actually a POSITIVE percent here, since armor_class's own
# bonus_percent makes the value more negative/better; see
# personality_bonus_percent's own docstring for the exact sign handling).
TRAIT_BONUSES = {
    "reckless":   {"damage_roll": 10, "armor_class": -10},
    "confident":  {"hit_roll": 10, "dodge_chance": -10},
    "reserved":   {"dodge_chance": 10, "damage_roll": -10},
    "calm":       {"armor_class": 10, "hit_roll": -10},
    "hot-headed": {"critical_chance": 10, "hit_roll": -10},
    "cunning":    {"critical_chance": 10, "armor_class": -10},
    "cheerful":   {"dodge_chance": 10, "critical_chance": -10},
    # "loyal" deliberately has NO entry here -- its own bonus is XP, a
    # genuinely different kind of thing, checked directly in combat.py
    # via LOYAL_GROUP_XP_BONUS_PCT instead of this dict at all.
}


def personality_bonus_percent(player, stat_name: str) -> int:
    """The real, signed percent bonus (positive helps, negative hurts)
    this player's own chosen personality_trait applies to the given
    derived_stats.py formula name -- "hit_roll", "damage_roll",
    "armor_class", "dodge_chance", or "critical_chance". 0 if their
    trait doesn't touch this particular stat at all (most traits only
    touch 2 of the 5 real stats). For armor_class specifically, this
    percent is passed straight into derived_stats.armor_class's own
    bonus_percent parameter exactly as-is -- that function's own
    established convention already makes a POSITIVE bonus_percent
    improve armor class (subtracting further from the base, since
    lower is better), so TRAIT_BONUSES' own -10 for a trait's armor
    class PENALTY is genuinely correct as a negative number here, not
    inverted."""
    return TRAIT_BONUSES.get(player.personality_trait, {}).get(stat_name, 0)
