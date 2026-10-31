"""
Summoning contracts (Section 118).

Per direct request/confirmation: "I want to add Naruto summons as many
cannon animals as you can find also each summon is unique in ability
as a partner in battle...you can only summon after signing a summoning
contract at one of the summons secret hideouts so a we could make this
our first set of scroll jutsu that are learnable." Confirmed to start
with a solid, well-researched batch of 5-8 major contracts rather than
a truly exhaustive list -- these 5 are the real, canonically central
ones: Toad (Mount Myoboku), Snake (Ryuchi Cave), Slug (Shikkotsu
Forest), Ninken (Kakashi's own dog pack), and Monkey (Enma's line).

Confirmed mechanics, locked in directly:
- Signing ONE contract unlocks a whole progressive TIER LADDER within
  that one family, not a single fixed summon -- a basic member of the
  family at the unlock level, stronger/rarer members unlocking at
  higher levels within that same contract.
- The first signed family is a permanent choice. A player cannot sign,
  call, or study Sage Mode with any other summoning family.
- A summon's real combat stats scale directly off the SUMMONER's own
  CURRENT character level, multiplied by that summon's own base
  modifier (stronger contracts/tiers have a higher modifier) -- the
  same relationship a mob's own level-scaled stats already have,
  just keyed to the summoner instead of a fixed mob level.
- Only ONE summon can be active at a time -- summoning a new one
  dismisses whatever was already out, mirroring the existing Shadow
  Clone Jutsu replacement pattern exactly (see combat.
  dismiss_shadow_clones/spawn_shadow_clones, the real precedent this
  whole feature is built on).
- Every contract's own TOP tier has a genuinely unique mechanic, not
  just bigger numbers than the tier below it -- confirmed one by one,
  each a real, different battle role:
    Toad:   a battlefield TRAP (Summoning: Crushing Toad Stomach, real
            canon) -- restrains the target for several rounds, no
            ongoing damage of its own at all.
    Snake:  a BIND that hard-counters the target's own 'flee' attempts
            for its duration, plus real poison damage-over-time.
    Slug:   a genuine, one-time SAFETY NET -- if the summoner would
            otherwise be defeated while it's out, it absorbs that one
            killing blow and heals them back up instead, then is
            consumed.
    Ninken: a hard FLEE-LOCK specifically against one chosen PvP
            target -- their own 'flee' attempts fail outright for the
            fight's duration once this ninken is out against them.
    Monkey: a SELF-BUFF, not an independent fighter at all -- merges
            into the summoner's own weapon, directly boosting the
            summoner's own hitroll/damage for the fight instead of
            attacking on its own.
"""

from typing import Optional


# --- Contract-level metadata -------------------------------------------

CONTRACTS = {
    "toad": {
        "display_name": "Toad",
        "hideout_name": "Mount Myoboku",
        "unlock_level": 20,
    },
    "snake": {
        "display_name": "Snake",
        "hideout_name": "Ryuchi Cave",
        "unlock_level": 20,
    },
    "slug": {
        "display_name": "Slug",
        "hideout_name": "Shikkotsu Forest",
        "unlock_level": 20,
    },
    "ninken": {
        "display_name": "Ninken",
        "hideout_name": "the Hidden Leaf Kennels",
        "unlock_level": 20,
    },
    "monkey": {
        "display_name": "Monkey",
        "hideout_name": "the Monkey Sanctuary",
        "unlock_level": 20,
    },
    "salamander": {
        "display_name": "Salamander",
        "hideout_name": "the Hidden Rain Salamander Marsh",
        "unlock_level": 20,
    },
}


# --- Tier ladders, one list per contract, in ascending order -----------
# Each tier: unlock_level (the SUMMONER's own level required to
# summon this specific tier -- a signed contract at its own base
# unlock_level immediately grants access to every tier whose own
# unlock_level the summoner already meets, no separate per-tier
# unlock action needed), display_name, base_modifier (multiplies the
# summoner's own current level to derive real HP/damage -- see
# combat.py's own stat_for_summon_tier), and mechanic ("fighter" for
# an ordinary independently-attacking Mob partner, or one of the 5
# unique top-tier mechanic keys below for that contract's own
# signature ability).

