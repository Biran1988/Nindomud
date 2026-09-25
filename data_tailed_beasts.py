"""
Tailed Beasts (Section 127).

Per direct request/confirmation: "The tailed beast are like natural
disasters the destroy and kill everything in sight...they are super
strong mobs that would take many high level ninja to defeat...they are
released in a random by immortals with the release beast command that
will randomly select a tailed beast that hasn't been captured by a
player using sealing jutsu so only 1 per player sealing."

All 9 real canon beasts, confirmed directly to include every one, not
a smaller starting subset -- in ascending tail-count order: Shukaku
(1), Matatabi (2), Isobu (3), Son Goku (4), Kokuo (5), Saiken (6),
Chomei (7), Gyuki (8), Kurama (9). Verified via direct research rather
than assumed.

Confirmed design, locked in directly across many turns:
- Released by an immortal via the 'unleash beast' command, which
  randomly picks ONE beast that hasn't currently been sealed into any
  player (see tailed_beasts.py for the actual selection/lifecycle
  logic -- this module is data only).
- HP/damage scale with tail count -- a genuinely real, escalating
  power tier. Buffed 10x across the board (Section 129, per direct
  request/confirmation: "Make the current tailed beast x10 stronger
  I was able to kill them solo") after the original tier proved
  soloable -- now roughly 150x-650x a maxed level-100 player's own HP
  (991), so even the weakest beast (Shukaku) requires a genuine,
  sustained group effort, and Kurama is meaningfully the hardest.
- Every beast is otherwise mechanically identical at this stage
  (same real mob template shape, same roaming/despawn/capture rules)
  -- what differs is purely these 2 numbers, tail count, and display
  name/flavor. Real mastery-based abilities (rampage, Tailed Beast
  Mode, the Tailed Beast Bomb) are a confirmed separate, later stage
  of this same feature, not built in this data module.
"""

TAILED_BEASTS = [
    {"key": "shukaku", "display_name": "Shukaku", "tails": 1,
     "max_health": 150000, "min_damage": 800, "max_damage": 1400},
    {"key": "matatabi", "display_name": "Matatabi", "tails": 2,
     "max_health": 200000, "min_damage": 1000, "max_damage": 1700},
    {"key": "isobu", "display_name": "Isobu", "tails": 3,
     "max_health": 250000, "min_damage": 1200, "max_damage": 2000},
    {"key": "son_goku", "display_name": "Son Goku", "tails": 4,
     "max_health": 300000, "min_damage": 1400, "max_damage": 2300},
    {"key": "kokuo", "display_name": "Kokuo", "tails": 5,
     "max_health": 370000, "min_damage": 1650, "max_damage": 2650},
    {"key": "saiken", "display_name": "Saiken", "tails": 6,
     "max_health": 440000, "min_damage": 1900, "max_damage": 3000},
    {"key": "chomei", "display_name": "Chomei", "tails": 7,
     "max_health": 510000, "min_damage": 2150, "max_damage": 3350},
    {"key": "gyuki", "display_name": "Gyuki", "tails": 8,
     "max_health": 580000, "min_damage": 2400, "max_damage": 3700},
    {"key": "kurama", "display_name": "Kurama", "tails": 9,
     "max_health": 650000, "min_damage": 2700, "max_damage": 4100},
]

TAILED_BEASTS_BY_KEY = {b["key"]: b for b in TAILED_BEASTS}
