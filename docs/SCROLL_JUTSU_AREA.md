# Scroll Jutsu object area — VNUM 31501–32000

**Object prototypes only.** The owner-created area, its rooms, exits, builders,
existing content and saved `/data` are not recreated or reset. No scroll is
placed in a shop, on a mob or at a spawn point automatically.

| Class | Item VNUM range | Items |
|---|---|---:|
| General | 31501–31550 | 50 |
| Ninjutsu | 31551–31625 | 75 |
| Taijutsu | 31626–31685 | 60 |
| Genjutsu | 31686–31715 | 30 |
| Bukijutsu | 31716–31735 | 20 |
| Unassigned | 31736–32000 | 265 |

All 235 registered techniques that can be represented by a teaching scroll
have a stable, distinct object VNUM, grouped by class and alphabetized by
technique display name. The one exception is Tailed Beast Bomb: its `READ`
handler expressly forbids scroll learning, because mastery is required.
Other classes' passive, bloodline, village and gate requirements are **not**
removed by adding prototypes. Some scrolls are intentionally restricted and
not distributed by default.

## Relocated existing public scrolls

- `9810` → `31501`: Scroll of 1000 Years of Death
- `9812` → `31502`: Advanced Shadow Clone Scroll
- `9771` → `31550`: Track Scroll
- `9750` → `31606`: Genin Study Scroll

A separate pre-existing restricted scroll is also migrated to its assigned
General-section VNUM without being advertised on the public help board.
All original item names are preserved, so carried copies still resolve through
`READ` after the change. Builder customizations follow the old scroll prototype
when its new VNUM is unused or automatically seeded. Saved spawn point IDs and
NPC shop stock references are migrated; collisions never overwrite an
unrelated builder object.

## Builder commands

Use `olist 31501 31735` or `ostat <vnum>` to browse prototypes within the
area. `oset load <vnum>` loads a specific scroll into the current room; use
`spawnpoint add item <vnum>` to create a persistent spawn after loading as
appropriate. Standard `READ <scroll>` consumes it on successful learning.

Keep the original `/data` directory when installing a new release. See
`Scroll_Jutsu_VNUMs.csv` delivered separately to the owner for the full
administrative mapping without exposing restricted discoveries in public notes.
