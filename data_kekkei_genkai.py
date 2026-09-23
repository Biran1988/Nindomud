"""
Kekkei Genkai (Bloodline Limit) framework.

Builds ONLY the underlying architecture for bloodline inheritance,
hidden Potential/Talent, and awakening -- explicitly NOT skills,
combat abilities, mastery trees, or the awakening quest itself. All
of those are reserved for later, per the design brief this module was
built from. Future systems read a player's clan/bloodline_id/
bloodline_potential/bloodline_talent/bloodline_mastery fields (see
models.Player) and this module's helper functions; they don't need to
know how inheritance was originally rolled.

Core philosophy: a Kekkei Genkai should feel legendary. Not every
member of an eligible clan has one, and even among those who do, very
few reach real mastery -- see Potential vs Talent below. A player
WITHOUT a Kekkei Genkai must remain fully viable throughout the game;
bloodlines exist to add unique flavor and long-term progression, not
to make a player objectively stronger than one without.

Everything a future balance pass would touch lives in this one file,
data-driven rather than scattered through code:
  - KEKKEI_GENKAI: the bloodline catalog (display name, description).
  - CLAN_INHERITANCE: clan -> {kkg_id: chance 0.0-1.0} -- which
    clan(s) can inherit which bloodline(s), and how likely each is. A
    clan absent from this dict, or mapped to an empty dict, simply
    has zero bloodline potential at all (true of most clans).

Potential vs Talent (both 1-100, rolled once, only for a character
that actually inherits a bloodline):
  - Potential is the ceiling -- the maximum mastery a character could
    ever reach, no matter how much they train.
  - Talent is the SLOPE -- learning speed, mastery speed, training
    efficiency. It does NOT raise the ceiling; it only changes how
    quickly a character climbs toward whatever ceiling Potential set.
  A character can be high-Potential/low-Talent (a slow-blooming
  prodigy who eventually surpasses almost everyone), low-Potential/
  high-Talent (fast early progress that caps out lower), or -- rarely
  -- high in both (an exceptional prodigy).

SECURITY: whether a player has a bloodline at all, and their
Potential/Talent/awakened state, must stay server-side only until a
future Level 50 awakening quest (not built yet -- this framework only
supports it) explicitly reveals the result to that specific player.
No NPC hint, no passive effect, no ability, no stat difference, and no
function in this module ever sends text to a player -- that's a
deliberate constraint, not an oversight, so no future caller can leak
a hidden value by copy-pasting a "helpful" status line from here.
Administrative visibility into these values is a separate, explicit
carve-out for staff-only debug/testing tools (see commands.cmd_bloodstat/
cmd_bloodset), gated the same way editing any other player's data is.
"""

import random

# clan_key -> {kekkei_genkai_id: inheritance chance, 0.0-1.0}. A clan
# not listed here (most of them) has zero bloodline potential.
# Centralized here, not scattered in logic, so balancing never
# requires touching code -- per explicit request. Raised to a flat
# 25% across every eligible clan in a later follow-up request (was
# 5-8%, varying per clan). Matches the specific clan -> bloodline
# examples named in the design brief this was built from; every clan
# key here already exists in data_clans.CLANS_BY_VILLAGE.
CLAN_INHERITANCE = {
    "uchiha": {"sharingan": 0.25},
    "hyuga": {"byakugan": 0.25},
    "kaguya": {"shikotsumyaku": 0.25},
    "yuki": {"ice_release": 0.25},
    "hozuki": {"hydrification": 0.25},
}

KEKKEI_GENKAI = {
    "sharingan": {
        "display_name": "Sharingan",
        "description": "The Uchiha's famed hereditary eye, said to perceive what others cannot.",
    },
    "byakugan": {
        "display_name": "Byakugan",
        "description": "The Hyuga's all-seeing eye, said to pierce flesh and distance alike.",
    },
    "shikotsumyaku": {
        "display_name": "Shikotsumyaku",
        "description": "The Kaguya's Dead Bone Pulse, letting the body's own skeleton become a weapon.",
    },
    "ice_release": {
        "display_name": "Ice Release",
        "description": "The Yuki clan's rare kekkei genkai, fusing wind and water into ice.",
    },
    "hydrification": {
        "display_name": "Hydrification",
        "description": "The Hozuki's fluid physiology, said to make their bodies as yielding as water.",
    },
}


