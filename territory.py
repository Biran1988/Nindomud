"""
War / territory capture system (Section 79), per an explicit multi-turn
design discussion. Deliberately built as a thin layer over TWO existing,
already-generic systems rather than a new hardcoded zone:

  - A "capture point" is just any room flagged "CapturePoint" via the
    already-fully-generic 'rset flags CapturePoint' (nothing new needed
    there at all -- see olc.py's cmd_rset "flags" subcommand).
  - Each capture point's income comes from its own AREA's `income` stat
    (areas.py, 'area set <name> income <n>'), not something tracked
    per-room. A builder adding a new control point is just: build/pick a
    room, set its area's income if not already set, flag the room
    CapturePoint. No code changes, ever, to add or move a control point.

This keeps village treasury spending scoped to defenses ONLY for now, per
explicit request -- no shop-tier unlocks or special trainers yet (that's
the "village perks" half of the original discussion, deliberately held
off). State (treasury balances, each point's owner/garrison/contest
progress, and the war window schedule) is one persisted global blob
(storage.load_territory/save_territory), same shape as bounties.py.

CAPTURE FLOW, only valid while a war window is active (see
war_window_active()):
  1. Every garrison mob at a point must be cleared (killed) first.
  2. Once the garrison is empty, whichever OTHER village currently has
     at least one player standing in the room starts "holding" it --
     tracked as contested_by + hold_started_at.
  3. The hold breaks (resets to nothing) if the owning village restocks
     the garrison (buys a new defense mob there) OR the attacking
     village's presence in the room drops to zero -- checked each pulse
     via tick() below, not just at the moment of the last kill.
  4. Held uncontested for HOLD_DURATION_SECONDS -> ownership flips. The
     new owner's garrison starts empty; they have to buy their own.

WAR WINDOWS are randomly scheduled ahead of time and announced when set
(server-wide broadcast), per explicit request -- never a fixed,
predictable slot, and never always-on (so a strong garrison bought
during the week actually matters, rather than being tested 24/7 /
vulnerable to being raided while everyone's offline).
"""

import random
import time
from typing import List, Optional

import damage_messages

HOLD_DURATION_SECONDS = 300  # 5 minutes uncontested to flip a point
INCOME_TICK_SECONDS = 300  # how often treasuries accrue (base + per-point)
BASE_INCOME_PER_TICK = 10  # every village earns this much per tick regardless of points held

WAR_WINDOW_DURATION_SECONDS = 45 * 60  # 45 minutes once active
WAR_WINDOW_MIN_DELAY_SECONDS = 6 * 3600  # next window scheduled 6-48h out
WAR_WINDOW_MAX_DELAY_SECONDS = 48 * 3600


def _state() -> dict:
    import storage
    return storage.load_territory()


def _save(state: dict) -> None:
    import storage
    storage.save_territory(state)


# --- Village treasury -------------------------------------------------

def treasury_balance(village: str) -> int:
    return _state().get("treasury", {}).get(village, 0)


def _add_treasury(state: dict, village: str, amount: int) -> None:
    state.setdefault("treasury", {})
    state["treasury"][village] = state["treasury"].get(village, 0) + amount


def deduct_treasury(village: str, amount: int) -> bool:
    """Spends `amount` from village's treasury if it can afford it.
    Returns False (no change made) if it can't."""
    state = _state()
    balance = state.get("treasury", {}).get(village, 0)
    if balance < amount:
        return False
    state.setdefault("treasury", {})
    state["treasury"][village] = balance - amount
    _save(state)
    return True


# --- Capture points -----------------------------------------------------

def all_capture_point_vnums() -> List[int]:
    """Every room vnum currently flagged CapturePoint, anywhere in the
    world -- the live, authoritative list. A room un-flagged later
    simply stops appearing here; its territory.json entry (if any) is
    just inert leftover data, not an error."""
    import world
    return sorted(vnum for vnum, room in world.WORLD.rooms.items() if "CapturePoint" in room.flags)


