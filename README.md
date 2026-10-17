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

## Current release

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