def eligible_kkg_for_clan(clan: str) -> dict:
    """The kekkei genkai a given clan has ANY chance of inheriting,
    with their individual chances -- empty for the vast majority of
    clans, which carry no bloodline potential at all."""
    return CLAN_INHERITANCE.get(clan, {})


def roll_inheritance(clan: str) -> dict:
    """Secretly resolves whether a freshly created character inherits
    their clan's kekkei genkai, and their hidden Potential/Talent if
    so. Called exactly once, at character creation (session.py),
    never re-rolled afterward.

    SECURITY: this function only returns values -- storing them on the
    player and never surfacing them until a future awakening quest is
    entirely the caller's responsibility (see this module's own
    docstring for the full reasoning).

    Returns {"bloodline_id": str|None, "potential": int, "talent":
    int} -- potential/talent are 0 (not a 1-100 roll) when
    bloodline_id is None, since an absent bloodline has no ceiling or
    learning speed to speak of."""
    candidates = eligible_kkg_for_clan(clan)
    for kkg_id, chance in candidates.items():
        if random.random() < chance:
            return {
                "bloodline_id": kkg_id,
                "potential": random.randint(1, 100),
                "talent": random.randint(1, 100),
            }
    return {"bloodline_id": None, "potential": 0, "talent": 0}


def attempt_awaken(player) -> dict:
    """The actual mechanism behind bloodline awakening -- called
    directly by attempt_automatic_awakening below (the real, live
    "first quest", per Section 112) once its own chance roll and
    level gate succeed, and also reachable directly by staff via
    commands.cmd_bloodset/cmd_awaken, for testing or a manual grant.
    Resolves whether the player has a kekkei genkai at all and, if so,
    flips it to awakened -- the only place bloodline_awakened is ever
    set True. Idempotent: calling this again on an already-awakened
    bloodline just reports the existing state rather than re-granting
    or re-rolling anything.

    Sharingan-specific, per explicit request: the first awakening
    grants exactly 1 tomoe (player.bloodline_tomoe). Every tomoe past
    the first is earned through real, slow mastery gain during actual
    combat use instead (see tick_mastery_gain/tomoe_for_mastery below)
    -- this function only ever grants the first one, regardless of how
    many times it's called. The other 4 bloodlines have no
    tomoe-equivalent concept and are unaffected; bloodline_tomoe stays
    0 for them.

    Returns {"has_bloodline": bool, "kekkei_genkai": str|None,
    "already_awakened": bool} -- enough for a caller to build its own
    player-facing narration around; this function itself never sends
    text to anyone."""
    if not player.bloodline_id:
        return {"has_bloodline": False, "kekkei_genkai": None, "already_awakened": False}
    already = player.bloodline_awakened
    player.bloodline_awakened = True
    if player.bloodline_id == "sharingan" and player.bloodline_tomoe == 0:
        player.bloodline_tomoe = 1
    return {
        "has_bloodline": True,
        "kekkei_genkai": player.bloodline_id,
        "already_awakened": already,
    }


AUTOMATIC_AWAKENING_LEVEL = 50  # matches the design notes' own long-standing "Level 50" framing
AUTOMATIC_AWAKENING_CHANCE_PER_ROUND = 1 / 300  # small and rare -- a genuine surprise, not something to grind for

