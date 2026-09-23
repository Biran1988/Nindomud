"""
Kage NPCs (Sections 5-6).

Each village's Kage lives in a dedicated chamber room and responds to a
small set of recognized phrases. Kage are independent per village by
construction (a plain dict keyed by village), so editing one village's
dialogue can never affect another's, satisfying Section 35's
independent-program requirement even without a full scripting engine.
"""

from typing import List, Tuple

import data_headbands
from data_villages import VILLAGES
from models import Player

KAGE_NAMES = {
    "leaf": "the Hokage",
    "stone": "the Tsuchikage",
    "water": "the Mizukage",
    "cloud": "the Raikage",
    "sand": "the Kazekage",
}

# (min_level, min_completed_missions, next_rank) -- one entry per
# promotion step, covering every rank in RANK_ORDER above Genin.
# Re-enabled per explicit request; the requirements below intentionally
# steepen toward the top (Village Elder demands both max-tier level
# investment and a real mission history), so the highest rank feels
# like a genuine, rare milestone rather than an automatic checkpoint.
# Genin -> Chunin is deliberately NOT in this ladder -- that promotion
# now requires passing the Chunin Exam (see chunin_exam.py) instead of
# a simple Kage request; handle_promotion_request below redirects a
# Genin who asks about promotion to go take the exam.
PROMOTION_LADDER: List[Tuple[int, int, str]] = [
    (40, 50, "special jonin"),
    (60, 100, "jonin"),
    (80, 500, "elite jonin"),
    (95, 1000, "village elder"),
]

RANK_ORDER = ["academy student", "genin", "chunin", "special jonin", "jonin", "elite jonin", "village elder", "kage"]

# "kage" is deliberately NOT reachable through PROMOTION_LADDER above --
# per explicit request, it can only ever be granted by an Implementor
# (see commands.cmd_setkage), never automatically through level/mission
# requirements like every other rank. At most one player per village
# holds it at a time; appointing a new one demotes the previous holder
# back to "village elder".

# Promotions, per explicit request. Previously disabled while the
# promotion ladder only covered up through Jonin (see git history /
# README for the full "properly re-enabled" writeup) -- extended above
# to cover every rank, so this can be safely turned back on.
PROMOTIONS_ENABLED = True


def kage_title(village: str) -> str:
    return KAGE_NAMES[village]


def handle_mission_redirect(player: Player) -> str:
    """The Kage no longer hands out missions directly -- only the
    village mission board does. This is just a flavor redirect."""
    return f"{kage_title(player.village)} says, \"I don't hand out missions myself -- check the mission board.\""


def announce_rank_up(player_name: str, new_rank: str) -> None:
    """A genuinely GLOBAL announcement -- every connected, playing
    session, regardless of room or village -- the moment a player's
    rank changes, per direct request/confirmation ("i want an
    announcmenet for when i player gains a rank that is global" ->
    confirmed: every rank-change path in the game (Kage promotions,
    the Chunin Exam, and the new mob-driven set_rank program action)
    triggers this same announcement, confirmed exact wording).

    A standalone function, not a Session method, since some
    rank-change call sites (Kage promotions, via handle_promotion_
    request below) only ever receive a bare Player object, with no
    live Session to broadcast from. Reaches every connected session
    directly via session.ACTIVE_SESSIONS, the same real, global list
    Session.broadcast_all itself already reads from, rather than
    requiring every caller to have (or fake) a session reference."""
    import session as session_module

    message = f"&Y{player_name} has been promoted to {new_rank.title()}!&x"
    for s in session_module.ACTIVE_SESSIONS:
        if s.state.name == "PLAYING":
            s.send(message)
            s.send_prompt()


GENIN_PROMOTION_MISSION_POINTS = 50


def award_genin_mission_points_if_applicable(session, player, new_rank: str) -> None:
    """Per direct request/confirmation (Section 157): "when soemone
    becomes a genin have it award 50 mission points ontop of the
    headband." Confirmed to apply regardless of which real path
    caused the promotion (Iruka's own hardcoded academy check, or the
    generic set_rank program action, if a builder ever uses it for
    genin on some other NPC) -- a single, centralized real function
    both call directly, rather than duplicating this award at every
    site that might ever promote someone to genin. A no-op for any
    other rank."""
    if new_rank != "genin":
        return
    player.mission_points += GENIN_PROMOTION_MISSION_POINTS
    player.mission_points_earned_total += GENIN_PROMOTION_MISSION_POINTS
    session.send(f"&GYou receive {GENIN_PROMOTION_MISSION_POINTS} mission point(s) for graduating the academy.&x")


def handle_promotion_request(player: Player) -> str:
    if not PROMOTIONS_ENABLED:
        return (
            f"{kage_title(player.village)} says, \"Promotions aren't handled through me yet -- "
            f"focus on mastering the basics for now.\""
        )

    current_index = RANK_ORDER.index(player.village_rank) if player.village_rank in RANK_ORDER else 0
    completed = len(player.completed_missions)

    if player.village_rank == "genin":
        return (
            f"{kage_title(player.village)} says, \"I don't hand out that promotion myself -- "
            f"the Chunin Exam decides who's ready. Take the exam ('exam') once you're qualified.\""
        )

    for min_level, min_missions, next_rank in PROMOTION_LADDER:
        target_index = RANK_ORDER.index(next_rank)
        if target_index != current_index + 1:
            continue
        if player.level < min_level or completed < min_missions:
            return (
                f"{kage_title(player.village)} says, \"Not yet. You need at least level "
                f"{min_level} and {min_missions} completed mission(s) for promotion to "
                f"{next_rank.title()}.\""
            )
        player.village_rank = next_rank
        data_headbands.apply_rank_headband(player, next_rank)
        announce_rank_up(player.name, next_rank)
        return (
            f"{kage_title(player.village)} says, \"Well done. I hereby promote you to "
            f"{next_rank.title()}.\"\n&YYou are promoted to {next_rank.title()}!&x"
        )

    return f"{kage_title(player.village)} says, \"There is no further promotion available for you right now.\""
