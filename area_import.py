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
import programs
import spawn_points
import storage
import world
import world_persistence

FORMAT = "nindo-area-v1"
MAX_FILE_BYTES = 2_000_000
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.json\Z")



# Only persistent, builder-editable properties are accepted from the offline
# editor. Dynamic room effects, player ownership and runtime entities are never
# exposed or written by an area package.
ROOM_BUILDER_KEYS = ("enabled", "apartment", "player_shop", "programs",
                     "exit_flags", "exit_door_open", "exit_key_item", "exit_passcode")
MOB_BASIC_KEYS = {"short_desc", "level", "hit_dice", "damage_dice", "respawns"}
ITEM_BASIC_KEYS = {"short_desc", "item_type", "cost"}
MOB_BUILDER_KEYS = frozenset(combat.DEFAULT_MOB_FIELDS) - MOB_BASIC_KEYS
ITEM_BUILDER_KEYS = frozenset(olc.DEFAULT_OBJECT_FIELDS) - ITEM_BASIC_KEYS - {"previous_short_descs"}


def _room_builder(room):
    return {key: copy.deepcopy(getattr(room, key)) for key in ROOM_BUILDER_KEYS}


def _template_builder(template, keys):
    return {key: copy.deepcopy(template.get(key))
            for key in sorted(keys) if key in template}


def _validate_programs(rows, triggers, label):
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError(f"{label}: use at most 100 programs.")
    import smaug_progs
    for entry in rows:
        if isinstance(entry, dict) and "script" in entry:
            errors = smaug_progs.validate_entry(entry, triggers)
            if errors:
                raise ValueError(f"{label}: {errors[0]}")
            continue
        if not isinstance(entry, dict) or set(entry) - {"trigger", "action", "args", "keyword"}:
            raise ValueError(f"{label}: program must contain valid legacy fields or a validated script.")
        trigger, action, args = entry.get("trigger"), entry.get("action"), entry.get("args")
        keyword = entry.get("keyword")
        if (not isinstance(trigger, str) or not isinstance(action, str)
                or not isinstance(args, str) or len(args) > 2000
                or (keyword is not None and (not isinstance(keyword, str) or len(keyword) > 120))):
            raise ValueError(f"{label}: program fields must be bounded text.")
        failures = programs.validate_program(trigger, action, args, triggers, keyword)
        if failures:
            raise ValueError(f"{label}: {failures[0]}")


def _validate_builder_value(value, default, label):
    """Check exact JSON types, size and nesting; no arbitrary object keys."""
    if default is None:
        if value is not None and (not isinstance(value, str) or len(value) > 200):
            raise ValueError(f"{label} must be text or null.")
    elif isinstance(default, bool):
        if type(value) is not bool:
            raise ValueError(f"{label} must be true or false.")
    elif type(default) is int:
        if type(value) is not int or not -1000000000 <= value <= 1000000000:
            raise ValueError(f"{label} must be an integer.")
    elif isinstance(default, str):
        if not isinstance(value, str) or len(value) > 5000:
            raise ValueError(f"{label} must be text of at most 5000 characters.")
    elif isinstance(default, list):
        if (not isinstance(value, list) or len(value) > 100
                or any(type(x) not in (str, int) or
                       (type(x) is str and len(x) > 200) or
                       (type(x) is int and not 0 <= x <= 999999)
                       for x in value)):
            raise ValueError(f"{label} must be a short list of text or VNUMs.")
    elif isinstance(default, dict):
        if (not isinstance(value, dict) or len(value) > 100
                or any(not isinstance(k, str) or len(k) > 60 or
                       type(v) not in (str, int) or
                       (type(v) is str and len(v) > 200) or
                       (type(v) is int and not -100000 <= v <= 100000)
                       for k, v in value.items())):
            raise ValueError(f"{label} must be a short dictionary.")
    else:
        raise ValueError(f"{label} has an unsupported type.")


def _validated_settings(settings, defaults, allowed, label, program_key, triggers):
    if not isinstance(settings, dict) or set(settings) - set(allowed):
        raise ValueError(f"{label} contains unknown or restricted builder fields.")
    for field, value in settings.items():
        if field == "act_flags" and (not isinstance(value, list) or
                                      any(flag not in olc.VALID_MOB_ACT_FLAGS for flag in value)):
            raise ValueError(f"{label} has an invalid mob flag.")
        if field == "extra_flags" and (not isinstance(value, list) or
                                        any(flag not in olc.VALID_ITEM_EXTRA_FLAGS for flag in value)):
            raise ValueError(f"{label} has an invalid item flag.")
        if field == program_key:
            _validate_programs(value, triggers, f"{label} {field}")
        else:
            _validate_builder_value(value, defaults[field], f"{label} {field}")
    return copy.deepcopy(settings)


