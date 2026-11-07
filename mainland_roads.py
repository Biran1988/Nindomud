"""One-time, collision-safe installation of the mainland road network into /data.

All long-distance road rooms belong to the existing Mainland Road Network area.
Country and village entrance rooms are single-exit SPURS off the roads; no
route requires walking into a village to continue past it.

Installer merges only newly allocated road rooms and one reciprocal exit on
each designated country entrance. Existing /data files, players, areas, mobs,
objects and unrelated rooms remain unchanged. Reboot never repeats an install.
"""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import math
import os

FIRST_VNUM = 20501
LAST_VNUM = 30500
MARKER_NAME = ".mainland_road_network_20501_installed.json"

# The first road room is the junction SOUTH of Konoha room 9.
# It exits NORTH into room 9 and is otherwise connected to the highway.
JUNCTIONS = (
    ("leaf_gate", "Konoha Southern Crossroads", "forest"),
    ("leaf_west", "Fire Country Western Fork", "forest"),
    ("leaf_east", "Fire Country Eastern Fork", "forest"),
    ("leaf_south", "Fire Country Southern Fork", "plains"),
    ("stone", "Stone Country Roadhead", "mountain"),
    ("grass", "Grass Country Roadhead", "forest"),
    ("rain", "Rain Country Roadhead", "swamp"),
    ("rivers", "Rivers Country Roadhead", "river"),
    ("birds", "Bird Country Roadhead", "plains"),
    ("waterfall", "Waterfall Country Roadhead", "forest"),
    ("sound", "Sound Country Roadhead", "forest"),
    ("frost", "Frost Country Roadhead", "mountain"),
    ("hotwater", "Hot Water Country Roadhead", "plains"),
    ("cloud", "Cloud Country Roadhead", "mountain"),
    ("sand", "Sand Country Roadhead", "desert"),
)

# name, area reservation, first VNUM, road-junction name, exit FROM road.
# Mist/Water and Whirlpool deliberately have no highway connections.
DESTINATIONS = (
    ("Leaf", "leaf", 9, "leaf_gate", "north", 1, 2500),
    ("Stone", "stone", 2501, "stone", "northwest", 2501, 5000),
    ("Cloud", "cloud", 7501, "cloud", "northeast", 7501, 10000),
    ("Sand", "sand", 10001, "sand", "southwest", 10001, 12500),
    ("Grass", "land of grass", 12501, "grass", "north", 12501, 13500),
    ("Rain", "land of rain", 13501, "rain", "south", 13501, 14500),
    ("Rivers", "land of rivers", 14501, "rivers", "south", 14501, 15500),
    ("Birds", "land of birds", 15501, "birds", "west", 15501, 16500),
    ("Waterfall", "land of waterfalls", 16501, "waterfall", "north", 16501, 17500),
    ("Sound", "land of sound", 17501, "sound", "south", 17501, 18500),
    ("Frost", "land of frost", 18501, "frost", "north", 18501, 19500),
    ("Hot Water", "land of hot water", 19501, "hotwater", "south", 19501, 20500),
)

