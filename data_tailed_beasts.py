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

# Announcement palettes are visual themes for this MUD. Each beast keeps
# the same chakra colors when released and sealed.
BEAST_ANNOUNCEMENTS = {
    "shukaku": {
        "colors": ("&[220]", "&[39]"), "title": "THE HOWLING SANDSTORM",
        "release": ("GOLDEN CHAKRA tears across the horizon in a wall of sand!",
                    "Azure seal-marks blaze as Shukaku's laughter shakes the dunes!"),
        "sealed": ("The golden sandstorm spirals into a blazing azure seal!",
                   "Shukaku's furious laughter fades. The dunes fall silent."),
    },
    "matatabi": {
        "colors": ("&[33]", "&[87]"), "title": "THE PHANTOM IN BLUE FLAMES",
        "release": ("COBALT CHAKRA ignites the darkness in a wildfire of ghostly blue!",
                    "Two burning tails lash the heavens. Matatabi is on the hunt!"),
        "sealed": ("Cobalt flames coil into the seal like twin burning serpents!",
                   "Matatabi's final roar gutters out. The blue inferno is bound."),
    },
    "isobu": {
        "colors": ("&[213]", "&[80]"), "title": "THE ABYSSAL TERROR",
        "release": ("CORAL-PINK CHAKRA erupts through a towering turquoise tidal surge!",
                    "Three armored tails churn the depths. Isobu rises from the abyss!"),
        "sealed": ("Coral chakra is dragged into a whirling turquoise sealing vortex!",
                   "Isobu sinks beyond the seal. The crushing tide finally recedes."),
    },
    "son_goku": {
        "colors": ("&[196]", "&[214]"), "title": "THE MOLTEN MONKEY KING",
        "release": ("CRIMSON CHAKRA splits the earth beneath rivers of molten gold!",
                    "Four tails hammer the ground. Son Goku bellows through the ash!"),
        "sealed": ("Crimson chakra and molten fire crash against the closing seal!",
                   "Son Goku's volcanic roar dies away. The earth stops trembling."),
    },
    "kokuo": {
        "colors": ("&[231]", "&[117]"), "title": "THE WHITE STEAM TEMPEST",
        "release": ("PEARL-WHITE CHAKRA bursts skyward in a blinding plume of steam!",
                    "Five tails break the clouds. Kokuo's charge thunders over the land!"),
        "sealed": ("Pearl-white chakra condenses into a brilliant ice-blue seal!",
                   "Kokuo's thunderous charge ends. The scalding steam dissolves."),
    },
    "saiken": {
        "colors": ("&[157]", "&[183]"), "title": "THE CORROSIVE MIASMA",
        "release": ("PALE-GREEN CHAKRA blooms inside a shimmering violet poison haze!",
                    "Six glistening tails stir the mist. Saiken oozes into the world!"),
        "sealed": ("Pale-green chakra bubbles against a ring of violet sealing light!",
                   "Saiken's corrosive haze collapses. The world draws breath again."),
    },
    "chomei": {
        "colors": ("&[46]", "&[226]"), "title": "THE SEVEN-WINGED AURORA",
        "release": ("EMERALD CHAKRA streaks across the sky in a dazzling golden aurora!",
                    "Seven wings scatter radiant dust. Chomei's shriek splits the air!"),
        "sealed": ("Emerald chakra and golden dust spiral into seven rings of light!",
                   "Chomei's wings fold into the seal. The radiant sky grows still."),
    },
    "gyuki": {
        "colors": ("&[141]", "&[201]"), "title": "THE EIGHT-ARMED CATACLYSM",
        "release": ("VIOLET CHAKRA detonates through a rolling ocean of black ink!",
                    "Eight vast tentacles crush the horizon. Gyuki roars a challenge!"),
        "sealed": ("Violet chakra lashes the seal beneath a storm of magenta sparks!",
                   "Gyuki's eight tentacles vanish. The black ink washes away."),
    },
    "kurama": {
        "colors": ("&[208]", "&[196]"), "title": "THE NINE-TAILED CALAMITY",
        "release": ("BLAZING ORANGE CHAKRA engulfs the heavens in a blood-red inferno!",
                    "Nine monstrous tails blot out the sky. KURAMA'S ROAR SHAKES ALL!"),
        "sealed": ("Orange chakra erupts one last time in a blood-red pillar of fury!",
                   "Nine tails are drawn into the seal. Kurama's terrible roar ends."),
    },
}
