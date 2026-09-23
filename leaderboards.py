"""
Leaderboards (Section 54) -- ranks every saved character by a handful
of tracked stats. Since player data lives one file per character (see
storage.py), a leaderboard has to load every save file fresh each time
it's viewed (storage.all_players(), the same helper apartment
ownership reconciliation uses at startup) rather than maintaining a
running rank live -- fine for an occasional player command, not meant
to be called on a hot path like the pulse loop.

Categories deliberately distinguish "earned" from "held" where a stat
can be spent: mission_points_earned is a lifetime total that only ever
goes up, while mission_points_held is the player's current spendable
balance (can go down when they buy a Kage perk). Both are worth
tracking -- one rewards long-term grinding, the other rewards saving
up. The same distinction doesn't apply to ryo (also spendable) here
only because ryo isn't asked for as a leaderboard category; a lifetime
"ryo earned" counter would be a reasonable future addition if wanted.

player_kills/player_deaths are real, live-tracked fields -- incremented
in combat.py's handle_pvp_defeat on every PvP kill, same as npc_kills
is for a mob kill. (An earlier version of this comment claimed PvP
wasn't implemented yet; that's no longer true and hadn't been updated.)

One honest limitation: mission_points_earned_total (and npc_kills) are
NEW counters -- a character who earned mission points or NPC kills
before this system existed will show a lower "earned" total than their
true history, since there's no way to reconstruct that retroactively.
Their current mission_points_held balance is unaffected.
"""

TOP_N = 10

CATEGORIES = {
    "npc_kills": ("NPC Kills", lambda p: p.npc_kills),
    "player_kills": ("Player Kills", lambda p: p.player_kills),
    "mission_points_earned": ("Most Mission Points Earned (lifetime)", lambda p: p.mission_points_earned_total),
    "mission_points_held": ("Most Mission Points Held (current)", lambda p: p.mission_points),
    "level": ("Highest Level", lambda p: p.level),
    "missions_completed": ("Most Missions Completed", lambda p: len(p.completed_missions)),
    "ryo": ("Wealthiest (Ryo)", lambda p: p.ryo),
    "playtime": ("Longest Play Time", lambda p: int(p.total_play_seconds)),
}


def top(category: str, limit: int = TOP_N) -> list:
    """Returns up to `limit` (name, value) pairs for `category`, highest
    first. Ties broken by name for stable, predictable output. Players
    at 0 for the category are excluded -- an empty leaderboard reads
    better than a wall of zeroes for a stat nobody's touched yet."""
    import storage

    _, key_fn = CATEGORIES[category]
    players = storage.all_players()
    scored = [(p.name, key_fn(p)) for p in players]
    scored = [(name, value) for name, value in scored if value > 0]
    scored.sort(key=lambda pair: (-pair[1], pair[0].lower()))
    return scored[:limit]
