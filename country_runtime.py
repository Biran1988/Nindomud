"""Live country expansion migration, scheduled wildlife and road navigation.

Only a checked plan is installed. Existing builder data, saved characters,
mission records, port records, and unrelated rooms are not rewritten.
The world snapshot carries a resumable installation record; legacy road
recovery must not recreate the removed highway rooms after installation.
"""
from collections import deque
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import time

import country_expansion as layout

VERSION = 1
ORIGINAL_ROOMS = 1528
TARGET_ROOMS = 1146
META_KEY = "country_expansion_v1"
PRIVATE_COUNTRIES = {"Whirlpool"}
MEALS = {
    "A Raw Chicken": ("A Cooked Chicken", 8, 12, 20),
    "A Raw Lamb": ("A Cooked Lamb", 12, 18, 25),
    "A Raw Beef": ("A Cooked Beef", 16, 22, 30),
}
PUBLIC_NAMES = {
    "Fire": "Fire Country / Konoha", "Earth": "Earth Country / Iwa",
    "Lightning": "Lightning Country / Kumo", "Wind": "Wind Country / Suna",
}
CARAVANS = (
    ("Food", "Rivers Country Causeway", "food",
     ("A Rice Ball","A Bowl of Ramen","A Canteen of Water","A Cooked Chicken")),
    ("Provision", "Stone-Grass Foothill Road", "general",
     ("A Copper Axe","A Copper Pickaxe","A Kindling Fishing Rod","A Copper Hoe","A Copper Cooking Pot","A Bundle of Kindling")),
    ("Trade", "Rain-Wind Caravan Road", "general",
     ("An Iron Ore","A Sturdy Oak Log","A Bundle of Kindling","A Birch Branch")),
    ("Medical", "Eastern Pilgrim Road", "general",
     ("A Healing Salve","A Soldier Pill","Antidote Pill")),
    ("Equipment", "Frost-Cloud Pass", "general",
     ("A Basic Kunai","A Basic Ninja Sword","A Throwing Shuriken","A Basic Ninja Shirt","A Basic Ninja Sandals")),
)
SIGN_WORDS = {"sign","signpost","wooden sign","road sign","wooden signpost","waymarker"}
_active = None
_active_path = None


class ExpansionError(ValueError):
    """A conflicting save must be reviewed before any expansion write."""


def _record(room):
    return {k:v for k,v in asdict(room).items() if k!="ground_ryo"}


def _load_meta():
    import storage
    meta=storage.load_world_state().get(META_KEY)
    if meta is not None and meta.get("version")!=VERSION:
        raise ExpansionError("Unrecognized country expansion save version.")
    return meta


def installed():
    return _load_meta() is not None


def active():
    import storage
    return _active if _active_path==str(storage.DATA_DIR) else None


def snapshot_metadata():
    meta=active()
    return {META_KEY:deepcopy(meta)} if meta else {}


def _activate(meta):
    global _active, _active_path
    import storage
    _active=deepcopy(meta)
    _active_path=str(storage.DATA_DIR)


def _references(value, candidates, found):
    """Conservatively retain any highway VNUM mentioned by saved records."""
    if isinstance(value, dict):
        for k,v in value.items():
            _references(k,candidates,found)
            _references(v,candidates,found)
    elif isinstance(value,(list,tuple,set)):
        for v in value:
            _references(v,candidates,found)
    elif isinstance(value,int) and not isinstance(value,bool):
        if value in candidates:
            found.add(value)
    elif isinstance(value,str) and value.isdigit():
        v=int(value)
        if v in candidates:
            found.add(v)


