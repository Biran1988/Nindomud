# Nindo_mud release contents

This is a complete source release. Extract the archive into a copy of your
existing server installation, keeping the server's `data/` directory intact.

## Recent changes included

- Colored damage words through 10,000+ damage: `damage_messages.py`, `colors.py`,
  `combat.py`, `commands.py`, and `mangekyo.py`.
- Shopkeeper stock and item prototypes saved by `save world` and restored after
  reboot: `world_persistence.py`, `storage.py`, and `world.py`.
- Area reset messages, missing mob respawns, and a 15-minute reset interval:
  `areas.py`, `spawn_points.py`, and `server.py`.
- Global `restore` and `respawn` commands, restricted mob classes, and builder
  tools including `ostat`: `admin_actions.py`, `data_classes.py`, `olc.py`,
  and `commands.py`.
- Progressive leveling, automatic level-sensitive mob XP, and migration of
  existing characters: `leveling.py`, `combat.py`, and `storage.py`.
- The in-game change history through version 15.226: `changelog.py`.
- `mset fields` is now grouped and wrapped for a MUD client;
  `mset fields player` displays player fields separately: `olc.py`.
- Builder commands accept compact field names, including `flags`, `wear`,
  `wearloc`, `concap`, and joined spellings for the other fields.
  `train str`, `train con`, and the other stat abbreviations work: `olc.py`,
  `commands.py`, and `help_system.py`.
- Local `say` chat displays in bright green: `commands.py`.
- `eq`/`equipment` lists every wear slot, including empty ones: `commands.py`.
- Setting `weapontype` also sets `itemtype weapon` and `wearloc wielded`;
  its matching skill shows in `ostat` and is learned when equipped.
  `wear <weapon>` and `wear all` wield weapons: `olc.py`, `commands.py`,
  `data_weapons.py`.

Verification: `python3 -m unittest discover -p 'test_*.py'` and
`python3 test_smoke.py`. The tests cover damage tiers, shop persistence,
leveling, mob XP, and the older gameplay smoke checks.
