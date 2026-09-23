"""
Passive skills.

Unlike jutsu (triggered with `perform`/bare name) or weapon proficiencies
(advanced with `practice`/`prac`), a passive skill is never manually
triggered and never gains proficiency from practice points -- it grows
automatically through combat participation instead (see
combat.tick_passive_skill_growth()), and its effect applies
automatically once the player has it learned.

Strong Fist Style is granted to every player regardless of primary
class (it's part of the universal starting kit -- see session.py),
giving a small melee damage bonus scaling with its own proficiency.
"""

PASSIVE_SKILLS = {
    "Strong Fist Style": {
        "class_requirement": None,  # universal -- every player starts with this
        "description": "A close-combat specialization that strengthens with battle experience.",
        "damage_bonus_at_mastery": 0.10,  # +10% melee damage at 100% proficiency, scaling linearly
    },
}


def is_passive(skill_name: str) -> bool:
    return skill_name in PASSIVE_SKILLS


def damage_multiplier(skill_name: str, proficiency_pct: int) -> float:
    """1.0 = no bonus. Scales linearly with proficiency up to the skill's
    damage_bonus_at_mastery at 100%."""
    info = PASSIVE_SKILLS.get(skill_name)
    if not info:
        return 1.0
    return 1.0 + info["damage_bonus_at_mastery"] * (proficiency_pct / 100)