def protected_roads(rooms, canonical, state):
    import storage
    import combat
    import iron_ascension
    ids=set(canonical)
    protected={iron_ascension.ROAD_ENTRANCE_VNUM}
    for v,room in rooms.items():
        if v not in ids:
            protected.update(t for t in room.exits.values() if t in ids)
        elif any(t not in ids for t in room.exits.values()):
            protected.add(v)
    protected.update(v for v,mobs in combat.MOBS_BY_ROOM.items() if mobs and v in ids)
    _references(state.get("mobs",{}),ids,protected)
    _references(state.get("items",{}),ids,protected)
    _references(combat.MOB_TEMPLATES,ids,protected)
    _references(storage.load_spawn_points(),ids,protected)
    _references(storage.load_custom_templates(),ids,protected)
    # Read only. Active missions and return rooms keep their exact VNUMs.
    paths=list(Path(storage.PLAYERS_DIR).glob("*.json"))
    paths+= [Path(storage.DATA_DIR)/name for name in
             ("ground_ryo.json","room_trap_tags.json","ocean_ports.json","territory.json")]
    for path in paths:
        if path.exists():
            try:
                _references(json.loads(path.read_text(encoding="utf-8")),ids,protected)
            except (OSError,ValueError) as exc:
                raise ExpansionError(f"Cannot safely inspect a saved road reference: {path.name}") from exc
    return protected


def shorten_mainland(rooms, canonical, protected=(), target=TARGET_ROOMS):
    """Contract only straight, unmodified, reciprocal two-exit highway rooms.

    Retained VNUMs never change. External anchors, modified rooms, ports,
    player/mission references and protected patrol rooms remain intact.
    The caller passes a staged copy, so a failed reduction cannot alter live
    rooms. An exact target is mandatory; otherwise the migration stops.
    """
    import room_flags
    from world import OPPOSITE_DIRECTION as opposite
    ids=set(canonical)
    if not ids.issubset(rooms):
        raise ExpansionError("Original mainland road graph is incomplete.")
    if not 0 < target <= len(ids):
        raise ExpansionError("Invalid mainland road count.")
    protected=set(protected)
    for v,room in rooms.items():
        if v not in ids:
            protected.update(t for t in room.exits.values() if t in ids)
        elif any(t not in ids for t in room.exits.values()):
            protected.add(v)
    eligible=set()
    for v in ids-protected:
        room,ref=rooms[v],deepcopy(canonical[v])
        room_flags.synchronize(ref,legacy=True)
        copy=deepcopy(room)
        room_flags.synchronize(copy,legacy=True)
        if copy==ref and len(room.exits)==2 and not room.ground_ryo:
            eligible.add(v)
    removed=set()
    # Spread cuts through corridors rather than stripping one entire region.
    order=sorted(eligible,key=lambda v:(v%4,v))
    for v in order:
        if len(ids)-len(removed)==target:
            break
        room=rooms[v]
        (d1,a),(d2,b)=tuple(room.exits.items())
        if opposite.get(d1)!=d2 or a==b or a not in ids or b not in ids:
            continue
        if a not in rooms or b not in rooms:
            continue
        if rooms[a].exits.get(d2)!=v or rooms[b].exits.get(d1)!=v:
            continue
        if any(d2 in getattr(rooms[a],field) or d1 in getattr(rooms[b],field)
               for field in ("exit_flags","exit_key_item","exit_passcode","exit_door_open")):
            continue
        rooms[a].exits[d2]=b
        rooms[b].exits[d1]=a
        del rooms[v]
        removed.add(v)
    if len(ids)-len(removed)!=target:
        raise ExpansionError("Not enough unmodified, unreferenced road rooms for a safe 25% reduction.")
    retained=ids-removed
    seen={min(retained)}
    q=deque(seen)
    while q:
        v=q.popleft()
        for d,n in rooms[v].exits.items():
            if n in removed:
                raise ExpansionError("A retained road still points to a removed VNUM.")
            if n in retained:
                if rooms[n].exits.get(opposite[d])!=v:
                    raise ExpansionError("Mainland road connection is not reciprocal.")
                if n not in seen:
                    seen.add(n);q.append(n)
    if seen!=retained:
        raise ExpansionError("Shortened highway is not fully connected.")
    if any(t in removed for r in rooms.values() for t in r.exits.values()):
        raise ExpansionError("An existing room references a removed road.")
    return removed


