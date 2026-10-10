"""Colorful combat damage descriptions with a matching help scale.

Damage remains numeric internally for combat math, but every player-facing
damage message uses one of these xterm-256 tiers. The final tier starts at
10,000 so end-game attacks remain descriptive without exposing raw numbers.
"""

from typing import Tuple


# (maximum damage for tier, label, xterm-256 foreground color)
# ``None`` is the open-ended 10,000+ tier.
DAMAGE_TIERS: Tuple[Tuple[int | None, str, int], ...] = (
    (1, "TRIVIAL", 245),
    (4, "GLANCING", 110),
    (9, "STINGING", 123),
    (19, "BONE-JARRING", 39),
    (34, "RIB-RATTLING", 75),
    (54, "THUNDEROUS", 135),
    (79, "BRUTAL", 171),
    (119, "FEROCIOUS", 168),
    (179, "CRUSHING", 174),
    (259, "SAVAGE", 215),
    (399, "MANGLE-INDUCING", 190),
    (599, "DEVASTATING", 220),
    (899, "ANNIHILATING", 214),
    (1299, "OBLITERATING", 208),
    (1999, "CATASTROPHIC", 202),
    (2999, "CATACLYSMIC", 196),
    (4999, "WORLD-BREAKING", 197),
    (7499, "REALITY-RENDING", 93),
    (9999, "REALITY-SHATTERING", 201),
    (None, "EXTINCTION-LEVEL", 213),
)


def damage_tier(amount: int) -> Tuple[str, int]:
    """Return the plain label and xterm color for ``amount`` damage."""
    amount = max(0, int(amount))
    for maximum, label, color in DAMAGE_TIERS:
        if maximum is None or amount <= maximum:
            return label, color
    raise AssertionError("open-ended damage tier is missing")


def describe_damage(amount: int) -> str:
    """Return a player-facing, number-free, 256-color damage phrase."""
    label, color = damage_tier(amount)
    return f"&[{color}]{label}&x"


def help_scale_lines() -> str:
    """Build the exact numeric ranges and colored words from the live tiers."""
    lines = []
    minimum = 0
    for maximum, label, color in DAMAGE_TIERS:
        span = f"{minimum:,}+" if maximum is None else f"{minimum:,}-{maximum:,}"
        lines.append(f"  {span:>13} damage  &[{color}]{label}&x")
        if maximum is not None:
            minimum = maximum + 1
    return "\n".join(lines)


def impact_flavor(amount: int) -> str:
    """A brief impact image that scales with the same damage as the word."""
    if amount < 10:
        return "A quick sting, barely more than a warning."
    if amount < 55:
        return "The impact snaps through the air."
    if amount < 180:
        return "The blow lands with a sharp, bone-deep crack."
    if amount < 600:
        return "The strike hits like a thunderclap."
    if amount < 2000:
        return "The force ripples across the battlefield."
    if amount < 10000:
        return "The air itself seems to split around the impact."
    return "For a heartbeat, the battlefield falls silent."