def attempt_automatic_awakening(player) -> dict:
    """"The first quest" -- the real, live, automatic version of
    bloodline awakening, per direct request/confirmation (Section
    112: "turn the sharingan unlock quest into something that is
    automatic that has a chance of awakening with a message showing
    it was awakened globally this is the first quest not the
    second...it will akwaken of course still at the level limit").

    Confirmed design: rolled ONLY during an actual combat round (not
    the idle world-pulse, and not on level-up) -- see combat.py's own
    tick_automatic_bloodline_awakening, called from both the PvE and
    PvP per-round tick chains, the same place tick_sharingan_upkeep/
    tick_sharingan_mastery_gain already hook in. Applies to ALL 5
    kekkei genkai, not just Sharingan, per direct confirmation ("All
    5 bloodlines -- any eligible player... gets the same automatic
    in-combat chance, regardless of which one they have") -- this
    function has no Sharingan-specific logic of its own at all; the
    Sharingan-specific "first tomoe" grant already lives inside
    attempt_awaken, which this calls into once eligibility and the
    roll both succeed.

    A player is eligible only if they genuinely have a real bloodline
    (bloodline_id set -- the vast majority of players have none at
    all and this returns immediately, no roll spent), are at least
    AUTOMATIC_AWAKENING_LEVEL, and aren't already awakened. Silent
    (no roll, no state change) for anyone not eligible, so calling
    this every combat round for every player in the game is cheap and
    harmless for the common case.

    Returns the same dict attempt_awaken returns, plus "rolled": bool
    (True only if a genuine chance roll actually happened this call)
    and "awakened_this_call": bool (True only if THIS call is the one
    that flipped it, as opposed to it already having been awakened
    some other way) -- callers use "awakened_this_call" to decide
    whether to narrate/announce anything at all."""
    if not player.bloodline_id or player.bloodline_awakened or player.level < AUTOMATIC_AWAKENING_LEVEL:
        return {"has_bloodline": bool(player.bloodline_id), "kekkei_genkai": player.bloodline_id,
                "already_awakened": player.bloodline_awakened, "rolled": False, "awakened_this_call": False}

    if random.random() >= AUTOMATIC_AWAKENING_CHANCE_PER_ROUND:
        return {"has_bloodline": True, "kekkei_genkai": player.bloodline_id,
                "already_awakened": False, "rolled": True, "awakened_this_call": False}

    result = attempt_awaken(player)
    result["rolled"] = True
    result["awakened_this_call"] = not result["already_awakened"]
    return result


# --- Sharingan mastery / tomoe progression ---
# Per direct follow-up request ("let's do the bloodline mastery route
# as a player uses the kkgk mastery goals up very slowly dependent on
# talent numbers") and design confirmation ("sharingan has many levels
# maxing out with 3 tamoe in each eye before a special quest unlocks
# the next stage but this is only for users 90% mastery or higher. So
# spread the tamoe over the mastery level evenly.").
#
# 2 eyes x 3 tomoe each = 6 total tomoe. Tomoe 1 is the existing,
# separate instant grant on first awakening (see attempt_awaken above)
# -- everything from tomoe 2 onward is earned here instead, through
# real, slow mastery gain during actual combat use. The remaining 5
# tomoe (2 through 6) are spread EVENLY across the player's own
# mastery range: 5 equal 20%-wide bands, so tomoe 2 unlocks at 20% of
# their personal Potential ceiling, tomoe 3 at 40%, and so on up to
# tomoe 6 at a full 100%.
SHARINGAN_MAX_TOMOE = 6
SHARINGAN_TOMOE_MASTERY_BAND_PERCENT = 1.0 / (SHARINGAN_MAX_TOMOE - 1)  # 20% per band, 5 bands total

# Potential-based tomoe ceiling, per direct follow-up request ("I want
# to cap tamoe so not everyone gets the full potential it makes luck
# of the draw a factor and not everyone will be the same so 50
# potential shouldn't allow a character to get 100% of sharingans
# powers") and confirmed design (a smooth 5-band scale, same shape as
# the mastery-percent bands above, but applied to the raw 0-100
# Potential number itself rather than a percentage of it). Independent
# of mastery -- a 50-Potential character can still grind their own
# mastery all the way to 100% of THEIR ceiling, but that no longer
# translates past this cap, so Potential genuinely gates the maximum
# reachable tomoe, not just how fast a player gets there.
SHARINGAN_TOMOE_CAP_BY_POTENTIAL_BAND = 20  # each 20-point band of Potential raises the tomoe ceiling by 1, starting at 2


