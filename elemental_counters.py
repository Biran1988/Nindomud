"""
Counter-jutsu (Section 97): elemental counters and collision effects,
per direct request/confirmation:

"A counter jutsu should be an opposing element only"

Confirmed design across several follow-ups:
- A one-directional 5-way elemental cycle, matching the classic
  anime/canon elemental wheel: Water beats Fire, Fire beats Wind,
  Wind beats Lightning, Lightning beats Earth, Earth beats Water.
  Each element counters exactly one other and is countered by
  exactly one other.
- A counter isn't a race or an interrupt -- it's a genuine COLLISION:
  if both casters' hand-sign delays finish within
  COLLISION_WINDOW_SECONDS of each other, and the two jutsu are of
  opposing elements, they collide in mid-air. Confirmed: "It's not in
  interruption as much as a counter/canceling when the jutsu hit
  eachother."
- Confirmed: BOTH jutsu are cancelled outright -- neither lands its
  normal damage/effect on its target. All that happens is a real,
  themed room effect (a collision message, plus a temporary room-
  description addition -- see world.Room.temp_description_text).
- Confirmed: every one of the 5 opposing pairs gets its own unique
  message and room effect, not a single generic placeholder.
"""

# The one-directional 5-way elemental cycle. ELEMENT_COUNTERS[x] is
# the element that BEATS x (i.e. counters a jutsu of element x).
ELEMENT_COUNTERS = {
    "fire": "water",
    "wind": "fire",
    "lightning": "wind",
    "earth": "lightning",
    "water": "earth",
}

COLLISION_WINDOW_SECONDS = 1.0

# Keyed by frozenset({countering_element, countered_element}) so the
# lookup works regardless of which side actually finished first.
COLLISION_EFFECTS = {
    frozenset({"water", "fire"}): {
        "message": "&C{winner}'s Water technique slams into {loser}'s Fire technique, and the two erupt into a hissing wall of steam!&x",
        "room_text": "A thick cloud of steam still hangs in the air, slowly dissipating.",
    },
    frozenset({"fire", "wind"}): {
        "message": "&R{winner}'s Fire technique catches {loser}'s Wind technique, and the collision flashes into a brief, searing firestorm!&x",
        "room_text": "Scorch marks and drifting ash mark where the two techniques collided.",
    },
    frozenset({"wind", "lightning"}): {
        "message": "&Y{winner}'s Wind technique tears through {loser}'s Lightning technique, scattering crackling sparks in every direction!&x",
        "room_text": "The air still smells faintly of ozone, and loose debris is still settling.",
    },
    frozenset({"lightning", "earth"}): {
        "message": "&W{winner}'s Lightning technique arcs straight through {loser}'s Earth technique, leaving the ground scorched and smoking!&x",
        "room_text": "Cracked, blackened earth marks where the two techniques met.",
    },
    frozenset({"earth", "water"}): {
        "message": "&Y{winner}'s Earth technique churns into {loser}'s Water technique, and the ground turns to thick, sucking mud!&x",
        "room_text": "The ground underfoot is still churned into thick, sucking mud.",
    },
}

TEMP_DESCRIPTION_DURATION_SECONDS = 60.0

# Overpowering (Section 98), per direct request/confirmation: "factor
# in the Justus level and mastery...making a higher level and mastery
# jutsu can overpower its naturally weak element." A genuine
# collision (opposing elements, timing within COLLISION_WINDOW_
# SECONDS) still happens, but if one side's combined power_score
# clears the other's by OVERPOWER_THRESHOLD or more, that side's
# jutsu punches through instead of both being fully cancelled --
# landing on its target at OVERPOWER_DAMAGE_MULTIPLIER of its normal
# damage (confirmed: "still lands, but at reduced strength"). The
# overpowered side's own jutsu is still fully cancelled either way,
# same as an even collision.
OVERPOWER_THRESHOLD = 30  # confirmed: a fixed point gap, not a percentage
OVERPOWER_DAMAGE_MULTIPLIER = 0.25  # confirmed: "a bigger cut, like 25% of normal damage"


def power_score(player_level: int, mastery_pct: int) -> int:
    """A single combined power score for the overpower check, per
    direct confirmation ("A weighted score from BOTH level and
    mastery % combined (e.g. level + mastery% as one combined
    number)"). Simply level + mastery%, so it ranges roughly 20 (the
    minimum level for an elemental jutsu, freshly unlocked at 0%
    mastery) up to 200 (max level, full mastery) -- the confirmed
    30-point OVERPOWER_THRESHOLD is meaningful, but achievable,
    across that whole range."""
    return player_level + mastery_pct


def counters(element: str) -> str:
    """The element that beats `element`, per the confirmed 5-way cycle."""
    return ELEMENT_COUNTERS[element]


def is_counter(countering_element: str, countered_element: str) -> bool:
    """Whether countering_element genuinely beats countered_element,
    per the confirmed cycle."""
    return ELEMENT_COUNTERS.get(countered_element) == countering_element


def collision_effect(element_a: str, element_b: str) -> dict:
    """The themed message/room_text for this specific opposing pair,
    regardless of which side actually finished first (looked up by
    the unordered pair)."""
    return COLLISION_EFFECTS[frozenset({element_a, element_b})]
