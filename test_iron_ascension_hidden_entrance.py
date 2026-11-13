"""Permanent hidden Iron Ascension entrance uses a narrow saved-world merge."""
import unittest
from copy import deepcopy
from unittest.mock import patch

import areas
import iron_ascension as tower
import storage
import world


class IronAscensionEntranceTests(unittest.TestCase):
    def setUp(self):
        self.road = world.Room(tower.ROAD_ENTRANCE_VNUM,
                               "Grassland Border Trail - winding passage",
                               "Travelers follow the forest trail.")
        self.road.exits.update({"northwest": 20673, "southeast": 20675})
        self.first = world.Room(tower.START, "Iron Ascension - Floor 1", "First arena")
        self.rooms = {self.road.vnum: self.road, self.first.vnum: self.first}
        self.saved = {"rooms": {
            str(self.road.vnum): {
                "name": self.road.name, "description": self.road.description,
                "exits": dict(self.road.exits), "exit_flags": {},
                "custom_builder_setting": "untouched",
            },
            "9": {"name": "Konoha", "exits": {"south": 20501}},
        }, "mobs": {"999": {"name": "untouched"}}}

    def test_hidden_road_exit_to_floor_one_and_reverse_only(self):
        with (patch.object(world.WORLD, "get", side_effect=self.rooms.get),
              patch.object(storage, "load_world_state", return_value=deepcopy(self.saved)),
              patch.object(storage, "save_world_state") as save):
            self.assertEqual(tower.install_entrance(), self.road.vnum)
        merged = save.call_args.args[0]
        self.assertEqual(merged["rooms"][str(self.road.vnum)]["exits"]["northeast"], tower.START)
        self.assertEqual(merged["rooms"][str(self.road.vnum)]["exit_flags"]["northeast"], ["hidden"])
        self.assertEqual(merged["rooms"][str(self.road.vnum)]["custom_builder_setting"], "untouched")
        self.assertEqual(merged["rooms"]["9"], self.saved["rooms"]["9"])
        self.assertEqual(merged["mobs"], self.saved["mobs"])
        self.assertEqual(self.road.exits["northeast"], tower.START)
        self.assertEqual(self.first.exits["southwest"], self.road.vnum)
        self.assertEqual(self.road.exit_flags["northeast"], ["hidden"])
        self.assertEqual(set(self.first.exits), {"southwest"})

    def test_occupied_exit_never_overwrites_builder_links(self):
        self.road.exits["northeast"] = 999999
        with (patch.object(world.WORLD, "get", side_effect=self.rooms.get),
              patch.object(storage, "load_world_state", return_value=deepcopy(self.saved)),
              patch.object(storage, "save_world_state") as save):
            with self.assertRaises(tower.IronAscensionError):
                tower.install_entrance()
        save.assert_not_called()
        self.assertEqual(self.road.exits["northeast"], 999999)
        self.assertEqual(self.first.exits, {})

    def test_old_prototype_area_is_switched_live_without_replacing_registry(self):
        entry = {"name": tower.AREA_NAME, "vnum_start": tower.START,
                 "vnum_end": tower.END, "prototype": True,
                 "builders": ["existing-builder"]}
        with (patch.object(areas, "all_areas", return_value={tower.AREA_NAME.lower(): entry}),
              patch.object(areas, "set_prototype") as set_prototype):
            tower._validate_area()
        set_prototype.assert_called_once_with(tower.AREA_NAME, False)


if __name__ == "__main__":
    unittest.main()
