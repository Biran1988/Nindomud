"""Colorful, number-free combat damage descriptions.

Damage remains numeric internally for combat math, but every player-facing
damage message uses one of these xterm-256 tiers. The final tier starts at
10,000 so end-game attacks remain descriptive without exposing raw numbers.
"""

from typing import Tuple


# (maximum damage for tier, label, xterm-256 foreground color)
# ``None`` is the open-ended 10,000+ tier.
DAMAGE_TIERS: Tuple[Tuple[int | None, str, int], ...] = (
    (1, "TRIVIAL", 245),
    (4, "GLANCING", 250),
    (9, "MINOR", 153),
    (19, "SOLID", 117),
    (34, "HARD", 81),
    (54, "HEAVY", 45),
    (79, "BRUTAL", 48),
    (119, "VICIOUS", 82),
    (179, "CRUSHING", 118),
    (259, "SAVAGE", 154),
    (399, "MANGLE-INDUCING", 190),
    (599, "DEVASTATING", 220),
    (899, "ANNIHILATING", 214),
    (1299, "OBLITERATING", 208),
    (1999, "CATASTROPHIC", 202),
    (2999, "CATACLYSMIC", 196),
    (4999, "WORLD-BREAKING", 197),
    (7499, "REALITY-RENDING", 199),
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
