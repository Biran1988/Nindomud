"""Validated offline area packages for the Nindo visual area builder.

Imports add new VNUMs only. Existing rooms, prototypes, exits, and spawn
points are never overwritten. The import writes a full world snapshot, like
``save world``, so this new content survives the next restart.
"""

import copy
import dataclasses
import hashlib
import json
import os
import re
from collections import deque

import areas
import biomes
import combat
import olc
import spawn_points
import storage
import world
import world_persistence

FORMAT = "nindo-area-v1"
MAX_FILE_BYTES = 2_000_000
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.json\Z")


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _dice_range(value, fallback):
    match = re.fullmatch(r"(\d+)d(\d+)(?:\+(-?\d+))?", str(value))
    if not match:
        return fallback
    count, sides, bonus = int(match[1]), int(match[2]), int(match[3] or 0)
    return count + bonus, count * sides + bonus


def _room_row(room):
    return {"vnum": room.vnum, "name": room.name, "description": room.description,
            "sector": room.sector, "biome": room.biome, "safe": room.safe,
            "flags": list(room.flags), "reset_message": room.reset_message or "",
            "exits": dict(room.exits)}


def _mob_row(vnum, template, room_vnum):
    health = _dice_range(template.get("hit_dice", ""), (100, 100))[1]
    low, high = _dice_range(template.get("damage_dice", ""), (1, 4))
    return {"vnum": vnum, "name": template.get("short_desc", "Mob"),
            "level": template.get("level", 1), "health": health,
            "damage_min": low, "damage_max": high, "room_vnum": room_vnum,
            "respawns": template.get("respawns", True)}


def _item_row(vnum, template, room_vnum):
    return {"vnum": vnum, "name": template.get("short_desc", "Item"),
            "item_type": template.get("item_type", "misc"),
            "cost": template.get("cost", 0), "room_vnum": room_vnum}


def _layout_rooms(rooms, prior):
    """Lay out connected rooms by compass links; retain prior editor positions."""
    steps = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
             "northeast": (1, -1), "northwest": (-1, -1),
             "southeast": (1, 1), "southwest": (-1, 1)}
    by_id = {room.vnum: room for room in rooms}
    occupied = set()
    positions = {}
    for vnum, row in prior.items():
        if vnum in by_id and isinstance(row, dict):
            x, y = row.get("x"), row.get("y")
            if type(x) in (int, float) and type(y) in (int, float):
                cell = (max(0, min(40, round(x / 96))), max(0, min(30, round(y / 96))))
                if cell not in occupied:
                    positions[vnum] = cell
                    occupied.add(cell)

    def nearest(preferred):
        px, py = preferred
        return min(((x, y) for y in range(31) for x in range(41)
                    if (x, y) not in occupied),
                   key=lambda cell: (abs(cell[0]-px)+abs(cell[1]-py),
                                     abs(cell[1]-py), abs(cell[0]-px)))

    for room in rooms:
        if room.vnum not in positions:
            seed = nearest((20, 15))
            positions[room.vnum] = seed
            occupied.add(seed)
        queue = deque([room.vnum])
        while queue:
            current = by_id[queue.popleft()]
            cx, cy = positions[current.vnum]
            for direction, target in current.exits.items():
                if target not in by_id or target in positions or direction not in steps:
                    continue
                dx, dy = steps[direction]
                cell = nearest((cx+dx, cy+dy))
                positions[target] = cell
                occupied.add(cell)
                queue.append(target)
    return {vnum: {"x": cell[0]*96, "y": cell[1]*96} for vnum, cell in positions.items()}


