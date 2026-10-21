# Nindo_mud

NindoMUD is a Naruto-inspired multiplayer text RPG written in Python.

## Run

```bash
python3 main.py
```

## Test

```bash
python3 -m unittest discover -p "test_*.py"
```

## Deployment safety

The normal release is a **direct source-code ZIP**, not a bundled or
standalone server. Extract the updated Python files into the folder
where you already run `python3 main.py`, then restart that server.
It contains no standalone `Nindo_mud` executable and no nested ZIP.
Back up `data/` but never replace it.

Deploy source code over the existing server installation. Never replace the
server's `data/` directory: it contains authoritative player, area, world,
spawn-point, shop, and builder-created state.

Every release is distributed as `Nindo_mud.zip`. The archive includes source,
tests, and individual reference pages under `helpfiles/`; runtime save data is
excluded. Restart the server with `python3 main.py` after extracting the new
source files. Startup copies missing reference pages into `data/help/` and
refreshes system-owned pages, while preserving staff-written help. The
`helpfiles/` directory is for inspection and does not replace saved data.

To build the current code into the required `Nindo_mud.zip` release locally, run
`python3 scripts/build_release.py dist`. The GitHub Actions workflow
`Validate Nindo_mud and package source` also runs the full test suite and
publishes a downloadable `Nindo_mud` ZIP artifact when its run succeeds.
Use a freshly built archive instead of any older archive checked into the
repository. Never overwrite the live server's `data/` directory.

## Current release

Version 15.330 includes the latest healing and room-display changes:
natural HP/Chakra/Stamina regeneration remains active outside combat;
sleeping restores resources at **3x** ordinary standing recovery, even
once normal recovery reaches its protective flat cap; a room with
`accelerated_healing` heals at **a minimum of 10x** standing recovery
without a flat hospital cap, or **30x** when sleeping, until each resource
reaches its own maximum. Compact exits, mobs-before-items, blocking
`look` while sleeping, and the `safe` room flag are also included.
The download contains the freshly rebuilt `Nindo_mud` launcher plus
normal Python source. The ZIP excludes the live `data/` and saved
builder area/world/player files. `python3 main.py` remains supported.

Version 15.329 cleans up the Kage's mission-point item list: instead
of alternating bright colors on every word, 14 legendary items use ONE
readable, character-appropriate 256-color shade for their entire name.
Six specifically favored designs retain their original two-tone palette:
Kakashi's Mask, Deidara's Clay Pouches, Itachi's Ring, Neji's Forehead
Bandages, Tobi's Spiral Mask and Sakumo's White Fang Chakra Blade.
Colors affect only item name rendering in the shop, purchase confirmation,
inventory, equipment and examine; no prices, equipment bonuses, saved
player/room files or builder content are altered. The normal source-only
ZIP remains the standard distribution.

Version 15.328 restores the original `Nindo_mud.zip` format:
normal Python source files, tests, builder tools and helpfiles only.
No bundled single-file server, extra ZIP wrapper, or runtime save data.
The archive test extracts the downloaded source and runs
`python3 main.py --preflight` to verify that the standard installation
starts correctly. All gameplay features from previous releases remain.

Version 15.327 fixes update packaging: `Nindo_mud.zip` now includes
the actual rebuilt `Nindo_mud` standalone executable alongside the source
and `UPDATE_INSTRUCTIONS.txt`. The GitHub release regression test checks
the archive contains v15.327, the Kage colors, and the live color editor;
it boots the bundled launcher in `--preflight` mode. No saves or
builder-created area/world files are included.

Version 15.326 upgrades the 20 legendary Kage mission-point items to unique
two-tone xterm-256 color palettes, matched to their Naruto designs: Naruto
orange/blue, Sasuke Uchiha blue/crimson, Gaara desert sand/red, Konan
paper-blue/blossom pink, and 16 more. Their saved item names, VNUMs,
wear slots and 500 mission-point prices remain unchanged. The Kage `list`
shop, purchase messages, inventory/equipment and examine now show those
character-specific color treatments, while rarity tags still only appear
on examine.