def point_income(room_vnum: int) -> int:
    """The per-tick income this point generates for its owner, pulled
    from its own area's income stat -- 0 if it isn't part of any
    registered area, or that area never had income configured."""
    import areas
    area = areas.find_area_for_vnum(room_vnum)
    return area.income if area else 0


def point_state(room_vnum: int) -> dict:
    """This point's dynamic state -- owner/garrison/contest progress.
    Always returns a fully-populated dict (never a missing-key error),
    defaulting to unowned/empty/uncontested for a point with no saved
    state yet (e.g. one just flagged CapturePoint for the first time)."""
    entry = _state().get("points", {}).get(str(room_vnum), {})
    return {
        "owner": entry.get("owner"),
        "garrison": list(entry.get("garrison", [])),
        "contested_by": entry.get("contested_by"),
        "hold_started_at": entry.get("hold_started_at"),
    }


def _save_point_state(state: dict, room_vnum: int, point: dict) -> None:
    state.setdefault("points", {})
    state["points"][str(room_vnum)] = point


# --- Garrison (buyable defense mobs) -------------------------------------

# Three tiers, escalating cost and strength -- registered as real mob
# templates by content.py's populate() (garrison_mob_vnum below), so a
# purchased garrison mob is a genuine, fightable NPC like any other.
GARRISON_TIERS = {
    "recruit": {"display_name": "Recruit Guard", "cost": 200, "level": 15, "max_health": 300,
                "min_damage": 10, "max_damage": 18},
    "veteran": {"display_name": "Veteran Guard", "cost": 600, "level": 35, "max_health": 700,
                "min_damage": 22, "max_damage": 34},
    "elite": {"display_name": "Elite Guard", "cost": 1500, "level": 60, "max_health": 1500,
              "min_damage": 40, "max_damage": 60},
}
GARRISON_TIER_ORDER = ["recruit", "veteran", "elite"]
MAX_GARRISON_PER_POINT = 3  # a village can stack up to 3 defenders at one point


def garrison_mob_vnum(village: str, tier: str) -> int:
    """The one, fixed mob template vnum for a given village+tier combo
    -- every garrison mob of that village/tier is the exact same
    template, matching how shopkeepers/villagers are one template
    reused everywhere rather than a new prototype per purchase. Base
    6950 (not 6900) -- 6900/6901 are chunin_exam.py's scroll guardian
    vnums, defined as bare constants there rather than inside
    content.py, so an earlier content.py-only vnum scan missed them."""
    import data_villages
    village_index = list(data_villages.VILLAGES.keys()).index(village)
    tier_index = GARRISON_TIER_ORDER.index(tier)
    return 6950 + village_index * 10 + tier_index


def buy_garrison(village: str, room_vnum: int, tier: str) -> str:
    """Attempts to station a new garrison mob of the given tier at
    room_vnum for `village`. Returns "" on success, or a human-readable
    reason it failed (not owned, garrison full, can't afford it, not a
    capture point, unknown tier) -- the caller (commands.py) sends that
    straight to the player, so failure messages live in one place."""
    if tier not in GARRISON_TIERS:
        return f"'{tier}' isn't a garrison tier. Choose one of: {', '.join(GARRISON_TIER_ORDER)}."
    if room_vnum not in all_capture_point_vnums():
        return "That isn't a capture point."

    point = point_state(room_vnum)
    if point["owner"] != village:
        return "Your village doesn't control that point."
    if len(point["garrison"]) >= MAX_GARRISON_PER_POINT:
        return f"That point's garrison is already at its maximum of {MAX_GARRISON_PER_POINT}."

    cost = GARRISON_TIERS[tier]["cost"]
    if not deduct_treasury(village, cost):
        return f"Your village treasury needs {cost:,} ryo for that -- it only has {treasury_balance(village):,}."

    import combat
    vnum = garrison_mob_vnum(village, tier)
    combat.spawn_mob(vnum, room_vnum)

    state = _state()
    point["garrison"].append(vnum)
    # Restocking the garrison breaks any in-progress capture against this point.
    point["contested_by"] = None
    point["hold_started_at"] = None
    _save_point_state(state, room_vnum, point)
    _save(state)
    return ""