def export_area(name: str, layout=None) -> tuple[str, dict]:
    """Export one reserved live area as an editable package with a safety baseline."""
    area = areas.find_area(name)
    if not area:
        raise ValueError("No area by that name exists. Use 'area list' for names.")
    rooms = sorted((room for room in world.WORLD.rooms.values()
                    if area.vnum_start <= room.vnum <= area.vnum_end), key=lambda r: r.vnum)
    if not rooms:
        raise ValueError("That area has no built rooms to export.")
    slug = re.sub(r"[^a-z0-9]+", "-", area.name.lower()).strip("-")[:55] or "area"
    filename = f"{slug}-{area.vnum_start}.json"
    directory = os.path.join(storage.DATA_DIR, "area_exports")
    prior = {}
    path = os.path.join(directory, filename)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                prior = {row["vnum"]: row for row in json.load(handle).get("rooms", [])}
        except (OSError, ValueError, TypeError, KeyError):
            pass
    if layout:
        prior.update(layout)
    positions = _layout_rooms(rooms, prior)
    rows = []
    for room in rooms:
        row = _room_row(room)
        row.update(positions[room.vnum])
        rows.append(row)
    room_ids = {room.vnum for room in rooms}
    points = sorted((p for p in spawn_points.list_spawn_points()
                     if p["room_vnum"] in room_ids),
                    key=lambda p: (p["kind"], p["vnum"], p["room_vnum"]))
    mobs, items = {}, {}
    for point in points:
        vnum = point["vnum"]
        if point["kind"] == "mob" and vnum in combat.MOB_TEMPLATES:
            mobs.setdefault(vnum, _mob_row(vnum, combat.MOB_TEMPLATES[vnum], point["room_vnum"]))
        if point["kind"] == "item" and vnum in olc.OBJECT_TEMPLATES:
            items.setdefault(vnum, _item_row(vnum, olc.OBJECT_TEMPLATES[vnum], point["room_vnum"]))
    baseline = {"area": _fingerprint(area.reset_message or ""),
                "rooms": {str(row["vnum"]): _fingerprint({k: v for k, v in row.items()
                                                          if k not in ("x", "y")}) for row in rows},
                "mobs": {str(v): _fingerprint(row) for v, row in mobs.items()},
                "items": {str(v): _fingerprint(row) for v, row in items.items()}}
    package = {"format": FORMAT,
               "area": {"name": area.name, "vnum_start": area.vnum_start,
                        "vnum_end": area.vnum_end, "reset_message": area.reset_message or ""},
               "rooms": rows, "mobs": list(mobs.values()), "items": list(items.values()),
               "source": {"mode": "update", "baseline": baseline,
                          "placements": {kind: {str(v): row["room_vnum"] for v, row in collection.items()}
                                         for kind, collection in (("mobs", mobs), ("items", items))}}}
    encoded = (json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("This area exceeds the 2 MB editor package limit.")
    os.makedirs(directory, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(encoded)
    return path, package


def load_package(filename: str) -> dict:
    """Read one basename under data/area_imports; never follow links out."""
    if not FILE_NAME.fullmatch(filename) or ".." in filename:
        raise ValueError("Use one .json filename from data/area_imports (no paths).")
    directory = os.path.realpath(os.path.join(storage.DATA_DIR, "area_imports"))
    path = os.path.realpath(os.path.join(directory, filename))
    if os.path.dirname(path) != directory or not os.path.isfile(path):
        raise ValueError(f"No import file named {filename} in data/area_imports.")
    if os.path.getsize(path) > MAX_FILE_BYTES:
        raise ValueError("Area package exceeds the 2 MB limit.")
    try:
        with open(path, encoding="utf-8") as handle:
            package = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read area package: {exc}") from exc
    return package


def _integer(value, label, low=1, high=999999):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be a whole number from {low} to {high}.")
    return value


def _text(value, label, max_length=3000, required=True):
    if not isinstance(value, str) or len(value) > max_length or (required and not value.strip()):
        raise ValueError(f"{label} must be text of 1-{max_length} characters.")
    return value.strip()


def validate(package: dict) -> dict:
    """Build staged records; raise before writing or mutating live content."""
    if not isinstance(package, dict) or package.get("format") != FORMAT:
        raise ValueError(f"Expected a {FORMAT} package.")
    info = package.get("area")
    if not isinstance(info, dict):
        raise ValueError("Area details are missing.")
    name = _text(info.get("name"), "Area name", 80)
    start = _integer(info.get("vnum_start"), "Area start VNUM")
    end = _integer(info.get("vnum_end"), "Area end VNUM")
    if end < start:
        raise ValueError("The area range must be ascending.")
    message = info.get("reset_message", "")
    _text(message, "Reset message", 500, required=False)

    existing_areas = areas.all_areas()
    existing = existing_areas.get(name.lower())
    source = package.get("source")
    updating = isinstance(source, dict) and source.get("mode") == "update"
    if source is not None and not updating:
        raise ValueError("Unknown area package source.")
    if not updating and end - start >= 1000:
        raise ValueError("A new area range must be at most 1,000 rooms wide.")
    baseline = source.get("baseline") if updating else None
    if updating and (not existing or not isinstance(baseline, dict)):
        raise ValueError("Export this existing area again before updating it.")
    if updating and not isinstance(baseline.get("rooms"), dict):
        raise ValueError("Invalid room baseline. Export again.")
    if existing:
        if (existing["vnum_start"], existing["vnum_end"]) != (start, end):
            raise ValueError("That area name already uses a different VNUM range.")
    elif any(not (end < entry["vnum_start"] or start > entry["vnum_end"])
             for entry in existing_areas.values()):
        raise ValueError("The area VNUM range overlaps another reservation.")

    room_rows = package.get("rooms")
    mob_rows = package.get("mobs", [])
    item_rows = package.get("items", [])
    if (not isinstance(room_rows, list) or not 1 <= len(room_rows) <= 1000
            or not isinstance(mob_rows, list) or len(mob_rows) > 500
            or not isinstance(item_rows, list) or len(item_rows) > 500):
        raise ValueError("Use 1-1,000 rooms and no more than 500 mobs or items each.")
    if updating:
        for kind, rows in (("mobs", mob_rows), ("items", item_rows)):
            if not isinstance(baseline.get(kind), dict):
                raise ValueError("Invalid export baseline. Export again.")
            listed = {str(row.get("vnum")) for row in rows if isinstance(row, dict)}
            if not set(baseline[kind]) <= listed:
                raise ValueError(f"An existing {kind[:-1]} is missing. Remove it in game, then export again.")
        if not isinstance(source.get("placements"), dict):
            raise ValueError("Invalid placement baseline. Export again.")

    rooms = {}
    if updating:
        old_ids = {v for v in world.WORLD.rooms if start <= v <= end}
        supplied_ids = {row.get("vnum") for row in room_rows if isinstance(row, dict)}
        if not old_ids <= supplied_ids:
            raise ValueError("An existing room is missing. Remove rooms in game, then export again.")
        if _fingerprint(existing.get("reset_message") or "") != baseline.get("area"):
            raise ValueError("The area's reset message changed since export. Export again.")
    for row in room_rows:
        if not isinstance(row, dict):
            raise ValueError("Every room must be an object.")
        vnum = _integer(row.get("vnum"), "Room VNUM", start, end)
        if vnum in rooms or (vnum in world.WORLD.rooms and not updating):
            raise ValueError(f"Room VNUM {vnum} is duplicated or already in use.")
        old = world.WORLD.rooms.get(vnum)
        if updating and old and _fingerprint(_room_row(old)) != baseline.get("rooms", {}).get(str(vnum)):
            raise ValueError(f"Room {vnum} changed since export. Export again.")
        if updating and old and str(vnum) not in baseline.get("rooms", {}):
            raise ValueError(f"Room {vnum} was not in this area's export.")
        name_text = _text(row.get("name"), f"Room {vnum} name", 120)
        description = _text(row.get("description", ""), f"Room {vnum} description", 5000, required=False)
        sector = _text(row.get("sector", "inside"), f"Room {vnum} sector", 40)
        biome = row.get("biome", "none")
        if biome not in biomes.BIOME_TYPES:
            raise ValueError(f"Room {vnum} has an unknown biome.")
        safe = row.get("safe", False)
        if type(safe) is not bool:
            raise ValueError(f"Room {vnum} safe must be true or false.")
        flags = row.get("flags", [])
        if not isinstance(flags, list) or len(flags) > 30 or any(
                not isinstance(flag, str) or not flag.strip() or len(flag) > 40 for flag in flags):
            raise ValueError(f"Room {vnum} flags must be a short text list.")
        reset = row.get("reset_message", "")
        _text(reset, f"Room {vnum} reset message", 500, required=False)
        exits = row.get("exits", {})
        if not isinstance(exits, dict):
            raise ValueError(f"Room {vnum} exits must be an object.")
        for direction, target in exits.items():
            if direction not in world.OPPOSITE_DIRECTION:
                raise ValueError(f"Room {vnum} has an unknown exit direction: {direction}.")
            _integer(target, f"Room {vnum} exit destination")
        room = copy.deepcopy(old) if old else world.Room(vnum, name_text, description)
        room.name, room.description, room.sector = name_text, description, sector
        room.exits, room.flags = dict(exits), list(dict.fromkeys(flags))
        room.safe, room.biome, room.reset_message = safe, biome, reset or None
        if old:
            for attr in ("exit_flags", "exit_door_open", "exit_key_item", "exit_passcode"):
                value = getattr(room, attr)
                for direction in list(value):
                    if old.exits.get(direction) != room.exits.get(direction):
                        del value[direction]
        rooms[vnum] = room
    for room in rooms.values():
        for target in room.exits.values():
            if target not in rooms and not (updating and target in world.WORLD.rooms):
                raise ValueError(f"Room {room.vnum} exits to {target}, outside this package."
                             " Link external areas in game after import.")

    mobs, items, points = {}, {}, {}
    for row in mob_rows:
        if not isinstance(row, dict):
            raise ValueError("Every mob must be an object.")
        vnum = _integer(row.get("vnum"), "Mob VNUM")
        if vnum in mobs or (vnum in combat.MOB_TEMPLATES and not updating):
            raise ValueError(f"Mob VNUM {vnum} is duplicated or already in use.")
        mob_name = _text(row.get("name"), f"Mob {vnum} name", 120)
        level = _integer(row.get("level", 1), f"Mob {vnum} level", 1, 100)
        health = _integer(row.get("health", 100), f"Mob {vnum} health", 1, 1000000)
        low = _integer(row.get("damage_min", 1), f"Mob {vnum} minimum damage", 1, 100000)
        high = _integer(row.get("damage_max", 4), f"Mob {vnum} maximum damage", low, 100000)
        room_vnum = row.get("room_vnum")
        if room_vnum is not None and room_vnum not in rooms:
            raise ValueError(f"Mob {vnum} is placed in an unknown room.")
        respawns = row.get("respawns", True)
        if type(respawns) is not bool:
            raise ValueError(f"Mob {vnum} respawns must be true or false.")
        old = combat.MOB_TEMPLATES.get(vnum)
        old_row = None
        if updating and old and str(vnum) not in baseline["mobs"]:
            raise ValueError(f"Mob {vnum} is already in use outside this export.")
        if old and updating:
            original = next((p["room_vnum"] for p in spawn_points.list_spawn_points()
                             if p["kind"] == "mob" and p["vnum"] == vnum and p["room_vnum"] in old_ids), None)
            old_row = _mob_row(vnum, old, original)
            if _fingerprint(old_row) != baseline.get("mobs", {}).get(str(vnum)):
                raise ValueError(f"Mob {vnum} changed since export. Export again.")
        template = copy.deepcopy(old) if old else combat.default_template(vnum, mob_name)
        template.update(short_desc=mob_name, level=level, respawns=respawns)
        if old_row is None or health != old_row["health"]:
            template["hit_dice"] = f"1d1+{health - 1}"
        if old_row is None or (low, high) != (old_row["damage_min"], old_row["damage_max"]):
            template["damage_dice"] = f"1d{high - low + 1}+{low - 1}"
        mobs[vnum] = template
        if room_vnum is not None:
            key = spawn_points._key("mob", vnum, room_vnum)
            points[key] = {"kind": "mob", "vnum": vnum, "room_vnum": room_vnum}

    for row in item_rows:
        if not isinstance(row, dict):
            raise ValueError("Every item must be an object.")
        vnum = _integer(row.get("vnum"), "Item VNUM")
        if vnum in items or (vnum in olc.OBJECT_TEMPLATES and not updating):
            raise ValueError(f"Item VNUM {vnum} is duplicated or already in use.")
        item_name = _text(row.get("name"), f"Item {vnum} name", 120)
        item_type = _text(row.get("item_type", "misc"), f"Item {vnum} type", 40)
        cost = _integer(row.get("cost", 0), f"Item {vnum} cost", 0, 1000000000)
        room_vnum = row.get("room_vnum")
        if room_vnum is not None and room_vnum not in rooms:
            raise ValueError(f"Item {vnum} is placed in an unknown room.")
        old = olc.OBJECT_TEMPLATES.get(vnum)
        if updating and old and str(vnum) not in baseline["items"]:
            raise ValueError(f"Item {vnum} is already in use outside this export.")
        if old and updating:
            original = next((p["room_vnum"] for p in spawn_points.list_spawn_points()
                             if p["kind"] == "item" and p["vnum"] == vnum and p["room_vnum"] in old_ids), None)
            if _fingerprint(_item_row(vnum, old, original)) != baseline.get("items", {}).get(str(vnum)):
                raise ValueError(f"Item {vnum} changed since export. Export again.")
        template = copy.deepcopy(old) if old else olc.default_object(vnum, item_name)
        template.update(short_desc=item_name, item_type=item_type, cost=cost)
        items[vnum] = template
        if room_vnum is not None:
            key = spawn_points._key("item", vnum, room_vnum)
            points[key] = {"kind": "item", "vnum": vnum, "room_vnum": room_vnum}

    if not updating and any(key in storage.load_spawn_points().get("points", {}) for key in points):
        raise ValueError("A spawn point in this package already exists.")
    removed_points = set()
    if updating:
        current_points = storage.load_spawn_points().get("points", {})
        for kind, rows in (("mob", mob_rows), ("item", item_rows)):
            old_locations = source["placements"].get(kind + "s", {})
            for row in rows:
                old_location = old_locations.get(str(row["vnum"]))
                if old_location is not None and old_location != row.get("room_vnum"):
                    old_key = spawn_points._key(kind, row["vnum"], old_location)
                    if old_key not in current_points:
                        raise ValueError(f"{kind.capitalize()} {row['vnum']} placement changed since export.")
                    removed_points.add(old_key)
    return {"name": name, "start": start, "end": end, "message": message,
            "existing": bool(existing), "rooms": rooms, "mobs": mobs,
            "items": items, "points": points, "updating": updating,
            "removed_points": removed_points,
            "layout": {row["vnum"]: {"x": row["x"], "y": row["y"]}
                       for row in room_rows if isinstance(row.get("x"), (int, float))
                       and isinstance(row.get("y"), (int, float))}}


def import_package(staged: dict, creator: str) -> dict:
    """Persist the validated package and make it live without a reboot."""
    area_state = storage.load_areas()
    world_state = world_persistence.snapshot_world()
    world_state["deleted_areas"] = storage.load_world_state().get("deleted_areas", [])
    template_state = storage.load_custom_templates()
    point_state = storage.load_spawn_points()
    area_state = copy.deepcopy(area_state)
    template_state = copy.deepcopy(template_state)
    point_state = copy.deepcopy(point_state)
    if not staged["existing"]:
        area_state[staged["name"].lower()] = dataclasses.asdict(
            areas.Area(staged["name"], staged["start"], staged["end"], creator,
                       prototype=True, reset_message=staged["message"] or None))
    elif staged["updating"]:
        area_state[staged["name"].lower()]["reset_message"] = staged["message"] or None
    for vnum, room in staged["rooms"].items():
        world_state["rooms"][str(vnum)] = dataclasses.asdict(room)
    for kind, payload, collection in (("mobs", staged["mobs"], "mobs"),
                                      ("items", staged["items"], "items")):
        for vnum, template in payload.items():
            world_state[kind][str(vnum)] = copy.deepcopy(template)
            template_state.setdefault(collection, {})[str(vnum)] = copy.deepcopy(template)
    old_point_keys = set(point_state.get("points", {}))
    for key in staged["removed_points"]:
        point_state.setdefault("points", {}).pop(key, None)
    for key, point in staged["points"].items():
        point_state.setdefault("points", {}).setdefault(key, point)

    # All collisions and references have been checked before these writes.
    # Keep existing world content in the snapshot rather than replacing it
    # with just the new area.
    storage.save_areas(area_state)
    storage.save_custom_templates(template_state)
    storage.save_spawn_points(point_state)
    storage.save_world_state(world_state)
    world.WORLD.rooms.update(staged["rooms"])
    combat.MOB_TEMPLATES.update(staged["mobs"])
    olc.OBJECT_TEMPLATES.update(staged["items"])
    for key, point in staged["points"].items():
        if key not in old_point_keys:
            spawn_points._spawn_one(point["kind"], point["vnum"], point["room_vnum"])
    # Keep the next export's editor grid and a fresh baseline after a save.
    try:
        export_area(staged["name"], staged["layout"])
    except (OSError, ValueError):
        pass  # The world import has already succeeded; exports can be retried.
    return {"rooms": len(staged["rooms"]), "mobs": len(staged["mobs"]),
            "items": len(staged["items"]), "placements": len(staged["points"])}
