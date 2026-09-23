"""
SMAUG/ROM-style dice notation: "XdY+Z" (X dice of Y sides, plus flat Z).
Used for mob hit points and damage so mob prototypes carry real dice
strings (as shown by `mstat`) instead of a flat min/max pair -- rolled
per-instance at spawn (hit points) or per-attack (damage), giving the
same kind of variance a real ROM/SMAUG mob prototype has.
"""

import random
import re
from typing import Tuple

_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


def parse(spec: str) -> Tuple[int, int, int]:
    """Parse 'XdY+Z' -> (num_dice, sides, bonus). Falls back to (1, 1, 0)
    plus treating the whole string as a flat bonus if it's just a plain
    integer, so 'mset ... hitdice 25' also works without dice notation."""
    spec = (spec or "").strip()
    match = _DICE_RE.match(spec)
    if match:
        num, sides, bonus = match.group(1), match.group(2), match.group(3)
        return int(num), int(sides), int(bonus.replace(" ", "")) if bonus else 0
    if spec.lstrip("-").isdigit():
        return 1, 1, int(spec)
    return 1, 1, 0


def roll(spec: str) -> int:
    num, sides, bonus = parse(spec)
    return sum(random.randint(1, sides) for _ in range(num)) + bonus


def average(spec: str) -> int:
    num, sides, bonus = parse(spec)
    return int(num * (sides + 1) / 2) + bonus


def is_valid(spec: str) -> bool:
    spec = (spec or "").strip()
    return bool(_DICE_RE.match(spec)) or spec.lstrip("-").isdigit()
