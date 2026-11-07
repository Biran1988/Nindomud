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
        mainland_roads.install_once()
    except mainland_roads.RoadInstallationError as error:
        # Keep the game running if one gate or room conflicts with a
        # player's live world; the installer has made no changes.
        print(f"[Mainland roads] Installation skipped: {error}")
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
