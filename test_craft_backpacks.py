"""Tiered, persistent backpacks with independent stored-item capacity."""
import unittest
from unittest.mock import patch

import commands
import content
import data_crafting
import inventory
import models
import olc
from session import Session, State


class CraftBackpackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def make_session(self, cls='bukijutsu', level=100):
        messages = []
        session = Session(messages.append, lambda: None)
        session.state = State.PLAYING
        player = models.Player('BackpackTester', 'BackpackTester', primary_class=cls, level=level)
        player.stamina = 1000
        session.player = player
        session.is_busy = lambda: False
        session.start_timed_action = lambda _type, _seconds, callback: callback()
        return session, player, messages

    def test_all_three_recipes_have_real_separate_item_capacities(self):
        expected = [('iron', 15), ('steel', 30), ('chakra', 50)]
        for tier, capacity in expected:
            with self.subTest(tier=tier):
                session, player, output = self.make_session()
                recipe = data_crafting.BACKPACK_RECIPES[tier]
                player.inventory = [recipe['wood'], recipe['ingot']]
                with patch.object(commands.storage, 'save_player') as save:
                    commands.cmd_craft(session, ['backpack', tier])
                self.assertEqual(player.inventory, [recipe['name']])
                self.assertEqual(len(player.backpack_contents), 0)
                self.assertEqual(recipe['capacity'], capacity)
                self.assertEqual(commands._find_object_prototype_by_name(recipe['name'])['container_capacity'], capacity)
                save.assert_called_once_with(player)
                self.assertIn(str(capacity), ''.join(output))
                self.assertEqual(models.Player.from_dict(player.to_dict()).inventory, player.inventory)

    def test_chakra_steel_two_word_alias_works(self):
        session, player, _output = self.make_session()
        recipe = data_crafting.BACKPACK_RECIPES['chakra']
        player.inventory = [recipe['wood'], recipe['ingot']]
        with patch.object(commands.storage, 'save_player'):
            commands.cmd_craft(session, ['bag', 'chakra', 'steel'])
        self.assertIn(recipe['name'], player.inventory)

    def test_craft_class_and_inventory_requirements(self):
        recipe = data_crafting.BACKPACK_RECIPES['chakra']
        for cls, level in [('ninjutsu', 100), ('bukijutsu', 24)]:
            session, player, output = self.make_session(cls, level)
            player.inventory = [recipe['wood'], recipe['ingot']]
            commands.cmd_craft(session, ['backpack', 'chakra'])
            self.assertEqual(player.inventory, [recipe['wood'], recipe['ingot']])
            self.assertTrue(any('requires' in msg.lower() or 'only' in msg.lower() for msg in output))
        session, player, _output = self.make_session('ninjutsu', 100)
        iron = data_crafting.BACKPACK_RECIPES['iron']
        player.inventory = [iron['wood'], iron['ingot']]
        with patch.object(commands.storage, 'save_player'):
            commands.cmd_craft(session, ['backpack', 'iron'])
        self.assertIn(iron['name'], player.inventory)

    def test_capacity_50_is_enforced_as_actual_stored_item_count(self):
        session, player, messages = self.make_session()
        name = data_crafting.BACKPACK_RECIPES['chakra']['name']
        player.inventory = [name] + ['A Basic Kunai'] * 51
        for i in range(50):
            commands.cmd_put(session, ['kunai', 'in', 'backpack'])
        self.assertEqual(len(player.backpack_contents['0']), 50)
        self.assertEqual(player.inventory, [name, 'A Basic Kunai'])
        commands.cmd_put(session, ['kunai', 'in', 'backpack'])
        self.assertIn('full', messages[-1].lower())
        self.assertEqual(player.backpack_contents['0'][0], 'A Basic Kunai')
        commands.cmd_backpack(session, ['backpack'])
        self.assertIn('50/50', messages[-1])
        commands.cmd_get(session, ['kunai', 'from', 'backpack'])
        self.assertEqual(len(player.backpack_contents['0']), 49)
        self.assertEqual(player.inventory, [name, 'A Basic Kunai', 'A Basic Kunai'])
        snapshot = models.Player.from_dict(player.to_dict())
        self.assertEqual(len(snapshot.backpack_contents['0']), 49)

    def test_multiple_bags_reindex_together_and_nested_bags_are_rejected(self):
        session, player, output = self.make_session()
        iron = data_crafting.BACKPACK_RECIPES['iron']['name']
        steel = data_crafting.BACKPACK_RECIPES['steel']['name']
        player.inventory = ['A Basic Kunai', iron, steel, 'A Throwing Shuriken']
        commands.cmd_put(session, ['kunai', 'in', 'ironbound'])
        self.assertEqual(player.backpack_contents['0'], ['A Basic Kunai'])
        commands.cmd_put(session, ['shuriken', 'in', 'steel ironwood backpack'])
        self.assertEqual(player.backpack_contents['1'], ['A Throwing Shuriken'])
        commands.cmd_put(session, ['ironbound', 'in', 'steel ironwood backpack'])
        self.assertIn('containers cannot', output[-1].lower())
        self.assertEqual(player.backpack_contents['0'], ['A Basic Kunai'])
        self.assertEqual(player.backpack_contents['1'], ['A Throwing Shuriken'])

    def test_full_container_cannot_drop_and_other_drops_reindex(self):
        session, player, output = self.make_session()
        bag = data_crafting.BACKPACK_RECIPES['iron']['name']
        player.inventory = ['A Basic Kunai', bag, 'A Throwing Shuriken']
        player.backpack_contents = {'1': ['A Rare Gem']}
        with patch.object(commands, 'WORLD', {player.room_vnum: type('Room', (), {'ground_items': []})()}):
            commands.cmd_drop(session, ['backpack'])
            self.assertIn('empty', output[-1].lower())
            commands.cmd_drop(session, ['all'])
            self.assertIn('empty', output[-1].lower())
            with patch('room_actions.bulk_items'):
                commands.cmd_drop(session, ['kunai'])
        self.assertEqual(player.inventory, [bag, 'A Throwing Shuriken'])
        self.assertEqual(player.backpack_contents, {'0': ['A Rare Gem']})


if __name__ == '__main__':
    unittest.main()
