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