def _validated_room_builder(data, room, label):
    if not isinstance(data, dict) or set(data) - set(ROOM_BUILDER_KEYS):
        raise ValueError(f"{label} has unknown or restricted room fields.")
    for field, value in data.items():
        if field == "programs":
            _validate_programs(value, programs.ROOM_TRIGGERS, label)
        elif field in ("enabled", "apartment", "player_shop"):
            _validate_builder_value(value, False, f"{label} {field}")
        else:
            if not isinstance(value, dict) or len(value) > 12:
                raise ValueError(f"{label} {field} must be a direction dictionary.")
            for direction, setting in value.items():
                if direction not in room.exits:
                    raise ValueError(f"{label} {field}: {direction} has no exit.")
                if field == "exit_flags":
                    if (not isinstance(setting, list) or len(setting) > 5
                            or any(x not in olc.EXIT_FLAG_NAMES for x in setting)):
                        raise ValueError(f"{label}: invalid exit flags.")
                else:
                    _validate_builder_value(setting, field == "exit_door_open"
                                            if field == "exit_door_open" else "",
                                            f"{label} {field}")
        setattr(room, field, copy.deepcopy(value))


def _validated_caps(row, label):
    data = row.get("spawn_caps")
    if data is None:
        return {}
    if not isinstance(data, dict) or set(data) - {"total_cap", "per_period_cap"}:
        raise ValueError(f"{label} has invalid spawn caps.")
    result = {}
    for key in ("total_cap", "per_period_cap"):
        value = data.get(key)
        if value is not None and (type(value) is not int or not 1 <= value <= 100000):
            raise ValueError(f"{label} {key} must be 1-100000 or null.")
        result[key] = value
    return result

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


