"""Five bandit camps, roadside inns, bathhouses and civilian hamlets.

One-time additive /data migration for the existing Mainland Road Network.
Do not replace the original road marker, existing rooms, templates or player data.
Neither this feature nor its discovery sites belong on the changes board.
"""
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import os

import mainland_roads

FIRST_NEW_ROOM = 22029   # main road generator currently ends at 22028
MOB_BASE = 29501
MARKER = ".roadside_camps_inns_20501_installed.json"
BATH_FEE = 100
HEADINGS = mainland_roads.HEADINGS
REVERSE = mainland_roads.REVERSE

# Attachment locations are indices into the named original highway segments,
# not arbitrary new links to a village's gate.
CAMPS = (
    ("leaf", "Ashen Hollow", "Rivers Country Causeway", 61, "southeast", "forest"),
    ("stone", "Broken Anvil", "Western Plateau Road", 62, "west", "mountain"),
    ("cloud", "Thunderbreak", "Lightning Mountain Approach", 26, "northwest", "mountain"),
    ("sand", "Red Jackal", "Windward River Highway", 17, "south", "desert"),
    ("border", "Blackthorn", "Grassfall Woodland Connector", 18, "north", "forest"),
)
INNS = (
    ("leaf", "Willow Lantern Inn", "Eastern Pilgrim Road", 35, "south", "forest"),
    ("stone", "Granite Hearth Inn", "Stone-Grass Foothill Road", 29, "south", "mountain"),
    ("cloud", "Rolling Thunder Inn", "Frost-Cloud Pass", 48, "east", "mountain"),
    ("sand", "Dune Blossom Inn", "Rain-Wind Caravan Road", 86, "east", "desert"),
    ("border", "Cedar Falls Inn", "Northern Escarpment Road", 16, "northwest", "forest"),
)
CAMP_ROOM_NAMES = (
    "Palisade Gate", "Outer Encampment", "Bandit Courtyard", "Smoldering Firepit",
    "Captain's Command Tent", "Western Lookout", "Sword Racks",
    "Thug Barracks", "Kunai Training Ring", "Plunder Supplies",
    "Rough Cooking Tent", "Prisoner Cages", "Stolen Cargo Cache",
)
# Different template / room pairs allow 22 persistent mobs per camp.
CAMP_SPAWNS = (
    (0, (0, 1, 2, 3, 4, 5, 6, 7)),
    (1, (1, 2, 3, 4, 8, 9, 10, 11)),
    (2, (2, 4, 7, 12)),
    (3, (4, 12)),
)
MOB_KINDS = (
    ("a roadside thug", 25, "A Basic Kunai", 320, 70),
    ("a sword-wielding bandit", 28, "A Basic Ninja Sword", 450, 100),
    ("a hardened bandit enforcer", 31, "A Basic Ninja Sword", 580, 140),
    ("a notorious bandit captain", 34, "A Basic Ninja Sword", 850, 220),
)

class RoadsideInstallationError(ValueError):
    """No partial migration when an existing VNUM or exit is occupied."""


def _link(rooms, start, direction, end):
    back = REVERSE[direction]
    if direction in rooms[start].exits or back in rooms[end].exits:
        raise RoadsideInstallationError(f"Exit conflict between {start} and {end}.")
    rooms[start].exits[direction] = end
    rooms[end].exits[back] = start


def _offset(direction, quarter_turn):
    return HEADINGS[(HEADINGS.index(direction) + quarter_turn) % len(HEADINGS)]


def _anchor(roads, title, index):
    candidates = sorted(vnum for vnum, room in roads.items()
                        if room.name.startswith(title + " - "))
    if index >= len(candidates):
        raise RoadsideInstallationError(f"No road position {index} on {title}.")
    return candidates[index]


def _side(road, preferred):
    # Pick a reproducible unoccupied compass exit for the off-road trail.
    for shift in (0, 1, -1, 2, -2, 3, -3, 4):
        heading = _offset(preferred, shift)
        if heading not in road.exits:
            return heading
    raise RoadsideInstallationError(f"No spare exit at road {road.vnum}.")