def _free_heading(room, preferred):
    return next((d for d in (preferred,*layout.HEADINGS) if d not in room.exits),None)


def _validate_registry(registry):
    result={}
    for country in layout.COUNTRIES:
        name=country.name+" Country"
        match=next(((k,e) for k,e in registry.items()
                    if e["name"].casefold()==name.casefold()),None)
        if match is None:
            raise ExpansionError("All commissioned country reservations must exist before installation.")
        k,entry=match
        if (entry["vnum_start"],entry["vnum_end"])!=(country.first,country.first+499):
            raise ExpansionError(f"Country reservation {country.first}-{country.first+499} has changed.")
        if any(k!=other and entry["vnum_start"]<=e["vnum_end"]
               and e["vnum_start"]<=entry["vnum_end"] for other,e in registry.items()):
            raise ExpansionError("Overlapping country reservations.")
        result[country.first]=k
    return result


def _add_mob(templates,points,country,index,name,level,patrol,cap=1,meat=None,
             animal=False,rare=False):
    import combat
    vnum=country.first+index
    t=combat.default_template(vnum,name)
    t.update(level=level,act_flags=["Npc","Wander"],auto_balance=True,
             country_expansion=VERSION,roadside_patrol_vnums=sorted(set(patrol)),
             ryo_reward=0 if animal else level, gold=0 if animal else level,
             respawns=not rare,country_animal=animal,
             loot_items=[meat] if meat else [])
    if animal:
        t["attack_verbs"]=["bite" if "wolf" in name or "snake" in name else "strike"]
    if rare:
        t["country_event"]=True
    templates[vnum]=t
    if not rare:
        # Spread initial mobs instead of stacking all the livestock in one room.
        for n in range(cap):
            place=patrol[min(len(patrol)-1,(n*len(patrol))//cap)]
            key=f"mob:{vnum}:{place}"
            points[key]={"kind":"mob","vnum":vnum,"room_vnum":place,
                         "total_cap":cap,"per_period_cap":1}
    return vnum


def _plan_population(country,habitats,road,templates,points,meta):
    farm=habitats["farm"]
    forest=habitats["forest"]
    roaming=forest+habitats["other"]
    for i,(name,level,meat) in enumerate(layout.MEAT):
        home=farm if i<4 else forest
        _add_mob(templates,points,country,i+1,f"a {country.name} {name}",level,
                 home,cap=5,meat=meat,animal=True)
    for i,name in enumerate(country.wildlife):
        home=habitats["fishing"] if country.name in {"Rain","Whirlpool"} and i==0 else roaming
        _add_mob(templates,points,country,10+i,f"a {country.name} {name}",
                 (15,23,33)[i],home,cap=4,animal=True)
    events=[]
    for i,(name,level) in enumerate(layout.ENCOUNTERS):
        habitat=forest+habitats["other"]
        events.append(_add_mob(templates,points,country,20+i,
                      f"a {country.name} {name}",level,habitat,rare=True))
    meta["events"][str(country.first)]=events


def _guard(country,direction,templates,points,place,rank="chunin",index=40):
    import combat
    vnum=country.first+index
    t=combat.default_template(vnum,f"a {country.name} Country border guard")
    speech=("Pass the Chuunin Exam before leaving your country."
            if rank=="chunin" else "Pass the Genin Exam before leaving your village.")
    t.update(level=50,auto_balance=False,act_flags=["Npc","Sentinel","Immortal"],
             hit_dice="1d1+9999",damage_dice="0d1+0",respawns=True,
             country_expansion=VERSION,
             mob_programs=[{"trigger":"move","action":"min_rank",
                            "args":f"{direction} {rank} {speech}"}])
    templates[vnum]=t
    points[f"mob:{vnum}:{place}"]={"kind":"mob","vnum":vnum,"room_vnum":place,
                                   "total_cap":1,"per_period_cap":1}


def _plan_items(objects,existing):
    import olc
    # One shared prototype for each plain-string item, so name lookup,
    # cooking and shops cannot disagree between country copies.
    names={t.get("short_desc","").casefold():v for v,t in existing.items()}
    index=33100
    def add(name,kind,cost):
        nonlocal index
        if name.casefold() in names:
            return names[name.casefold()]
        while index in existing or index in objects:
            index+=1
        if index>33375:
            raise ExpansionError("No unused object VNUMs remain for country goods.")
        t=olc.default_object(index,name)
        t.update(item_type=kind,cost=cost,country_expansion=VERSION)
        objects[index]=t
        names[name.casefold()]=index
        index+=1
        return index-1
    for raw,(cooked,cost,xp,stamina) in MEALS.items():
        add(raw,"material",max(1,cost//2))
        add(cooked,"food",cost)
    for name in sorted({n for group in (*layout.GROUND.values(),*layout.RARE_GROUND.values()) for n in group}):
        add(name,"material",1)
    return names


def _plan_caravans(rooms,retained,templates,points,names,meta):
    import combat
    import shop_flags
    for i,(kind,title,specialty,stock) in enumerate(CARAVANS):
        route=sorted(v for v in retained if rooms[v].name.startswith(title+" - "))
        if len(route)<2 or any(b not in rooms[a].exits.values() for a,b in zip(route,route[1:])):
            raise ExpansionError(f"Cannot make a connected caravan route on {title}.")
        vnum=20501+9800+i
        t=combat.default_template(vnum,f"a traveling {kind.lower()} caravan")
        t.update(level=50,auto_balance=False,act_flags=["Npc","Sentinel","Immortal"],
                 hit_dice="1d1+9999",damage_dice="0d1+0",respawns=True,
                 country_expansion=VERSION,country_caravan_route=route,
                 long_desc=f"A traveling {kind.lower()} caravan of wooden wagons is here.",
                 description=f"Wooden wagons carry {kind.lower()} supplies along a regular trade route.",
                 shop_items=[names[n.casefold()] for n in stock if n.casefold() in names])
        if not t["shop_items"]:
            raise ExpansionError(f"No existing stock for the {kind} caravan.")
        shop_flags.set_type(t,specialty)
        templates[vnum]=t
        points[f"mob:{vnum}:{route[0]}"]={"kind":"mob","vnum":vnum,"room_vnum":route[0],
                                         "total_cap":1,"per_period_cap":1}
        meta["caravans"].append(vnum)
        for k in (0,len(route)//2,len(route)-1):
            v=route[k]
            if "A caravan rest stop" not in rooms[v].description:
                rooms[v].description+=" A caravan rest stop stands beside the highway."


def build_plan(live,registry,state,existing_mobs,existing_objects,protected):
    """Stage the entire graph and population, without performing any writes."""
    import mainland_roads
    from world import OPPOSITE_DIRECTION
    registry_keys=_validate_registry(registry)
    canonical,hubs=mainland_roads.build_rooms()
    if len(canonical)!=ORIGINAL_ROOMS:
        raise ExpansionError("Unexpected baseline highway size.")
    # Copy only affected room objects; no mutation of the live world.
    rooms=dict(live)
    for v in set(canonical)|{c.village for c in layout.COUNTRIES}:
        if v in live:
            rooms[v]=deepcopy(live[v])
    removed=shorten_mainland(rooms,canonical,protected)
    retained=set(canonical)-removed
    meta={"version":VERSION,"pending":True,"removed":sorted(removed),
          "retained":sorted(retained),"areas":registry_keys,"signs":{},
          "groups":{},"borders":{},"events":{},"caravans":[],
          "campfires":[],"country_rooms":{}}
    templates,objects,points={}, {}, {}
    public_targets={}
    main_allowed=set(retained)
    names=_plan_items(objects,existing_objects)
    for country in layout.COUNTRIES:
        gate=rooms.get(country.village)
        if gate is None:
            raise ExpansionError(f"Existing country gate room {country.village} is missing.")
        if country.hub:
            hub=hubs[country.hub]
            from_gate=[d for d,v in gate.exits.items() if v==hub]
            from_hub=[d for d,v in rooms[hub].exits.items() if v==gate.vnum]
            if len(from_gate)!=1 or len(from_hub)!=1 or OPPOSITE_DIRECTION[from_gate[0]]!=from_hub[0]:
                raise ExpansionError(f"Country gate {gate.vnum} is not connected reciprocally to its original road.")
            direction=from_gate[0]
        else:
            hub=None
            direction=_free_heading(gate,country.outward)
            if direction is None:
                raise ExpansionError("No free local coastal country entrance.")
        country=replace(country,outward=direction)
        generated,habitats=layout.build_country(country)
        for v,new in generated.items():
            if v in rooms:
                old=rooms[v]
                if (old.name!="An Unfinished Room" or old.exits or old.ground_items or old.ground_ryo
                        or old.programs or old.flags or old.owner):
                    raise ExpansionError(f"Country room VNUM {v} is already occupied.")
            rooms[v]=new
        first,last=country.first,country.first+24
        if hub is not None:
            layout.attach_country(rooms,country,gate.vnum,hub,direction,from_hub[0])
            border_direction=next(d for d,v in rooms[last].exits.items() if v==hub)
            _guard(country,border_direction,templates,points,last)
            meta["borders"][str(last)]=[border_direction,"chunin"]
            main_allowed.update(range(first,last+1))
            main_allowed.add(gate.vnum)
            public_targets[first]=PUBLIC_NAMES.get(country.name,country.name+" Country")
        else:
            # Keep island navigation local. No invented bridge to the mainland.
            layout.link(rooms,gate.vnum,direction,first)
            rooms[last].description+=" The country road ends at a coastal lookout."
        # Keep the original Academy gate program and provide a non-bypass
        # rank check on the exact newly installed outward village exit.
        if country.name in PUBLIC_NAMES or country.name in PRIVATE_COUNTRIES:
            meta["borders"][str(gate.vnum)]=[direction,"genin"]
        _plan_population(country,habitats,list(range(first,last+1)),templates,points,meta)
        local_targets={gate.vnum:PUBLIC_NAMES.get(country.name,country.name+" settlement")}
        local_targets[last]="Mainland road" if hub is not None else "Coastal lookout"
        for kind,ids in habitats.items():
            local_targets[ids[0]]=country.themes[("forest","farm","fishing","mine","other").index(kind)]
        local_allowed=set(generated)|{gate.vnum}
        if hub is not None:
            local_allowed.add(hub)
            local_targets[hub]="Mainland highway"
        group=str(first)
        meta["groups"][group]={"allowed":sorted(local_allowed),
                               "targets":{str(v):n for v,n in local_targets.items()}}
        meta["country_rooms"][group]=sorted(generated)
        for v in range(first,last+1):
            if v in (first,last) or len(rooms[v].exits)>2:
                meta["signs"][str(v)]=group
                if "signpost" not in rooms[v].description:
                    rooms[v].description+=" A wooden signpost stands here."
        meta["campfires"].append(first+12)
        rooms[first+12].description+=" A sheltered permanent campfire provides cooking fuel."
    # Existing non-expanded highway destinations remain unchanged.
    for title,area,v,hub,direction,start,end in mainland_roads.DESTINATIONS:
        if v not in {c.village for c in layout.COUNTRIES} and v in rooms:
            main_allowed.add(v)
            public_targets[v]=title+" Country"
    meta["groups"]["mainland"]={"allowed":sorted(main_allowed),
                                "targets":{str(v):n for v,n in public_targets.items()}}
    for v in hubs.values():
        meta["signs"][str(v)]="mainland"
        rooms[v].description+=" A permanent directional signpost stands at the crossroads."
    # Place recognizable landmarks on retained highway rooms, without
    # renaming them (existing delivery and recovery targets keep identity).
    landmarks=("stone mile marker","wooden bridge","roadside shrine",
               "abandoned watchtower","roadside well","travelers' campsite")
    for i,(a,b,steps,first,final,title,biome) in enumerate(mainland_roads.SEGMENTS):
        chain=sorted(v for v in retained if rooms[v].name.startswith(title+" - "))
        if not chain:
            continue
        v=chain[len(chain)//2]
        rooms[v].description+=f" A {landmarks[i%len(landmarks)]} marks this stretch of road."
        if i%len(landmarks)==5:
            meta["campfires"].append(v)
            rooms[v].description+=" A permanent campfire burns beside the trail."
    _plan_caravans(rooms,retained,templates,points,names,meta)
    if set(templates)&set(existing_mobs) or set(objects)&set(existing_objects):
        raise ExpansionError("A country mobile or object VNUM is occupied.")
    meta["points"]=points
    meta["mob_vnums"]=sorted(templates)
    meta["item_vnums"]=sorted(objects)
    return rooms,templates,objects,meta


def _complete(meta):
    """Resume a partially committed install without overwriting builder stock."""
    import storage
    import world
    import combat
    import olc
    registry=storage.load_areas()
    keys=_validate_registry(registry)
    for key in keys.values():
        registry[key]["prototype"]=False
    saved=storage.load_world_state()
    custom=storage.load_custom_templates()
    points=storage.load_spawn_points()
    custom_mobs=custom.setdefault("mobs",{})
    custom_items=custom.setdefault("items",{})
    for v in meta["mob_vnums"]:
        template=saved.get("mobs",{}).get(str(v))
        if template is None:
            raise ExpansionError("Incomplete country mobile snapshot.")
        custom_mobs.setdefault(str(v),template)
        combat.MOB_TEMPLATES[v]=custom_mobs[str(v)]
    for v in meta["item_vnums"]:
        template=saved.get("items",{}).get(str(v))
        if template is None:
            raise ExpansionError("Incomplete country object snapshot.")
        custom_items.setdefault(str(v),template)
        olc.OBJECT_TEMPLATES[v]=custom_items[str(v)]
    for key,point in meta["points"].items():
        points.setdefault("points",{}).setdefault(key,point)
    storage.save_custom_templates(custom)
    storage.save_spawn_points(points)
    storage.save_areas(registry)
    for point in meta["points"].values():
        v,place=point["vnum"],point["room_vnum"]
        if not world.WORLD.get(place):
            raise ExpansionError("Country spawn room missing after migration.")
        if not any(m.template_vnum==v for m in combat.mobs_in_room(place)):
            combat.spawn_mob(v,place)
    meta["pending"]=False
    saved[META_KEY]=meta
    storage.save_world_state(saved)
    _activate(meta)


def install_or_restore():
    import storage
    import world
    import combat
    import olc
    import mainland_roads
    state=storage.load_world_state()
    old=state.get(META_KEY)
    if old:
        if old.get("version")!=VERSION:
            raise ExpansionError("Unknown country expansion version.")
        if old.get("pending"):
            _complete(old)
        else:
            _activate(old)
        return False
    registry=storage.load_areas()
    _validate_registry(registry)
    canonical,_=mainland_roads.build_rooms()
    protected=protected_roads(world.WORLD.rooms,canonical,state)
    rooms,templates,objects,meta=build_plan(world.WORLD.rooms,registry,state,
                                             combat.MOB_TEMPLATES,olc.OBJECT_TEMPLATES,protected)
    existing_points=storage.load_spawn_points().get("points",{})
    if set(existing_points)&set(meta["points"]):
        raise ExpansionError("Country spawn point already exists.")
    custom=storage.load_custom_templates()
    if set(map(str,templates))&set(custom.get("mobs",{})) or set(map(str,objects))&set(custom.get("items",{})):
        raise ExpansionError("Country template collides with a saved custom prototype.")
    saved=deepcopy(state)
    records=saved.setdefault("rooms",{})
    for v in meta["removed"]:
        records.pop(str(v),None)
    for v,r in rooms.items():
        prior=world.WORLD.get(v)
        if prior is not r and (prior is None or prior!=r):
            records[str(v)]=_record(r)
    saved.setdefault("mobs",{}).update({str(v):t for v,t in templates.items()})
    saved.setdefault("items",{}).update({str(v):t for v,t in objects.items()})
    saved[META_KEY]=meta
    storage.save_world_state(saved)
    world.WORLD.rooms.clear()
    world.WORLD.rooms.update(rooms)
    combat.MOB_TEMPLATES.update(templates)
    olc.OBJECT_TEMPLATES.update(objects)
    _complete(meta)
    return True


def read_sign(room,query):
    """Read a permanent, non-takeable sign using LOOK or EXAMINE."""
    import world
    meta=active()
    if not meta or not room or query.strip().casefold() not in SIGN_WORDS:
        return None
    group=meta["signs"].get(str(room.vnum))
    if not group:
        return None
    info=meta["groups"][group]
    targets={int(v):n for v,n in info["targets"].items()}
    directions=layout.sign_directions(world.WORLD.rooms,room.vnum,targets,set(info["allowed"]))
    lines=["&YDirectional Signpost&x"]
    lines.extend(f"  &W{d.capitalize():12}&x {name}" for name,d in sorted(directions.items(),key=lambda item:(item[1],item[0])))
    if not directions:
        lines.append("The sign points toward the surrounding trails.")
    return "\n".join(lines)


def blocks_border(session,room,direction):
    meta=active()
    if not meta:
        return False
    gate=meta["borders"].get(str(room.vnum))
    if not gate or direction!=gate[0]:
        return False
    if session.account is not None and session.account.staff_level!="player":
        return False
    import kage
    from programs import _canonical_gate_rank
    rank=_canonical_gate_rank(getattr(session.player,"village_rank","student"))
    required=_canonical_gate_rank(gate[1])
    if rank not in kage.RANK_ORDER or kage.RANK_ORDER.index(rank)<kage.RANK_ORDER.index(required):
        session.send("A border guard blocks your way. Pass your "+("Chuunin" if required=="chunin" else "Genin")+" Exam first.")
        return True
    return False


def free_campfire(room):
    meta=active()
    return bool(meta and room and room.vnum in meta["campfires"])


def reset_area(area,rng=random):
    """Occasional capped environmental items and uncommon wandering enemies."""
    import world
    import combat
    meta=active()
    if not meta:
        return
    key=str(area.vnum_start)
    ids=meta["country_rooms"].get(key)
    if ids is None:
        if area.vnum_start!=20501:
            return
        ids=meta["retained"]
    rooms=[world.WORLD.get(v) for v in ids]
    rooms=[r for r in rooms if r and r.enabled]
    ground_names={n for group in (*layout.GROUND.values(),*layout.RARE_GROUND.values()) for n in group}
    present=sum(any(n in ground_names for n in r.ground_items) for r in rooms)
    cap=max(1,len(rooms)*8//100)
    candidates=list(rooms)
    rng.shuffle(candidates)
    for r in candidates:
        if present>=cap:
            break
        if layout.ground_spawn(r,rng):
            present+=1
    event_vnums=meta["events"].get(key,[])
    if not event_vnums or rng.random()>=.18:
        return
    if any(m.template_vnum in event_vnums for mobs in combat.MOBS_BY_ROOM.values() for m in mobs):
        return
    v=rng.choices(event_vnums,weights=[38,30,18,10,4],k=1)[0]
    template=combat.MOB_TEMPLATES.get(v)
    if template:
        places=[p for p in template.get("roadside_patrol_vnums",[])
                if world.WORLD.get(p) and world.WORLD.get(p).enabled and not world.WORLD.get(p).safe]
        if places:
            where=rng.choice(places)
            combat.spawn_mob(v,where)
            combat._broadcast_to_room(where,"A wandering stranger steps onto the trail.")


def tick_caravans(now=None):
    """Only tagged caravan merchants follow scheduled road patrols."""
    import combat
    import world
    import programs
    meta=active()
    if not meta:
        return
    now=time.monotonic() if now is None else now
    for mobs in list(combat.MOBS_BY_ROOM.values()):
        for mob in list(mobs):
            if mob.template_vnum not in meta["caravans"] or mob.health<=0:
                continue
            template=combat.MOB_TEMPLATES.get(mob.template_vnum,{})
            route=template.get("country_caravan_route",[])
            if len(route)<2 or mob.room_vnum not in route:
                continue
            if not hasattr(mob,"_country_caravan_due"):
                mob._country_caravan_due=now+60
                continue
            if now<mob._country_caravan_due or combat._mob_is_being_fought(mob):
                continue
            i=route.index(mob.room_vnum)
            step=getattr(mob,"_country_caravan_step",1)
            if i==0:
                step=1
            elif i==len(route)-1:
                step=-1
            target=route[i+step]
            here=world.WORLD.get(mob.room_vnum)
            there=world.WORLD.get(target)
            direction=next((d for d,v in here.exits.items() if v==target and "hidden" not in here.exit_flags.get(d,[])),None) if here else None
            if not direction or not there or not there.enabled:
                mob._country_caravan_due=now+60
                continue
            combat._broadcast_to_room(here.vnum,f"{mob.name.capitalize()} continues {direction} along the road.")
            combat.MOBS_BY_ROOM[here.vnum].remove(mob)
            mob.room_vnum=target
            combat.MOBS_BY_ROOM.setdefault(target,[]).append(mob)
            combat._broadcast_to_room(target,f"{mob.name.capitalize()} arrives from the {world.OPPOSITE_DIRECTION[direction]}.")
            mob._country_caravan_step=step
            mob._country_caravan_due=now+(180 if i+step in (0,len(route)//2,len(route)-1) else 60)
            programs.fire_mob_entry(mob)


def _visible_neighbors(room):
    import world
    return [(d,world.WORLD.get(v)) for d,v in room.exits.items()
            if "hidden" not in room.exit_flags.get(d,[]) and world.WORLD.get(v)
            and world.WORLD.get(v).enabled]


def cmd_where(session,args):
    import areas
    import world
    room=world.WORLD.get(session.player.room_vnum)
    if not room:
        return
    area=areas.find_area_for_vnum(room.vnum)
    session.send(f"Location: {room.name}"+(f" ({area.name})" if area else ""))


def cmd_map(session,args):
    import world
    room=world.WORLD.get(session.player.room_vnum)
    if not room:
        return
    lines=[f"&WLocal map: {room.name}&x","  [You are here]"]
    for direction,dest in _visible_neighbors(room):
        lines.append(f"  {direction.capitalize():12} -> {dest.name}")
    session.send("\n".join(lines))


def cmd_survey(session,args):
    import world
    import combat
    import fishing
    import mining
    import lumberjack
    import farming
    room=world.WORLD.get(session.player.room_vnum)
    if not room:
        return
    lines=["&WNearby gathering and wildlife&x"]
    for direction,r in [("here",room),*_visible_neighbors(room)]:
        jobs=[label for label,check in (("chop",lumberjack.can_chop_here),
                 ("farm",farming.can_farm_here),("fish",fishing.can_fish_here),
                 ("mine",mining.can_mine_here)) if check(r.biome)]
        animals=[m.name for m in combat.mobs_in_room(r.vnum)
                 if m.health>0 and combat.MOB_TEMPLATES.get(m.template_vnum,{}).get("country_animal")]
        if jobs or animals:
            lines.append(f"  {direction.capitalize()}: "+", ".join(jobs+animals))
    if len(lines)==1:
        lines.append("No nearby gathering opportunities or wildlife.")
    session.send("\n".join(lines))
