# Mob class cleanup - 2026-09-20

Only ninjutsu, taijutsu, genjutsu, and bukijutsu are assignable mob classes.
Mobs default to None, not a random class. Use:

    mset <vnum> class ninjutsu
    mset <vnum> class none

Assignment/clearing updates the prototype and its currently spawned mobs.
Race and the obsolete char_class field are no longer offered or displayed.
Old saved race/char_class values are ignored; no saved world files are rewritten
by installation. Invalid legacy mob primary classes spawn as None. Player class
choices remain the existing four classes, and player race was not a model field.
This update does not change player saves or assign new classes to players.

Back up your code/data, save pending builder work normally, and stop the server.
Upload ONLY combat.py and olc.py into the existing folder containing main.py,
using WinSCP/PSCP, then restart through your normal service/launch procedure.
If your live files have newer independent edits, merge them before replacing.
These replacements are based on the original repository ZIP used in this chat.

No saved world, area, spawn, player data, or configuration is included. Do not
delete or replace your game directory. This incremental update can be installed
alongside the prior emote and restore/respawn updates; it does not bundle them.

Optional tests: upload test_mob_classes.py and run:

    python3 -m unittest test_mob_classes -v

The included test_smoke.py updates the old random-class expectations. Only run
the full smoke suite in a separate disposable copy, never in a live game folder.

To roll back, stop the server and restore your backed-up combat.py and olc.py.
Leave all saved world and player data untouched.
