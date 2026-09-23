# Nindo restore / respawn update (includes emotes)

Administrator and Implementor commands:

- `restore`: refill all connected players' HP, chakra, and stamina to their own
  maximums, including editors/pagers. Offline saves and status effects are not
  changed. Combat continues normally. Uses existing autosave for player progress.
- `respawn`: immediately refill registered mob populations to total caps, ignoring
  per-period limits. Existing mobs and wanderers within their area are counted;
  they are not healed, moved, or replaced. Pending timer spawns are processed
  without leaving duplicate timers. Uncapped populations mean one per template
  per area, as in normal area resets. Unassigned rooms are checked individually.
  Unused prototypes and items are not spawned. Disabled templates are skipped.

Use `help restore` and `help respawn`. The 80-emote update is also included.

## Safe installation

Back up your current code and data outside the game folder. These replacement
files are based on Nindo_mud_github_ready.zip plus our emote update. If your live
code has newer independent changes, merge those before installing.

Save player progress and pending builder work normally, then stop the server.
Extract this ZIP and upload ONLY these four runtime files using WinSCP or PSCP
to the existing folder containing main.py:

- commands.py
- help_system.py
- admin_actions.py (new)
- emotes.py

Restart with your existing service/launch procedure, not a second server process.
No saved world/area files, data directories, configuration, starter content, or
area/world engine modules are included. Never replace or delete the game folder.
New command help topics use the existing startup help mechanism.

Optional isolated tests (upload test_admin_actions.py and test_emotes.py):

    python3 -m unittest test_admin_actions test_emotes -v

Rollback: stop the server and restore the backed-up commands.py and
help_system.py. Extra new modules may remain unused. Leave saved data intact.
