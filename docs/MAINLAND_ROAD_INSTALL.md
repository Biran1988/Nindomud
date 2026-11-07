# Mainland Road Network — One-time /data installation

The main game startup now calls `mainland_roads.install_once()` after the Forest of Death's own migrations.

## Exact VNUM contract

**Road area:** Mainland Road Network `20501–30500`.

- First road room: **20501**, with `north -> 9` (Konoha).
- Konoha room **9** gains exactly one external highway exit: `south -> 20501`.
- Built road rooms: **1,528**, consecutively `20501–22028`.
- Remaining road-area room slots **22029–30500** are untouched and available for later building.
- The highway includes internal junctions, a coastal Grass–Waterfall–Sound connector, and gently curving two-way roads.
- All destinations are *side spurs* off the highway. Travel never requires passing through a village.

| Country or village | Entrance room | Exit from the entrance onto the highway |
|---|---:|---|
| Leaf / Konoha | **9** | south |
| Stone | 2501 | southeast |
| Cloud | 7501 | southwest |
| Sand | 10001 | northeast |
| Land of Grass | 12501 | south |
| Land of Rain | 13501 | north |
| Land of Rivers | 14501 | north |
| Land of Birds | 15501 | east |
| Land of Waterfalls | 16501 | south |
| Land of Sound | 17501 | north |
| Land of Frost | 18501 | south |
| Land of Hot Water | 19501 | north |

Existing destination rooms are preserved, with only **one** new reciprocal exit.
If a destination's first VNUM does not yet contain a room, the migration creates a simple editable **Country Entrance** room in its pre-existing area. It does not add or change an area reservation.

## Major-village shortest walking distances

Computed on the actual generated room graph, counting both village entrance spurs.

| Villages | Steps |
|---|---:|
| Leaf–Stone | 197 |
| Leaf–Cloud | 212 |
| Leaf–Sand | 182 |
| Stone–Cloud | 248 |
| Stone–Sand | 217 |
| Cloud–Sand | 392 (indirect journey; no direct corridor) |

The major named direct corridors satisfy the latest requested approximate **100–250-room** standard.

## Safety and installation behavior

1. Back up the live `data/` directory. Extract the **current program update** without replacing any `data/` files.
2. On the next game startup, the code checks all 13 required area reservations and precise ranges against your live registry.
3. It checks that no proposed road VNUM is already occupied and that each destination's chosen exit is unused. **Any conflict cancels the entire installation**, logs the specific conflict on the server console, and leaves the MUD running.
4. On success, it merges new roads and the chosen entrance exits into **the existing `data/world_state.json`** using the existing atomic save and `.bak` backup.
5. It writes `data/.mainland_road_network_20501_installed.json` only after a successful world save. Future restarts **never reapply** the migration, so subsequent builder changes survive.
6. Mist (water) and Whirlpool are not linked. The future samurai and 2D spacecraft systems are deferred.

To verify in-game, stand in Konoha room 9, head `south`, then use `rlist` or `rstat 20501`. The resulting road junction should exit `north` back into room 9. `area list` is unchanged, since all area registrations were already created.

**Do not delete the installation marker unless intentionally recovering from a failed/manual deployment.** The marker and the saved road rooms must be kept together during backups and restores.

This deployment has **no changes-board or changelog entry**, as requested.
