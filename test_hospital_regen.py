"""Hospital recovery remains much stronger without changing normal regeneration."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import regen
import world


class HospitalRegenerationTests(unittest.TestCase):
    def setUp(self):
        self.normal = world.Room(9810, "Training Field", "Open field")
        self.hospital = world.Room(9811, "Village Hospital", "Medical ward")
        self.hospital.flags.append("accelerated_healing")
        self.player = NS(
            room_vnum=9810, position="standing", health=100, maximum_health=1000,
            chakra=100, maximum_chakra=1000, stamina=100, maximum_stamina=1000,
            chakra_control=10,
        )

    def test_natural_regen_still_occurs_outside_hospital(self):
        with patch.object(world.WORLD, "get", return_value=self.normal):
            regen.tick_player(self.player)
        self.assertGreater(self.player.health, 100)
        self.assertGreater(self.player.chakra, 100)
        self.assertGreater(self.player.stamina, 100)

    def test_hospital_better_for_all_three_resources(self):
        normal = {}
        with patch.object(world.WORLD, "get", return_value=self.normal):
            regen.tick_player(self.player)
        normal = (self.player.health - 100, self.player.chakra - 100, self.player.stamina - 100)
        self.player.health = self.player.chakra = self.player.stamina = 100
        self.player.room_vnum = 9811
        with patch.object(world.WORLD, "get", return_value=self.hospital):
            regen.tick_player(self.player)
        hospital = (self.player.health - 100, self.player.chakra - 100, self.player.stamina - 100)
        self.assertTrue(all(h > n for h, n in zip(hospital, normal)))
        self.assertGreaterEqual(hospital[0], normal[0] * 4)

    def test_hospital_bypasses_all_resource_caps(self):
        self.player.maximum_health = 100000
        self.player.maximum_chakra = 100000
        self.player.maximum_stamina = 100000
        self.player.room_vnum = 9811
        with patch.object(world.WORLD, "get", return_value=self.hospital):
            regen.tick_player(self.player)
        self.assertGreater(self.player.health - 100, 150)
        self.assertGreater(self.player.chakra - 100, 50)
        self.assertGreater(self.player.stamina - 100, 25)

    def test_sleeping_triples_uncapped_base_rate(self):
        standing = regen.BASE_REGEN_PERCENT["health"] * 10000
        standing_gain = regen._regen_amount(10000, "health", 1.0)
        sleeping_gain = regen._regen_amount(10000, "health", regen.POSITION_MULTIPLIER["sleeping"])
        self.assertEqual(regen.POSITION_MULTIPLIER["sleeping"], 3.0)
        self.assertGreater(sleeping_gain, standing_gain)

    def test_hospital_at_least_ten_times_normal_for_small_stats(self):
        for resource in ("health", "chakra", "stamina"):
            normal = regen._regen_amount(100, resource, 1.0)
            hospital = regen._regen_amount(100, resource, 10.0, hospital=True)
            self.assertGreaterEqual(hospital, normal * 10)

    def test_sleeping_stacks_with_hospital_healing(self):
        self.player.position = "sleeping"
        with patch.object(world.WORLD, "get", return_value=self.hospital):
            regen.tick_player(self.player)
        self.assertGreater(self.player.health, 100)

    def test_healing_never_exceeds_maximum(self):
        self.player.health = self.player.chakra = self.player.stamina = 999
        with patch.object(world.WORLD, "get", return_value=self.hospital):
            regen.tick_player(self.player)
        self.assertEqual((self.player.health, self.player.chakra, self.player.stamina),
                         (1000, 1000, 1000))

    def test_defeated_players_do_not_regenerate(self):
        self.player.health = 0
        with patch.object(world.WORLD, "get", return_value=self.hospital):
            regen.tick_player(self.player)
        self.assertEqual(self.player.health, 0)


if __name__ == "__main__":
    unittest.main()
