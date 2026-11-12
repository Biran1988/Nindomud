"""Coordinate-based ocean navigation inspired by SMAUG space travel.

The ocean is NOT a grid of rooms. Boats own ONE private helm/cabin room;
ship positions and courses are persisted as scalar X/Z coordinates. Registered
ports connect that simulated ocean back to existing land rooms only at dock.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from typing import Optional

import storage
import world

OCEAN_SIZE = 20_000.0       # X and Z both span 0 through 20,000
CRUISE_SPEED = 25.0       # ocean coordinate units per second
DETECT_RADIUS = 100.0
DOCK_RADIUS = 50.0
BORDER_RETREAT = 500.0
BOAT_PRICE_RYO = 75_000
BOAT_VNUM_BASE = 9_000_000_000  # deliberately outside regular builder/area vnums


def boat_room_vnum(player) -> int:
    unique = f"{player.account_name.casefold()}:{player.name.casefold()}".encode()
    return BOAT_VNUM_BASE + int(hashlib.sha256(unique).hexdigest()[:13], 16)


def state(player) -> dict:
    """Never auto-grant ownership; handle old player saves with no boat field."""
    value = getattr(player, "boat_state", None)
    return value if isinstance(value, dict) else {}


def is_aboard(player) -> bool:
    return bool(state(player).get("owned")) and player.room_vnum == boat_room_vnum(player)


def _port_file() -> str:
    return os.path.join(storage.DATA_DIR, "ocean_ports.json")


def ports() -> list[dict]:
    """Port locations are durable staff-managed data, not area/room changes."""
    filename = _port_file()
    if not os.path.isfile(filename):
        return []
    with open(filename, encoding="utf-8") as handle:
        contents = json.load(handle)
    if not isinstance(contents, list):
        raise ValueError("Invalid ocean port registry")
    result = []
    for entry in contents:
        if (not isinstance(entry, dict) or not isinstance(entry.get("name"), str)
                or not isinstance(entry.get("room_vnum"), int)
                or not isinstance(entry.get("x"), (int, float))
                or not isinstance(entry.get("z"), (int, float))
                or not 0 <= entry["x"] <= OCEAN_SIZE
                or not 0 <= entry["z"] <= OCEAN_SIZE):
            raise ValueError("Invalid ocean port entry")
        result.append(entry)
    return result


def save_ports(entries: list[dict]) -> None:
    storage.ensure_dirs()
    filename = _port_file()
    fd, temp = tempfile.mkstemp(prefix=".ocean-ports-", dir=storage.DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(entries, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, filename)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _port_key(name: str) -> str:
    return " ".join(name.casefold().split())


def _find_port(name: str, entries: Optional[list[dict]] = None):
    return next((p for p in (ports() if entries is None else entries)
                 if _port_key(p["name"]) == _port_key(name)), None)


def _distance(boat: dict, port: dict) -> float:
    return math.hypot(float(boat.get("x", 0)) - port["x"],
                      float(boat.get("z", 0)) - port["z"])


def _describe(boat: dict) -> str:
    x, z = float(boat["x"]), float(boat["z"])
    goal = boat.get("course")
    course = (f"Current course: X {goal[0]:.0f}, Z {goal[1]:.0f}."
              if goal is not None else "Engines at rest.")
    docked = f"Docked at {boat['docked']}" if boat.get("docked") else "At sea"
    return ("A small wooden cabin and a steering helm overlook the water. "
            "There are no ocean room exits; steer with COURSE <x> <z>.\n"
            f"{docked}. Ocean position: X {x:.1f}, Z {z:.1f}. {course}\n"
            "Use DOCK to search for ports within 100 units, DOCK <name> "
            "within 50 units, or DISEMBARK when berthed.")


def ensure_boat_room(player):
    """Rebuild the ONE physical interior after restart/reconnect, if owned."""
    boat = state(player)
    if not boat.get("owned"):
        return None
    boat.setdefault("x", 0.0)
    boat.setdefault("z", 0.0)
    boat.setdefault("course", None)
    boat.setdefault("docked", None)
    boat.setdefault("discovered", [])
    vnum = boat_room_vnum(player)
    room = world.WORLD.get(vnum)
    if room is None:
        room = world.Room(vnum=vnum, name=f"{player.name}'s Boat - Helm",
                          description="", safe=True, flags=["boat"])
        world.WORLD.add_room(room)
    elif room.name != f"{player.name}'s Boat - Helm":
        raise ValueError("Private boat room vnum collision")
    room.description = _describe(boat)
    return room


def _save(player):
    ensure_boat_room(player)
    storage.save_player(player)


def _can_act(session) -> bool:
    if getattr(session, "combat_target", None) is not None or getattr(session, "pvp_target", None) is not None:
        session.send("You cannot handle the boat while fighting.")
        return False
    return True


def command_setport(session, args):
    if not session.account or session.account.staff_level == "player":
        session.send("Only immortals may place or remove ports.")
        return
    if not args:
        session.send("Usage: SETPORT <x> <z> <name> (in existing land room); SETPORT LIST; SETPORT REMOVE <name>.")
        return
    try:
        entries = ports()
    except (OSError, ValueError) as exc:
        session.send(f"Port registry unavailable: {exc}")
        return
    if args[0].casefold() == "list":
        session.send("Registered ocean ports:\n" + ("\n".join(
            f"  {p['name']} - X {p['x']}, Z {p['z']} - room {p['room_vnum']}" for p in entries
        ) if entries else "  (none)"))
        return
    if args[0].casefold() in ("remove", "delete"):
        name = " ".join(args[1:]).strip()
        if not name or _find_port(name, entries) is None:
            session.send("That port is not registered.")
            return
        removed = _find_port(name, entries)
        entries.remove(removed)
        save_ports(entries)
        session.send(f"Port {removed['name']} removed. Boats already docked there retain their saved coordinates.")
        return
    if len(args) < 3:
        session.send("Usage: SETPORT <x> <z> <port name> (while standing in its shoreline room).")
        return
    try:
        x, z = float(args[0]), float(args[1])
    except ValueError:
        session.send("Port X and Z must be numbers between 0 and 20,000.")
        return
    if not (math.isfinite(x) and math.isfinite(z) and 0 <= x <= OCEAN_SIZE and 0 <= z <= OCEAN_SIZE):
        session.send("Port coordinates must lie within X/Z 0 to 20,000.")
        return
    if is_aboard(session.player) or world.WORLD.get(session.player.room_vnum) is None:
        session.send("Stand in a real shoreline room to create a port, not aboard a boat.")
        return
    name = " ".join(args[2:]).strip()
    if not name or len(name) > 60 or any(c in name for c in "\r\n\x1e"):
        session.send("Give the port a name of 1-60 characters.")
        return
    existing = _find_port(name, entries)
    updated = {"name": name, "x": x, "z": z, "room_vnum": session.player.room_vnum}
    if existing:
        entries[entries.index(existing)] = updated
    else:
        entries.append(updated)
    save_ports(entries)
    session.send(f"Port {name} {'updated' if existing else 'created'} at X {x:g}, Z {z:g}, linked to room {session.player.room_vnum}.")


def buy_boat(session):
    player = session.player
    if state(player).get("owned"):
        session.send("You already own a boat. Use BOARD BOAT at its dock.")
        return
    if not _can_act(session):
        return
    try:
        port = next((p for p in ports() if p["room_vnum"] == player.room_vnum), None)
    except (OSError, ValueError):
        session.send("The harbor registry is unavailable.")
        return
    if not port:
        session.send("Buy your boat at a registered harbor (an immortal places one with SETPORT).")
        return
    if player.ryo < BOAT_PRICE_RYO:
        session.send(f"A basic boat costs {BOAT_PRICE_RYO:,} ryo; you have {player.ryo:,}.")
        return
    player.ryo -= BOAT_PRICE_RYO
    player.boat_state = {"owned": True, "x": port["x"], "z": port["z"],
                         "course": None, "docked": port["name"], "discovered": [port["name"]]}
    _save(player)
    session.send(f"You buy a one-room boat for {BOAT_PRICE_RYO:,} ryo, berthed at {port['name']}. Use BOARD BOAT to enter its helm.")


def command_board(session, args):
    player = session.player
    if not args or " ".join(args).casefold() not in ("boat", "my boat"):
        session.send("Usage: BOARD BOAT")
        return
    if not _can_act(session):
        return
    boat = state(player)
    if not boat.get("owned"):
        session.send("You don't own a boat. Use BUY BOAT at a registered harbor.")
        return
    if is_aboard(player):
        session.send("You're already aboard your boat.")
        return
    try:
        port = _find_port(boat.get("docked") or "")
    except (OSError, ValueError):
        session.send("The harbor registry is unavailable.")
        return
    if not port or player.room_vnum != port["room_vnum"]:
        session.send("Your boat is not berthed at this port. Return to its current dock to board.")
        return
    ensure_boat_room(player)
    player.room_vnum = boat_room_vnum(player)
    _save(player)
    session.send("You board your boat and step into the helm cabin.")
    import commands
    commands.cmd_look(session, [])


def command_status(session, args):
    if not state(session.player).get("owned"):
        session.send(f"You do not own a boat. Buy one for {BOAT_PRICE_RYO:,} ryo at a registered harbor.")
        return
    boat = state(session.player)
    session.send(_describe(boat))


def command_course(session, args):
    player = session.player
    if not is_aboard(player):
        session.send("You must BOARD BOAT and steer from its helm.")
        return
    if not _can_act(session):
        return
    if len(args) != 2:
        session.send("Usage: COURSE <x> <z>  (or VECTOR <x> <z>); ocean boundary 0-20,000.")
        return
    try:
        x, z = float(args[0]), float(args[1])
    except ValueError:
        session.send("Enter numeric X and Z coordinates.")
        return
    if not all(math.isfinite(n) and 0 <= n <= OCEAN_SIZE for n in (x, z)):
        session.send("Course coordinates must be between 0 and 20,000 on both axes.")
        return
    boat = state(player)
    if math.hypot(x - boat["x"], z - boat["z"]) <= 0.01:
        boat["course"] = None
        session.send("You're already at those coordinates. Engines stopped.")
    else:
        boat["course"] = [x, z]
        boat["docked"] = None
        session.send(f"Course locked: X {x:g}, Z {z:g}. Your boat turns toward the coordinates and gets underway.")
    _save(player)


def command_anchor(session, args):
    if not is_aboard(session.player):
        session.send("You must be aboard your boat to anchor it.")
        return
    boat = state(session.player)
    boat["course"] = None
    _save(session.player)
    session.send("You cut the engines and hold position.")


def command_dock(session, args):
    player = session.player
    if not is_aboard(player):
        session.send("You must be aboard your boat to search for docks.")
        return
    if not _can_act(session):
        return
    try:
        near = sorted([( _distance(state(player), port), port) for port in ports()
                       if world.WORLD.get(port["room_vnum"]) is not None], key=lambda item:item[0])
    except (OSError, ValueError):
        session.send("The harbor registry is unavailable.")
        return
    visible = [(d, port) for d, port in near if d <= DETECT_RADIUS]
    boat = state(player)
    if not args:
        if not visible:
            session.send("DOCK: No ports detected within 100 ocean units. Change COURSE and search again.")
            return
        for distance, port in visible:
            if port["name"] not in boat["discovered"]:
                boat["discovered"].append(port["name"])
            label = "in docking range" if distance <= DOCK_RADIUS else "approach closer"
            session.send(f"DOCK: {port['name']} - {distance:.1f} units away ({label}).")
        _save(player)
        session.send("Use DOCK <port name> within 50 units to berth.")
        return
    name = " ".join(args)
    match = next(((d,p) for d,p in visible if _port_key(p["name"]) == _port_key(name)), None)
    if not match:
        session.send("That port is not detected within 100 ocean units. Use DOCK to scan.")
        return
    distance, port = match
    if distance > DOCK_RADIUS:
        session.send(f"{port['name']} is {distance:.1f} units away. Steer within 50 units before docking.")
        return
    boat["course"] = None
    boat["x"], boat["z"] = port["x"], port["z"]
    boat["docked"] = port["name"]
    if port["name"] not in boat["discovered"]:
        boat["discovered"].append(port["name"])
    _save(player)
    session.send(f"You secure your boat at {port['name']}. DISEMBARK to enter the port room.")


def command_disembark(session, args):
    player = session.player
    if not is_aboard(player):
        session.send("You are not aboard a boat.")
        return
    if not _can_act(session):
        return
    boat = state(player)
    try:
        port = _find_port(boat.get("docked") or "")
    except (OSError, ValueError):
        session.send("The harbor registry is unavailable.")
        return
    if not port or world.WORLD.get(port["room_vnum"]) is None:
        session.send("You must DOCK at a registered port before disembarking.")
        return
    player.room_vnum = port["room_vnum"]
    _save(player)
    session.send(f"You disembark at {port['name']}.")
    import commands
    commands.cmd_look(session, [])


def tick_boats(sessions, dt=1.0):
    """One vector step per server pulse for each online piloted vessel."""
    if not math.isfinite(dt) or dt <= 0:
        return
    for session in list(sessions):
        if (getattr(getattr(session, "state", None), "name", "") != "PLAYING"
                or not getattr(session, "player", None)):
            continue
        player = session.player
        boat = state(player)
        if not boat.get("owned") or not is_aboard(player) or boat.get("course") is None:
            continue
        try:
            dx = float(boat["course"][0]) - float(boat["x"])
            dz = float(boat["course"][1]) - float(boat["z"])
            distance = math.hypot(dx, dz)
        except (ValueError, TypeError, IndexError, KeyError):
            boat["course"] = None
            _save(player)
            continue
        if distance < 0.001:
            boat["course"] = None
            _save(player)
            continue
        step = min(CRUISE_SPEED * dt, distance)
        current_x = float(boat["x"]) + dx / distance * step
        current_z = float(boat["z"]) + dz / distance * step
        boat["x"] = max(0.0, min(OCEAN_SIZE, current_x))
        boat["z"] = max(0.0, min(OCEAN_SIZE, current_z))
        hit_x = ((boat["x"] <= 0.0001 and dx < 0) or (boat["x"] >= OCEAN_SIZE - 0.0001 and dx > 0))
        hit_z = ((boat["z"] <= 0.0001 and dz < 0) or (boat["z"] >= OCEAN_SIZE - 0.0001 and dz > 0))
        if hit_x or hit_z:
            # Reverse any boundary-facing component, no escape/soft-lock.
            inland_x = (BORDER_RETREAT if boat["x"] <= 0.001 else
                        OCEAN_SIZE - BORDER_RETREAT if boat["x"] >= OCEAN_SIZE - 0.001
                        else boat["x"])
            inland_z = (BORDER_RETREAT if boat["z"] <= 0.001 else
                        OCEAN_SIZE - BORDER_RETREAT if boat["z"] >= OCEAN_SIZE - 0.001
                        else boat["z"])
            boat["course"] = [inland_x, inland_z]
            session.send("&YThe ocean boundary rises ahead! Your boat turns around toward open water.&x")
            _save(player)
        elif step >= distance - 0.0001:
            boat["course"] = None
            session.send(f"&CYou arrive at X {boat['x']:.0f}, Z {boat['z']:.0f}. Engines idle. Use DOCK to scan for nearby ports.&x")
            _save(player)
        else:
            # Autosave periodically during long voyages; never persist every tick.
            boat["unsaved_seconds"] = float(boat.get("unsaved_seconds", 0)) + dt
            if boat["unsaved_seconds"] >= 10:
                boat["unsaved_seconds"] = 0.0
                _save(player)
        ensure_boat_room(player)
