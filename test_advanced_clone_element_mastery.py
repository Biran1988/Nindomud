"""Advanced clone workforce and use-grown chakra nature regression tests."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import data_jutsu
import elemental_mastery
import shadow_clone_workforce as workforce
import world
from models import Player


class AdvancedCloneWorkforceTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(world.WORLD, "rooms", {}),
            patch.object(combat, "MOBS_BY_ROOM", {}),
            patch.object(workforce, "ACTIVE_MOBS", {}),
            patch("storage.save_player"),
            patch("world_autosave.mark_dirty"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.player = Player("WorkTester", "WorkTester", level=100,
                             primary_class="ninjutsu", room_vnum=771234)
        self.player.chakra = self.player.maximum_chakra = 4000
        self.player.learned_skills.append("Advanced Shadow Clone Jutsu")
        self.session = NS(player=self.player, account=NS(staff_level="player"),
                          combat_target=None, pvp_target=None,
                          pending_cast=None, is_busy=lambda: False,
                          send=Mock())
        world.WORLD.rooms[771234] = world.Room(771234, "Rock face", "Stone", biome="mountain")

    def test_scroll_only_and_basic_mining_needs_no_copper_tool(self):
        self.assertTrue(data_jutsu.JUTSU["advanced shadow clone jutsu"]["scroll_only"])
        self.assertNotIn("advanced shadow clone jutsu",
                         data_jutsu.all_unlocked_for_class("ninjutsu", 100))
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["mine", "500"])
        state = self.player.work_clone
        self.assertEqual(self.player.chakra, 3500)
        self.assertEqual(state["ends_at"] - state["started_at"], 1800.0)
        self.assertEqual(state["tool"], "")
        self.assertEqual(state["tool_base"], "a copper pickaxe")
        self.assertEqual(len(combat.MOBS_BY_ROOM[771234]), 1)

    def test_upgraded_tool_breaks_and_basic_gathering_continues(self):
        self.player.job_levels["mining"] = 60
        self.player.inventory.append("A Steel Ironwood Pickaxe [1/250 uses]")
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["mine", "100", "with", "steel", "ironwood"])
        self.assertNotIn("A Steel Ironwood Pickaxe [1/250 uses]", self.player.inventory)
        import mining
        with patch.object(mining, "attempt_mine", return_value={"failed": False, "name": "an iron ore", "xp": 15}) as mine:
            workforce.tick(self.session, now=1065.0)
        self.assertEqual(mine.call_args_list[0].args[1], "a steel ironwood pickaxe")
        self.assertEqual(mine.call_args_list[1].args[1], "a copper pickaxe")
        self.assertEqual(self.player.work_clone["tool"], "")
        self.assertEqual(len(self.player.work_clone["items"]), 2)

    def test_apartment_receives_all_items_instead_of_caster_inventory(self):
        world.WORLD.rooms[771235] = world.Room(771235, "Private apartment", "Home",
                                                 apartment=True, owner=self.player.name)
        self.player.apartment_room_vnum = 771235
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["mine", "100"])
        self.player.work_clone["items"] = ["An Iron Ore", "An Iron Ore"]
        workforce.finish(self.session)
        self.assertEqual(self.player.inventory, [])
        self.assertEqual(world.WORLD.rooms[771235].ground_items,
                         ["An Iron Ore", "An Iron Ore"])
        self.assertFalse(self.player.work_clone)

    def test_training_requires_dummy_and_reports_gains(self):
        self.player.chakra_nature = "fire"
        self.player.chakra_nature_revealed = True
        self.player.learned_skills.append("Fireball Jutsu")
        self.player.skill_proficiencies["Fireball Jutsu"] = 20
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["train", "Fireball", "Jutsu", "100"])
        self.assertFalse(self.player.work_clone)
        dummy = combat.Mob(400, 6, "training dummy", 1, 100, 100, 771234, 0, 0)
        combat.MOBS_BY_ROOM[771234] = [dummy]
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["train", "Fireball", "Jutsu", "100"])
        self.assertEqual(self.player.work_clone["skill"], "Fireball Jutsu")
        with patch.object(workforce.random, "randint", return_value=1):
            workforce.tick(self.session, now=1400.0)
        self.assertGreater(self.player.skill_proficiencies["Fireball Jutsu"], 20)
        self.assertFalse(self.player.work_clone)
        self.assertIn("Fireball Jutsu", " ".join(str(c.args[0]) for c in self.session.send.call_args_list))

    def test_player_save_preserves_prepaid_task_and_pending_haul(self):
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["mine", "500"])
        self.player.work_clone["items"] = ["An Iron Ore"]
        loaded = Player.from_dict(self.player.to_dict())
        self.assertEqual(loaded.work_clone["funded"], 500)
        self.assertEqual(loaded.work_clone["items"], ["An Iron Ore"])

    def test_cannot_summon_second_worker_or_crafting_clone(self):
        with patch.object(workforce.time, "time", return_value=1000.0):
            workforce.command(self.session, ["mine", "100"])
            workforce.command(self.session, ["mine", "100"])
            workforce.command(self.session, ["weaponsmith", "100"])
        self.assertEqual(self.player.work_clone["funded"], 100)
        self.assertEqual(self.player.chakra, 3900)


class ElementAffinityMasteryTests(unittest.TestCase):
    def test_full_innate_affinity_does_not_grant_instant_bonus(self):
        player = Player("ElementTest", "ElementTest", chakra_nature="water",
                        chakra_nature_revealed=True)
        info = {"element": "water"}
        self.assertEqual(elemental_mastery.known_natures(player), ("water",))
        self.assertEqual(elemental_mastery.damage_multiplier(player, info), 1.0)
        player.element_mastery["water"] = 100
        self.assertAlmostEqual(elemental_mastery.damage_multiplier(player, info), 1.15)
        self.assertEqual(elemental_mastery.damage_multiplier(player, {"element": "fire"}), 1.0)

    def test_actual_elemental_use_grows_mastery_and_no_off_element(self):
        player = Player("ElementTest", "ElementTest", chakra_nature="fire",
                        chakra_nature_revealed=True)
        with patch.object(elemental_mastery.random, "randint", return_value=1):
            self.assertTrue(elemental_mastery.record_use(player, {"element": "fire"}))
            self.assertEqual(player.element_mastery["fire"], 1)
            self.assertFalse(elemental_mastery.record_use(player, {"element": "earth"}))
            self.assertEqual(player.element_mastery["fire"], 1)


if __name__ == "__main__":
    unittest.main()
