"""
Mangekyo Sharingan techniques (Section 140).

Per direct request/confirmation, across a long design conversation:
"I want [Mangekyo] to be unique per player as it was in the anime."
Confirmed design, locked in piece by piece:

- Every Mangekyo user (bloodline_mangekyo=True) automatically, always
  has Susanoo -- a real, universal ability tied to having Mangekyo at
  all, NOT part of the rolled roster below, never something a player
  could "miss." Susanoo's own real combat mechanics are not designed
  yet (a separate, later follow-up).
- On unlock, exactly 2 more techniques are rolled from
  TECHNIQUE_ROSTER below, one "per eye" -- confirmed directly to be
  2 INDEPENDENT rolls, guaranteed different from each other (no
  player ever gets the same technique twice). The two rolled
  techniques are also confirmed to be fully independent of each
  other -- no combined/synergy effect between a player's own two.
- The roster is deliberately, explicitly UNEVEN in power (some
  techniques are simply better than others, confirmed directly,
  matching how canon itself is uneven -- Amaterasu is stronger than
  most other Mangekyo abilities). Relative power is never documented
  anywhere in help -- confirmed directly this should be discovered
  through play, not looked up.
- Both rolled techniques (and Susanoo) are permanent once unlocked --
  confirmed directly there is NO mechanic yet to lose an eye/technique,
  though this is explicitly left open as a possible future addition.
- The roster is designed to GROW over time -- confirmed directly to
  start building now with only 6 fully-speced techniques rather than
  waiting to fill out a full 10, since nothing about the system
  itself needs to change to add an 11th, 12th, etc. later.
- Kotoamatsukami was explicitly DESIGNED then DROPPED, per direct
  confirmation ("i think we should remove this one its very hard to
  come up with usefull realistic effectd") -- do not re-add without a
  genuinely new, concrete mechanical proposal being confirmed first.

Each entry's own real mechanical spec, confirmed directly across the
design conversation:

- Tsukuyomi: casting immediately moves BOTH caster and target into a
  shared, real torture room (in one action, unlike Kamui's own
  2-step entry). A real random number from 5-10 is rolled at the
  start, hidden from both players, setting how many of the caster's
  own actions the technique lasts. The target is frozen the whole
  time -- only the caster acts, choosing each round from 5 real
  commands (see TSUKUYOMI_COMMANDS below). When the countdown runs
  out (or an early-end command triggers), both players return, and
  the target is left with very little HP and no stamina.

- Amaterasu: casting inflicts a real, PERMANENT burn on the target
  (40-60 dmg/tick, no duration -- burns forever) AND simultaneously
  sets the room they're standing in on fire too, burning everyone in
  it except the caster (25-40 dmg/tick). If the burned target
  leaves, their own burn travels with them; the room's fire stays
  behind (confirmed directly) and would burn anyone else who walks
  in. The room-fire lasts a real 30 minutes from the cast, or until
  sealed early. The ONLY way to remove either burn (player or room)
  is a real, scroll-taught sealing jutsu (not yet built) -- no other
  cure works, confirmed directly.

- Kamui: 3 SEPARATE real jutsu (confirmed directly), not one combined
  ability:
    1. Pocket Dimension (transfer) -- a real, deliberate 2-step cast:
       casting on a TARGET sends them alone to a real, dedicated room
       with no normal exits; the caster then casts it again on
       THEMSELVES to join. No chakra cost to enter. Once the caster
       is inside, real upkeep drains 15 chakra/tick with just the
       caster present, 35 chakra/tick once the target is also there.
       Ends when the caster leaves, or chakra runs out.
    2. Intangibility (defense) -- a real, guaranteed 3-round window
       where all incoming attacks miss. 60-second real cooldown.
    3. Limb Removal (offense) -- a long, interruptible 6-8 second
       real cast; if it lands, a one-time burst of roughly 1200-1600
       damage.

- Izanagi: a real, deliberate stance the player must proactively
  activate (confirmed directly: NOT automatic) -- stays active
  indefinitely until triggered, with no separate expiration of its
  own. The very next time the player's HP would hit 0 while active,
  it's instead restored to FULL HP, and the stance is consumed. A
  real, once-per-real-day cooldown after use.

- Izanami: casting traps a target in a real, recursive loop. A real
  random number from 1-25 is set ONCE at the start and never changes
  (confirmed directly -- not re-rolled each round, so a target could
  narrow it down over repeated guesses). Each real round, the target
  gets exactly one guess; a correct guess ends it immediately. The
  target cannot be attacked by anyone while looped. No cap on
  duration at all -- confirmed directly it only ends on a correct
  guess, however long that takes. The caster is completely free to
  act normally elsewhere while it's running (confirmed directly --
  not tied up or restricted in any way).

- Kekkei no Me ("Barrier Eye"): casting transforms the CURRENT room
  in place (confirmed directly -- no one moves anywhere, unlike
  Kamui/Tsukuyomi's shared rooms). The room's element becomes
  whatever the caster's own real, current chakra nature already is.
  The caster gets a real +50% damage bonus to their own jutsu
  matching that element while inside. Everyone else in the room
  (the caster is exempt) takes 12-20 chakra AND 12-20 stamina drain
  per tick. Lasts a real 90 seconds.
"""

