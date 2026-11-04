"""One-time, bounded installation of the 25 x 25 Forest of Death map.

Only room VNUMs 45..669 are replaced. Existing data/world_state.json is
merged, not replaced wholesale. The persisted install marker prevents a later
release from overwriting builders' subsequent changes to these rooms.
"""

from dataclasses import asdict
from pathlib import Path
import json
import os

FIRST_VNUM = 45
WIDTH = HEIGHT = 25
LAST_VNUM = FIRST_VNUM + WIDTH * HEIGHT - 1
ENTRANCE_VNUM = FIRST_VNUM
TOWER_VNUM = FIRST_VNUM + (HEIGHT // 2) * WIDTH + WIDTH // 2
MARKER_NAME = ".forest_of_death_45_669_installed.json"


def vnum_at(x: int, y: int) -> int:
    """Zero-based grid position: (0, 0) is the southwest corner."""
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        raise ValueError("Forest coordinates must be within the 25x25 grid")
    return FIRST_VNUM + y * WIDTH + x


def build_rooms() -> dict:
    """Create a complete, bidirectional, four-direction square grid."""
    from world import Room

    rooms = {}
    for y in range(HEIGHT):
        for x in range(WIDTH):
            vnum = vnum_at(x, y)
            exits = {}
            if y < HEIGHT - 1:
                exits["north"] = vnum_at(x, y + 1)
            if y > 0:
                exits["south"] = vnum_at(x, y - 1)
            if x < WIDTH - 1:
                exits["east"] = vnum_at(x + 1, y)
            if x > 0:
                exits["west"] = vnum_at(x - 1, y)

            if vnum == ENTRANCE_VNUM:
                name = "Forest of Death -- Entrance"
                description = (
                    "A forbidding perimeter fence fades into the trees behind you. "
                    "The Forest of Death stretches north and east beneath a dense canopy."
                )
            elif vnum == TOWER_VNUM:
                name = "Forest of Death -- Central Tower"
                description = (
                    "An imposing stone tower rises in a broad clearing deep in the "
                    "Forest of Death. Trials are completed within its walls."
                )
            else:
                name = "Forest of Death"
                description = (
                    "Towering trees and tangled roots crowd a shadowy forest path. "
                    "Distant movement stirs the undergrowth."
                )

            room = Room(vnum, name, description, sector="forest", exits=exits)
            room.biome = "forest"
            if vnum in (ENTRANCE_VNUM, TOWER_VNUM):
                room.safe = True
            rooms[vnum] = room
    return rooms


def populate_world(world_obj=None) -> None:
    """Fresh defaults. A saved world can still override builder edits on boot."""
    import world
    if world_obj is None:
        world_obj = world.WORLD
    for room in build_rooms().values():
        world_obj.add_room(room)


def install_once() -> bool:
    """Merge exactly the 625 requested room VNUMs into the live saved data.

    Runs *after* content.populate() has restored all saved rooms. Do not ship
    a substitute data/world_state.json file: the live one contains users'
    customized rooms, mobs, and item templates. Unlike a wholesale import,
    this operation retains every other save-field and room VNUM untouched.
    """
    import storage
    import world

    marker = Path(storage.DATA_DIR) / MARKER_NAME
    if marker.exists():
        return False
    rooms = build_rooms()
    state = storage.load_world_state()
    if not isinstance(state, dict):
        raise ValueError("Invalid world save: expected JSON object")
    saved_rooms = state.setdefault("rooms", {})
    if not isinstance(saved_rooms, dict):
        raise ValueError("Invalid world save: expected rooms object")
    for vnum, room in rooms.items():
        saved_rooms[str(vnum)] = asdict(room)

    # This save is atomic and preserves a .bak of the prior complete file.
    storage.save_world_state(state)
    for room in rooms.values():
        world.WORLD.add_room(room)

    # Commit the marker *after* the data save. A later reboot must never
    # reset an editor's adjustments to the forest's rooms or exits.
    marker.parent.mkdir(parents=True, exist_ok=True)
    tmp = marker.with_name(marker.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as file:
            json.dump({"first_vnum": FIRST_VNUM, "last_vnum": LAST_VNUM,
                       "rooms": WIDTH * HEIGHT, "version": 1}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, marker)
    finally:
        if tmp.exists():
            tmp.unlink()
    return True


# VNUM 670 is intentionally outside the original 45..669 forest migration.
FINAL_ROOM_MARKER = ".forest_of_death_final_670_installed.json"


def build_final_room():
    """The sealed, single-room Chunin 1v1 battleground."""
    from world import Room
    room = Room(670, "Forest of Death -- Final Trial Chamber",
                "A sealed stone chamber surrounds you. The proctor's barrier "
                "leaves no exit; only victory or forfeiture will release you.",
                sector="inside", exits={})
    room.safe = True
    return room


def populate_final_room(world_obj=None):
    import world
    (world_obj or world.WORLD).add_room(build_final_room())


def install_final_room_once() -> bool:
    """Replace saved VNUM 670 exactly once, keeping every other /data entry."""
    import storage
    import world

    marker = Path(storage.DATA_DIR) / FINAL_ROOM_MARKER
    if marker.exists():
        return False
    state = storage.load_world_state()
    if not isinstance(state, dict):
        raise ValueError("Invalid world save: expected JSON object")
    saved_rooms = state.setdefault("rooms", {})
    if not isinstance(saved_rooms, dict):
        raise ValueError("Invalid world save: expected rooms object")
    room = build_final_room()
    saved_rooms[str(room.vnum)] = asdict(room)
    storage.save_world_state(state)
    world.WORLD.add_room(room)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temp = marker.with_name(marker.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as file:
            json.dump({"vnum": 670, "version": 1}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, marker)
    finally:
        if temp.exists():
            temp.unlink()
    return True
