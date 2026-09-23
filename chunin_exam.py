"""
Chunin Exam -- the Forest of Death scroll mechanic.

Per explicit design discussion: the simple "ask the Kage, meet a
level/mission threshold" Genin -> Chunin promotion is replaced by a
real trial, modeled on canon's Forest of Death -- a genin enters with
one of two scroll types (Heaven or Earth) and must obtain the other to
pass, either by defeating one of two dangerous "scroll guardian" mobs
deep in the forest, or by defeating ANOTHER player who's also in the
exam and taking theirs. Reaching the tower with both scrolls completes
the exam and promotes the player to Chunin on the spot.

The entry gate itself is UNCHANGED from the old Genin -> Chunin
requirement (level 10, 25 completed missions) -- this doesn't add a
new, separate gate, it changes what happens once you're qualified.
Deliberately NOT level-capped beyond that minimum: a genin who
qualified a while ago and is now higher level can still take the exam
at any time, same as canon doesn't retroactively disqualify anyone.

Every other rank (Special Jonin through Village Elder) is untouched --
still handled by kage.handle_promotion_request exactly as before; only
the Genin -> Chunin step moved out of that ladder and into this
module. See kage.py's own PROMOTION_LADDER, which no longer has a
Chunin entry, and its handle_promotion_request, which now redirects a
Genin asking about promotion to come here instead.

One shared zone (not per-village) -- canon's Chunin Exams are
explicitly an inter-village event, and a shared space is what makes
the "steal another candidate's scroll" mechanic mean anything at all
(nothing to steal if every village's genin do this in isolation).
"""

from typing import Optional

ENTRANCE_VNUM = 60000
FOREST_VNUMS = [60001, 60002, 60003]
TOWER_VNUM = 60004

HEAVEN_SCROLL = "A Heaven Scroll"
EARTH_SCROLL = "An Earth Scroll"
SCROLLS = (HEAVEN_SCROLL, EARTH_SCROLL)

HEAVEN_GUARDIAN_VNUM = 6900
EARTH_GUARDIAN_VNUM = 6901

# The exact same gate the old Genin -> Chunin ladder entry used
# (level, min_completed_missions) -- kept here as the single source of
# truth now that kage.py's own ladder no longer has a Chunin entry, so
# a future balance change only has to touch one place.
MIN_LEVEL = 10
MIN_COMPLETED_MISSIONS = 25


def qualifies_for_exam(player) -> bool:
    return (
        player.village_rank == "genin"
        and player.level >= MIN_LEVEL
        and len(player.completed_missions) >= MIN_COMPLETED_MISSIONS
    )


def missing_scroll(player) -> Optional[str]:
    """Which scroll type the player still needs, or None if they
    already have both (or the given item name is neither scroll)."""
    for scroll in SCROLLS:
        if not any(item.lower() == scroll.lower() for item in player.inventory):
            return scroll
    return None


def has_both_scrolls(player) -> bool:
    return missing_scroll(player) is None


def steal_scroll_on_pvp_defeat(winner, loser) -> Optional[str]:
    """Per the PvP scroll-theft mechanic: if both players are actively
    in the exam and the loser is carrying a scroll type the winner
    doesn't have, the winner takes it. Only ever takes ONE scroll (the
    one the winner is actually missing) -- if the loser happens to be
    carrying both, the winner still only walks away with whichever one
    they needed, not a full sweep, since taking a scroll the winner
    already has would just be destroying the loser's copy for no
    reason. Returns the scroll name taken, or None if nothing changed
    hands (either player isn't in the exam, or the loser had nothing
    the winner needed)."""
    if not (winner.in_chunin_exam and loser.in_chunin_exam):
        return None
    needed = missing_scroll(winner)
    if needed is None:
        return None  # winner already has both, nothing to gain
    match = next((item for item in loser.inventory if item.lower() == needed.lower()), None)
    if match is None:
        return None
    loser.inventory.remove(match)
    winner.inventory.append(match)
    return match
