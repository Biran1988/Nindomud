# Legacy village room relocation (15.486)

The registered area ranges are authoritative:

| Village | Area | Legacy room block | Destination block |
|---|---|---|---|
| Iwa | stone (2501-5000) | 1100-1185 | 2600-2685 |
| Kiri | water (5001-7500) | 1200-1285 | 5100-5185 |
| Kumo | cloud (7501-10000) | 1300-1385 | 7600-7685 |
| Suna | sand (10001-12500) | 1400-1485 | 10100-10185 |

Only these original room offsets are migrated: 0, 1, 10, 20, 21, 30,
40, 50, 60, 70, 71, 72, 73, 80 and 85. Additional custom Leaf rooms in
those general ranges remain untouched. The two standalone old gathering rooms
2499 (small mine) and 2500 (small forest) move to Stone-area 2700 and 2701.

This is **not** a replacement of built-in Kage rooms: 2501, 5001, 7501 and
10001 stay where they are. Legacy village rooms keep their names, original
custom descriptions, flags, doors, exits, spawns and details.

Migration occurs after the saved world snapshot is applied and before spawn
points are loaded. The game writes a one-time translation ledger to
`data/village_room_moves.json` (not included in release archives). This keeps
saved character locations, housing deeds, missing-return locations and ground
Ryo aligned with moved rooms during login and later saves. Existing purchased
apartment expansions do **not** move: their old VNUMs become explicit deed
entries before the main-apartment VNUM is translated.

If any destination VNUM is already occupied in the saved snapshot or live
world, the **entire affected village group** stays unchanged and startup prints
`[Village VNUM migration] SKIPPED: ...`. The game never replaces a builder
room to complete this migration. Back up your live `/data` before upgrading;
never replace that directory with the release ZIP.