def export_area(name: str, layout=None, *, write: bool = True) -> tuple[str, dict]:
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
        row["builder"] = _room_builder(room)
        rows.append(row)
    room_ids = {room.vnum for room in rooms}
    points = sorted((p for p in spawn_points.list_spawn_points()
                     if p["room_vnum"] in room_ids),
                    key=lambda p: (p["kind"], p["vnum"], p["room_vnum"]))
    mobs, items = {}, {}
    for point in points:
        vnum = point["vnum"]
        if point["kind"] == "mob" and vnum in combat.MOB_TEMPLATES:
            if vnum not in mobs:
                row = _mob_row(vnum, combat.MOB_TEMPLATES[vnum], point["room_vnum"])
                row["settings"] = _template_builder(combat.MOB_TEMPLATES[vnum], MOB_BUILDER_KEYS)
                row["spawn_caps"] = {k: point.get(k) for k in ("total_cap", "per_period_cap")}
                mobs[vnum] = row
        if point["kind"] == "item" and vnum in olc.OBJECT_TEMPLATES:
            if vnum not in items:
                row = _item_row(vnum, olc.OBJECT_TEMPLATES[vnum], point["room_vnum"])
                row["settings"] = _template_builder(olc.OBJECT_TEMPLATES[vnum], ITEM_BUILDER_KEYS)
                row["spawn_caps"] = {k: point.get(k) for k in ("total_cap", "per_period_cap")}
                items[vnum] = row
    baseline = {"area": _fingerprint(area.reset_message or ""), "area_income": _fingerprint(area.income),
                "rooms": {str(row["vnum"]): _fingerprint({k: v for k, v in row.items()
                                                          if k not in ("x", "y", "builder")}) for row in rows},
                "mobs": {str(v): _fingerprint({k: row[k] for k in ("vnum", "name", "level", "health", "damage_min", "damage_max", "room_vnum", "respawns")}) for v, row in mobs.items()},
                "items": {str(v): _fingerprint({k: row[k] for k in ("vnum", "name", "item_type", "cost", "room_vnum")}) for v, row in items.items()}}
    baseline["details"] = {
        "rooms": {str(room.vnum): _fingerprint(_room_builder(room)) for room in rooms},
        "mobs": {str(v): _fingerprint(_template_builder(combat.MOB_TEMPLATES[v], MOB_BUILDER_KEYS))
                 for v in mobs},
        "items": {str(v): _fingerprint(_template_builder(olc.OBJECT_TEMPLATES[v], ITEM_BUILDER_KEYS))
                  for v in items},
        "caps": {kind: {str(v): _fingerprint(row["spawn_caps"]) for v, row in collection.items()}
                 for kind, collection in (("mobs", mobs), ("items", items))},
    }
    package = {"format": FORMAT,
               "area": {"name": area.name, "vnum_start": area.vnum_start,
                        "vnum_end": area.vnum_end, "reset_message": area.reset_message or "", "income": area.income},
               "rooms": rows, "mobs": list(mobs.values()), "items": list(items.values()),
               "source": {"mode": "update", "baseline": baseline,
                          "placements": {kind: {str(v): row["room_vnum"] for v, row in collection.items()}
                                         for kind, collection in (("mobs", mobs), ("items", items))}}}
    encoded = (json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("This area exceeds the 2 MB editor package limit.")
    if write:
        os.makedirs(directory, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(encoded)
    return path, package



WORLD_FORMAT = "nindo-world-v1"
MAX_WORLD_FILE_BYTES = 25_000_000


def export_world() -> tuple[str, dict]:
    """Export the whole world as a read-only editor workspace, not a deployable import.

    Empty area reservations appear as markers; only populated areas get
    editable area packages. Never changes live rooms or saved world state.
    """
    registry = sorted(areas.all_areas().values(), key=lambda a: a["vnum_start"])
    packages, markers, warnings = [], [], []
    links = set()
    by_room = {}
    for entry in registry:
        start, end = entry["vnum_start"], entry["vnum_end"]
        for vnum in world.WORLD.rooms:
            if start <= vnum <= end:
                by_room[vnum] = entry["name"]
        if any(start <= v <= end for v in world.WORLD.rooms):
            try:
                _, pkg = export_area(entry["name"], write=False)
                packages.append(pkg)
            except ValueError as exc:
                warnings.append(f"{entry['name']}: {exc}")
        else:
            warnings.append(f"{entry['name']}: empty area reservation.")
        index = len(markers)
        markers.append({"name": entry["name"], "vnum_start": start,
                        "vnum_end": end,
                        "room_count": sum(start <= v <= end for v in world.WORLD.rooms),
                        "x": 180 + (index % 5) * 270,
                        "y": 160 + (index // 5) * 170,
                        "notes": "", "category": "area"})
    unassigned = sorted(v for v in world.WORLD.rooms if v not in by_room)
    if unassigned:
        name = "Unassigned rooms (unreserved)"
        markers.append({"name": name, "vnum_start": min(unassigned),
                        "vnum_end": max(unassigned), "room_count": len(unassigned),
                        "x": 180 + ((len(markers) - 1) % 5) * 270,
                        "y": 160 + ((len(markers) - 1) // 5) * 170,
                        "notes": "Rooms outside registered area reservations. "
                                 "Reference-only; reserve/import a proper area to edit.",
                        "category": "region"})
        for v in unassigned:
            by_room[v] = name
        warnings.append(f"{len(unassigned)} room(s) outside registered areas "
                        "are shown as a reference marker, not importable area packages.")
    for room in world.WORLD.rooms.values():
        a = by_room.get(room.vnum)
        if a:
            for vnum in room.exits.values():
                b = by_room.get(vnum)
                if b and b != a:
                    links.add(tuple(sorted((a, b))))
    bundle = {"format": WORLD_FORMAT,
              "world": {"name": "Nindo_mud World", "width": 1600,
                        "height": 1000, "image": None},
              "markers": markers,
              "links": [{"from": a, "to": b} for a, b in sorted(links)],
              "areas": packages, "warnings": warnings}
    encoded = (json.dumps(bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_WORLD_FILE_BYTES:
        raise ValueError("World export exceeds the 25 MB portable-world limit.")
    directory = os.path.join(storage.DATA_DIR, "world_exports")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "nindo-world.json")
    with open(path, "wb") as stream:
        stream.write(encoded)
    return path, bundle


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
    income = info.get("income")
    if income is not None:
        _integer(income, "Area income", 0, 1000000000)

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
        if income is not None and (baseline.get("area_income") is None or
                                   _fingerprint(existing.get("income", 0)) != baseline["area_income"]):
            raise ValueError("The area's income changed since export. Export again.")
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
        if "builder" in row:
            details = (baseline or {}).get("details", {}).get("rooms", {})
            if old and (str(vnum) not in details or
                        _fingerprint(_room_builder(old)) != details[str(vnum)]):
                raise ValueError(f"Room {vnum} advanced fields changed since export. Export again.")
            _validated_room_builder(row["builder"], room, f"Room {vnum}")
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
        if "dice" in row:
            dice = row["dice"]
            if not isinstance(dice, dict) or set(dice) - {"hit_dice", "damage_dice"}:
                raise ValueError(f"Mob {vnum} has invalid dice overrides.")
            for field, value in dice.items():
                if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d{0,2}d[1-9]\d{0,5}(?:[+-]\d{1,7})?", value):
                    raise ValueError(f"Mob {vnum} has an invalid {field} dice expression.")
                template[field] = value
        if "settings" in row:
            details = (baseline or {}).get("details", {}).get("mobs", {})
            if old and (str(vnum) not in details or
                        _fingerprint(_template_builder(old, MOB_BUILDER_KEYS)) != details[str(vnum)]):
                raise ValueError(f"Mob {vnum} advanced fields changed since export. Export again.")
            template.update(_validated_settings(row["settings"], combat.DEFAULT_MOB_FIELDS,
                                                MOB_BUILDER_KEYS, f"Mob {vnum}",
                                                "mob_programs", programs.MOB_TRIGGERS))
        mobs[vnum] = template
        if room_vnum is not None:
            key = spawn_points._key("mob", vnum, room_vnum)
            caps = _validated_caps(row, f"Mob {vnum}")
            if old and "spawn_caps" in row:
                details = (baseline or {}).get("details", {}).get("caps", {}).get("mobs", {})
                old_location = source.get("placements", {}).get("mobs", {}).get(str(vnum), room_vnum)
                old_key = spawn_points._key("mob", vnum, old_location)
                current = storage.load_spawn_points().get("points", {}).get(old_key, {})
                old_caps = {k: current.get(k) for k in ("total_cap", "per_period_cap")}
                if str(vnum) not in details or _fingerprint(old_caps) != details[str(vnum)]:
                    raise ValueError(f"Mob {vnum} spawn caps changed since export. Export again.")
            points[key] = {"kind": "mob", "vnum": vnum, "room_vnum": room_vnum}
            points[key].update(caps)

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
        if "settings" in row:
            details = (baseline or {}).get("details", {}).get("items", {})
            if old and (str(vnum) not in details or
                        _fingerprint(_template_builder(old, ITEM_BUILDER_KEYS)) != details[str(vnum)]):
                raise ValueError(f"Item {vnum} advanced fields changed since export. Export again.")
            settings = dict(row["settings"])
            if "damage" in settings:
                amount = settings.pop("damage")
                if amount is not None and (type(amount) is not int or not 0 <= amount <= 1000000):
                    raise ValueError(f"Item {vnum} damage must be a nonnegative integer or null.")
                template["damage"] = amount
            template.update(_validated_settings(settings, olc.DEFAULT_OBJECT_FIELDS,
                                                ITEM_BUILDER_KEYS, f"Item {vnum}",
                                                "item_programs", programs.ITEM_TRIGGERS))
        items[vnum] = template
        if room_vnum is not None:
            key = spawn_points._key("item", vnum, room_vnum)
            caps = _validated_caps(row, f"Item {vnum}")
            if old and "spawn_caps" in row:
                details = (baseline or {}).get("details", {}).get("caps", {}).get("items", {})
                old_location = source.get("placements", {}).get("items", {}).get(str(vnum), room_vnum)
                old_key = spawn_points._key("item", vnum, old_location)
                current = storage.load_spawn_points().get("points", {}).get(old_key, {})
                old_caps = {k: current.get(k) for k in ("total_cap", "per_period_cap")}
                if str(vnum) not in details or _fingerprint(old_caps) != details[str(vnum)]:
                    raise ValueError(f"Item {vnum} spawn caps changed since export. Export again.")
            points[key] = {"kind": "item", "vnum": vnum, "room_vnum": room_vnum}
            points[key].update(caps)

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
            "income": income,
            "existing": bool(existing), "rooms": rooms, "mobs": mobs,
            "items": items, "points": points, "updating": updating,
            "removed_points": removed_points,
            "layout": {row["vnum"]: {"x": row["x"], "y": row["y"]}
                       for row in room_rows if isinstance(row.get("x"), (int, float))
                       and isinstance(row.get("y"), (int, float))}}


def import_package(staged: dict, creator: str) -> dict:
    """Persist the validated package and make it live without a reboot."""
    # A queued older builder snapshot must not overwrite this import.
    import world_autosave
    world_autosave.wait_for_pending()
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
                       prototype=True, reset_message=staged["message"] or None,
                       income=staged["income"] or 0))
    elif staged["updating"]:
        area_state[staged["name"].lower()]["reset_message"] = staged["message"] or None
        if staged["income"] is not None:
            area_state[staged["name"].lower()]["income"] = staged["income"]
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
        stored = point_state.setdefault("points", {}).setdefault(key, point)
        if "total_cap" in point:
            stored["total_cap"] = point["total_cap"]
            stored["per_period_cap"] = point["per_period_cap"]

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