def _spur_heading(road, first_room, preferred):
    """Reuse an already persisted road-to-camp link during recovery."""
    for direction, destination in road.exits.items():
        if destination == first_room and direction in REVERSE:
            return direction
    return _side(road, preferred)


def _road_patrol(roads, center, maximum=8):
    """Only a handful of highway rooms around this camp, never villages."""
    visited = {center}
    pending = deque([(center, 0)])
    while pending:
        vnum, steps = pending.popleft()
        if steps >= maximum:
            continue
        for next_vnum in roads[vnum].exits.values():
            if next_vnum in roads and next_vnum not in visited:
                visited.add(next_vnum)
                pending.append((next_vnum, steps + 1))
    return visited


def _room(vnum, title, detail, biome, safe=False):
    from world import Room
    obj = Room(vnum, title, detail, sector="field")
    obj.biome = biome
    obj.safe = safe
    return obj


def _mob_template(vnum, name, level, weapon=None, xp=0, ryo=0, camp=None, patrol=()):
    import combat
    t = combat.default_template(vnum, name)
    t["level"] = level
    t["hit_dice"] = "1d1+999"
    t["damage_dice"] = "1d8+4"
    t["experience_reward"] = xp
    t["ryo_reward"] = ryo
    t["gold"] = ryo
    t["respawns"] = True
    if camp is not None:
        t["act_flags"] = ["Npc", "Wander", "aggressive_everyone"]
        t["roadside_camp"] = camp
        t["roadside_patrol_vnums"] = sorted(patrol)
        t["roadside_weapon"] = weapon
        t["loot_items"] = [weapon]
        t["long_desc"] = f"{name.capitalize()} watches the trail with a {weapon.lower()}."
    else:
        t["act_flags"] = ["Npc", "Sentinel"]
        t["auto_balance"] = False
        t["experience_reward"] = 0
        t["ryo_reward"] = 0
        t["gold"] = 0
        t["hit_dice"] = "1d1+99"
        t["damage_dice"] = "1d1+0"
    return t


def _spawn_entry(points, template_vnum, room_vnum, total=1):
    key = f"mob:{template_vnum}:{room_vnum}"
    if key in points:
        raise RoadsideInstallationError(f"Duplicate camp spawn {key}.")
    points[key] = {
        "kind": "mob", "vnum": template_vnum, "room_vnum": room_vnum,
        "total_cap": total, "per_period_cap": 1,
    }