def max_tomoe_for_potential(potential: int) -> int:
    """The highest tomoe count a player's Potential allows them to
    EVER reach, regardless of how much mastery they grind out -- a
    genuinely separate ceiling from mastery_percent/tomoe_for_mastery_
    percent above, not a replacement for them. 5 bands of 20 Potential
    points each: under 20 caps at 2 tomoe, 20-39 caps at 3, 40-59 caps
    at 4 (a 50-Potential character's example from the direct request),
    60-79 caps at 5, 80+ caps at the full 6. Never below 1 (tomoe 1 is
    always the separate, guaranteed awakening grant -- see
    attempt_awaken -- independent of Potential entirely)."""
    if potential <= 0:
        return 1
    band = min(4, potential // SHARINGAN_TOMOE_CAP_BY_POTENTIAL_BAND)
    return max(1, 2 + band)

# The chance, per combat round, to gain +1 raw mastery while the
# Sharingan is actively toggled on -- deliberately tiny, scaled
# linearly by the player's own hidden Talent (1-100), so a max-Talent
# character still only has a 2% chance per round (an average of ~50
# rounds of real, active combat use per single point of mastery), and
# a low-Talent character crawls far slower than that. Mastery itself
# is capped at the player's own Potential (their personal ceiling,
# never raised by any of this) -- "very slowly" and genuinely
# legendary to max out, matching this module's own stated philosophy.
MASTERY_GAIN_CHANCE_PER_TALENT_POINT = 0.0002  # e.g. Talent 100 -> 0.02 (2%) chance per round


def mastery_percent(player) -> float:
    """The player's current mastery as a fraction (0.0-1.0) of their
    OWN Potential ceiling -- not a flat 0-100 scale, since Potential
    varies per character. 0.0 if they have no Potential at all (no
    bloodline, or one somehow never rolled)."""
    if not player.bloodline_potential:
        return 0.0
    return min(1.0, player.bloodline_mastery / player.bloodline_potential)


def tomoe_for_mastery_percent(percent: float) -> int:
    """How many tomoe a given mastery percent (0.0-1.0, see
    mastery_percent above) should translate to -- tomoe 1 is always
    the baseline (granted separately at awakening, see attempt_awaken
    above; this function's floor is 1, not 0, so it never contradicts
    that grant), then +1 for each 20%-wide band crossed, capped at
    SHARINGAN_MAX_TOMOE (6). Rounds to 6 decimal places before
    dividing -- plain floating-point division here can land just
    under a clean threshold (e.g. 0.60 / 0.2 computes to
    2.9999999999999996, not 3.0), which int() truncation would
    silently round down, denying a tomoe right at the boundary a
    player actually reached."""
    bands_crossed = round(percent / SHARINGAN_TOMOE_MASTERY_BAND_PERCENT, 6)
    return min(SHARINGAN_MAX_TOMOE, 1 + int(bands_crossed))


def tick_mastery_gain(player) -> dict:
    """Rolls the small, Talent-scaled per-round chance to gain +1 raw
    mastery (see MASTERY_GAIN_CHANCE_PER_TALENT_POINT above), then
    recomputes tomoe count from the new mastery percent -- clamped by
    the player's own Potential-based tomoe ceiling (max_tomoe_for_
    potential above), per direct follow-up request: mastery can still
    climb all the way to 100% of a player's OWN Potential, but that no
    longer automatically means the full 6 tomoe -- a low-Potential
    character's ceiling stops them well short of that, no matter how
    much mastery they grind out. Callers (combat.py) are expected to
    have already checked player.sharingan_active and player.
    bloodline_awakened before calling this -- per explicit design
    confirmation, mastery gain requires the bloodline to already be
    formally awakened, it doesn't silently accumulate before that.
    Silent on every call that doesn't cross a new tomoe threshold --
    callers should only narrate the "tomoe_increased" case, never raw
    mastery numbers, keeping the same security posture as the rest of
    this module (Potential/Talent/exact mastery stay hidden; only the
    discrete, already-player-visible fact of "your Sharingan just got
    sharper" surfaces).

    Returns {"mastery_gained": bool, "tomoe_increased": bool,
    "new_tomoe": int}."""
    gained = False
    if player.bloodline_mastery < player.bloodline_potential:
        chance = player.bloodline_talent * MASTERY_GAIN_CHANCE_PER_TALENT_POINT
        if random.random() < chance:
            player.bloodline_mastery += 1
            gained = True

    old_tomoe = player.bloodline_tomoe
    mastery_based_tomoe = tomoe_for_mastery_percent(mastery_percent(player))
    new_tomoe = min(mastery_based_tomoe, max_tomoe_for_potential(player.bloodline_potential))
    tomoe_increased = new_tomoe > old_tomoe
    if tomoe_increased:
        player.bloodline_tomoe = new_tomoe

    return {
        "mastery_gained": gained,
        "tomoe_increased": tomoe_increased,
        "new_tomoe": player.bloodline_tomoe,
    }


def eligible_for_awakening_quest(player) -> bool:
    """Framework hook for a FUTURE stage-2 awakening quest (explicitly
    out of scope for this pass, not built yet) to call -- same "build
    the hook, not the quest" scope discipline as attempt_awaken()
    itself. Requires BOTH: the player's raw Potential itself at 90 or
    higher (per direct follow-up request -- "only characters with 90+
    potential shouldn't allow be eligible for the second quest" -- a
    genuinely separate condition from mastery progress, since Potential
    alone determines whether this door is even open at all, luck of
    the draw at chargen, not something training can raise), AND their
    mastery maxed out at 100% of their own Potential ceiling (the
    existing progress requirement, unchanged). Never sends text to
    anyone; a future quest owns all of that."""
    return player.bloodline_potential >= 90 and mastery_percent(player) >= 1.0


def is_most_grouped_partner(player, other_player_name: str) -> bool:
    """Whether other_player_name is genuinely player's OWN single
    most-grouped combat partner (the highest count in their own
    combat_partner_counts -- see Section 81's own tracking), per
    direct request/confirmation (Section 116: the Mangekyo betrayal
    mechanic is only reachable against "the friendship/most grouped
    player"). Ties are broken alphabetically by name, so the result
    is stable and predictable rather than randomly flickering between
    two equally-grouped partners on repeated calls. False if
    other_player_name has no credit at all, or if it's tied with (or
    beaten by) someone else's count."""
    counts = player.combat_partner_counts
    if not counts or other_player_name not in counts:
        return False
    best_count = max(counts.values())
    if counts[other_player_name] != best_count:
        return False
    tied_names = sorted(name for name, count in counts.items() if count == best_count)
    return tied_names[0] == other_player_name


def eligible_for_mangekyo_betrayal(attacker, target) -> bool:
    """The complete, real gate for the Mangekyo Sharingan betrayal
    mechanic, per direct request/confirmation (Section 116). Every
    condition confirmed directly: Sharingan specifically (not any of
    the other 4 bloodlines, even if they'd meet the same numbers);
    genuinely eligible for the stage-2 quest at all (Potential>=90,
    fully-maxed mastery -- eligible_for_awakening_quest above); not
    already unlocked (a one-time, permanent event); and the target is
    genuinely the attacker's own single most-grouped partner, not
    just someone they've fought alongside at some point."""
    return (
        attacker.bloodline_id == "sharingan"
        and eligible_for_awakening_quest(attacker)
        and not attacker.bloodline_mangekyo
        and is_most_grouped_partner(attacker, target.name)
    )


def sharingan_genjutsu_resistant(player) -> bool:
    """Whether player has the 4-tomoe Sharingan's genjutsu resistance
    perk active right now -- requires the Sharingan actively toggled
    on AND at least 4 tomoe, per the fuller progression table."""
    return bool(player.sharingan_active and player.bloodline_tomoe >= 4)


def reduced_genjutsu_duration(original_duration: int) -> int:
    """Applies the 4-tomoe Sharingan's genjutsu-resistance reduction to
    an effect's normal duration -- per direct design confirmation
    ("reduces genjutsu effect duration/severity rather than fully
    resisting"), this shortens the duration rather than negating the
    effect outright. Callers (combat.py) are expected to have already
    checked sharingan_genjutsu_resistant(player) is True before
    calling this. Always leaves at least 1 pulse of duration -- a
    "resistance" that could reduce an effect to literally zero pulses
    would be indistinguishable from full immunity, which isn't what
    was asked for here."""
    import commands
    reduced = int(original_duration * (1 - commands.SHARINGAN_GENJUTSU_RESIST_REDUCTION_PERCENT / 100))
    return max(1, reduced)


def display_name(kkg_id: str) -> str:
    entry = KEKKEI_GENKAI.get(kkg_id)
    return entry["display_name"] if entry else "Unknown"
