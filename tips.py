"""
Tip-of-the-day system, per direct request ("a config called tips and
an addtip command and remtip command for immortals only. Tips can be
configured on/off default on and display to a player with the config
on every 30 minutes").

Three pieces, split across their natural homes rather than crammed
into one file:

  - THE LIST ITSELF (here) -- a plain, staff-curated list of tip
    strings, persisted to tips.json (storage.py, same shape as
    spawn_points.json/territory.json). add_tip/remove_tip/all_tips are
    the only three operations this needs.

  - THE STAFF COMMANDS ('addtip'/'remtip', commands.py) -- gated to
    STAFF_CAN_BUILD (builder and above), the same tier every other
    world-content curation tool (mset/oset/rset) already uses, since
    adding flavor/help text to the game is ordinary building work, not
    the more sensitive player-data-editing tier (bloodstat/bloodset/
    awaken use administrator+ instead).

  - THE PLAYER-FACING CONFIG ('tips' in commands.CONFIG_OPTIONS) and
    THE PERIODIC DISPLAY TIMER (server.py's own main loop, TIPS_
    INTERVAL_SECONDS below) -- a plain per-player bool defaulting True
    (Player.tips, matching every other CONFIG_OPTIONS field's
    own default-on convention), and a global elapsed-time counter in
    the server's main loop firing every 30 minutes, sending one tip to
    every currently-playing session with tips still on. Rotates
    through the list in order rather than randomly, so tips don't
    repeat back-to-back by chance and every tip actually gets seen
    over time.
"""

import storage

TIPS_INTERVAL_SECONDS = 30 * 60  # 30 minutes, per explicit request


def all_tips() -> list:
    return storage.load_tips()


def add_tip(text: str) -> None:
    tips = storage.load_tips()
    tips.append(text)
    storage.save_tips(tips)


def remove_tip(index: int) -> bool:
    """1-indexed, matching how the tip list is displayed to staff via
    'addtip' with no arguments -- returns False if the index doesn't
    exist rather than raising, so the caller can send a clean refusal
    instead of a traceback."""
    tips = storage.load_tips()
    if index < 1 or index > len(tips):
        return False
    tips.pop(index - 1)
    storage.save_tips(tips)
    return True


def next_tip(current_index: int) -> tuple:
    """Rotates to the next tip in the list, wrapping back to the
    start. Returns (tip_text, new_index) so the caller (server.py)
    can track its own rotation position -- returns (None, 0) if the
    list is empty, since there's nothing to show."""
    tips = storage.load_tips()
    if not tips:
        return None, 0
    index = current_index % len(tips)
    return tips[index], index + 1
