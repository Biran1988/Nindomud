"""Release regression: game command dispatcher actually forges/holds/gathers."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import commands, content, data_crafting, fishing, mining, lumberjack
import gathering_job, olc, storage, world, gems
from models import Player
from session import Session, State

class GatheringCommandIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content._register_shared_items()

    def _fresh_player(self):
        output = []
        session = Session(output.append, lambda: None)
        session.player = Player('ToolFlowTester', 'ToolFlowTester', village='leaf',
                                primary_class='bukijutsu', clan='nara', level=100)
        session.state = State.PLAYING
        session.account = SimpleNamespace(name='ToolFlowTester', staff_level='player')
        session.player.job_levels = {'fishing': 100, 'mining': 100, 'lumberjack': 100}
        session.player.stamina = 500
        session.is_busy = lambda: False
        session.start_timed_action = lambda label, seconds, resolve: resolve()
        return session, output

    def test_real_commands_forge_hold_and_gather_all_nine_tools(self):
        mapping = [('rod','fishing','fish','ocean',fishing.RODS, fishing.FIND_TABLE),
                   ('pickaxe','mining','mine','mountain',mining.PICKAXES,mining.FIND_TABLE),
                   ('axe','lumberjack','chop','forest',lumberjack.AXES,lumberjack.FIND_TABLE)]
        for kind, job, command, biome, tools, table in mapping:
            for tier in ('iron','steel','chakra'):
                with self.subTest(kind=kind, tier=tier):
                    s, output = self._fresh_player()
                    recipe = data_crafting.TOOL_RECIPES[tier]
                    s.player.inventory.extend((recipe['wood'],recipe['ingot']))
                    product = data_crafting.job_tool_name(kind,tier)
                    with patch.object(storage,'save_player'), patch.object(world.WORLD,'get', return_value=SimpleNamespace(biome=biome)):
                        s.handle_line(f'craft tool {kind} {tier}')
                        self.assertIn(product,s.player.inventory)
                        self.assertNotIn(recipe['wood'],s.player.inventory)
                        self.assertNotIn(recipe['ingot'],s.player.inventory)
                        s.handle_line(f'hold {product}')
                        self.assertIn(product,s.player.equipment.get('tool',''))
                        allowed=[x[0] for x in table if x[1] <= tools[product.lower()]['max_resource_level']]
                        # Challenge the command path, not only the static tables.
                        with patch.object(gathering_job.random,'randint',return_value=100), \
                             patch.object(gathering_job.random,'choices',side_effect=lambda available,weights,k:[available[-1]]), \
                             patch.object(gems,'roll_bonus_gem',return_value=None):
                            s.handle_line(command)
                        self.assertIn(allowed[-1].casefold(), {x.casefold() for x in s.player.inventory})
                        self.assertNotEqual(s.player.equipment.get('tool'), product,
                                            'one use of crafted tool must consume durability')

    def test_copper_cannot_gather_endgame_material(self):
        for tool, find, callback in [('a copper axe', lumberjack.FIND_TABLE, lumberjack.attempt_chop),
                                    ('a copper pickaxe', mining.FIND_TABLE, mining.attempt_mine),
                                    ('a kindling fishing rod', fishing.FIND_TABLE, fishing.attempt_catch)]:
            seen=set()
            with patch.object(gathering_job.random,'randint',return_value=100), \
                 patch.object(gathering_job.random,'choices',side_effect=lambda available,weights,k:(seen.update(x[0] for x in available) or [available[-1]])):
                callback(100,tool)
            self.assertNotIn(find[-1][0],seen)

if __name__ == '__main__':
    unittest.main()
