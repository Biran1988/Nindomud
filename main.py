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
    import seasonal_events
    seasonal_events.sync_visitors()
    from world import reconcile_apartment_ownership
    reconcile_apartment_ownership()
    # Money piles have their own automatic ledger; never replace world/area saves.
    import currency_piles
    currency_piles.restore_piles()
    import commands
    commands.force_all_player_configs_on()
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
    else:
        main()
