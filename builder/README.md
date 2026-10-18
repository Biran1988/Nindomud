# Offline Nindo_mud visual builder

Open `builder/Nindo_Area_Builder.html` in a modern browser. No installation, connection, or MUD login is needed to edit. The editor works with the server's existing `nindo-area-v1` JSON format.

## Save progress and resume later

- **Automatic save:** every completed field edit, room addition, link, and drag updates the current named draft in that browser's local storage.
- **Save draft now:** records your work even when the area is incomplete. The editor can hold more than one project. **Saved draft** lets you select and reopen any of them; **New project** creates a separate blank draft without deleting the current one.
- **Download project backup:** saves a portable `*.nindo-project.json` file with rooms, prototypes, settings, and the existing-area safety baseline. Use **Open project backup** to resume on a different device, after clearing browser storage, or after a browser reinstall. Keep this file in a safe location; autosaved drafts remain only in the original browser/profile.
- **Open / import area JSON:** imports a server-exported area or previously exported *game package* into a new editable draft. This differs from a project backup.
- **Export area JSON:** builds the validated game import file; unlike Save draft, it requires at least one valid room and complete references.

Browser storage has limited capacity. **Download project backup** regularly. A backup is a normal local file, not synced to GitHub or to the running game.

## Full World Map (uploadable)

Click **Full World Map** at the top of the same editor. This view is a world-level overview separate from the room grid.

**Import the entire existing game world:** In game, as Implementor, run:

```text
area exportworld
```


Transfer the generated file from `data/world_exports/nindo-world.json` to your computer. Click **Upload full world JSON**. All registered areas appear as movable map markers; already-built areas also become editable area drafts. Known exits between different areas appear as lines. Empty area reservations are shown without inventing rooms. Existing area files are not overwritten during the world export.

**Upload a background map:** Use **Background world image** with a PNG, JPG/JPEG, or WebP image (maximum input 12 MB). The editor resizes and compresses the image for portable offline storage. Place area pins by dragging them over your uploaded map. Use the zoom controls or scroll wheel.

**Build and navigate:** Use **Add area marker** for future regions, **Place current area draft** for the area you're building, or **Upload area JSON files** for multiple existing/new area packages. Select markers to edit labels, category, notes, and VNUM ranges. Select one and click **Connect areas**, then another marker, to draw a *visual* world route. Double-click any linked marker to open its room grid in the Area Editor.

**Save and upload later:** Your world overview autosaves in the current browser. **Download world backup** creates a portable `*-world.json` containing the world image, all markers, connections, and linked area packages. Re-upload it later with **Upload full world JSON** on this or another device. The backup protects unfinished work.

**Important safety boundary:** Uploading or changing the world *map* does **not** alter the server. World bundles are **not** accepted by `area import`. To deploy edits, open one linked area, **Export area JSON**, and run `area import <file.json> check` then `area import <file.json>` in-game. This protects saved world data and enforces the current per-area stale-export checks. The world route lines are visual planning links; they do not create game exits. Browser storage capacity varies, so download portable backups regularly.

## Hostile NPC flags and reconnaissance

Mob prototypes can now have **aggressive_everyone**, **aggressive_village**
and/or **aggressive_clan** in the flag selector. For village/clan targeting,
set the Full Prototype Properties fields `aggro_village` or `aggro_clan`
to the exact identity to attack, e.g. `leaf` or `uchiha`. The flags
automatically start normal PvE fights when eligible players arrive.
The controlled elemental clone is also vulnerable to hostile mobs.

Characters who master a specific elemental Bunshin to 100% may use
`clone control` outside combat to pilot the actual living clone for
reconnaissance. The original body remains in its room. The link ends
only upon `clone disperse` or actual clone dispersal/defeat.
See [clone control and NPC aggression](../docs/CLONE_RECON_AND_AGGRESSION.md).

## Multiline SmaugFUSS-style scripts

Each mob, room and item program panel has a **Multiline SMAUG script**
option, alongside the original one-action addprogram format. Scripts can
contain several commands and nested conditional branches. The new script
format is validated when imported into the server. Supported mob triggers
include greet, speech, death, fight, random, move, give and bribe. Speech
scripts require a keyword. Existing simple programs continue working.

The room flag picker now includes **no_wander**, which blocks random
NPC movement into that room (including tailed beasts), without
blocking players, explicit spawns or scripted `mpgoto` actions.
Scripts now support `wait` (non-blocking delayed continuation),
arrival `entry` triggers, HP-percentage boss conditions, quest
memory markers, adjacent room messages, and bounded Chakra/Stamina
restoration.

SMAUG scripts now support `mpforce $n <allowed player command>`, which
runs a permitted movement, social, information or combat command
through the triggering player's normal command interpreter. The original
`mpforce say TEXT` shorthand remains usable. Immortals can use the
in-game `force <online player> <command>` command. Staff targets, account,
economy, file and builder commands are excluded for safety.

See [SMAUG scripting documentation](../docs/SMAUG_MOB_PROGRAMS.md)
for full editor commands, variables, grammar, examples and safety limits.

## Build areas

1. For an existing area, run `area export <area name>` as Implementor. Transfer the file from `data/area_exports/` and open it with **Open / import area JSON**. For a new area, enter its name and a non-overlapping room VNUM range (maximum 1,000 room numbers).
2. Place rooms on the snap grid. Mouse-wheel and zoom buttons change scale. Dragging a room snaps it back to the grid. **Connect rooms** creates matched two-way compass exits from their positions; use connection type for up/down and inside/outside.
3. Edit room names, descriptions, sectors, biomes, safety, room flags, reset messages, enabled/apartment/player-shop status, and declarative room programs. Doors, hidden exits, locks, keys and passcodes are configured per exit. Rooms retain exit settings when a linked room moves to another compass direction.
4. In each selected room, add mobs and items with persistent spawn points. **Edit** on a placed prototype opens the full mset/oset-style properties, including mob attributes, attack information, loot, flags, teachers, shop stock, item equipment/wear settings, rarity, stat bonuses, resistances, healing fields, and programs. Configure total/per-reset spawn limits. Optional SMAUG mob dice overrides take precedence over the initial damage/health inputs.
5. Edit area income and reset message. **Save draft now** or download a project backup at any time, including before rooms, mobs, and items are finished.

Only declarative program triggers/actions supported by the game engine are available: this does **not** provide arbitrary Python execution, in-game player editing, staff promotion, or unrestricted administration. Those are not ordinary area-building features.

## Deploy an area into the game

1. Click **Export area JSON** after editing and validation.
2. Transfer that JSON file (not the `*.nindo-project.json` backup) to the server's **existing** `data/area_imports/` folder. Never extract source releases over `data/`.
3. As Implementor, run `area import filename.json check`. Inspect any errors. Then run `area import filename.json` to apply. Imported content is saved across restarts.

Existing-area imports compare room, prototype, advanced field and spawn-cap baselines against the current server. If the area changed since export, **export a fresh copy from the game and merge changes**, instead of forcing a stale package into the world. Older editor packages without advanced baselines remain usable for their original basic fields, but advanced editing requires a fresh server export. Existing rooms and prototypes cannot be removed in the offline editor; remove them in game and export again. Links outside the area remain protected. The importer does not replace another area, player accounts, or saved world data.
