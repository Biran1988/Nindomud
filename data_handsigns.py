"""
Hand signs (Section 91), per direct request/design conversation:

"add a level 20 skill called Handsigns thats extremly hard to master
and it at 1% non practiceable....add in a system of handsigns that
you do before performing a jutsu that match best you can with naruto
handsigns"

...then, on what Handsigns mastery should actually DO:

"lets put a lag time before doing jutsu while your casting so
mastery of handsigns will lowere that lag time and give it a real
naruto feel...also this will play into counter jutsu later because a
player can see their opponents handsigns and try to counter the
jutsu"

Confirmed design across several follow-ups:
- Handsigns has a practice CAP of 1% (essentially non-practiceable --
  one practice attempt already exceeds it), reusing the exact same
  mechanism as every other skill's own practice cap
  (data_jutsu.PRACTICE_CAP_PERCENT), just set drastically lower.
  Everything past 1% comes from actual usage (see
  combat.grow_skill_from_usage, called once per successful jutsu
  cast that used hand signs at all).
- Only Ninjutsu and Genjutsu jutsu use hand signs at all, matching
  canon -- Taijutsu and Bukijutsu techniques never did in the source
  material, and don't here either.
- Each jutsu has its OWN FIXED hand-sign sequence, confirmed directly
  rather than randomized per cast -- matching how a canon jutsu
  always uses the same signs in the same order every time.
- The 12 real canon hand signs (the zodiac set): Rat, Ox, Tiger,
  Hare, Dragon, Snake, Horse, Ram, Monkey, Rooster, Dog, Boar.
- A genuine real-time casting delay while performing the sequence --
  confirmed design: roughly 3-4 seconds at 0% Handsigns mastery,
  shrinking toward roughly 0.5-1 second at 100% -- during which the
  caster is genuinely locked in (confirmed: can't attack, move, or
  cast something else) until the jutsu resolves. The sequence itself
  is broadcast to everyone in the room as it's performed (confirmed
  design -- this is deliberate groundwork for a future counter-jutsu
  system, not built yet: "this will play into counter jutsu later
  because a player can see their opponents handsigns").
- Scope confirmed explicitly bounded for now to the delay + visible
  signs + Handsigns mastery shrinking the delay -- the actual
  counter-jutsu mechanic (one jutsu interrupting another) is a
  separate, later feature, not built here.
"""

HANDSIGNS_MIN_LEVEL = 20
HANDSIGNS_PRACTICE_CAP = 1  # confirmed design: "1% non practiceable"

# The 12 real canon hand signs (the zodiac set used throughout the
# source material for every jutsu with a shown sequence).
ALL_SIGNS = ["Rat", "Ox", "Tiger", "Hare", "Dragon", "Snake", "Horse", "Ram", "Monkey", "Rooster", "Dog", "Boar"]

# Confirmed design: only Ninjutsu/Genjutsu jutsu use hand signs at
# all. Each entry is a FIXED sequence for that jutsu -- matched to
# real canon sequences where a genuine canon counterpart exists
# (Fireball Jutsu's sequence here is the real one), and a reasonable,
# thematically-appropriate invented sequence for jutsu original to
# this MUD (everything else below).
JUTSU_HANDSIGNS = {
    "shadow shuriken technique": ["Dog", "Boar", "Ram"],
    "shadow clone jutsu": ["Ram", "Snake", "Tiger"],
    "fireball jutsu": ["Snake", "Ram", "Monkey", "Boar", "Horse", "Tiger"],  # the real canon sequence
    "water dragon jutsu": ["Ox", "Monkey", "Hare", "Boar", "Horse", "Rat", "Dragon"],
    "wind blade jutsu": ["Tiger", "Hare", "Dog"],
    "lightning strike jutsu": ["Ox", "Hare", "Monkey", "Boar"],
    "earth wall crusher": ["Snake", "Boar", "Dog", "Tiger"],
    "demonic illusion hell viewing technique": ["Ram", "Rat", "Boar"],
    "narakumi": ["Snake", "Ram", "Ox", "Tiger"],
    "illusion walk": ["Tiger", "Ram", "Ox"],
    "amaterasu": ["Tiger", "Snake", "Ram", "Boar"],
    "tsukuyomi": ["Snake", "Ram", "Ox"],
    "kamui pocket dimension": ["Ox", "Snake", "Dog"],
    "kamui intangibility": ["Rat", "Tiger"],
    "kamui limb removal": ["Snake", "Boar", "Ram", "Tiger", "Ox"],
    "izanami": ["Ram", "Snake", "Tiger", "Ox"],
    "kekkei no me": ["Ox", "Ram", "Tiger", "Snake", "Boar"],
}


def has_handsigns(jutsu: dict) -> bool:
    """Whether jutsu uses hand signs at all -- confirmed design:
    Ninjutsu and Genjutsu only, never Taijutsu or Bukijutsu. A
    genuinely passive jutsu (never cast directly at all -- checked by
    its own jutsu_type, e.g. "counter" or "silent_genjutsu_passive")
    never uses hand signs either, regardless of its class."""
    if jutsu.get("jutsu_type") in ("counter", "silent_genjutsu_passive", "ambush", "stance"):
        return False
    return jutsu.get("class_requirement") in ("ninjutsu", "genjutsu")


def sequence_for(jutsu_key: str) -> list:
    """The fixed hand-sign sequence for this jutsu, or an empty list
    if it genuinely has none registered (shouldn't happen for any
    jutsu where has_handsigns() is True, but never crashes either
    way)."""
    return JUTSU_HANDSIGNS.get(jutsu_key, [])


def casting_delay_seconds(handsigns_mastery_pct: int) -> float:
    """The real-time delay (confirmed design: "3-4 seconds at 0%
    mastery" shrinking toward "0.5-1 second at 100%") a player waits
    while performing a hand-sign sequence, based on their own current
    Handsigns proficiency. Linear interpolation between the two
    confirmed endpoints."""
    start, end = 3.5, 0.75
    pct = max(0, min(100, handsigns_mastery_pct)) / 100
    return start - (start - end) * pct
