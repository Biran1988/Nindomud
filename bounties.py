"""
The Bingo Book (Section 57) -- a bounty system for wanted targets,
themed after the in-universe secret ledger of dangerous/wanted ninja.
Originally mob-only (PvP didn't exist yet); now supports player
targets too, per explicit request, now that PvP combat is real (see
combat.py's player_kills/player_deaths tracking). Every bounty entry
now has a "target_type" of "mob" or "player" -- a legacy entry saved
before this change has no such key at all, and is always treated as
"mob" for backward compatibility (see target_type_of()).

Bounty IDs are allocated within a fixed range PER VILLAGE, matching
which village the wanted target is associated with (the target mob's
own village theme, or the target PLAYER's own village for a player
bounty) -- not room vnums (rooms already use small numbers like
1000-1499 for Leaf alone) but a separate ID namespace just for bounty
entries:
    Leaf  1000-1999   Sand  2000-2999   Stone 3000-3999
    Water 4000-4999   Cloud 5000-5999
Within a village's block, the next unused ID is assigned automatically
when a bounty is created.

Player bounties can be posted two ways: staff via the existing 'bounty
create' command (no payment required, same as a mob bounty), or by any
player in person at a mob flagged "BountyOffice" (see act_flags) via
the new 'place bounty' command -- which DOES require the poster to pay
the full reward up front (deducted immediately), so it can't be spammed
for free. FAILSAFE, per explicit request: a player-placed bounty can
never target someone in the poster's own village -- bounties are for
rival-village ninja, not internal betrayal. Staff-created bounties (via
'bounty create') are NOT subject to this same-village restriction,
since a staff member creating one is presumed to have a deliberate
narrative reason.

A bounty is claimed at most ONCE per player (tracked in "claimed_by"),
even though the underlying mob prototype can still respawn and be
killed again -- a wanted-dead-or-alive reward is a one-time payout per
hunter, not a farmable loop. The same one-claim-per-hunter rule applies
to a player bounty: multiple different players could each individually
land the killing PvP blow across separate fights and each still claim
it once, but any single hunter can't claim the same posted bounty
twice. Reward is ryo and/or mission points, mirroring the
give_ryo/give_mission_points program actions.
"""

VILLAGE_ID_RANGES = {
    "leaf": (1000, 1999),
    "sand": (2000, 2999),
    "stone": (3000, 3999),
    "water": (4000, 4999),
    "cloud": (5000, 5999),
}


def next_id_for_village(village: str):
    """Returns the next unused ID in `village`'s block, or None if the
    block is entirely full (1000 possible bounties per village, so this
    is a theoretical safeguard more than a real limit)."""
    import storage

    if village not in VILLAGE_ID_RANGES:
        return None
    low, high = VILLAGE_ID_RANGES[village]
    bounties = storage.load_bounties()
    used = {int(bid) for bid in bounties.keys()}
    for candidate in range(low, high + 1):
        if candidate not in used:
            return candidate
    return None


def target_type_of(entry: dict) -> str:
    """"mob" or "player" for any bounty entry, including a legacy one
    saved before target_type existed at all (always "mob" in that
    case, since player bounties didn't exist yet)."""
    return entry.get("target_type", "mob")


def create_bounty(target_type: str, target, village: str, reward_ryo: int,
                   reward_mission_points: int, description: str, posted_by=None):
    """Posts a new bounty, returning its assigned ID (or None if the
    village isn't recognized or its ID block is full). target_type is
    "mob" (target = a mob prototype vnum) or "player" (target = a
    player name). posted_by is the placing player's name for a
    player-placed bounty (via 'place bounty'), or None for a
    staff-created one (via 'bounty create')."""
    import storage

    bounty_id = next_id_for_village(village)
    if bounty_id is None:
        return None
    bounties = storage.load_bounties()
    bounties[str(bounty_id)] = {
        "target_type": target_type,
        "mob_vnum": target if target_type == "mob" else None,
        "target_player": target if target_type == "player" else None,
        "village": village,
        "reward_ryo": reward_ryo, "reward_mission_points": reward_mission_points,
        "description": description, "claimed_by": [], "posted_by": posted_by,
    }
    storage.save_bounties(bounties)
    return bounty_id


def remove_bounty(bounty_id: int) -> bool:
    import storage

    bounties = storage.load_bounties()
    key = str(bounty_id)
    if key not in bounties:
        return False
    del bounties[key]
    storage.save_bounties(bounties)
    return True


def all_bounties() -> dict:
    import storage
    return storage.load_bounties()


def find_bounty_for_mob(mob_vnum: int):
    """Returns (id, entry) for the first active bounty on this mob
    vnum, or (None, None) if it isn't a wanted target."""
    for bounty_id, entry in all_bounties().items():
        if target_type_of(entry) == "mob" and entry["mob_vnum"] == mob_vnum:
            return int(bounty_id), entry
    return None, None


def find_bounty_for_player(player_name: str):
    """Returns (id, entry) for the first active bounty on this player
    (by name), or (None, None) if they aren't a wanted target."""
    for bounty_id, entry in all_bounties().items():
        if target_type_of(entry) == "player" and entry["target_player"] == player_name:
            return int(bounty_id), entry
    return None, None


def claim_bounty(bounty_id: int, player_name: str) -> bool:
    """Marks the bounty claimed by player_name. Returns False (and
    changes nothing) if they've already claimed it before."""
    import storage

    bounties = storage.load_bounties()
    key = str(bounty_id)
    entry = bounties.get(key)
    if not entry:
        return False
    if player_name in entry["claimed_by"]:
        return False
    entry["claimed_by"].append(player_name)
    storage.save_bounties(bounties)
    return True
