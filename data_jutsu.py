"""
Jutsu data table.

Every player gets exactly the same starting kit regardless of primary
class: one active jutsu per combat category (Ninjutsu/Taijutsu/Genjutsu/
Bukijutsu) plus a passive (see data_passives.py). class_requirement is
kept on each entry for CATEGORIZATION only (prac's category grouping,
and dispatch_line's "Taijutsu/Bukijutsu can be used by bare name" rule)
-- it is NOT an access gate anymore; combat.use_jutsu no longer checks
it, since every player knows all four jutsu regardless of their chosen
class.

There is no level-gated unlock tier system anymore (Section 13's
tiered progression is retired in favor of "everyone starts with
everything") -- these are all level_requirement 1.
"""

# damage is (min, max). effect is an optional status-effect key applied
# to the target (see status_effects.py).
# Confirmed design: EVERY jutsu and weapon skill can only be
# practiced up to DEFAULT_PRACTICE_CAP_PERCENT (50%) -- past that,
# only actual usage in combat (see combat.tick_usage_growth and
# commands.cmd_practice) raises it further, all the way to its own
# real ceiling of 100%. PRACTICE_CAP_PERCENT holds exceptions to that
# universal default -- currently just Shadow Clone Jutsu, which keeps
# its own harder, lower 20% cap (a genuine Kage-tier technique,
# confirmed as a deliberate exception before the universal 50% cap
# was introduced) rather than being silently raised to the new
# default.
DEFAULT_PRACTICE_CAP_PERCENT = 50

PRACTICE_CAP_PERCENT = {
    "Shadow Clone Jutsu": 20,
    "Handsigns": 1,  # confirmed design ("1% non practiceable") -- see data_handsigns.py
}