def _live_garrison_count(room_vnum: int) -> int:
    """How many of this point's own garrison mobs are actually still
    alive in the room right now -- the source of truth for whether a
    capture can even begin, since a mob dying doesn't retroactively
    edit territory.json (that only happens here, on read)."""
    import combat
    point = point_state(room_vnum)
    living_vnums = [m.template_vnum for m in combat.mobs_in_room(room_vnum)]
    return sum(1 for vnum in point["garrison"] if vnum in living_vnums)


# --- Traps / bombs (defensive structures near a capture point) -----------

# Per explicit request: traps placed in an approach room near a
# capture point (not the point itself, unlike garrison mobs), that
# check an entering player's village and the war window before
# triggering. Two types: a reusable snare (moderate damage, entangles
# the target so they can't just walk past it toward the point) and a
# one-time bomb (bigger damage, no entangle, destroyed after it goes
# off once -- an "exploding" structure has to actually be consumed to
# read as an explosion rather than a wall).
TRAP_TYPES = {
    "snare": {"display_name": "Snare Trap", "cost": 150, "min_damage": 15, "max_damage": 30,
              "entangles": True, "consumed_on_trigger": False},
    "bomb": {"display_name": "Bomb", "cost": 400, "min_damage": 40, "max_damage": 70,
             "entangles": False, "consumed_on_trigger": True},
}
MAX_TRAP_DISTANCE = 2  # "within 1-2 rooms of the capture point", per explicit request


def trap_mob_vnum(village: str, trap_type: str) -> int:
    """The one, fixed mob template vnum for a given village+trap-type
    combo -- same one-template-reused-everywhere pattern as
    garrison_mob_vnum. Base 6850, a separate range from garrison's
    6950 -- these are two different concepts (a point's own defenders
    vs. a nearby approach-room hazard), so keeping their vnum ranges
    distinct too avoids any chance of the two ever being confused."""
    import data_villages
    village_index = list(data_villages.VILLAGES.keys()).index(village)
    type_index = list(TRAP_TYPES.keys()).index(trap_type)
    return 6850 + village_index * 10 + type_index


def rooms_within_steps(start_vnum: int, max_steps: int) -> set:
    """Every room vnum reachable from start_vnum within max_steps
    exits (breadth-first, direction-agnostic), NOT including
    start_vnum itself. Used to validate a trap is actually placed near
    a capture point, not just anywhere in the world."""
    import world

    visited = {start_vnum}
    frontier = {start_vnum}
    reachable = set()
    for _ in range(max_steps):
        next_frontier = set()
        for vnum in frontier:
            room = world.WORLD.get(vnum)
            if not room:
                continue
            for dest in room.exits.values():
                if dest not in visited:
                    visited.add(dest)
                    next_frontier.add(dest)
                    reachable.add(dest)
        frontier = next_frontier
        if not frontier:
            break
    return reachable


def nearest_owned_point_within_range(village: str, room_vnum: int):
    """The vnum of a capture point `village` currently owns, within
    MAX_TRAP_DISTANCE of room_vnum -- or None if there isn't one
    (either no owned point is close enough, or room_vnum IS itself a
    capture point, which isn't a valid trap placement -- traps are for
    the approach, not the point)."""
    if room_vnum in all_capture_point_vnums():
        return None
    nearby = rooms_within_steps(room_vnum, MAX_TRAP_DISTANCE)
    for vnum in all_capture_point_vnums():
        if vnum in nearby and point_state(vnum)["owner"] == village:
            return vnum
    return None


def trap_at(room_vnum: int):
    """The trap entry ({"village", "trap_type"}) placed at room_vnum,
    or None if there isn't one."""
    return _state().get("traps", {}).get(str(room_vnum))


