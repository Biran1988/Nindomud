"""Deterministic country expansion layout. No implicit writes to player data.

The builder creates 375 rooms in each commissioned 500-VNUM reservation.
A caller must preflight the saved world and explicitly select valid boundary
connections before installing. Island connections must use real local gates.
"""
from collections import deque
from dataclasses import dataclass
from world import Room, OPPOSITE_DIRECTION

@dataclass(frozen=True)
class Country:
    name: str
    first: int
    village: int
    hub: str | None
    outward: str
    counts: tuple
    themes: tuple
    wildlife: tuple

# Counts: forest, farm, fishing, mine, other. Each sums to 350.
COUNTRIES = (
    Country("Grass",32501,12501,"grass","south",(100,150,35,25,40),
            ("Bamboo Grove","Open Pasture","Meadow Stream","Shallow Cave","Grassy Trail"),
            ("rabbit","fox","deer")),
    Country("Fire",33001,9,"leaf_gate","south",(150,100,35,50,15),
            ("Fire Woodland","Wheat Farm","Freshwater Pond","Abandoned Mine","Forest Shrine"),
            ("deer","wild boar","wolf")),
    Country("Wind",33501,10001,"sand","northeast",(65,50,25,125,85),
            ("Dead Forest","Irrigated Farm","Desert Oasis","Sandstone Mine","Desert Canyon"),
            ("scorpion","coyote","desert snake")),
    Country("Lightning",34001,7501,"cloud","southwest",(90,65,25,120,50),
            ("Mountain Pine Forest","Highland Pasture","Mountain Lake","Cliffside Mine","Mountain Trail"),
            ("mountain goat","eagle","bear")),
    Country("Earth",34501,2501,"stone","southeast",(60,50,20,170,50),
            ("Dry Woodland","Terraced Farm","Mountain Spring","Deep Mine","Rocky Valley"),
            ("wild ram","hare","mountain lion")),
    Country("Rain",35001,13501,"rain","north",(100,65,100,35,50),
            ("Flooded Forest","Rice Paddy","Rainwater Pool","Damp Cavern","Rain Shelter"),
            ("frog","water snake","crocodile")),
    Country("Waterfalls",35501,16501,"waterfall","south",(110,50,120,45,25),
            ("Verdant Forest","Riverside Farm","Waterfall Pool","Hidden Cave","Riverside Trail"),
            ("monkey","wild boar","leopard")),
    Country("Whirlpool",36001,80001,None,"south",(90,75,125,35,25),
            ("Coastal Forest","Island Farm","Tidal Pool","Coastal Cavern","Coastal Trail"),
            ("crab","turtle","seabird")),
    Country("Sound",36501,17501,"sound","north",(125,75,25,75,50),
            ("Dark Forest","Rural Farm","Woodland Pond","Underground Tunnel","Abandoned Shelter"),
            ("bat","wild dog","wolf")),
    Country("Frost",37001,18501,"frost","south",(125,35,50,90,50),
            ("Frozen Forest","Sheltered Farm","Frozen Lake","Ice Cavern","Snowy Trail"),
            ("snow hare","elk","snow wolf")),
)

HEADINGS = ("north","northeast","east","southeast","south","southwest","west","northwest")
FARM_BIOME = "plains"
LANDMARKS = {4:"Stone Mile Marker",8:"Roadside Well",12:"Travelers' Campsite",
             16:"Wooden Bridge",20:"Roadside Shrine",23:"Border Watchtower"}
GROUND = {
    "forest": ("A Bundle of Kindling","A Fallen Twig","A Piece of Bark","A Pinecone"),
    "plains": ("A Bundle of Straw","A Scattered Seed","A Wheat Stalk"),
    "lake": ("A Smooth Stone","A Reed"),
    "river": ("A Smooth Stone","A Reed"),
    "ocean": ("A Seashell","A Piece of Driftwood"),
    "mountain": ("A Loose Stone","A Flint Fragment","A Coal Fragment"),
    "desert": ("A Dry Branch","A Palm Leaf"),
    "swamp": ("A Reed","A Fallen Twig"),
}
RARE_GROUND = {
    "forest": ("A Wild Mushroom","A Piece of Amber","Medicinal Herbs"),
    "mountain": ("An Unpolished Gemstone",),
    "desert": ("A Desert Flower",),
    "plains": ("A Medicinal Herb",),
}
MEAT = (("chicken",10,"A Raw Chicken"),("lamb",13,"A Raw Lamb"),
        ("cow",18,"A Raw Beef"),("sheep",21,"A Raw Lamb"),
        ("wild bull",26,"A Raw Beef"),("wild ram",30,"A Raw Lamb"))
