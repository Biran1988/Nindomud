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
    content.populate()
    from world import reconcile_apartment_ownership
    reconcile_apartment_ownership()
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
    main()
