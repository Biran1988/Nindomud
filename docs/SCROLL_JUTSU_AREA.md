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
| Later released defense scrolls | 31736–31739 | 4 |
| Legacy retired Second/Third scroll IDs | 31740–31741 | 2 |
| Bukijutsu-only Fourth/Fifth scrolls | 31742–31743 | 2 |
| Anime-inspired class technique scrolls | 31744–31759 | 16 |
| Kai (Genjutsu Release) | 31760 | 1 |
| Trap Tag Placement (Bukijutsu 10; scroll for others 25) | 31761 | 1 |
| Unassigned | 31762–32000 | 239 |

The original 235 registered techniques that can be represented by a teaching scroll
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

## Numbered attacks: universal automatic unlocks and restricted scrolls

| Item VNUM | Ability | Current requirement | Scroll needed? |
|---|---|---|---|
| 31740 (legacy) | Second Attack | ALL classes: level 25 | No; automatic |
| 31741 (legacy) | Third Attack | ALL classes: level 75 | No; automatic |
| 31742 | Fourth Attack | Bukijutsu: level 75 | Yes |
| 31743 | Fifth Attack | Bukijutsu: level 90 | Yes |

Second and Third Attack are now automatically granted on leveling or login
catch-up. Older scroll objects at 31740/31741 remain registered so live
builder prototypes, spawn points and carried copies retain their identities;
they no longer teach, grant or consume an attack on READ. No new items are
spawned or stocked automatically. Fourth and Fifth Attack still require
their Bukijutsu-only scrolls and the normal PRAC/combat mastery progression.

The 16 anime-inspired combat arts are appended after these reserved IDs and
can be acquired at the appropriate level by their own class or via the
existing cross-class teaching scroll rules; no new scrolls auto-spawn.

## Builder commands

Use `olist 31501 31760` or `ostat <vnum>` to browse prototypes within the
area. `oset load <vnum>` loads a specific scroll into the current room; use
`spawnpoint add item <vnum>` to create a persistent spawn after loading as
appropriate. Standard `READ <scroll>` consumes it on successful learning.

Keep the original `/data` directory when installing a new release. See
`Scroll_Jutsu_VNUMs.csv` delivered separately to the owner for the full
administrative mapping without exposing restricted discoveries in public notes.