ENCOUNTERS = (("petty thief",12),("roadside bandit",18),
              ("bandit lieutenant",25),("rogue Genin",30),("missing-nin",35))

def link(rooms,a,d,b):
    reverse=OPPOSITE_DIRECTION[d]
    if d in rooms[a].exits or reverse in rooms[b].exits:
        raise ValueError(f"occupied country exit {a}:{d} or {b}:{reverse}")
    rooms[a].exits[d]=b
    rooms[b].exits[reverse]=a

def room(vnum, name, description, biome, safe=False):
    return Room(vnum,name,description,sector="field",
                flags=["biome_"+biome]+(["safe"] if safe else []))

def _grid(rooms, ids, width):
    # Farm and fishing blocks use loops rather than a single long chain.
    for i,v in enumerate(ids):
        if i%width and i>0:
            link(rooms,ids[i-1],"east",v)
        if i>=width:
            link(rooms,ids[i-width],"south",v)

def _tree(rooms, ids, blocked):
    # Branching trails: each node has up to two children. Never reuse
    # the inbound direction. Names and room identities remain stable.
    q=deque([ids[0]])
    i=1
    while i<len(ids):
        parent=q.popleft()
        available=[d for d in HEADINGS if d not in rooms[parent].exits
                   and not (parent==ids[0] and d==blocked)]
        for d in available[::3][:2]:
            if i==len(ids):
                break
            link(rooms,parent,d,ids[i])
            q.append(ids[i])
            i+=1

def _mine(rooms,ids):
    # A descending spine, with short horizontal veins every fourth room.
    current=ids[0]
    i=1
    while i<len(ids):
        link(rooms,current,"down",ids[i])
        current=ids[i]
        i+=1
        if i%4==0:
            for direction in ("east","west"):
                if i<len(ids):
                    link(rooms,current,direction,ids[i])
                    i+=1

def build_country(country):
    """Return rooms and habitat IDs; all connections are reciprocal.

    First room is village-facing; room 25 is highway/harbor-facing.
    External exits are deliberately not fabricated by the pure builder.
    """
    base=country.first
    c=country.name
    out=country.outward
    rooms={}
    road=list(range(base,base+25))
    road_biome={"Wind":"desert","Earth":"mountain","Lightning":"mountain",
                "Rain":"swamp","Frost":"mountain"}.get(c,"plains")
    for i,v in enumerate(road):
        detail=LANDMARKS.get(i)
        name=f"{c} Country Road"+(f" - {detail}" if detail else "")
        desc=f"The {c} Country Road leads between the local settlement and the outer border."
        if detail:
            desc+=f" A {detail.lower()} marks this stretch of road."
        rooms[v]=room(v,name,desc,road_biome,safe=i==12)
        if i:
            link(rooms,road[i-1],out,v)
    habitats={}
    cursor=base+25
    kinds=("forest","farm","fishing","mine","other")
    fish={"Grass":"river","Waterfalls":"river","Whirlpool":"ocean","Rain":"swamp"}.get(c,"lake")
    biomes=("forest",FARM_BIOME,fish,"mountain",road_biome)
    # Separate entrances spread over the 25-room road; side headings
    # follow the actual country bearing rather than a fixed global north.
    quarter=(HEADINGS.index(out)+2)%8
    sides=(HEADINGS[quarter],HEADINGS[(quarter+4)%8])
    for index,(kind,count,theme,biome) in enumerate(zip(kinds,country.counts,country.themes,biomes)):
        ids=list(range(cursor,cursor+count))
        cursor+=count
        habitats[kind]=ids
        for n,v in enumerate(ids):
            variant=("Entrance" if n==0 else ("Clearing","Passage","Edge","Interior")[n%4])
            rooms[v]=room(v,f"{c} {theme} - {variant}",
                          f"This part of the {theme.lower()} lies within {c} Country. "
                          f"{_detail(kind,n)}",biome)
        anchor=road[(3,7,11,15,19)[index]]
        # Grid roots occupy east/south, leaving north/west free. Select
        # a legal approach without overwriting the existing road.
        if kind in ("farm","fishing"):
            _grid(rooms,ids,10 if kind=="farm" else 8)
        elif kind=="mine":
            _mine(rooms,ids)
        preferred="down" if kind=="mine" else sides[index%2]
        choices=[preferred]+list(HEADINGS)
        direction=next(d for d in choices if d not in rooms[anchor].exits
                       and OPPOSITE_DIRECTION[d] not in rooms[ids[0]].exits)
        link(rooms,anchor,direction,ids[0])
        if kind in ("forest","other"):
            _tree(rooms,ids,OPPOSITE_DIRECTION[direction])
        rooms[anchor].description+=f" A sign points {direction} toward the {theme.lower()}."
    if cursor!=base+375:
        raise ValueError("country allocation must contain exactly 375 rooms")
    return rooms,habitats