JUTSU = {
    "shadow shuriken technique": {
        "jutsu_id": "ninjutsu_starter", "display_name": "Shadow Shuriken Technique",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 10, "stamina_cost": 0, "cooldown": 2.0,
        "damage": (12, 20), "damage_type": "chakra", "effect": None,
        "tier": 1, "element": "none",
    },
    "dynamic entry": {
        "jutsu_id": "taijutsu_starter", "display_name": "Dynamic Entry",
        "class_requirement": "taijutsu", "level_requirement": 1,
        "chakra_cost": 0, "stamina_cost": 6, "cooldown": 2.0,
        "damage": (10, 18), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none",
    },
    "demonic illusion hell viewing technique": {
        "jutsu_id": "genjutsu_starter", "display_name": "Demonic Illusion: Hell Viewing Technique",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 12, "stamina_cost": 0, "cooldown": 3.0,
        "damage": (8, 16), "damage_type": "mental", "effect": "frightened",
        "tier": 1, "element": "none",
    },
    "narakumi": {
        "jutsu_id": "genjutsu_narakumi", "display_name": "Narakumi",
        "class_requirement": "genjutsu", "level_requirement": 15,
        "chakra_cost": 22, "stamina_cost": 0, "cooldown": 4.0,
        "damage": (20, 36), "damage_type": "mental", "effect": "narakumi", "effect_chance_pct": 50,
        "tier": 2, "element": "none",
    },
    "shadow clone jutsu": {
        "jutsu_id": "ninjutsu_shadow_clone", "display_name": "Shadow Clone Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 30,
        "chakra_cost": 50, "stamina_cost": 0, "cooldown": 10.0,
        "jutsu_type": "summon", "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none",
        # No damage roll at all -- this jutsu summons a clone (or
        # clones) that fight alongside the player each round instead
        # of dealing damage itself. See combat.use_shadow_clone_jutsu.
    },
    "track": {
        "jutsu_id": "general_track", "display_name": "Track",
        "class_requirement": "general", "level_requirement": 30,
        "chakra_cost": 15, "stamina_cost": 0, "cooldown": 5.0,
        "jutsu_type": "track", "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none",
        # No damage roll at all -- this jutsu begins a real, ongoing
        # tracking session (see tracking.py) that autonomously walks
        # the caster toward a chosen mob or player, one room per real
        # pulse, rather than resolving anything in a single moment.
        # "general" class_requirement per direct confirmation
        # ("Track can only be learned from a scroll by any class" ->
        # confirmed display category: "General Skills").
    },
    "sealing jutsu": {
        "jutsu_id": "general_sealing_jutsu", "display_name": "Sealing Jutsu",
        "class_requirement": "general", "level_requirement": 100,
        "chakra_cost": 100, "stamina_cost": 0, "cooldown": 0.0,
        "jutsu_type": "sealing", "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # No damage roll at all -- per direct request/confirmation
        # (Section 127 continued): cast on a Tailed Beast already at
        # 0 HP (see combat.handle_mob_defeat's own real "downed,
        # awaiting sealing" state) to seal it into the caster instead
        # of an ordinary kill. Genuinely a real, deliberate SECOND
        # action, not automatic -- confirmed directly the player must
        # already have brought the beast down through ordinary
        # combat first. "general" class_requirement, matching Track's
        # own real precedent for a scroll-taught technique open to
        # any class.
    },
    "release jutsu": {
        "jutsu_id": "general_release_jutsu", "display_name": "Release Jutsu",
        "class_requirement": "general", "level_requirement": 100,
        "chakra_cost": 100, "stamina_cost": 0, "cooldown": 0.0,
        "jutsu_type": "beast_release", "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # No damage roll at all -- a genuinely SEPARATE jutsu from
        # Sealing Jutsu, confirmed directly (its own scroll, its own
        # level requirement, same 100 here). Extracts a Tailed Beast
        # from another player who was just defeated in real PvP
        # combat, per direct confirmation, putting the beast back
        # into the wild (a fresh real release, same as 'release
        # beast' -- full roaming schedule and despawn timer) rather
        # than killing the former jinchuriki's own character.
    },
    "tailed beast bomb": {
        "jutsu_id": "general_tailed_beast_bomb", "display_name": "Tailed Beast Bomb",
        "class_requirement": "general", "level_requirement": 100,
        "chakra_cost": 150, "stamina_cost": 0, "cooldown": 30.0,
        "jutsu_type": "beast_bomb", "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # No fixed damage tuple -- per direct confirmation (Section
        # 127 continued): "with its own real damage scaling by tail
        # count too (a 9-tail's Bomb hits much harder than a
        # 1-tail's)." The real amount is computed live from the
        # caster's own specific beast (see tailed_beasts.
        # bomb_damage), not a static range like an ordinary jutsu.
        # Only usable while Tailed Beast Mode is genuinely toggled on
        # (confirmed directly), refused otherwise.
    },
    "illusion walk": {
        "jutsu_id": "genjutsu_illusion_walk", "display_name": "Illusion Walk",
        "class_requirement": "genjutsu", "level_requirement": 20,
        "chakra_cost": 12, "stamina_cost": 0, "cooldown": 3.0,
        "jutsu_type": "illusion_walk", "damage": None, "damage_type": None, "effect": None,
        "tier": 1, "element": "none",
        # No damage roll at all -- a pure illusion/control effect, per
        # direct request/confirmation (Section 120): the victim's own
        # real room_vnum never changes at all while this is active;
        # only what they personally SEE when they try to move is
        # faked (see combat.py's own illusion_walk handling). Genuinely
        # player-only -- confirmed directly, since a mob has no real
        # output stream of its own to fake.
    },
    "throw shuriken": {
        "jutsu_id": "bukijutsu_starter", "display_name": "Throw Shuriken",
        "class_requirement": "bukijutsu", "level_requirement": 1,
        "chakra_cost": 0, "stamina_cost": 6, "cooldown": 2.0,
        "damage": (10, 18), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none", "jutsu_type": "thrown",
    },
    "throw kunai": {
        "jutsu_id": "bukijutsu_throw_kunai", "display_name": "Throw Kunai",
        "class_requirement": "bukijutsu", "level_requirement": 15,
        "chakra_cost": 0, "stamina_cost": 10, "cooldown": 2.5,
        "damage": (18, 30), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none", "jutsu_type": "thrown", "requires_item": "kunai",
        # Genuinely consumes a real kunai from inventory and drops it
        # on the ground where thrown -- see combat.use_jutsu's
        # requires_item handling. Confirmed: consumed/dropped
        # regardless of hit or miss, since a thrown kunai leaves your
        # hand either way.
    },
    "counter kunai": {
        "jutsu_id": "bukijutsu_counter_kunai", "display_name": "Counter Kunai",
        "class_requirement": "bukijutsu", "level_requirement": 25,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none", "jutsu_type": "counter",
        # A genuinely passive jutsu, never cast directly -- confirmed
        # design ("passively block another's kunai throw if you have
        # one in your inventory and it will consume the kunai").
        # Checked automatically whenever an incoming attack is
        # jutsu_type "thrown" (see combat._try_counter_kunai), not
        # through 'perform' at all.
    },
    "silent genjutsu": {
        "jutsu_id": "genjutsu_silent_passive", "display_name": "Silent Genjutsu",
        "class_requirement": "genjutsu", "level_requirement": 75,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 3, "element": "none", "jutsu_type": "silent_genjutsu_passive",
        # A genuinely passive jutsu, never cast directly -- per direct
        # request/confirmation (Section 122): "removes the requirement
        # to have perform before the genjutsu name your casting and
        # the jutsu is instant with no handsigns required...it also
        # at 100% mastery the other player won't see the jutsu name
        # being cast." Confirmed directly: applies to EVERY Genjutsu
        # the player already knows, always on once learned (no
        # toggle), regardless of target (mob or player -- that part
        # is about the caster's own casting style). The 100%-mastery
        # message-hiding is genuinely PvP-only and one-directional --
        # the CASTER always sees their own full normal message
        # regardless of mastery; only the TARGET's own message is
        # affected. Checked automatically in commands.dispatch (for
        # the bare-name/no-perform part) and combat.begin_pending_cast/
        # use_jutsu_on_player (for the instant-cast and message-hiding
        # parts), not through 'perform' itself.
    },
    "explosive tag kunai": {
        "jutsu_id": "bukijutsu_explosive_tag_kunai", "display_name": "Explosive Tag Kunai",
        "class_requirement": "bukijutsu", "level_requirement": 30,
        "chakra_cost": 19, "stamina_cost": 12, "cooldown": 6.0,
        "damage": (18, 30), "damage_type": "physical", "effect": None,
        "tier": 2, "element": "none", "jutsu_type": "thrown", "requires_item": "kunai",
        "explosive_chance_pct": 30, "explosive_damage": (50, 80),
        # Confirmed design: a SINGLE roll picks EITHER the normal
        # kunai damage range above OR the bigger explosive_damage
        # range -- never both on the same throw. Same requires_item
        # consumption as Throw Kunai (this is thematically the same
        # basic kunai, just occasionally rigged to detonate).
    },
    "fireball jutsu": {
        "jutsu_id": "ninjutsu_fireball", "display_name": "Fireball Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "burning", "effect_chance_pct": 40,
        "tier": 2, "element": "fire",
        # HARD elemental gate (Section 85, confirmed: "a person cant
        # cast jutsu that is not theire element") -- only castable by
        # a player whose chakra_nature (primary OR secondary) is
        # genuinely "fire", checked in combat._can_use_jutsu. A 40%
        # chance to also inflict Burning (HP damage over time, a
        # genuine standalone per-round timer -- see
        # combat.tick_effects_pulse/tick_all_mob_effects).
    },
    "water dragon jutsu": {
        "jutsu_id": "ninjutsu_water_dragon", "display_name": "Water Dragon Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "drained", "effect_chance_pct": 40,
        "tier": 2, "element": "water",
        # Same hard gate as Fireball Jutsu above, requiring "water".
        # 40% chance to inflict Drained (chakra loss over time --
        # confirmed design distinct from Off Balance's stamina drain,
        # even though both reduce a resource, per direct request to
        # differentiate Water from Wind).
    },
    "wind blade jutsu": {
        "jutsu_id": "ninjutsu_wind_blade", "display_name": "Wind Blade Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "off_balance", "effect_chance_pct": 40,
        "tier": 2, "element": "wind",
        # Same hard gate, requiring "wind". 40% chance to inflict Off
        # Balance (stamina loss over time -- confirmed flavor:
        # "knocked off balance", explicitly NOT a dodge/accuracy
        # effect, explicitly NOT the same mechanic as Water's chakra
        # drain despite the surface-level similarity).
    },
    "lightning strike jutsu": {
        "jutsu_id": "ninjutsu_lightning_strike", "display_name": "Lightning Strike Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 28, "stamina_cost": 0, "cooldown": 6.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "paralyzed", "effect_chance_pct": 30,
        "tier": 2, "element": "lightning",
        # Same hard gate, requiring "lightning". A genuinely lower 30%
        # chance than the other 3 (12/18/-- wait, matches their 40%
        # actually not applicable) -- Paralyzed blocks the target's
        # entire next action outright (reusing the same blocks_action
        # mechanic already proven by genjutsu_locked/stunned), a
        # stronger effect than a damage/resource drain over time, so
        # it's intentionally rarer to trigger.
    },
    "earth wall crusher": {
        "jutsu_id": "ninjutsu_earth_wall_crusher", "display_name": "Earth Wall Crusher",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (40, 64), "damage_type": "chakra", "effect": None,
        "tier": 2, "element": "earth",
        # Same hard gate, requiring "earth". Confirmed design: Earth
        # deliberately carries NO status effect at all -- instead, its
        # own damage range (20-32) is noticeably higher than the
        # other 4 elemental jutsu above (12-20), reflecting "raw,
        # upfront damage" per direct confirmation, rather than a
        # lingering effect.
    },
    "tsukuyomi": {
        "jutsu_id": "mangekyo_tsukuyomi", "display_name": "Tsukuyomi",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 65, "stamina_cost": 0, "cooldown": 90.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): casting immediately
        # moves BOTH caster and target into a shared, real torture
        # room (mangekyo.open_tsukuyomi), unlike Kamui's own 2-step
        # entry. A real random number from 5-10 (hidden from both
        # players) sets how many of the caster's own real actions the
        # technique lasts -- see the 5 real torture commands (stab/
        # impale/burn/crush/unmake) in commands.py's own cmd_stab
        # etc.
        "jutsu_type": "mangekyo_tsukuyomi",
        "kkg_gate": "mangekyo_technique",
    },
    "amaterasu": {
        "jutsu_id": "mangekyo_amaterasu", "display_name": "Amaterasu",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 60, "stamina_cost": 0, "cooldown": 30.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): gated by genuinely
        # having rolled Amaterasu as one of the player's own 2 real
        # Mangekyo eye techniques, checked via combat._can_use_jutsu's
        # own real kkg_gate handling (see "mangekyo_technique" there).
        # No fixed real damage tuple -- the actual effect (a genuinely
        # permanent player-burn AND a real, separate room-fire) is
        # applied directly by commands.py's own dispatch, see its
        # "mangekyo_amaterasu" jutsu_type branch.
        "jutsu_type": "mangekyo_amaterasu",
        "kkg_gate": "mangekyo_technique",
    },
    "kamui pocket dimension": {
        "jutsu_id": "mangekyo_kamui_pocket_dimension", "display_name": "Kamui: Pocket Dimension",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): a real, deliberate
        # 2-step cast -- casting on a TARGET opens the dimension and
        # sends them alone; casting again on ONESELF joins them there.
        # No chakra cost to enter (confirmed directly) -- real upkeep
        # only starts once the caster is actually inside (see
        # mangekyo.process_kamui_pocket_dimensions). Shares
        # mangekyo_roster_key with the other 2 real Kamui jutsu below,
        # since all 3 are unlocked by a single real roll of "kamui".
        "jutsu_type": "mangekyo_kamui_pocket_dimension",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kamui",
    },
    "kamui intangibility": {
        "jutsu_id": "mangekyo_kamui_intangibility", "display_name": "Kamui: Intangibility",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 40, "stamina_cost": 0, "cooldown": 60.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): a real, guaranteed
        # 3-round window (data_mangekyo.KAMUI_INTANGIBILITY_ROUNDS)
        # where every incoming attack simply misses. Applied via the
        # real kamui_intangibility_rounds_left counter on Player,
        # checked at every real hit-roll site.
        "jutsu_type": "mangekyo_kamui_intangibility",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kamui",
    },
    "kamui limb removal": {
        "jutsu_id": "mangekyo_kamui_limb_removal", "display_name": "Kamui: Limb Removal",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 80, "stamina_cost": 0, "cooldown": 45.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): a long, real,
        # interruptible 6-8 second cast (data_mangekyo.
        # KAMUI_LIMB_REMOVAL_CAST_SECONDS); if it lands, a one-time
        # burst of roughly 1200-1600 damage (data_mangekyo.
        # KAMUI_LIMB_REMOVAL_DAMAGE). Uses the same real delayed-cast
        # system as Amaterasu/Illusion Walk, just with a genuinely
        # longer, randomized real delay instead of the usual
        # Handsigns-based one.
        "jutsu_type": "mangekyo_kamui_limb_removal",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kamui",
    },
    "izanami": {
        "jutsu_id": "mangekyo_izanami", "display_name": "Izanami",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 70, "stamina_cost": 0, "cooldown": 60.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): traps a target in a
        # real, recursive loop -- a fixed real number from 1-25, set
        # once and never re-rolled, that the target must correctly
        # guess (one real guess per round) to escape. Cannot be
        # attacked by anyone while looped, confirmed directly. No cap
        # on duration at all -- only ends on a correct guess. The
        # CASTER is completely free to act normally elsewhere while
        # it's running, confirmed directly.
        "jutsu_type": "mangekyo_izanami",
        "kkg_gate": "mangekyo_technique",
    },
    "kekkei no me": {
        "jutsu_id": "mangekyo_kekkei_no_me", "display_name": "Kekkei no Me",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 50, "stamina_cost": 0, "cooldown": 120.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): transforms the
        # CURRENT room in place (no one moves) into the caster's own
        # real, active chakra-nature element. The caster gets a real
        # +50% damage bonus to their own matching-element jutsu while
        # inside; everyone else takes real chakra AND stamina drain
        # per tick. Lasts a real 90 seconds.
        "jutsu_type": "mangekyo_kekkei_no_me",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kekkei_no_me",
    },
}