# Each edge count is the exact number of traversable steps between
# roadside junctions. The first/last compass headings preserve the
# relative geography; intervening headings arc gently (not straight
# corridors and not arbitrary repeated backtracking).
# a, b, steps, exit at a, exit at b, road title, biome
SEGMENTS = (
    ("leaf_gate", "leaf_west", 5, "west", "east", "Konoha West Approach", "forest"),
    ("leaf_gate", "leaf_east", 5, "east", "west", "Konoha East Approach", "forest"),
    ("leaf_gate", "leaf_south", 5, "south", "north", "Konoha South Approach", "forest"),
    ("stone", "grass", 105, "southeast", "northwest", "Stone-Grass Foothill Road", "mountain"),
    ("grass", "leaf_west", 85, "southeast", "northwest", "Grassland Border Trail", "forest"),
    ("stone", "rain", 118, "south", "north", "Earth-Rain Canyon Road", "mountain"),
    ("rain", "leaf_west", 90, "east", "west", "Rain-Fire Trade Road", "forest"),
    ("rain", "sand", 114, "southwest", "north", "Rain-Wind Caravan Road", "plains"),
    ("leaf_south", "rivers", 95, "southwest", "northeast", "Rivers Country Causeway", "river"),
    ("rivers", "sand", 80, "southwest", "northeast", "Windward River Highway", "desert"),
    ("leaf_east", "hotwater", 112, "east", "west", "Eastern Pilgrim Road", "plains"),
    ("hotwater", "cloud", 93, "northeast", "south", "Lightning Mountain Approach", "mountain"),
    ("leaf_east", "sound", 80, "north", "southwest", "Sound Border Trail", "forest"),
    ("sound", "frost", 55, "northeast", "south", "Northern Sound Ridge", "mountain"),
    ("frost", "cloud", 75, "northeast", "southwest", "Frost-Cloud Pass", "mountain"),
    ("leaf_east", "waterfall", 108, "northeast", "south", "Hidden Waterfall Highway", "forest"),
    ("waterfall", "frost", 30, "northeast", "southwest", "Northern Escarpment Road", "mountain"),
    ("stone", "birds", 108, "southwest", "northeast", "Western Plateau Road", "mountain"),
    ("birds", "sand", 107, "southeast", "northwest", "Bird-Wind Caravan Route", "desert"),
    ("grass", "waterfall", 36, "east", "southwest", "Grassfall Woodland Connector", "forest"),
    ("waterfall", "sound", 28, "east", "west", "Northern Gulf Coastal Road", "plains"),
)

HEADINGS = ("north", "northeast", "east", "southeast", "south",
            "southwest", "west", "northwest")
REVERSE = {heading: HEADINGS[(i + 4) % 8] for i, heading in enumerate(HEADINGS)}

class RoadInstallationError(ValueError):
    """Abort the whole migration rather than overwriting an existing room."""


def _link(rooms, a, direction, b):
    reverse = REVERSE[direction]
    if direction in rooms[a].exits:
        raise RoadInstallationError(f"Road {a} already has a {direction} exit.")
    if reverse in rooms[b].exits:
        raise RoadInstallationError(f"Road {b} already has a {reverse} exit.")
    rooms[a].exits[direction] = b
    rooms[b].exits[reverse] = a


def _headings(first, last, steps):
    """Gentle S-bend with a few long runs and gradual turns."""
    start, finish = HEADINGS.index(first), HEADINGS.index(last)
    delta = (finish - start + 4) % 8 - 4
    headings = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        # One broad arc in each direction, at most 45 degrees off course.
        bend = math.sin(2 * math.pi * t) * 0.9 if steps >= 18 else 0
        index = round(start + delta * t + bend) % 8
        headings.append(HEADINGS[index])
    headings[0], headings[-1] = first, last
    return headings


