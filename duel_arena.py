"""
The Duel Arena (Section 89), per direct request/design conversation:

"What you described but it transfers combatants to an 10 room arena
with several biomes. When combat ends they are returned to the room
they came from."

10 rooms, vnums 9900-9909, spanning 5 real biomes (forest, mountain,
desert, swamp, plains) so elemental jutsu affinity genuinely applies
here -- confirmed directly, not cosmetic. The layout is deliberately
irregular/maze-like (confirmed design: "genuinely takes some real
exploring/searching to find each other"), not a simple line or grid --
some rooms have 2 exits, some have 3, and the two starting rooms
(9900 and 9909) sit at opposite ends of the graph with no direct path
between them shorter than several rooms.

The arena itself is a normal, permanent part of the world (built once
in content.py's own populate(), like everything else) -- what makes a
duel special is entirely in duel.py: teleporting both combatants in
at the start (to the two distinct starting rooms, confirmed design),
and back to wherever they originally came from once the fight ends in
a genuine defeat (confirmed: defeat only ends a duel, no yield/concede
option) -- with no penalties at all for the loser (confirmed design:
"No penalties at all -- just health/chakra/stamina restored a bit and
returned to their original room, purely a friendly/formal match").
"""

ARENA_START_VNUM_A = 9900
ARENA_START_VNUM_B = 9909


def build_arena(world_module) -> None:
    """Registers all 10 arena rooms and their (deliberately irregular)
    exits into world_module.WORLD. Called once from content.populate(),
    matching every other static content section's own pattern."""
    from world import Room

    rooms = [
        (9900, "Arena: Forest Clearing", "A quiet clearing ringed by tall trees, the traditional starting point for one side of a formal duel.", "forest"),
        (9901, "Arena: Dense Thicket", "Thick underbrush and low branches make footing here treacherous.", "forest"),
        (9902, "Arena: Rocky Outcrop", "Jagged stone juts up from the earth, offering both cover and a clear vantage.", "mountain"),
        (9903, "Arena: Narrow Ravine", "A tight ravine cuts through the rock, echoing every footstep.", "mountain"),
        (9904, "Arena: Sunbaked Flat", "Cracked earth stretches out under a punishing sun.", "desert"),
        (9905, "Arena: Dune Crossing", "Loose sand shifts underfoot, slowing every step.", "desert"),
        (9906, "Arena: Murky Bog", "Standing water and reeds make this stretch slow going.", "swamp"),
        (9907, "Arena: Sunken Marsh", "The ground here barely holds weight, sucking at every footfall.", "swamp"),
        (9908, "Arena: Open Field", "A wide, open stretch of grass with nowhere to hide.", "plains"),
        (9909, "Arena: Windswept Plain", "Rolling grassland under an open sky, the traditional starting point for the other side of a formal duel.", "plains"),
    ]
    for vnum, name, desc, biome in rooms:
        world_module.WORLD.add_room(Room(vnum=vnum, name=name, description=desc, biome=biome))

    # Deliberately irregular connections -- confirmed maze-like design,
    # NOT a simple line or small grid. The two starting rooms (9900,
    # 9909) sit at genuinely opposite ends of this graph.
    links = [
        (9900, "east", 9901),
        (9901, "east", 9902),
        (9901, "south", 9906),
        (9902, "south", 9903),
        (9902, "east", 9904),
        (9903, "east", 9905),
        (9904, "south", 9905),
        (9904, "east", 9908),
        (9905, "south", 9907),
        (9906, "east", 9907),
        (9907, "east", 9908),
        (9908, "east", 9909),
        (9903, "south", 9906),
    ]
    for a_vnum, direction, b_vnum in links:
        world_module.WORLD.link(a_vnum, direction, b_vnum)