def build_plan(road_rooms=None):
    """Deterministic construction plan; optional live road graph for safe spurs."""
    roads, hubs = mainland_roads.build_rooms()
    occupied_roads = road_rooms if road_rooms is not None else roads
    rooms, links, templates, spawns = {}, [], {}, {}
    camp_info, inn_info = {}, {}
    vnum = FIRST_NEW_ROOM

    for index, (key, name, title, position, preferred, biome) in enumerate(CAMPS):
        anchor = _anchor(roads, title, position)
        heading = _spur_heading(occupied_roads.get(anchor) or roads[anchor],
                                vnum, preferred)
        trail = list(range(vnum, vnum + 4))
        camp = list(range(vnum + 4, vnum + 17))  # 13 actual camp rooms
        vnum += 17
        for j, room_vnum in enumerate(trail):
            rooms[room_vnum] = _room(
                room_vnum, f"{name} - Hidden Bandit Trail",
                ("Boot prints and discarded kunai marks lead away from the highway. "
                 "A faint column of smoke rises from deeper in the wilderness."
                 if j >= 2 else
                 "A barely visible footpath winds through scrub and loose stone. "
                 "Broken branches and boot prints suggest frequent passage."),
                biome)
        for j, room_vnum in enumerate(camp):
            rooms[room_vnum] = _room(
                room_vnum, f"{name} - {CAMP_ROOM_NAMES[j]}",
                f"The {CAMP_ROOM_NAMES[j].lower()} forms part of {name}, "
                f"a fortified outlaw camp in the {biome} country. "
                "Swords, kunai and stolen travel goods are scattered about. "
                "Armed bandits keep watch over their territory.",
                biome)
        chain = trail + camp[:5]
        for a, b in zip(chain, chain[1:]):
            _link(rooms, a, heading, b)
        # Eight side rooms branching off the five-room central camp axis.
        for j, spine_index in enumerate(range(1, 5)):
            _link(rooms, camp[spine_index], _offset(heading, -2), camp[5 + 2*j])
            _link(rooms, camp[spine_index], _offset(heading, 2), camp[6 + 2*j])
        rooms[trail[0]].exits[REVERSE[heading]] = anchor
        links.append((anchor, heading, trail[0]))
        patrol = set(trail + camp) | _road_patrol(roads, anchor)
        base = MOB_BASE + index*6
        for kind, (label, level, weapon, xp, ryo) in enumerate(MOB_KINDS):
            templates[base+kind] = _mob_template(
                base+kind, f"{label} of {name}", level, weapon,
                xp, ryo, camp=key, patrol=patrol)
        total = 0
        for kind, positions in CAMP_SPAWNS:
            for position in positions:
                _spawn_entry(spawns, base+kind, camp[position],
                             total=len(CAMP_SPAWNS[kind][1]) + 1)
                total += 1
        # Four outriders per camp start on the road and its hidden trail,
        # while all 22 core residents remain inside the camp itself.
        for kind, lookout_room in enumerate((trail[0], anchor, trail[2], trail[3])):
            _spawn_entry(spawns, base+kind, lookout_room,
                         total=len(CAMP_SPAWNS[kind][1]) + 1)
            total += 1
        camp_info[key] = {
            "name": name, "anchor": anchor, "trail": trail,
            "camp": camp, "mob_count": total,
        }

    for index, (key, name, title, position, preferred, biome) in enumerate(INNS):
        anchor = _anchor(roads, title, position)
        heading = _spur_heading(occupied_roads.get(anchor) or roads[anchor],
                                vnum, preferred)
        left, right = _offset(heading, -2), _offset(heading, 2)
        porch, lobby, tea, guest, bath, lane, house1, house2, house3 = range(vnum, vnum+9)
        vnum += 9
        scenes = (
            ("Roadside Courtyard", "An inn sign swings above a sheltered stopping place for weary travelers."),
            ("Reception and Hearth", "A friendly innkeeper offers a healing bath for 100 ryo. Type INN ENTER to pay and enter the bathhouse."),
            ("Tea House", "Steaming teapots and low tables fill a quiet tearoom where travelers trade stories."),
            ("Traveler's Guest Room", "Simple futons and clean blankets provide a warm place to sleep."),
            ("Healing Bathhouse", "Mineral pools and fragrant steam soothe tired muscles, restoring health, chakra and stamina."),
            ("Civilian Hamlet Lane", "A narrow residential lane connects modest homes behind the roadside inn."),
            ("Village Farmer's House", "A family home is filled with baskets, vegetables and neatly kept tools."),
            ("Village Weaver's House", "Cloth hangs beside a hearth in this peaceful cottage."),
            ("Village Merchant's House", "Crates of household wares line the walls of a small civilian home."),
        )
        ids = (porch, lobby, tea, guest, bath, lane, house1, house2, house3)
        for room_vnum, (label, detail) in zip(ids, scenes):
            rooms[room_vnum] = _room(room_vnum, f"{name} - {label}", detail, biome, safe=True)
        rooms[bath].flags.append("accelerated_healing")
        _link(rooms, porch, heading, lobby)
        _link(rooms, lobby, left, tea)
        _link(rooms, lobby, right, guest)
        _link(rooms, porch, left, lane)
        _link(rooms, lane, heading, house1)
        _link(rooms, lane, left, house2)
        _link(rooms, lane, REVERSE[heading], house3)
        # Paid entrance is deliberately ONE-WAY. There is NO physical
        # lobby -> bath exit that would bypass the 100-ryo fee.
        rooms[bath].exits["outside"] = lobby
        rooms[porch].exits[REVERSE[heading]] = anchor
        links.append((anchor, heading, porch))
        base = MOB_BASE + index*6
        templates[base+4] = _mob_template(base+4, f"the innkeeper of {name}", 1)
        templates[base+5] = _mob_template(base+5, f"a local villager near {name}", 1)
        _spawn_entry(spawns, base+4, lobby)
        for home in (house1, house2, house3):
            _spawn_entry(spawns, base+5, home, total=3)
        inn_info[key] = {
            "name": name, "anchor": anchor, "porch": porch, "lobby": lobby,
            "tea": tea, "bath": bath, "homes": [house1, house2, house3],
        }

    if vnum - 1 > mainland_roads.LAST_VNUM:
        raise RoadsideInstallationError("Roadside rooms overflow the mainland reservation.")
    return rooms, links, templates, spawns, {"camps": camp_info, "inns": inn_info}