def build_rooms():
    """Return (road rooms, named junction VNUMs); deterministic and pure."""
    from world import Room
    roads = {}
    hubs = {}
    next_vnum = FIRST_VNUM

    for key, title, biome in JUNCTIONS:
        vnum = next_vnum
        next_vnum += 1
        hubs[key] = vnum
        room = Room(vnum, title,
                    "A maintained highway branches at a stone waymarker. "
                    "Travelers can continue between countries without entering "
                    "the villages along the route.", sector="field")
        room.biome = biome
        roads[vnum] = room

    for a, b, steps, first, final_port, title, biome in SEGMENTS:
        if steps < 1:
            raise RoadInstallationError(f"Invalid road length for {title}")
        chain = [hubs[a]]
        for index in range(steps - 1):
            vnum = next_vnum
            next_vnum += 1
            phase = index / max(1, steps - 2)
            setting = ("outer trail" if phase < .28 else
                       "winding passage" if phase < .70 else "border approach")
            room = Room(vnum, f"{title} - {setting}",
                        f"The {title.lower()} follows gentle curves through "
                        f"the {biome} country. A worn trail leads toward "
                        f"{a.replace('_', ' ').title()} and "
                        f"{b.replace('_', ' ').title()}.",
                        sector="field")
            room.biome = biome
            roads[vnum] = room
            chain.append(vnum)
        chain.append(hubs[b])
        directions = _headings(first, REVERSE[final_port], steps)
        for i, direction in enumerate(directions):
            _link(roads, chain[i], direction, chain[i + 1])

    for title, area, vnum, hub, exit_direction, start, end in DESTINATIONS:
        if exit_direction in roads[hubs[hub]].exits:
            raise RoadInstallationError(
                f"{hub} has no free {exit_direction} exit for {title}")
        # A destination is linked into the world ONLY by install_once().
        # The planned single exit is reserved in this new roadside junction.
        roads[hubs[hub]].exits[exit_direction] = vnum

    if next_vnum - 1 > LAST_VNUM:
        raise RoadInstallationError("Road construction exceeds reserved area.")
    return roads, hubs


def ensure_live_mainland_area():
    """Mark only the reserved mainland road area live, including old installations.

    This changes areas.json metadata, NOT any area boundaries or saved rooms.
    Preserve builders and prototype ownership records for auditing; only
    the prototype restriction itself is turned off.
    """
    import storage
    registry = storage.load_areas()
    key = next((key for key, entry in registry.items()
                if entry.get("name", "").casefold() == "mainland road network"), None)
    if key is None:
        return False  # A missing area cannot be invented without inspecting reservations.
    entry = registry[key]
    if (entry.get("vnum_start"), entry.get("vnum_end")) != (FIRST_VNUM, LAST_VNUM):
        raise RoadInstallationError(
            "Mainland Road Network reservation differs from 20501-30500; area left unchanged.")
    if entry.get("prototype") is False:
        return False
    updated = deepcopy(registry)
    updated[key]["prototype"] = False
    storage.save_areas(updated)
    return True


def repair_leaf_gate():
    """Repair a missing Leaf south -> 20501 / road north -> 9 connection.

    Do this even after the original one-time installer marker exists. Never
    steal an occupied exit or recreate/overwrite either room's other fields.
    """
    import storage
    import world
    leaf, road = world.WORLD.get(9), world.WORLD.get(FIRST_VNUM)
    if leaf is None or road is None:
        return False
    # A saved placeholder can occupy 20501 even while other road rooms
    # exist. Never connect the village to that unrelated/unfinished room.
    # A legitimate crossroads must match the named road junction and have
    # real onward routes, not merely the numeric VNUM reservation.
    if road.name != "Konoha Southern Crossroads":
        return False
    onward = [destination for heading, destination in road.exits.items()
              if heading != "north" and FIRST_VNUM <= destination <= LAST_VNUM
              and world.WORLD.get(destination) is not None]
    if len(set(onward)) < 2:
        return False
    if (leaf.exits.get("south") not in (None, FIRST_VNUM)
            or road.exits.get("north") not in (None, 9)):
        return False  # Existing builder links win; report conflicts separately.
    if leaf.exits.get("south") == FIRST_VNUM and road.exits.get("north") == 9:
        return False
    state = storage.load_world_state()
    if not isinstance(state.get("rooms"), dict):
        return False
    if str(9) not in state["rooms"] or str(FIRST_VNUM) not in state["rooms"]:
        return False
    # The saved snapshot is authoritative: do not overrule any saved exit.
    saved_leaf = state["rooms"]["9"].get("exits", {})
    saved_road_data = state["rooms"][str(FIRST_VNUM)]
    if saved_road_data.get("name") != "Konoha Southern Crossroads":
        return False
    saved_road = saved_road_data.get("exits", {})
    if (saved_leaf.get("south") not in (None, FIRST_VNUM)
            or saved_road.get("north") not in (None, 9)):
        return False
    merged = deepcopy(state)
    merged["rooms"]["9"]["exits"]["south"] = FIRST_VNUM
    merged["rooms"][str(FIRST_VNUM)]["exits"]["north"] = 9
    storage.save_world_state(merged)
    leaf.exits["south"] = FIRST_VNUM
    road.exits["north"] = 9
    return True


