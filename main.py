"""
Entry point. Run with:  python3 main.py
Then connect with:      telnet localhost 4000
"""

import asyncio

import storage
import content
from server import run_server
from config import ADMIN_NAME


def main():
    storage.ensure_dirs()
    # Restore globally saved room colors before anyone can enter the MUD.
    import ui_palette
    ui_palette.load()
    content.populate()
    # Merge the commissioned VNUM 45-669 forest into existing /data once.
    import forest_of_death_grid
    forest_of_death_grid.install_once()
    forest_of_death_grid.install_final_room_once()
    # Merge the mainland highway and country gates into the existing /data
    # only once, just like the Forest of Death. Never replace existing
    # builder rooms or a previously occupied gate exit.
    import mainland_roads
    try:
        mainland_roads.ensure_live_mainland_area()
    except mainland_roads.RoadInstallationError as error:
        print(f"[Mainland roads] Area kept unchanged: {error}")
    try:
        mainland_roads.install_once()
    except mainland_roads.RoadInstallationError as error:
        # An existing room or exit is never replaced by the installer.
        print(f"[Mainland roads] Installation skipped: {error}")
    # A prior one-time marker does not guarantee all saved road rooms survived.
    # Repair the generated highway and just the missing exits at the existing
    # Leaf/Anki village entry rooms; never replace a regular village room.
    import mainland_recovery
    try:
        result = mainland_recovery.repair_missing_roads()
        if result["updated_rooms"]:
            print(f"[Mainland roads] Repaired {result['updated_rooms']} rooms "
                  f"({result['restored_rooms']} missing, "
                  f"{result['replaced_unfinished']} unfinished).")
        for warning in result["unavailable"]:
            print(f"[Mainland roads] Unavailable entry: {warning}")
    except mainland_recovery.RoadRecoveryError as error:
        print(f"[Mainland roads] Repair safely skipped: {error}")
    # Expand the same reserved mainland area with one-time camp/inn additions.
    # This does not touch the changes board or replace unrelated /data.
    import roadside_encounters
    try:
        roadside_encounters.install_once()
    except roadside_encounters.RoadsideInstallationError as error:
        print(f"[Roadside encounters] Installation skipped: {error}")
    try:
        repaired = roadside_encounters.repair_missing()
        if any(repaired.values()):
            print(f"[Roadside encounters] Restored: {repaired}")
    except roadside_encounters.RoadsideInstallationError as error:
        print(f"[Roadside encounters] Repair safely skipped: {error}")
    import commands
    commands.COMMANDS["inn"] = roadside_encounters.cmd_inn
    import seasonal_events
    seasonal_events.sync_visitors()
    from world import reconcile_apartment_ownership
    reconcile_apartment_ownership()
    # Money piles have their own automatic ledger; never replace world/area saves.
    import currency_piles
    currency_piles.restore_piles()
    # Player preferences are persistent: never reset saved config choices on boot.
    import help_system
    help_system.seed_default_help()
    if not storage.account_exists(ADMIN_NAME):
        print(f"No '{ADMIN_NAME}' account found yet. Connect and log in as "
              f"'{ADMIN_NAME}' to create the primary administrator password.")
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nServer shutting down.")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--preflight"]:
        # Reboot validates the installed source in a fresh interpreter
        # before disconnecting any players.
        import session
        import combat
        import commands
        import help_system
        import jutsu_colors
        import mangekyo_discovery
        import mainland_roads
    else:
        main()