Six comparatively light legendary sets (Deidara, Pain, Konan, Tobi,
Kabuto, and Jiraiya) also receive moderate Nindo_mud-balanced, dynamically
calculated combat bonuses. The original NarutoMUD's exact item-level
bonus table could not be verified from public sources, so NO bonuses are
claimed as imported. The combat engine now honors the `hitroll` and
`damroll` on ALL equipped armor/jewelry too (previously only wielded
weapon prototypes counted) and correctly normalizes old negative
`armor_class` protection values alongside positive headband bonuses.
Existing-equipped items gain these derived bonuses immediately, without
migrating player saves or overwriting builder areas or prototypes.

Version 15.325 adds a LIVE, global admin room-color scheme. Administrator and
Implementor accounts can change room names, descriptions and exits in real
time, using any xterm-256 foreground (0-255). Enter `colorscheme` to see
current settings and preview your own room, or try:
`colorscheme name 208`, `colorscheme desc 223`,
`colorscheme exits 110`, `colorscheme set 208 223 110`, or
`colorscheme reset`. Every successful edit automatically writes
`data/color_scheme.json` using an atomic, synced replace before it
becomes live; startup restores the saved settings, even after crashes.
`save world` is not needed, and *no builder area/room files are changed.*
Other colors throughout the MUD are unaffected.

Version 15.324 changes **only** the two global room-display colors to the
Ember & Sand scheme: room name xterm-256 **208** (`&[208]`, vibrant ember
orange) and room description xterm-256 **223** (`&[223]`, warm sand).
The centralized display palette applies to ordinary, illusory, and
reconnaissance room views without editing any saved room or area data,
or altering exits, NPCs, items, or combat color schemes.

Version 15.323 refines the global look-room palette: every ordinary,
illusory and scouting room display uses jade green (xterm-256 color 114)
for room names and readable soft silver (color 253) for descriptions.
Exits, players, mobs, items, combat, and saved builder/area data keep
their existing appearance. Iruka's only exam launch phrase is now
`say Start Genin exam` spoken in the room with mob VNUM 11; the old
`ask iruka about graduation` and legacy scripted shortcut no longer
launch the exam.

Version 15.322 replaces Iruka (mob VNUM 11)'s instant Academy graduation
with a challenging Genin written exam. Before starting, an Academy Student
must reach level 10 and master all five starting disciplines to 100%:
Shadow Shuriken Technique, Dynamic Entry, Demonic Illusion: Hell Viewing
Technique, Throw Shuriken, and Strong Fist Style. Use
`say Start Genin exam` when standing beside Iruka. Each attempt
draws 10 of 20 Naruto-anime trivia questions in a different combination,
randomly shuffles all four answer positions, and requires a 10/10 score.
The old `iruka_graduation_check` mob program starts the quiz rather than
promoting outright. A pass retains the existing Genin headband, 50 mission
points, and global promotion announcement. Player-built rooms, templates
and saved area data are untouched.

Version 15.321 adds real ground Ryo piles and direct player-to-player
money transfers: `drop 500 ryo`, `look ryo`, `get ryo`,
`get 500 ryo`, `get all ryo`, and `give 500 ryo <player>`.
The piles stay visible to other players, survive restarts through a
separate auto-saved `data/ground_ryo.json` ledger, and never overwrite
builder-created room, area or world saves. Pickups credit your Ryo
balance without using inventory slots.

Version 15.320 makes elemental clone scouting visually indistinguishable from
ordinary player movement and speech. Both the stationary real body and the
traveling clone display the player's normal name and description (no remote
control label); look/examine, say and emotes don't disclose a clone connection.
The pilot receives the destination room normally, while others see one
standard departure/arrival pair. The body remains physically vulnerable, and
only dispersal or defeat returns control.

Version 15.319 keeps the original caster's body visible and physically
stationary throughout elemental clone reconnaissance—even while rendering
the clone's first-person `look`. Returning to the body's room shows the
motionless original character, while moving the clone gives a single
clear movement confirmation instead of duplicate room broadcasts.

Version 15.318 introduces first-person reconnaissance through fully mastered
elemental clones: `clone control`, `clone status` and `clone disperse`.
Control cannot start during combat, the real body remains stationary and
vulnerable, and only dispersal or the clone's defeat returns the viewpoint.
The clone is a real attackable Mob with its own HP and real-room movement.
Adds autonomous `aggressive_village`, `aggressive_clan` and
`aggressive_everyone` mobile flags, configurable target village/clan
fields, and hostile mobs capable of attacking controlled elemental clones.
Original world and area save files remain untouched. See
docs/CLONE_RECON_AND_AGGRESSION.md for builder commands and mechanics.