def _validate_areas():
    import areas
    actual = {entry["name"].casefold(): entry for entry in areas.all_areas().values()}
    required = [("Mainland Road Network", FIRST_VNUM, LAST_VNUM)]
    required += [(area, start, end)
                 for _, area, _, _, _, start, end in DESTINATIONS]
    for name, start, end in required:
        entry = actual.get(name.casefold())
        if not entry or (entry["vnum_start"], entry["vnum_end"]) != (start, end):
            raise RoadInstallationError(
                f"Area {name!r} must be reserved at {start}-{end} first.")


def _checked_rooms(world_obj, road_rooms, hubs):
    """Stage a complete plan without editing live rooms or occupied exits."""
    from world import Room
    staged = {}
    for vnum in road_rooms:
        if world_obj.get(vnum) is not None:
            raise RoadInstallationError(
                f"Road VNUM {vnum} is occupied. No rooms or exits were changed.")
    for title, area, vnum, hub, direction, start, end in DESTINATIONS:
        existing = world_obj.get(vnum)
        if vnum == 9 and existing is None:
            raise RoadInstallationError(
                "Konoha room 9 must exist before its south exit can connect.")
        room = deepcopy(existing) if existing else Room(
            vnum, f"{title} Country Entrance",
            f"A simple entrance marks the border of {title} Country.",
            sector="field")
        reverse = REVERSE[direction]
        if reverse in room.exits:
            raise RoadInstallationError(
                f"{title} entrance {vnum} already uses its {reverse} exit; "
                "no existing exit will be overwritten.")
        room.exits[reverse] = hubs[hub]
        staged[vnum] = room
    return staged


def install_once():
    """Merge the graph and first-room entrances into saved /data exactly once.

    A failed preflight does not write or change any area/room. Existing
    snapshots retain all other rooms, player structures and custom data.
    """
    import storage
    import world

    marker = Path(storage.DATA_DIR) / MARKER_NAME
    if marker.exists():
        return False
    _validate_areas()
    roads, hubs = build_rooms()
    state = storage.load_world_state()
    if not isinstance(state, dict) or not isinstance(state.get("rooms", {}), dict):
        raise RoadInstallationError("World state must contain a rooms dictionary.")

    saved = state.get("rooms", {})
    for vnum in roads:
        if str(vnum) in saved:
            raise RoadInstallationError(
                f"Saved road VNUM {vnum} already exists; nothing overwritten.")
    staged_entrances = _checked_rooms(world.WORLD, roads, hubs)

    # Work on a copy, preserving other data fields and unrelated VNUMs.
    merged = deepcopy(state)
    merged_rooms = merged.setdefault("rooms", {})
    for vnum, room in roads.items():
        merged_rooms[str(vnum)] = {k: v for k, v in asdict(room).items() if k != "ground_ryo"}
    for vnum, room in staged_entrances.items():
        merged_rooms[str(vnum)] = {k: v for k, v in asdict(room).items() if k != "ground_ryo"}

    # Uses the normal atomic world write and .bak backup.
    storage.save_world_state(merged)
    world.WORLD.rooms.update(roads)
    world.WORLD.rooms.update(staged_entrances)

    marker.parent.mkdir(parents=True, exist_ok=True)
    temp = marker.with_name(marker.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as file:
            json.dump({"version": 1, "first_vnum": FIRST_VNUM,
                       "last_built_vnum": max(roads), "rooms": len(roads),
                       "entrances": [item[2] for item in DESTINATIONS]}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, marker)
    finally:
        if temp.exists():
            temp.unlink()
    return True