def _detail(kind,n):
    choices={
        "forest":("Tree roots cross a narrow trail.","Branches stretch over the path.","A small clearing opens between the trees."),
        "farm":("Neat rows of crops line the field.","A worn fence borders the cultivated ground.","A narrow walking path divides the plots."),
        "fishing":("Ripples move across the water.","The bank provides a place to cast a line.","Water laps against the stones."),
        "mine":("A rough vein cuts across the exposed rock.","The passage slopes deeper underground.","Loose fragments lie beside the mine wall."),
        "other":("A worn footpath crosses the terrain.","Old footprints mark the ground.","The landscape opens into a quiet clearing."),
    }
    return choices[kind][n%3]

def build_all():
    rooms,habitats={},{}
    for country in COUNTRIES:
        generated,habitat=build_country(country)
        if rooms.keys() & generated.keys():
            raise ValueError("duplicate country VNUM")
        rooms.update(generated)
        habitats[country.name]=habitat
    return rooms,habitats

def attach_country(rooms,country,gate,outer,gate_direction,outer_direction):
    """Connect verified boundaries on a staged graph only.

    Existing reciprocal direct gate/highway exits are replaced only when
    they match each other. A coastal caller supplies its actual port room.
    """
    first,last=country.first,country.first+24
    if len({gate,outer,first,last})!=4:
        raise ValueError("country boundaries must be distinct")
    for a,d,b in ((gate,gate_direction,outer),(outer,outer_direction,gate)):
        if rooms[a].exits.get(d) not in (None,b):
            raise ValueError(f"existing custom boundary exit at {a}:{d}")
    if OPPOSITE_DIRECTION[gate_direction] in rooms[first].exits or OPPOSITE_DIRECTION[outer_direction] in rooms[last].exits:
        raise ValueError("country endpoint heading conflicts")
    rooms[gate].exits.pop(gate_direction,None)
    rooms[outer].exits.pop(outer_direction,None)
    link(rooms,gate,gate_direction,first)
    link(rooms,outer,outer_direction,last)

def sign_directions(rooms, start, destinations, allowed=None):
    """Shortest-path first headings for named destinations on real exits.

    Callers choose public destinations; undisclosed locations are never
    automatically added. Optional allowed set excludes non-public rooms.
    """
    if start not in rooms:
        return {}
    seen={start}
    q=deque([(start,None)])
    found={}
    while q:
        v,heading=q.popleft()
        if v in destinations and heading:
            found[destinations[v]]=heading
        for direction,target in rooms[v].exits.items():
            if target in seen or target not in rooms or (allowed is not None and target not in allowed):
                continue
            if not rooms[target].enabled or "hidden" in rooms[v].exit_flags.get(direction,[]):
                continue
            seen.add(target)
            q.append((target,heading or direction))
    return found

def ground_spawn(room, rng, chance=.08):
    """One occasional environmental item at most; never grant job drops.

    Returns the new item (or None). Does not touch player inventories.
    The caller owns the normal area-reset scheduling.
    """
    ordinary=GROUND.get(room.biome,())
    rare=RARE_GROUND.get(room.biome,())
    existing={item for items in (*GROUND.values(),*RARE_GROUND.values()) for item in items}
    if not ordinary or any(item in existing for item in room.ground_items) or rng.random()>=chance:
        return None
    item=rng.choice(rare if rare and rng.random()<.04 else ordinary)
    room.ground_items.append(item)
    return item