def _serializable_room(room):
    return {key: value for key, value in asdict(room).items() if key != "ground_ryo"}


def install_once():
    """Save new rooms and camps into /data without replacing any old content."""
    import areas
    import combat
    import spawn_points
    import storage
    import world
    marker = Path(storage.DATA_DIR) / MARKER
    if marker.exists():
        return False

    area = {entry["name"].casefold(): entry for entry in areas.all_areas().values()}.get(
        "mainland road network")
    if (not area or area["vnum_start"] != mainland_roads.FIRST_VNUM
            or area["vnum_end"] != mainland_roads.LAST_VNUM):
        raise RoadsideInstallationError("Mainland Road Network 20501-30500 must exist.")

    # Builder-created highway exits may occupy the original preferred
    # attachment direction. Choose another genuinely available direction
    # on the live roads instead of aborting all five camps and inns.
    rooms, links, templates, points, details = build_plan(road_rooms=world.WORLD.rooms)
    state = storage.load_world_state()
    saved_rooms = state.get("rooms", {})
    saved_mobs = state.get("mobs", {})
    existing_points = storage.load_spawn_points()
    existing_templates = storage.load_custom_templates()
    for vnum in rooms:
        if world.WORLD.get(vnum) is not None or str(vnum) in saved_rooms:
            raise RoadsideInstallationError(f"Room {vnum} is occupied; nothing changed.")
    for vnum in templates:
        if (vnum in combat.MOB_TEMPLATES or str(vnum) in saved_mobs
                or str(vnum) in existing_templates.get("mobs", {})):
            raise RoadsideInstallationError(f"Mobile {vnum} is occupied; nothing changed.")
    for key in points:
        if key in existing_points.get("points", {}):
            raise RoadsideInstallationError(f"Spawn {key} exists; nothing changed.")

    road_patches = {}
    for anchor, direction, destination in links:
        road = world.WORLD.get(anchor)
        if road is None or str(anchor) not in saved_rooms:
            raise RoadsideInstallationError(f"Mainland road {anchor} must be installed first.")
        if direction in road.exits or direction in saved_rooms[str(anchor)].get("exits", {}):
            raise RoadsideInstallationError(f"Road {anchor} already has an exit {direction}.")
        changed = deepcopy(road)
        changed.exits[direction] = destination
        road_patches[anchor] = changed

    merged = deepcopy(state)
    merged.setdefault("rooms", {}).update({
        str(vnum): _serializable_room(room) for vnum, room in rooms.items()
    })
    merged["rooms"].update({
        str(vnum): _serializable_room(room) for vnum, room in road_patches.items()
    })
    merged.setdefault("mobs", {}).update({
        str(vnum): template for vnum, template in templates.items()
    })
    updated_points = deepcopy(existing_points)
    updated_points.setdefault("points", {}).update(points)
    updated_templates = deepcopy(existing_templates)
    updated_templates.setdefault("mobs", {}).update({
        str(vnum): template for vnum, template in templates.items()
    })

    # Preflight is over: preserve every unrelated saved field and record.
    storage.save_world_state(merged)
    storage.save_custom_templates(updated_templates)
    storage.save_spawn_points(updated_points)
    world.WORLD.rooms.update(rooms)
    world.WORLD.rooms.update(road_patches)
    combat.MOB_TEMPLATES.update(templates)
    spawn_points.apply_all()

    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as out:
            json.dump({"rooms": len(rooms), "first_vnum": min(rooms),
                       "last_vnum": max(rooms), "camps": details["camps"],
                       "inns": details["inns"]}, out, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, marker)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True