def buy_trap(village: str, room_vnum: int, trap_type: str) -> str:
    """Attempts to place a new trap of the given type at room_vnum for
    `village`. Returns "" on success, or a human-readable reason it
    failed -- the caller (commands.py) sends that straight to the
    player."""
    if trap_type not in TRAP_TYPES:
        return f"'{trap_type}' isn't a trap type. Choose one of: {', '.join(TRAP_TYPES.keys())}."
    if trap_at(room_vnum) is not None:
        return "There's already a trap in this room."
    if nearest_owned_point_within_range(village, room_vnum) is None:
        return f"This isn't within {MAX_TRAP_DISTANCE} rooms of a capture point your village controls."

    cost = TRAP_TYPES[trap_type]["cost"]
    if not deduct_treasury(village, cost):
        return f"Your village treasury needs {cost:,} ryo for that -- it only has {treasury_balance(village):,}."

    import combat
    vnum = trap_mob_vnum(village, trap_type)
    combat.spawn_mob(vnum, room_vnum)

    state = _state()
    state.setdefault("traps", {})[str(room_vnum)] = {"village": village, "trap_type": trap_type}
    _save(state)
    return ""


def remove_trap(room_vnum: int) -> bool:
    """Removes whatever trap is at room_vnum (its spawned mob
    instance, if any, plus its tracked state), if one exists. Used
    both by staff cleanup and automatically when a one-time bomb
    consumes itself on trigger."""
    import combat

    state = _state()
    entry = state.get("traps", {}).pop(str(room_vnum), None)
    if entry is None:
        return False
    trap_vnum = trap_mob_vnum(entry["village"], entry["trap_type"])
    for mob in list(combat.mobs_in_room(room_vnum)):
        if mob.template_vnum == trap_vnum:
            combat.remove_mob(mob)
    _save(state)
    return True


def check_trap_trigger(player) -> Optional[str]:
    """Called when a player arrives in a new room (see commands.
    _fire_enter_triggers) -- if that room has a trap belonging to a
    DIFFERENT village than the player's own, AND a war window is
    currently active, the trap triggers: real damage, and (for a
    snare specifically) the "entangled" status effect. A bomb is
    destroyed after triggering once; a snare stays and can trigger
    again. Returns a message to send the player, or None if nothing
    happened (no trap here, player's own village's trap, or no war
    window active right now)."""
    entry = trap_at(player.room_vnum)
    if entry is None or entry["village"] == player.village or not war_window_active():
        return None

    import random
    import status_effects

    trap_info = TRAP_TYPES[entry["trap_type"]]
    damage = random.randint(trap_info["min_damage"], trap_info["max_damage"])
    player.health = max(1, player.health - damage)

    message = f"&rA {trap_info['display_name'].lower()} triggers! You take {damage_messages.describe_damage(damage)} damage!&x"
    if trap_info["entangles"]:
        status_effects.apply_effect(player.active_status_effects, "entangled", source="trap")
        message += " You're entangled!"
    if trap_info["consumed_on_trigger"]:
        remove_trap(player.room_vnum)
        message += " The bomb is spent."
    return message


# --- War windows ----------------------------------------------------------

def war_window_active() -> bool:
    state = _state()
    window = state.get("war_window", {})
    active_until = window.get("active_until")
    return active_until is not None and time.time() < active_until


def war_window_status() -> dict:
    """{'active': bool, 'ends_at'/'starts_at': timestamp or None} for
    display -- 'territory' command and similar."""
    state = _state()
    window = state.get("war_window", {})
    if war_window_active():
        return {"active": True, "ends_at": window["active_until"]}
    return {"active": False, "starts_at": window.get("scheduled_at")}


