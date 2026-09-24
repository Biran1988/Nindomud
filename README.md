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

Every release is distributed as `Nindo_mud.zip`. The archive intentionally
contains source and tests only; runtime save data is excluded.

## Current release

The archive includes `damage_messages.py` and its integration in combat,
commands, and Mangekyo attacks. Damage is shown as a colored word from
TRIVIAL to EXTINCTION-LEVEL (10,000+). It also includes persistent shopkeeper
stock and item prototypes, 15-minute area resets, the restore and respawn
commands, SMAUG-style builder commands, and progressive leveling and mob XP.
See `docs/RELEASE_NOTES.md` for the files and checks that verify this release.
Builders can use `mset fields` for a wrapped mob field list and
`mset fields player` for the separate player field list.
Builder field names also accept compact forms such as `mset flags`,
`oset flags`, `oset wear`, `oset wearloc`, and `oset containercapacity`.
The original underscore spellings still work. Player training accepts
short forms such as `train str` and `train con`.