def repair_missing():
    """Recreate missing camps, inns and spawn points even if marker exists.

    Existing edited rooms and templates survive; only our missing rooms,
    expected reciprocal exits and missing mob/spawn records are restored.
    Neither prototype settings nor unrelated /data entries are changed.
    """
    import areas
    import combat
    import spawn_points
    import storage
    import world

    area = next((entry for entry in areas.all_areas().values()
                 if entry.get("name", "").casefold() == "mainland road network"), None)
    if not area or (area["vnum_start"], area["vnum_end"]) != (
            mainland_roads.FIRST_VNUM, mainland_roads.LAST_VNUM):
        raise RoadsideInstallationError(
            "Mainland Road Network 20501-30500 is not registered.")
    rooms, links, templates, points, details = build_plan(road_rooms=world.WORLD.rooms)
    state = storage.load_world_state()
    if not isinstance(state.get("rooms"), dict):
        raise RoadsideInstallationError("World snapshot has no rooms map.")
    saved = state["rooms"]
    live = world.WORLD.rooms

    # Validate the full repair before writing any file.
    staged = {}
    added = 0
    for vnum, reference in rooms.items():
        existing = live.get(vnum)
        saved_name = (saved.get(str(vnum)) or {}).get("name")
        if ((existing and existing.name not in (reference.name, "An Unfinished Room"))
                or saved_name not in (None, reference.name, "An Unfinished Room")):
            raise RoadsideInstallationError(
                f"Roadside VNUM {vnum} contains a custom room; no changes made.")
        if existing is None or existing.name == "An Unfinished Room":
            staged[vnum] = deepcopy(reference)
            added += 1
        else:
            staged[vnum] = deepcopy(existing)
        for direction, destination in reference.exits.items():
            prior = staged[vnum].exits.get(direction)
            if prior not in (None, destination) and prior not in rooms:
                raise RoadsideInstallationError(
                    f"Roadside room {vnum} has a custom {direction} exit; no changes made.")
            staged[vnum].exits[direction] = destination

    anchor_patches = {}
    for anchor, direction, first in links:
        live_road = live.get(anchor)
        if live_road is None:
            raise RoadsideInstallationError(
                f"Highway anchor {anchor} is missing; repair the mainland roads first.")
        patched = deepcopy(live_road)
        if patched.exits.get(direction) not in (None, first):
            raise RoadsideInstallationError(
                f"Highway {anchor} uses {direction} for another location.")
        patched.exits[direction] = first
        anchor_patches[anchor] = patched

    existing_points = storage.load_spawn_points()
    existing_templates = storage.load_custom_templates()
    missing_templates = {}
    for vnum, reference in templates.items():
        existing = combat.MOB_TEMPLATES.get(vnum)
        saved_mob = (state.get("mobs") or {}).get(str(vnum))
        prior_template = existing_templates.get("mobs", {}).get(str(vnum))
        for candidate in (existing, saved_mob, prior_template):
            if candidate and candidate.get("short_desc") != reference["short_desc"]:
                raise RoadsideInstallationError(
                    f"Mob VNUM {vnum} belongs to another prototype.")
        if existing is None:
            missing_templates[vnum] = deepcopy(prior_template or saved_mob or reference)
    added_points = {key: deepcopy(point) for key, point in points.items()
                    if key not in existing_points.get("points", {})}

    combined = {**staged, **anchor_patches}
    updates = {}
    merged = deepcopy(state)
    for vnum, new_room in combined.items():
        existing = live.get(vnum)
        if existing is not None and _serializable_room(existing) == _serializable_room(new_room):
            continue
        original_record = saved.get(str(vnum))
        if (existing is not None and existing.name != "An Unfinished Room"
                and isinstance(original_record, dict)):
            record = deepcopy(original_record)
            record["exits"] = deepcopy(new_room.exits)
        else:
            record = _serializable_room(new_room)
        merged["rooms"][str(vnum)] = record
        updates[vnum] = new_room
    if missing_templates:
        merged.setdefault("mobs", {}).update({
            str(vnum): template for vnum, template in missing_templates.items()
        })

    if updates or missing_templates:
        storage.save_world_state(merged)
    if missing_templates:
        new_templates = deepcopy(existing_templates)
        new_templates.setdefault("mobs", {}).update({
            str(vnum): template for vnum, template in missing_templates.items()
        })
        storage.save_custom_templates(new_templates)
    if added_points:
        new_points = deepcopy(existing_points)
        new_points.setdefault("points", {}).update(added_points)
        storage.save_spawn_points(new_points)
    if updates:
        world.WORLD.rooms.update(updates)
    if missing_templates:
        combat.MOB_TEMPLATES.update(missing_templates)
    if updates or missing_templates or added_points:
        spawn_points.apply_all()

    # A previous marker can remain from a partial snapshot. Keep it, but
    # ensure new repairs also record their installed region for diagnostics.
    marker = Path(storage.DATA_DIR) / MARKER
    if not marker.exists():
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as out:
                json.dump({"rooms": len(rooms), "first_vnum": min(rooms),
                           "last_vnum": max(rooms), "camps": details["camps"],
                           "inns": details["inns"]}, out, indent=2)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, marker)
        finally:
            if temporary.exists():
                temporary.unlink()
    return {"restored_rooms": added, "updated_rooms": len(updates),
            "restored_templates": len(missing_templates),
            "restored_spawnpoints": len(added_points)}

