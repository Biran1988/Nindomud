# Mainland road network — planning draft (not deployed)

This is a **proposed** Nindo MUD overworld graph. It does not create or change any live area rooms, exits, or `/data` files. The illustrated companion map is `Nindo_Mainland_Road_Planner.html`, intended for review and markup before implementation.

## Rules

- Four mainland great villages: Stone (Iwagakure), Leaf (Konohagakure), Sand (Sunagakure), Cloud (Kumogakure).
- A single planned major-village-to-major-village corridor must contain **150 to 250 navigable steps/rooms between the selected gate rooms** (gate VNUMs will be chosen before deployment).
- Multiple routes to the same village are allowed, including routes through **minor countries**. The segment counts in the table are route budgets, not graphical scale.
- A shared physical segment or junction is built **once**, with the same VNUMs regardless of which named route uses it.
- Mist / Kirigakure is **offshore and unconnected by roads**. A future Star Wars-style 2D starship travel plane may connect to it, with no mandatory up/down axis. That is not part of this rollout.
- The hidden Whirlpool village remains separate, unless explicitly approved for roads.
- Reserve fresh road areas/VNUM blocks and audit collisions before building, especially against forest, exam, village, and apartment VNUM ranges. Do not overwrite `/data` as part of the draft.
- Roads should branch into optional camps, merchants, bandit patrols, mini-dungeons, and side quests in the minor countries, but those detours do not count toward the direct gate-to-gate standard unless they are part of a designated route.

## Proposed direct village corridors

| ID | From | To | Stopovers | Rooms |
| --- | --- | --- | --- | ---: |
| R1 | Stone | Leaf | Grass | 105 + 85 = **190** |
| R2 | Stone | Leaf | Rain | 123 + 95 = **218** |
| R3 | Leaf | Sand | Rivers | 95 + 80 = **175** |
| R4 | Leaf | Sand | Rain | 95 + 113 = **208** |
| R5 | Leaf | Cloud | Hot Water | 112 + 93 = **205** |
| R6 | Leaf | Cloud | Waterfall, Frost | 95 + 65 + 78 = **238** |
| R7 | Stone | Cloud | Iron | 118 + 117 = **235** |
| R8 | Stone | Sand | Birds | 106 + 112 = **218** |
| R9 | Leaf | Cloud | Sound, Hot Water | 80 + 35 + 93 = **208** |

The Land of Rain stopover provides another implicit Stone–Sand corridor: Stone → Rain (123) + Rain → Sand (113) = **236** rooms. Sand to Cloud currently has **no direct corridor**; travel is possible by connecting at Leaf (175 + 205 = 380) or Stone (218 + 235 = 453), which is intentionally a multi-journey route. The 150–250 specification applies to direct named corridors, not every possible multi-stop journey.

## Shared segment budget

- Stone–Grass **105**, Grass–Leaf **85**
- Stone–Rain **123**, Rain–Leaf **95**, Rain–Sand **113**
- Leaf–Rivers **95**, Rivers–Sand **80**
- Leaf–Hot Water **112**, Hot Water–Cloud **93**
- Leaf–Waterfall **95**, Waterfall–Frost **65**, Frost–Cloud **78**
- Stone–Iron **118**, Iron–Cloud **117**
- Stone–Birds **106**, Birds–Sand **112**
- Leaf–Sound **80**, Sound–Hot Water **35**

Suggested later junctions: Grass–Rain, Rain–Rivers, Frost–Iron. They are **not** included in the distance sums above until their room budgets are allocated and validated.

## Next step after marking up the map

Choose village entrance VNUMs, confirm minor-country positions and route junctions, then allocate collision-free area blocks and generate linked rooms from this exact route graph. Run automated pathfinding checks for each direct corridor before applying changes to the MUD. Keep edits to `/data` opt-in.
