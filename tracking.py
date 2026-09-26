"""
Track (Section 119) -- a scroll-taught jutsu that autonomously walks
the caster, one room per real pulse, toward a chosen mob or player.

Per direct request/confirmation: "Let's add a special scroll jutsu
called track that will automatically track the desired mob or player
and move room to room in that direction." Every real mechanic
confirmed directly before building, not assumed:

- Genuine autonomous movement -- the caster's own character walks
  itself, one room per real pulse, mirroring how a wandering mob
  already moves on its own timer (see combat.py's own Wander
  handling). Not a compass/hint the player still has to walk
  manually.
- Scoped to only the TARGET's own real area (areas.find_area_for_vnum)
  -- pathfinding never searches the whole map, only rooms within
  that one area's own registered vnum range.
- Stays active in the background regardless of what other commands
  the player types -- ordinary movement, combat, practice, etc. all
  still work normally while tracking is running.
- Automatically PAUSES the instant the player enters active combat
  (PvE or PvP), and resumes the moment that fight ends -- confirmed
  directly, since being yanked room to room mid-fight would be
  genuinely disruptive.
- Works on BOTH a real wandering mob and a real player character.
- Ends cleanly, with a clear message, the instant the target becomes
  genuinely unreachable for any reason: they leave their own area,
  log off, die, or are simply no longer findable at all.
- A genuine, ongoing PER-PULSE chakra upkeep while active (mirroring
  Shadow Clone Jutsu's own established upkeep pattern) -- tracking
  stops automatically the moment the caster's chakra runs out.
"""

from collections import deque
from typing import Optional


def find_mob_anywhere_in_world(combat_module, query: str):
    """A genuinely world-wide version of combat.find_mob's own exact
    matching logic (case-insensitive substring), per direct
    confirmation ("The player can name ANY mob/player by name from
    anywhere, and the game searches the whole world to find them
    first"). Returns the first live combat.Mob instance anywhere in
    the world whose name matches, or None. If several different
    live mobs share a matching name, this deliberately returns
    whichever one is found first (iteration order over
    MOBS_BY_ROOM) -- Track doesn't need a specific instance chosen
    over another identically-named one, just a genuine, real match to
    start tracking."""
    query = query.lower()
    for room_mobs in combat_module.MOBS_BY_ROOM.values():
        for mob in room_mobs:
            if query in mob.name.lower():
                return mob
    return None


def find_online_player_anywhere(session_module, query: str):
    """A genuinely world-wide search for a real, currently-online,
    playing session whose character name matches (case-insensitive
    substring, same matching convention as find_mob_anywhere_in_
    world). Returns the real Session, or None if no online player
    matches at all -- an offline player is never a valid Track
    target, since there'd be nowhere real to walk toward."""
    query = query.lower()
    for other_session in session_module.ACTIVE_SESSIONS:
        if (other_session.player and other_session.state.name == "PLAYING"
                and query in other_session.player.name.lower()):
            return other_session
    return None


TRACK_UPKEEP_PER_PULSE = 5  # a small, real, ongoing chakra cost -- mirrors Shadow Clone Jutsu's own established upkeep pattern


def _room_exits_are_passable(room, direction: str) -> bool:
    """Whether the caster's own automatic tracking is allowed to use
    this specific exit -- respects a closed, unopened door exactly
    the same way ordinary player movement already does (see
    commands.cmd_move's own identical check), so an autonomous
    tracker can never bypass a restriction a manually-walking player
    couldn't."""
    if "door" in room.exit_flags.get(direction, []) and not room.exit_door_open.get(direction, False):
        return False
    return True


def find_path(world_module, start_vnum: int, target_vnum: int, area) -> Optional[list]:
    """A genuine breadth-first search for the shortest real path from
    start_vnum to target_vnum, using only rooms within `area`'s own
    registered vnum range (area.vnum_start to area.vnum_end
    inclusive) -- confirmed directly to never search the whole map,
    only the target's own area. Respects closed/locked doors exactly
    like ordinary movement (_room_exits_are_passable). Returns a list
    of direction strings (e.g. ["north", "north", "east"]) for the
    caller to walk one at a time, or None if no real path exists at
    all within that area (a genuinely disconnected room, or
    start_vnum/target_vnum not actually within the area's own
    range)."""
    if not (area.vnum_start <= start_vnum <= area.vnum_end):
        return None
    if not (area.vnum_start <= target_vnum <= area.vnum_end):
        return None
    if start_vnum == target_vnum:
        return []

    visited = {start_vnum}
    queue = deque([(start_vnum, [])])
    while queue:
        current_vnum, path_so_far = queue.popleft()
        room = world_module.WORLD.get(current_vnum)
        if room is None:
            continue
        for direction, next_vnum in room.exits.items():
            if next_vnum in visited:
                continue
            if not (area.vnum_start <= next_vnum <= area.vnum_end):
                continue
            if not _room_exits_are_passable(room, direction):
                continue
            new_path = path_so_far + [direction]
            if next_vnum == target_vnum:
                return new_path
            visited.add(next_vnum)
            queue.append((next_vnum, new_path))
    return None


