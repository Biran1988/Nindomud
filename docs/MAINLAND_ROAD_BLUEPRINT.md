# Nindo MUD Mainland Road Blueprint — Northern Coastal Revision v3

**Status: planning only; no deployed rooms, exits, gate VNUMs, or changes to `/data`.**
Map and mark-up editor distributed in ChatGPT as `Nindo_Mainland_Map_Kit_v3.zip`.

## Geographic layout
- Land of Earth / Stone is in the northwest, WEST of the Great Northern Bay.
- Land of Lightning / Cloud is far north/northeast, on the opposite peninsula.
- **Sound Country is relocated to the southern shore of the bay, BETWEEN Grass and Waterfall.** It is not east of Leaf.
- Fire / Leaf is central-south, Wind / Sand southwest, Water / Mist on offshore eastern islands.
- Land of Iron / samurai remains a future zone north of Lightning in this Nindo proposal. No roads through Iron yet.
- Mist will eventually use separate 2D spacecraft travel; no up/down axis and no road in this phase.

## NEW: Coastal road C1 (minor-country connection)

**Grass → Sound (32 rooms) → Waterfall (34 rooms), total 66 rooms.**
This is a continuous overland route along the SOUTH shore of the Great Northern Bay. No open water crossing.
Existing proposed **Leaf–Sound** and **Sound–Hot Water** links are removed. These segments are no longer geographically appropriate.

The 150–250-room requirement applies to named **major-village entrance-to-entrance corridors**, not an individual minor-country link such as C1.

## Named major-village corridors

| Route | Villages | Waypoints | Planned navigable rooms |
|---|---|---|---:|
| R1 | Stone ↔ Leaf | Grass | 105 + 85 = **190** |
| R2 | Stone ↔ Leaf | Rain | 123 + 95 = **218** |
| R3 | Leaf ↔ Sand | Rivers | 95 + 80 = **175** |
| R4 | Leaf ↔ Sand | Rain | 95 + 113 = **208** |
| R5 | Leaf ↔ Cloud | Hot Water | 112 + 93 = **205** |
| R6 | Leaf ↔ Cloud | Waterfall, Frost | 105 + 30 + 45 = **180** |
| R7 | Stone ↔ Cloud | Grass, Sound, Waterfall, Frost (coastal road) | 105 + 32 + 34 + 30 + 45 = **246** |
| R8 | Stone ↔ Sand | Birds | 106 + 112 = **218** |
| R9 | Leaf ↔ Cloud | Grass, Sound, Waterfall, Frost | 85 + 32 + 34 + 30 + 45 = **226** |

All nine named major village corridors meet the **150–250** room standard. R7 and R9 REUSE the same Grass–Sound and Sound–Waterfall physical rooms as C1; never duplicate the shared road.

## Authoritative planned segment graph

- Stone–Grass 105; Grass–Leaf 85
- Stone–Rain 123; Rain–Leaf 95; Rain–Sand 113
- Leaf–Rivers 95; Rivers–Sand 80
- Leaf–Hot Water 112; Hot Water–Cloud 93
- Leaf–Waterfall 105; Waterfall–Frost 30; Frost–Cloud 45
- Stone–Birds 106; Birds–Sand 112
- **Grass–Sound 32; Sound–Waterfall 34 (NEW)**

All costs are **proposed navigable-room budgets**, not geographic distances or existing game rooms. An alternative route can take a different total number of steps; validate all designated major-village paths after selecting gates.

## Deployment requirements
1. Owner reviews and marks up the v3 map/HTML planner. These lines are a schematic, not a traced or exact canon atlas.
2. Confirm each village entrance VNUM and minor-country junction.
3. Allocate unused area/VNUM ranges; audit existing village, Forest of Death, exam, private apartment, and user-created spaces. Do not overwrite any existing `/data`.
4. Build shared segments once, place landmarks/sidequests, then test bidirectional exits and route counts.
5. No live world construction until separately requested.

## Geographic reference

- [User-supplied Reddit researched map by u/DetectiveEvyDevy](https://www.reddit.com/r/Naruto/comments/17lree4/the_map_of_the_naruto_world_based_on_everything_i/)
- [Naruto geography (Narutopedia)](https://naruto.fandom.com/wiki/Geography)
- [Wikimedia Naruto World Map](https://commons.wikimedia.org/wiki/File:Naruto_World_Map.svg)

The Reddit map combines manga, anime, and inferred geography; this blueprint is an original Nindo-specific interpretation, not a claim of exact canon placement.