Version 15.317 introduces the immortal `force <player> <command>`
command and full targeted SMAUG `mpforce $n <command>` support.
Approved movement, social, informational and combat commands execute
through the target character's ordinary game handler; builder, account,
economy and security commands are excluded. Administrator/Implementor
`force all` is restricted to safe social/status actions. Each forced
target sees a notice; immortal actions are logged. Older NPC
`mpforce say`, `mpforce look` and freeform `mpforce emote` scripts
remain compatible. See docs/SMAUG_MOB_PROGRAMS.md.

Version 15.316 expands the SmaugFUSS-inspired script engine with
non-blocking `wait` continuations, mob `entry` events, HP/Chakra/
Stamina conditions, remembered quest markers, ambient echoes, and
additional bounded NPC actions. Adds the **no_wander** room flag
(`rset flags no_wander`) to prevent random wandering mobs and
tailed beasts entering that room; players and deliberate spawns are
unaffected. Saved room flags are preserved by existing world/area
persistence. See docs/SMAUG_MOB_PROGRAMS.md for details.

Version 15.315 adds a real, multiline SmaugFUSS-inspired program editor:
mob mpedit/mpstat/mpset, room rpedit/rpstat, object opedit/opstat,
nested if/or/else/endif, $n/$i and other context variables, bounded
NPC actions, and NPC hand-in/bribe interactions. Existing addprogram
entries still execute unchanged, and save world persists all new scripts.
The visual HTML editor also supports multiline scripts. See
docs/SMAUG_MOB_PROGRAMS.md for syntax, supported events and limits.
This is a sandboxed SmaugFUSS-inspired subset, not complete SMAUG
language parity.

Version 15.314 fixes the synchronized-Wander problem: each live mob receives
its own independently seeded first movement timer at spawn. Groups that spawn
at the same instant stagger their departures, and a mob is only processed once
per pulse, regardless of which room it enters. Subsequent moves retain the
normal 2–4 minute independent interval. Staff can use `mstat <mob name>` or
`mstat 2.<mob keyword>` in the mob's room to see that specific instance's
next Wander countdown. Updating source requires a server restart; existing
area/world saves remain untouched.

Version 15.313 adds an uploadable, image-backed Full World Map tab. Use Implementor
`area exportworld` to obtain the current world in one JSON file, upload it,
position areas over a PNG/JPG/WebP background, inspect cross-area links and
open individual imported areas in the room editor. Map autosave and a portable
world backup carry linked area drafts with them. Editing a world overview
never imports or replaces game world files. See `builder/README.md`.

Version 15.312 expands the offline area editor with multi-project autosaves,
portable backup/restore, full room/mob/item builder settings, programs, shop
stock, exit door settings and spawn caps. Game imports validate advanced edits
against the original server export before applying them.

Version 15.307 added a trainable signature move: select a 100%-mastered active
jutsu with `signature <move>`, practice it to 150%, then gain a 25% bonus to
its damage or effect duration. Switching drops the old move back to 100%.
The visual area editor remains at `builder/Nindo_Area_Builder.html`.
See `builder/README.md` for the offline-to-server workflow. Earlier updates
added elemental releases, staff-wide jutsu testing, and jutsu base damage
scaling along the damage-word ladder. The `reboot` command checks installed
source before disconnecting players and reports import errors without taking
the server offline.
Ushiro remains an opener. The prior update added Bukijutsu-only medicinal and antidote pill crafting with
selectable item levels, Medicinal Herbs, and level/effect details in `examine`.
Earlier updates added Ninja Arts/Bukijutsu throws, traps, trap disabling,
permanent item-bound weapon properties, wind-only fan attacks, and Water
Release: Glue Technique. It also includes the 21 Genjutsu techniques,
Barrier's 25% damage reduction for three minutes or until moving rooms, and
three-minute combined Sharingan upkeep reports.
See `docs/RELEASE_NOTES.md` for the files and checks that verify this release.
Builders can use `mset fields` for a wrapped mob field list and
`mset fields player` for the separate player field list.
Builder field names also accept compact forms such as `mset flags`,
`oset flags`, `oset wear`, `oset wearloc`, and `oset concap`.
The original underscore spellings still work. Player training accepts
short forms such as `train str` and `train con`.