# The universal starting kit -- every player gets exactly these,
# regardless of class. Used by both session.py's chargen AND
# leveling.sync_universal_skills() (the login update-check), so the two
# can never drift apart -- add a jutsu here once and both paths pick it
# up automatically.
UNIVERSAL_STARTING_SKILLS = [
    "Shadow Shuriken Technique",
    "Dynamic Entry",
    "Demonic Illusion: Hell Viewing Technique",
    "Throw Shuriken",
    "Strong Fist Style",
    "Anki",
]

# Examine (commands.cmd_examine) is NOT part of the universal
# starting kit -- whether a player has it at all is gated by character
# LEVEL, not granted for free at creation. Unlocked automatically the
# first time a player reaches this level (leveling.py's level-up
# rewards, and leveling.sync_universal_skills() for a returning
# high-level player who predates this or never logged in to trigger
# the level-up grant).
APPRAISAL_LEVEL_REQUIREMENT = 20

# Multiple attacks per round, per explicit request. Each entry is
# (display_name, level_requirement, required_primary_class_or_None).
# Second/Third Attack are general -- any primary class gets them.
# Fourth/Fifth Attack are Bukijutsu-specific. All four are auto-granted
# the moment a qualifying character reaches the level (leveling.py's
# level-up rewards, and leveling.sync_universal_skills() for a
# returning high-level player), exactly the same mechanism as
# Examine above -- not taught by a scroll/teacher. Each is trainable
# via 'practice' afterward like any other skill; the % chance of that
# extra attack actually landing in a given combat round scales with
# proficiency (see combat.py's attack-count resolution), so a freshly
# -granted skill at 0% doesn't immediately double a character's damage
# output -- it has to be trained up first, same as everything else
# proficiency-gated in this game.
MULTI_ATTACK_SKILLS = [
    ("Second Attack", 25, None),
    ("Third Attack", 50, None),
    ("Fourth Attack", 75, "bukijutsu"),
    ("Fifth Attack", 90, "bukijutsu"),
]