import random

TECHNIQUE_ROSTER = {
    "tsukuyomi": {
        "display_name": "Tsukuyomi",
        "description": "Traps a target in a shared torture room, frozen and defenseless, while the caster inflicts a real, randomized ordeal.",
    },
    "amaterasu": {
        "display_name": "Amaterasu",
        "description": "Sets a target ablaze with real, permanent black flame that never goes out on its own -- and the room around them catches fire too.",
    },
    "kamui": {
        "display_name": "Kamui",
        "description": "A real trio of space-time techniques: banish a target to a pocket dimension, become briefly intangible, or unleash a devastating, slow-cast strike.",
    },
    "izanagi": {
        "display_name": "Izanagi",
        "description": "A real, deliberate stance that rewrites fate itself -- the next fatal blow while active is undone entirely, restoring full health.",
    },
    "izanami": {
        "display_name": "Izanami",
        "description": "Traps a target in a real, recursive loop they can only escape by guessing a fixed, hidden number.",
    },
    "kekkei_no_me": {
        "display_name": "Kekkei no Me",
        "description": "Transforms the current room into the caster's own elemental territory, empowering their jutsu while draining everyone else's chakra and stamina.",
    },
}

# The real, confirmed 5 torture commands available during a Tsukuyomi
# cast, each its own distinct real effect (see docstring above).
TSUKUYOMI_COMMANDS = {
    "stab": {"countdown_cost": 1, "hp_damage": (30, 50)},
    "impale": {"countdown_cost": 2, "hp_damage": (60, 90)},
    "burn": {"countdown_cost": 1, "hp_damage": (20, 40), "stamina_drain": (30, 50)},
    "crush": {"countdown_cost": 1, "hp_damage": (80, 120), "early_end_chance_pct": 25},
    "unmake": {"countdown_cost": 1, "hp_damage": (0, 0), "stamina_drain": (40, 60), "chakra_drain": (40, 60)},
}

# Confirmed real numbers (Section 140 design conversation).
AMATERASU_PLAYER_BURN_PER_TICK = (40, 60)
AMATERASU_ROOM_BURN_PER_TICK = (25, 40)
AMATERASU_ROOM_FIRE_DURATION_SECONDS = 30 * 60

KAMUI_UPKEEP_ALONE_PER_TICK = 15
KAMUI_UPKEEP_WITH_TARGET_PER_TICK = 35
KAMUI_INTANGIBILITY_ROUNDS = 3
KAMUI_INTANGIBILITY_COOLDOWN_SECONDS = 60.0
KAMUI_LIMB_REMOVAL_CAST_SECONDS = (6.0, 8.0)
KAMUI_LIMB_REMOVAL_DAMAGE = (1200, 1600)

IZANAGI_COOLDOWN_SECONDS = 24 * 60 * 60  # once per real day, confirmed directly

IZANAMI_NUMBER_MIN = 1
IZANAMI_NUMBER_MAX = 25

KEKKEI_NO_ME_ELEMENT_DAMAGE_BONUS_PCT = 50
KEKKEI_NO_ME_CHAKRA_DRAIN_PER_TICK = (12, 20)
KEKKEI_NO_ME_STAMINA_DRAIN_PER_TICK = (12, 20)
KEKKEI_NO_ME_DURATION_SECONDS = 90.0


def roll_two_eye_techniques() -> tuple:
    """The real, confirmed roll: 2 independent picks from
    TECHNIQUE_ROSTER, guaranteed different from each other. Returns
    a real (eye_1_key, eye_2_key) tuple. Susanoo is deliberately never
    part of this roll -- it's universal, checked via
    player.bloodline_mangekyo alone."""
    keys = list(TECHNIQUE_ROSTER.keys())
    return tuple(random.sample(keys, 2))