def _resolve_target_room_vnum(player, combat_module, session_module) -> Optional[int]:
    """The real, current room vnum of whatever this player is
    tracking right now, or None if that target is genuinely
    unreachable for any reason (per direct confirmation: "tracking
    simply ends/fails silently-but-notified the moment the target
    becomes unreachable"). Checks exactly one of the two real target
    kinds -- a specific mob instance (re-identified by its own stable
    instance_id, since a template vnum alone could match many live
    instances) or a specific player (must be genuinely online and
    alive)."""
    if player.tracking_target_mob_id is not None:
        for room_mobs in combat_module.MOBS_BY_ROOM.values():
            for mob in room_mobs:
                if mob.instance_id == player.tracking_target_mob_id:
                    return mob.room_vnum if mob.health > 0 else None
        return None
    if player.tracking_target_player_name is not None:
        for other_session in session_module.ACTIVE_SESSIONS:
            if (other_session.player and other_session.state.name == "PLAYING"
                    and other_session.player.name == player.tracking_target_player_name):
                return other_session.player.room_vnum if other_session.player.health > 0 else None
        return None
    return None


def start_tracking(player, target_mob=None, target_player_name: Optional[str] = None, area_name: Optional[str] = None) -> None:
    """Begins a fresh tracking session for exactly one of target_mob
    (a real combat.Mob instance) or target_player_name -- callers are
    expected to have already resolved which of the two the player
    actually meant before calling this. area_name is the target's own
    real area at the moment tracking starts, per direct confirmation
    ("only within the same area/region the target is actually in")."""
    player.tracking_target_mob_id = target_mob.instance_id if target_mob else None
    player.tracking_target_player_name = target_player_name
    player.tracking_area_name = area_name
    player.tracking_paused_by_combat = False


def stop_tracking(player) -> None:
    """Ends any active tracking session for this player, clearing
    every real piece of tracking state at once. Safe to call even
    when nothing is actually being tracked."""
    player.tracking_target_mob_id = None
    player.tracking_target_player_name = None
    player.tracking_area_name = None
    player.tracking_paused_by_combat = False


def tick_tracking(session) -> None:
    """The real per-pulse engine for an active Track jutsu, per
    direct request/confirmation (Section 119). Called once per real
    game pulse for every session with tracking genuinely active (see
    server.py's own pulse loop, matching the same call pattern
    combat.tick_pending_casts already uses). Does nothing at all for
    a session with no active tracking, so this is cheap and safe to
    call unconditionally for every connected session every pulse.

    Confirmed order of real checks, each ending tracking cleanly with
    its own clear message on failure:
      1. Still has enough chakra for this pulse's own upkeep cost --
         stops automatically the moment it runs out.
      2. Not currently in active combat (PvE or PvP) -- if so, PAUSES
         (does not end) for this pulse only, resuming automatically
         once that fight ends, per direct confirmation.
      3. The target is still genuinely reachable at all (see
         _resolve_target_room_vnum) -- ends cleanly if not.
      4. Already arrived -- ends cleanly with a success message,
         rather than silently continuing to "track" someone already
         standing right there.
      5. A genuine, real path exists to the target's own current
         room, scoped to the target's own area -- ends cleanly if
         none does (e.g. the target left that area entirely, even if
         still otherwise reachable in principle).
    Otherwise, walks exactly one real room in the correct direction
    for this pulse, exactly like an ordinary player move."""
    player = session.player
    if player is None:
        return
    if player.tracking_target_mob_id is None and player.tracking_target_player_name is None:
        return

    import combat as combat_module
    import session as session_module
    import world
    import areas
    import commands as commands_module

    if player.chakra < TRACK_UPKEEP_PER_PULSE:
        session.send("&YYou're out of chakra -- you lose the trail.&x")
        stop_tracking(player)
        return

    if session.combat_target is not None or session.pvp_target is not None:
        player.tracking_paused_by_combat = True
        return
    if player.tracking_paused_by_combat:
        player.tracking_paused_by_combat = False
        session.send("&YThe fight over, you pick up the trail again.&x")

    target_vnum = _resolve_target_room_vnum(player, combat_module, session_module)
    if target_vnum is None:
        session.send("&YYou lose the trail -- your target is nowhere to be found.&x")
        stop_tracking(player)
        return

    if target_vnum == player.room_vnum:
        session.send("&GYou've caught up with your target!&x")
        stop_tracking(player)
        return

    area = areas.find_area_for_vnum(target_vnum)
    if area is None or area.name != player.tracking_area_name:
        session.send("&YYour target has slipped out of range -- you lose the trail.&x")
        stop_tracking(player)
        return

    path = find_path(world, player.room_vnum, target_vnum, area)
    if not path:
        session.send("&YYou lose the trail -- there's no way to reach your target from here.&x")
        stop_tracking(player)
        return

    player.chakra -= TRACK_UPKEEP_PER_PULSE
    session.send(f"&CTracking uses {TRACK_UPKEEP_PER_PULSE} chakra to remain active.&x")
    direction = path[0]
    commands_module.cmd_move(session, direction)