# Renames of an existing skill's display name (old -> new). Empty for
# now -- exists so that if a jutsu is ever renamed, existing players'
# learned_skills/skill_proficiencies keys can be migrated automatically
# at login instead of silently going stale. See
# leveling.sync_universal_skills().
SKILL_RENAMES = {
    "Appraisal": "Examine",  # per direct request ("rename appraisal to examine like its command to use it")
}


# Confirmed design: "e" alone should never resolve to Explosive Tag
# Kunai -- a single letter is too easy to type by accident for an
# ability with real consequences (consumes a real inventory kunai, a
# genuine chance of a much bigger hit than intended). Every other
# jutsu's existing single-letter-or-more shorthand behavior is
# completely unaffected -- this is a targeted exception, not a
# general rule (confirmed directly rather than assumed either way).
MIN_MATCH_PREFIX_LENGTH = {
    "explosive tag kunai": 2,
}


def match_prefix(lower_words):
    """Match a jutsu from the given lowercased word list. Two things
    can happen, tried longest-input-first so the full name still works
    exactly as before:
      1. The player typed the FULL name (or more, e.g. followed by a
         target) -- the classic case, where the jutsu key is a prefix
         of what they typed.
      2. The player typed a SHORT keyword or partial name (e.g. 'demonic'
         for 'Demonic Illusion: Hell Viewing Technique', or 'shadow
         shuriken' for 'Shadow Shuriken Technique') -- what they typed
         is a prefix of the jutsu's full name instead. Tried from the
         longest plausible partial down to a single word, so a two-word
         partial like 'shadow shuriken' doesn't wrongly eat only 'shadow'
         and leave 'shuriken' to be misread as part of the target name.

    Returns (jutsu_key, word_count_consumed) or (None, 0).
    """
    joined = " ".join(lower_words)
    for key in sorted(JUTSU.keys(), key=lambda k: -len(k.split())):
        if joined == key or joined.startswith(key + " "):
            return key, len(key.split())

    max_jutsu_words = max((len(k.split()) for k in JUTSU), default=1)
    for length in range(min(max_jutsu_words, len(lower_words)), 0, -1):
        candidate = " ".join(lower_words[:length])
        matches = sorted(key for key in JUTSU if key.startswith(candidate))
        if len(matches) == 1:
            if len(candidate) < MIN_MATCH_PREFIX_LENGTH.get(matches[0], 1):
                # The only match exists, but the player's own typed
                # candidate is too short for THIS specific jutsu's own
                # confirmed minimum (e.g. "e" for Explosive Tag Kunai)
                # -- treat it as no match at all rather than accepting
                # a shorthand deliberately disallowed for this one.
                continue
            return matches[0], length
        if len(matches) > 1:
            # A genuine tie at this word-length -- e.g. "shadow" alone
            # now matches both "shadow clone jutsu" and "shadow
            # shuriken technique". Refuse to guess rather than pick one
            # arbitrarily; the caller reports "you don't know a jutsu
            # by that name" and the player can be more specific (e.g.
            # "shadow shuriken" or "shadow clone", both unambiguous).
            return None, 0

    return None, 0