def ensure_war_window_scheduled(broadcast_fn=None) -> None:
    """Called once per pulse (see server.py) -- if there's no window
    currently active or scheduled, picks a random future time within
    [WAR_WINDOW_MIN_DELAY_SECONDS, WAR_WINDOW_MAX_DELAY_SECONDS] and
    saves it, calling broadcast_fn(message) once to announce it (per
    explicit request: always announced ahead of time, never a surprise
    or a fixed predictable slot). Also flips a scheduled window into
    "active" once its time arrives, and clears an active window back to
    "nothing scheduled" once it ends -- so the very next tick picks a
    fresh random time for the one after that."""
    state = _state()
    window = state.setdefault("war_window", {})
    now = time.time()

    if window.get("active_until") is not None and now >= window["active_until"]:
        window["active_until"] = None
        window["scheduled_at"] = None
        if broadcast_fn:
            broadcast_fn("&rThe war window has ended. Contested points are safe again.&x")

    if window.get("active_until") is None and window.get("scheduled_at") is not None and now >= window["scheduled_at"]:
        window["active_until"] = now + WAR_WINDOW_DURATION_SECONDS
        window["scheduled_at"] = None
        if broadcast_fn:
            minutes = WAR_WINDOW_DURATION_SECONDS // 60
            broadcast_fn(f"&r*** A WAR WINDOW HAS OPENED! *** &xContested points can be captured for the next {minutes} minutes!")

    if window.get("active_until") is None and window.get("scheduled_at") is None:
        delay = random.randint(WAR_WINDOW_MIN_DELAY_SECONDS, WAR_WINDOW_MAX_DELAY_SECONDS)
        window["scheduled_at"] = now + delay
        if broadcast_fn:
            hours = delay // 3600
            broadcast_fn(f"&YThe next war window has been scheduled -- roughly {hours} hour(s) from now.&x")

    _save(state)


# --- Income tick ------------------------------------------------------

def tick_income(broadcast_fn=None) -> None:
    """Called periodically (see server.py's pulse loop) -- every
    village earns BASE_INCOME_PER_TICK regardless of holdings, plus
    each currently-owned point's own area income on top."""
    import data_villages

    state = _state()
    for village in data_villages.VILLAGES:
        _add_treasury(state, village, BASE_INCOME_PER_TICK)
    for vnum in all_capture_point_vnums():
        point = state.get("points", {}).get(str(vnum), {})
        owner = point.get("owner")
        if owner:
            _add_treasury(state, owner, point_income(vnum))
    _save(state)


# --- Capture progress tick -------------------------------------------

def tick_captures(broadcast_fn=None) -> None:
    """Called every pulse (see server.py) -- advances or resets each
    capture point's hold progress based on LIVE conditions right now,
    not just what happened at the moment a garrison mob died. Only
    does anything while a war window is active; outside one, every
    point is simply inert (no progress is lost, it just doesn't
    advance -- see the module docstring)."""
    if not war_window_active():
        return

    import session as session_module

    state = _state()
    changed = False
    for vnum in all_capture_point_vnums():
        point = point_state(vnum)
        garrison_alive = _live_garrison_count(vnum) > 0
        present_villages = {
            s.player.village for s in session_module.ACTIVE_SESSIONS
            if s.state == session_module.State.PLAYING and s.player and s.player.room_vnum == vnum
            and s.player.village != point["owner"]
        }

        if garrison_alive or not present_villages:
            if point["contested_by"] is not None:
                point["contested_by"] = None
                point["hold_started_at"] = None
                _save_point_state(state, vnum, point)
                changed = True
            continue

        if len(present_villages) > 1:
            # More than one rival village present at once blocks
            # progress entirely -- neither gets to sneak through just
            # because one of them happens to match a stale holder from
            # before the other one arrived.
            if point["contested_by"] is not None:
                point["contested_by"] = None
                point["hold_started_at"] = None
                _save_point_state(state, vnum, point)
                changed = True
            continue

        attacker = next(iter(present_villages))

        if point["contested_by"] != attacker:
            point["contested_by"] = attacker
            point["hold_started_at"] = time.time()
            _save_point_state(state, vnum, point)
            changed = True
        elif time.time() - point["hold_started_at"] >= HOLD_DURATION_SECONDS:
            old_owner = point["owner"]
            point["owner"] = attacker
            point["garrison"] = []
            point["contested_by"] = None
            point["hold_started_at"] = None
            _save_point_state(state, vnum, point)
            changed = True
            if broadcast_fn:
                import world
                room = world.WORLD.get(vnum)
                room_name = room.name if room else f"room {vnum}"
                broadcast_fn(
                    f"&r*** {attacker.upper()} HAS CAPTURED {room_name.upper()}"
                    f"{' FROM ' + old_owner.upper() if old_owner else ''}! ***&x"
                )

    if changed:
        _save(state)
