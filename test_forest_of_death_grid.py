"""Forest of Death grid geometry and guarded saved-data migration."""
import os
import tempfile
import unittest
from unittest.mock import patch

import forest_of_death_grid as forest
import storage
import world


class ForestOfDeathGridTests(unittest.TestCase):
    def test_all_625_rooms_have_reciprocal_boundary_clipped_exits(self):
        rooms = forest.build_rooms()
        self.assertEqual(len(rooms), 625)
        self.assertEqual(set(rooms), set(range(45, 670)))
        self.assertEqual(forest.vnum_at(0, 0), 45)
        self.assertEqual(forest.vnum_at(24, 24), 669)
        self.assertEqual(forest.TOWER_VNUM, 357)
        reverse = {"north": "south", "south": "north", "east": "west", "west": "east"}
        for y in range(25):
            for x in range(25):
                v = forest.vnum_at(x, y)
                expected = 4 - (x == 0) - (x == 24) - (y == 0) - (y == 24)
                self.assertEqual(len(rooms[v].exits), expected)
                self.assertEqual(rooms[v].biome, "forest")
                for direction, other in rooms[v].exits.items():
                    self.assertEqual(rooms[other].exits[reverse[direction]], v)
        self.assertEqual(rooms[45].exits, {"north": 70, "east": 46})
        self.assertEqual(rooms[669].exits, {"south": 644, "west": 668})
        self.assertEqual(rooms[357].exits, {"north": 382, "south": 332, "east": 358, "west": 356})

    def test_install_patches_only_forest_rooms_and_never_reapplies(self):
        with tempfile.TemporaryDirectory() as directory:
            with (patch.object(storage, "DATA_DIR", directory),
                  patch.object(storage, "ACCOUNTS_DIR", os.path.join(directory, "accounts")),
                  patch.object(storage, "PLAYERS_DIR", os.path.join(directory, "players")),
                  patch.object(world.WORLD, "rooms", {44: world.Room(44, "Keep me", "original"),
                                                    45: world.Room(45, "Replaced", "old"),
                                                    670: world.Room(670, "Keep too", "original")})):
                old = {"rooms": {"44": {"vnum": 44, "name": "Keep me"},
                                 "45": {"vnum": 45, "name": "Replaced"},
                                 "670": {"vnum": 670, "name": "Keep too"}},
                       "mobs": {"11": {"name": "Iruka"}},
                       "items": {"222": {"name": "Scroll"}},
                       "deleted_areas": [], "other_metadata": {"unchanged": True}}
                storage.save_world_state(old)
                self.assertTrue(forest.install_once())
                new = storage.load_world_state()
                self.assertEqual(new["rooms"]["44"], old["rooms"]["44"])
                self.assertEqual(new["rooms"]["670"], old["rooms"]["670"])
                self.assertEqual(new["mobs"], old["mobs"])
                self.assertEqual(new["items"], old["items"])
                self.assertEqual(new["other_metadata"], old["other_metadata"])
                self.assertEqual(new["rooms"]["45"]["exits"], {"north": 70, "east": 46})
                self.assertEqual(len([k for k in new["rooms"] if 45 <= int(k) <= 669]), 625)
                self.assertTrue(os.path.isfile(os.path.join(directory, "world_state.json.bak")))
                new["rooms"]["45"]["name"] = "My personal edit"
                storage.save_world_state(new)
                self.assertFalse(forest.install_once())
                self.assertEqual(storage.load_world_state()["rooms"]["45"]["name"], "My personal edit")


if __name__ == "__main__":
    unittest.main()