def jutsu_for_class_at_level(class_name: str, level: int):
    """Return jutsu keys newly unlocked exactly at this level for this
    class, called from leveling.py on every level-up. Genuinely empty
    for the original starter jutsu (level_requirement 1 -- everyone
    already has those from character creation, before this function
    is ever called), but NOT a no-op overall: every jutsu added since
    with a real level_requirement above 1 (Shadow Clone Jutsu,
    Narakumi, Throw Kunai, Counter Kunai, Explosive Tag Kunai) is
    genuinely granted through this exact path the moment a matching-
    class player reaches the right level -- verified directly, not
    assumed."""
    return [
        key for key, data in JUTSU.items()
        if data["class_requirement"] == class_name and data["level_requirement"] == level
    ]


def all_jutsu_keys():
    """Every single jutsu in the whole table, no class or level filter
    at all -- used only for the staff bypass (see session.py's
    _enter_world), per confirmed design ("Immediately, regardless of
    level -- the moment an account is staff, their character has
    every jutsu from every class, even at level 1"). Deliberately
    different from all_unlocked_for_class, which still respects
    level_requirement -- this respects nothing at all."""
    return list(JUTSU.keys())


def all_unlocked_for_class(class_name: str, level: int):
    return [
        key for key, data in JUTSU.items()
        if data["class_requirement"] == class_name and data["level_requirement"] <= level
    ]
