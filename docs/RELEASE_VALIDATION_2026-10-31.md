# Nindo_mud release verification — October 31, 2026

This report documents tests run against the extracted `Nindo_mud.zip` release and the newly built replacement, including actual in-game command routes.

## Passing checks

- **830/830 Python unit tests** passed (`python -m unittest discover -p 'test_*.py'`).
- **7/7 targeted gathering tests** passed. They cover all 9 upgraded items, Bukijutsu-level restrictions, material consumption, durability, holding the item, and fishing/mining/chopping from the live player command dispatcher.
- The 4 tier tables for fishing rods, lumber axes and mining pickaxes unlock their intended resources and retain earlier material overlap.
- New copper/Kindling starter tools cannot catch or mine the highest-tier resources.
- The bundled `Nindo_mud` single-file launcher passed `--preflight`.
- The server started in a fresh isolated directory, listened on a localhost TCP socket, accepted a connection, and sent the NindoMUD login banner.
- The ZIP passed Python compilation, archive CRC integrity, and path-safety checks; it contains no `data/` directory or saved player records.
- The live help-topic reference `help food shop`, previously missing from the SELL help, is now resolved.

## Remaining older smoke-suite limitation

The separate 18,000+-line `python test_smoke.py` is **not** fully passing. It contains assumptions from older versions of the game, including a now-disallowed `none` clan selection during character creation, an assumed flee route in a room without exits, outdated rank/experience limits, and a single-tool-per-job assertion. The modern 830-test regression suite and the targeted new live-command tests pass. These older smoke tests should be rewritten to current requirements, rather than changing working game mechanics to satisfy obsolete assumptions.

## Deploy safely

Stop the MUD. Extract this ZIP directly over the **existing program directory**, replacing code/launcher files while preserving its existing `data/` folder intact. Never delete the current folder or overwrite saved data. Back up `data/` before deployment.
