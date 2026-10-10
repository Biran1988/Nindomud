# Offline area builder

Open `Nindo_Area_Builder.html` in a browser. It needs no installation or
internet connection. Your current draft is kept in that browser's local
storage; use **Export area JSON** to make a portable backup or import package.

1. For an area already in the game, run `area export <area name>` as Implementor
   and copy the reported file from `data/area_exports/` to your computer. Click
   **Open / import area JSON** in the editor. Its existing rooms, exits, and
   placed mob/item prototypes will load. For a new area, set a unique room
   VNUM range and name; a matching empty reservation is allowed.
2. Add rooms and drag them onto the snap grid. Scroll over the map or use the
   zoom controls to see more rooms or inspect them closely. Select a room, press
   **Connect rooms**, then click its destination. The builder determines north,
   northeast, east, and other compass exits from grid placement and always
   creates the matching reverse exit. Choose a special connection type for
   up/down or inside/outside. Moving a linked room updates its compass exits;
   conflicting moves are rejected. Choose room flags from the dropdown. Edit descriptions, sector, biome,
   safety, and reset messages.
3. Select a room to create basic mob and item prototypes with spawn points.
   More detailed shop, equipment, and program settings can be added through
   `mset`, `oset`, and `rset` after import.
4. Export the JSON file and copy it to the server's `data/area_imports/` folder.
   Keep its filename unchanged. Do not replace the server's `data/` directory.
5. As an Implementor, run `area import filename.json check` to validate the
   entire package without changing the game. Then run `area import filename.json`.
   The area is available immediately and saved across restarts.

An exported existing area can update its own rooms and placed mob/item
prototypes, add new content, and retain advanced settings such as programs,
shop fields, and spawn caps. Existing rooms and prototypes cannot be deleted
through the editor; remove them in game, then export again. The import checks
whether editable content changed in game since export and refuses stale edits.
Existing links to other areas are kept. An area export includes prototypes with
spawn points inside the area's rooms; prototypes without one remain in game.

New area packages add unused VNUMs and refuse collisions or broken links. Link
new imported rooms to other areas using `rset exit` or `rset bexit` in game.
