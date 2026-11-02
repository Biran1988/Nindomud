"""Level-aware jutsu resource pressure and distinctive power profiles.

This module deliberately does not mutate the JUTSU catalog. The live caster's
level and maximum pool determine the paid price; listed base costs and ongoing
maintenance/upkeep remain the source of truth for their existing mechanics.
"""
import math

# Additional (level x percent) cost, and a percent of the current maximum pool.
# High ranks get powerful techniques, but only a handful of top-tier casts.
LEVEL_RATE = {1: .12, 2: .24, 3: .42, 4: .64, 5: .85}
POOL_RATE = {1: .06, 2: .095, 3: .14, 4: .19, 5: .245}
POWER = {1: 1.55, 2: 1.85, 3: 2.20, 4: 2.65, 5: 3.15}
DURATION = {1: 1.45, 2: 1.75, 3: 2.15, 4: 2.55, 5: 3.0}

# Individual attacks are not all equal within one unlock tier.
ATTACK_POWER = {
    "shadow shuriken technique": 1.35,
    "chakra ball": 1.55,
    "rasengan": 2.25,
    "oodama rasengan": 2.7,
    "nanairo no rasengan": 3.0,
    "chidori": 2.2,
    "dual chidori": 2.45,
    "full body chidori": 2.75,
    "maximum chidori": 3.35,
    "raikiri": 3.1,
    "particle spear": 3.7,
    "fireball jutsu": 1.95,
    "water dragon jutsu": 2.35,
    "lightning strike jutsu": 2.3,
    "wind blade jutsu": 2.2,
}
# Longer individual effects/utility casts, not generic uniform buffs.
EFFECT_POWER = {
    "barrier": 3.0,
    "hidden mist jutsu": 2.6,
    "henge": 2.0,
    "greater henge": 2.75,
    "ultimate henge": 3.5,
    "narakumi": 2.5,
    "demonic illusion hell viewing technique": 2.0,
    "nehan shouja": 2.0,
    "ice prison": 2.4,
    "wood binding roots": 2.4,
    "camouflage": 2.0,
    "sensory detect": 2.5,
    "focused mind": 2.5,
}

def _tier(jutsu):
    return max(1, min(5, int(jutsu.get("tier", 1) or 1)))

def cast_cost(actor, jutsu, resource="chakra", *, base_override=None, apply_control=True):
    """Actual whole-resource price for this cast, before mutation.

    A copied Sharingan cast has already recorded the original paid cost x2;
    pass that amount as base_override to preserve its exact cost without
    charging the level surcharge a second time.
    """
    if resource not in ("chakra", "stamina"):
        raise ValueError("Resource must be chakra or stamina")
    base = max(0, int(jutsu.get(resource + "_cost", 0) if base_override is None else base_override))
    if base == 0 or base_override is not None:
        return base
    level = max(1, int(getattr(actor, "level", 1)))
    tier = _tier(jutsu)
    maximum = max(0, int(getattr(actor, "maximum_" + resource, 0)))
    level_rate = float(jutsu.get("balance_level_rate", LEVEL_RATE[tier]))
    pool_rate = float(jutsu.get("balance_pool_rate", POOL_RATE[tier]))
    # Small low-level pools keep entry jutsu approachable; at high level
    # the percentage of the much larger chakra/stamina pool matters.
    maturity = min(1.0, .30 + .70 * level / 250.0)
    surcharge = max(math.ceil(level * level_rate),
                    math.ceil(maximum * pool_rate * maturity))
    cost = base + surcharge
    if apply_control and resource == "chakra" and jutsu.get("class_requirement") in ("ninjutsu", "genjutsu"):
        import derived_stats
        reduction = derived_stats.chakra_control_cost_discount_percent(
            getattr(actor, "chakra_control", 10))
        cost = max(1, math.ceil(cost * (100 - reduction) / 100))
    return cost

def boosted_damage(actor, jutsu, damage):
    """Apply a per-jutsu offensive boost to damage, preserving zero damage."""
    if damage <= 0:
        return damage
    name = jutsu.get("display_name", "").lower()
    tier = _tier(jutsu)
    multiplier = float(jutsu.get("balance_damage_multiplier",
                                 ATTACK_POWER.get(name, POWER[tier])))
    # Trained high-level shinobi get extra force from familiar techniques,
    # without turning the lowest-level starter move into a capstone attack.
    gained = max(0, int(getattr(actor, "level", 1)) - int(jutsu.get("level_requirement", 1)))
    multiplier *= 1 + min(.35, gained / 500.0)
    return max(1, int(round(damage * multiplier)))

def boosted_duration(actor, jutsu, seconds, *, is_pvp=False, effect=None):
    """Increase each jutsu's lasting power without indefinite hard-locks."""
    if not seconds or seconds < 1:
        return seconds
    name = jutsu.get("display_name", "").lower()
    multiplier = float(jutsu.get("balance_duration_multiplier",
                                 EFFECT_POWER.get(name, DURATION[_tier(jutsu)])))
    gained = max(0, int(getattr(actor, "level", 1)) - int(jutsu.get("level_requirement", 1)))
    multiplier *= 1 + min(.25, gained / 800.0)
    result = max(1, math.ceil(seconds * multiplier))
    if effect:
        import status_effects
        definition = status_effects.EFFECT_DEFS.get(effect, {})
        if definition.get("blocks_action"):
            # Six seconds max in PvP prevents endless incapacity from recasts.
            return min(result, 6 if is_pvp else 12)
        if definition.get("blocks_movement"):
            return min(result, 15 if is_pvp else 35)
    return result