TOAD_TIERS = [
    {"key": "toad_1", "display_name": "a small toad", "unlock_level": 20,
     "base_modifier": 1.0, "mechanic": "fighter"},
    {"key": "toad_2", "display_name": "Gamakichi", "unlock_level": 45,
     "base_modifier": 1.6, "mechanic": "fighter", "evasive": True},
    {"key": "toad_3", "display_name": "Gamabunta", "unlock_level": 70,
     "base_modifier": 2.4, "mechanic": "fighter"},
    {"key": "toad_4", "display_name": "the Toad Stomach", "unlock_level": 90,
     "base_modifier": 3.2, "mechanic": "trap"},
]

SNAKE_TIERS = [
    {"key": "snake_1", "display_name": "a small snake", "unlock_level": 20,
     "base_modifier": 1.0, "mechanic": "fighter", "poison": True},
    {"key": "snake_2", "display_name": "a constricting snake", "unlock_level": 45,
     "base_modifier": 1.6, "mechanic": "fighter", "poison": True},
    {"key": "snake_3", "display_name": "Manda", "unlock_level": 90,
     "base_modifier": 3.4, "mechanic": "bind", "poison": True},
]

SLUG_TIERS = [
    {"key": "slug_1", "display_name": "a small slug", "unlock_level": 20,
     "base_modifier": 0.8, "mechanic": "healer", "heal_percent": 8},
    {"key": "slug_2", "display_name": "a healing slug", "unlock_level": 50,
     "base_modifier": 1.2, "mechanic": "healer", "heal_percent": 14},
    {"key": "slug_3", "display_name": "Katsuyu", "unlock_level": 85,
     "base_modifier": 1.8, "mechanic": "safety_net", "heal_percent": 20},
]

NINKEN_TIERS = [
    {"key": "ninken_1", "display_name": "a ninken pup", "unlock_level": 20,
     "base_modifier": 0.9, "mechanic": "fighter", "extra_attack": True},
    {"key": "ninken_2", "display_name": "Pakkun", "unlock_level": 45,
     "base_modifier": 1.5, "mechanic": "fighter", "extra_attack": True},
    {"key": "ninken_3", "display_name": "the ninken pack", "unlock_level": 80,
     "base_modifier": 2.2, "mechanic": "flee_lock", "extra_attack": True},
]

MONKEY_TIERS = [
    {"key": "monkey_1", "display_name": "a small monkey", "unlock_level": 20,
     "base_modifier": 1.0, "mechanic": "fighter", "evasive": True},
    {"key": "monkey_2", "display_name": "a battle monkey", "unlock_level": 50,
     "base_modifier": 1.6, "mechanic": "fighter", "evasive": True},
    {"key": "monkey_3", "display_name": "Enma", "unlock_level": 85,
     "base_modifier": 2.0, "mechanic": "weapon_buff"},
]

