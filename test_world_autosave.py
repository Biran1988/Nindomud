"""Regression tests for silent background builder saves and reboot checkpoints."""

import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import commands
import olc
import spawn_points
import storage
import world
import world_autosave
from models import Player


class BackgroundWorldSaveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for target, name, value in (
            (storage, "DATA_DIR", self.temp.name),
            (storage, "ACCOUNTS_DIR", os.path.join(self.temp.name, "accounts")),
            (storage, "PLAYERS_DIR", os.path.join(self.temp.name, "players")),
            (olc, "AUDIT_LOG_PATH", os.path.join(self.temp.name, "builder_audit.log")),
            (world.WORLD, "rooms", {}),
            (combat, "MOB_TEMPLATES", {}),
            (combat, "MOBS_BY_ROOM", {}),
            (olc, "OBJECT_TEMPLATES", {}),
        ):
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        world.WORLD.add_room(world.Room(900, "Original", "Original description."))
        world.WORLD.add_room(world.Room(901, "New room", "Second room."))
        import config
        self.session = NS(
            account=NS(name=config.ADMIN_NAME, staff_level="implementor"),
            player=Player(config.ADMIN_NAME, config.ADMIN_NAME, room_vnum=900),
            send=Mock(),
        )

    async def test_room_links_mobs_and_items_are_silently_saved(self):
        olc.cmd_rset(self.session, ["name", "Updated", "Leaf", "Hall"])
        olc.cmd_rset(self.session, ["bexit", "east", "901"])
        olc.cmd_mset(self.session, ["create", "950", "a", "training", "dummy"])
        olc.cmd_mset(self.session, ["950", "level", "12"])
        olc.cmd_oset(self.session, ["create", "960", "an", "iron", "kunai"])
        olc.cmd_oset(self.session, ["960", "cost", "234"])

        # Yield to the next game loop tick to dispatch the pending snapshot.
        for _ in range(50):
            await asyncio.sleep(0.01)
            saved = storage.load_world_state()
            if saved.get("rooms", {}).get("900", {}).get("name") == "Updated Leaf Hall":
                break
        world_autosave.wait_for_pending()
        saved = storage.load_world_state()
        self.assertEqual(saved["rooms"]["900"]["exits"]["east"], 901)
        self.assertEqual(saved["rooms"]["901"]["exits"]["west"], 900)
        self.assertEqual(saved["mobs"]["950"]["level"], 12)
        self.assertEqual(saved["items"]["960"]["cost"], 234)
        self.assertFalse(any("world saved" in str(call).lower()
                             for call in self.session.send.call_args_list))

    async def test_follow_up_edit_while_disk_busy_is_not_lost(self):
        import world_persistence
        # An initial pending save, a new edit, and a forced final checkpoint
        # must all resolve to the most recent builder version.
        olc.cmd_rset(self.session, ["name", "First"])
        await asyncio.sleep(0.01)
        olc.cmd_rset(self.session, ["name", "Last"])
        world_persistence.save_world()
        self.assertEqual(storage.load_world_state()["rooms"]["900"]["name"], "Last")

    async def test_atomic_backup_survives_corrupted_primary(self):
        storage.save_world_state({"rooms": {"900": {"name": "First"}}})
        storage.save_world_state({"rooms": {"900": {"name": "Second"}}})
        with open(os.path.join(self.temp.name, "world_state.json"), "w", encoding="utf-8") as f:
            f.write("{truncated")
        self.assertEqual(storage.load_world_state()["rooms"]["900"]["name"], "First")
        storage.save_world_state({"rooms": {"900": {"name": "Third"}}})
        self.assertEqual(storage.load_world_state()["rooms"]["900"]["name"], "Third")
        with open(os.path.join(self.temp.name, "world_state.json.bak"),
                  encoding="utf-8") as f:
            import json
            self.assertEqual(json.load(f)["rooms"]["900"]["name"], "First")

    async def test_deleted_custom_prototypes_do_not_reappear(self):
        storage.save_custom_templates({
            "mobs": {"123": {"short_desc": "Deleted NPC"}},
            "items": {"456": {"short_desc": "Deleted Object"}},
        })
        spawn_points.refresh_template_snapshots()
        self.assertNotIn("123", storage.load_custom_templates().get("mobs", {}))
        self.assertNotIn("456", storage.load_custom_templates().get("items", {}))


class RebootWorldSaveTests(unittest.TestCase):
    def test_reboot_saves_world_before_restarting(self):
        order = []
        session = NS(account=NS(staff_level="implementor"), send=Mock())
        with (patch.object(commands, "_reboot_preflight", return_value=""),
              patch("world_persistence.save_world", side_effect=lambda: order.append("world saved")),
              patch.object(commands, "_reboot_process", side_effect=lambda: order.append("reboot")),
              patch("session.ACTIVE_SESSIONS", [])):
            commands.cmd_reboot(session, [])
        self.assertEqual(order, ["world saved", "reboot"])

    def test_reboot_stays_online_if_world_save_fails(self):
        session = NS(account=NS(staff_level="implementor"), send=Mock())
        with (patch.object(commands, "_reboot_preflight", return_value=""),
              patch("world_persistence.save_world", side_effect=OSError("disk full")),
              patch.object(commands, "_reboot_process") as reboot,
              patch("session.ACTIVE_SESSIONS", [])):
            commands.cmd_reboot(session, [])
        reboot.assert_not_called()
        self.assertIn("Reboot cancelled", session.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