def cmd_inn(session, args):
    """At reception, INN ENTER pays 100 ryo for an accelerated-healing bath."""
    import combat
    import commands
    import world
    player = getattr(session, "player", None)
    if player is None:
        return
    _, _, _, _, details = build_plan()
    lobby_map = {i["lobby"]: i["bath"] for i in details["inns"].values()}
    bath_map = {value: key for key, value in lobby_map.items()}
    location = player.room_vnum
    if args and args[0].lower() in ("leave", "exit"):
        if location in bath_map:
            commands.cmd_move(session, "outside")
        else:
            session.send("You are not inside an inn bathhouse.")
        return
    if not args:
        session.send("Roadside inn: INN ENTER - pay 100 ryo for a private healing bath. INN LEAVE - exit the bath.")
        return
    if args[0].lower() not in ("enter", "bathe", "bath", "pay"):
        session.send("Usage: inn enter | inn leave")
        return
    if location not in lobby_map:
        session.send("You must speak to the innkeeper at a roadside inn reception.")
        return
    if (getattr(session, "combat_target", None) or getattr(session, "pvp_target", None)
            or player.health <= 0):
        session.send("You cannot enter the healing bath while fighting.")
        return
    if player.ryo < BATH_FEE:
        session.send("The healing bath costs 100 ryo. You do not have enough.")
        return
    bath_vnum = lobby_map[location]
    bath = world.WORLD.get(bath_vnum)
    if not bath or "accelerated_healing" not in bath.flags:
        session.send("The bathhouse is temporarily unavailable.")
        return
    player.ryo -= BATH_FEE
    player.room_vnum = bath_vnum
    commands._wake_and_stand(session)
    session.send("&GYou pay 100 ryo and enter the steamy bathhouse. Healing is accelerated here.&x")
    commands._fire_enter_triggers(session)
    commands.cmd_look(session, [])