# The level cap is 250. Every existing contract now has a complete
# progression toward that cap; previous lower-tier keys stay stable.
TOAD_TIERS.extend([
    {"key": "toad_5", "display_name": "Gamahiro the Toad Swordsman", "unlock_level": 135, "base_modifier": 3.8, "mechanic": "fighter"},
    {"key": "toad_6", "display_name": "Gamaken the Stalwart", "unlock_level": 195, "base_modifier": 4.6, "mechanic": "fighter"},
    {"key": "toad_7", "display_name": "the Great Toad Stomach", "unlock_level": 250, "base_modifier": 5.8, "mechanic": "trap"},
])
SNAKE_TIERS.extend([
    {"key": "snake_4", "display_name": "a Giant War Serpent", "unlock_level": 135, "base_modifier": 3.9, "mechanic": "fighter", "poison": True},
    {"key": "snake_5", "display_name": "Aoda", "unlock_level": 190, "base_modifier": 4.8, "mechanic": "fighter", "poison": True},
    {"key": "snake_6", "display_name": "the Elder White Snake", "unlock_level": 250, "base_modifier": 6.0, "mechanic": "bind", "poison": True},
])
SLUG_TIERS.extend([
    {"key": "slug_4", "display_name": "a Great Healing Slug", "unlock_level": 135, "base_modifier": 2.7, "mechanic": "healer", "heal_percent": 25},
    {"key": "slug_5", "display_name": "Katsuyu's Grand Division", "unlock_level": 195, "base_modifier": 3.8, "mechanic": "healer", "heal_percent": 32},
    {"key": "slug_6", "display_name": "Katsuyu's Supreme Guardian", "unlock_level": 250, "base_modifier": 5.0, "mechanic": "safety_net", "heal_percent": 45},
])
NINKEN_TIERS.extend([
    {"key": "ninken_4", "display_name": "a Battle-Hardened Wolf", "unlock_level": 135, "base_modifier": 3.4, "mechanic": "fighter", "extra_attack": True},
    {"key": "ninken_5", "display_name": "an Elite Tracking Hound", "unlock_level": 195, "base_modifier": 4.4, "mechanic": "fighter", "extra_attack": True},
    {"key": "ninken_6", "display_name": "the Seven Ninja Hounds", "unlock_level": 250, "base_modifier": 6.2, "mechanic": "flee_lock", "extra_attack": True},
])
MONKEY_TIERS.extend([
    {"key": "monkey_4", "display_name": "the Adamantine Staff Sentinel", "unlock_level": 135, "base_modifier": 3.1, "mechanic": "fighter"},
    {"key": "monkey_5", "display_name": "Enma the Monkey King", "unlock_level": 195, "base_modifier": 4.6, "mechanic": "weapon_buff"},
    {"key": "monkey_6", "display_name": "the Adamantine Monkey King", "unlock_level": 250, "base_modifier": 5.8, "mechanic": "weapon_buff"},
])
SALAMANDER_TIERS = [
    {"key": "salamander_1", "display_name": "a Tiny Marsh Salamander", "unlock_level": 20, "base_modifier": 0.9, "mechanic": "fighter", "poison": True},
    {"key": "salamander_2", "display_name": "a Venom-Spitting Salamander", "unlock_level": 55, "base_modifier": 1.5, "mechanic": "fighter", "poison": True},
    {"key": "salamander_3", "display_name": "a Hardened Swamp Salamander", "unlock_level": 100, "base_modifier": 2.5, "mechanic": "fighter", "poison": True},
    {"key": "salamander_4", "display_name": "a Giant Marsh Guardian", "unlock_level": 155, "base_modifier": 3.6, "mechanic": "fighter", "poison": True},
    {"key": "salamander_5", "display_name": "Ibuse the Giant Salamander", "unlock_level": 210, "base_modifier": 4.8, "mechanic": "poison_cloud", "poison": True},
    {"key": "salamander_6", "display_name": "the Ancient Salamander", "unlock_level": 250, "base_modifier": 6.0, "mechanic": "poison_cloud", "poison": True},
]

CONTRACT_TIERS = {
    "toad": TOAD_TIERS,
    "snake": SNAKE_TIERS,
    "slug": SLUG_TIERS,
    "ninken": NINKEN_TIERS,
    "monkey": MONKEY_TIERS,
    "salamander": SALAMANDER_TIERS,
}


def best_available_tier(contract: str, summoner_level: int) -> Optional[dict]:
    """The single highest tier within `contract` the summoner's own
    current level genuinely qualifies for right now -- e.g. a level 60
    Toad-contract summoner gets Gamabunta (tier 3, unlocks at 70)... no,
    gets Gamakichi (tier 2, unlocks at 45), since they're not yet 70.
    None if `contract` isn't real, or the summoner hasn't even reached
    that contract's own base unlock_level yet."""
    tiers = CONTRACT_TIERS.get(contract)
    if not tiers:
        return None
    eligible = [t for t in tiers if summoner_level >= t["unlock_level"]]
    if not eligible:
        return None
    return max(eligible, key=lambda t: t["unlock_level"])


def tier_by_key(tier_key: str) -> Optional[dict]:
    """Direct lookup of one specific tier dict by its own key (e.g.
    "toad_3"), regardless of contract or level -- used when a live
    Mob's own summon_tier_key needs to be resolved back to its real
    tier data (for e.g. checking its own mechanic during combat)."""
    for tiers in CONTRACT_TIERS.values():
        for tier in tiers:
            if tier["key"] == tier_key:
                return tier
    return None
