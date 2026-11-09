"""Secret summoning bond escape from Kamui pocket dimensions."""
import unittest
import tempfile
from unittest.mock import patch

import combat
import content
import data_jutsu
import mangekyo
import reverse_summoning
import storage
import world
from models import Account, Player
from session import Session, State


class SecretReverseSummonTests(unittest.TestCase):
    @staticmethod
    def make_session(name, room, eye=False):
        output = []
        session = Session(output.append, lambda: None)
        session.player = Player(name, name, room_vnum=room, chakra=500, maximum_chakra=500)
        session.player.pvp_organization = 'anbu' if name == 'Caster' else 'root'
        session.player.village = 'leaf'
        session.player.bloodline_id = 'sharingan' if eye else None
        session.player.bloodline_mangekyo = eye
        session.player.mangekyo_eye_1 = 'kamui' if eye else None
        session.player.sharingan_active = eye
        session.account = Account(name, '', '')
        session.state = State.PLAYING
        session.color_enabled = False
        output.clear()
        return session, output

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        rooms = {1: world.Room(1, 'Starting room', 'A room.'),
                 2: world.Room(2, 'Other room', 'Another room.')}
        for target, value in (
            ('session.ACTIVE_SESSIONS', []),
            ('world.WORLD.rooms', rooms),
            ('mangekyo._NEXT_POCKET_DIMENSION_VNUM', None),
            ('storage.DATA_DIR', directory.name),
            ('storage.ACCOUNTS_DIR', directory.name + '/accounts'),
            ('storage.PLAYERS_DIR', directory.name + '/players'),
        ):
            item = patch(target, value)
            item.start()
            self.addCleanup(item.stop)
        self.caster, self.output = self.make_session('Caster', 1, eye=True)
        self.target, self.target_output = self.make_session('Target', 1)
        import session as session_module
        self.rooms = world.WORLD.rooms
        self.kage_vnum = content._VILLAGE_ROOMS['leaf']['kage']
        self.rooms[self.kage_vnum] = world.Room(self.kage_vnum, 'Hokage Chamber', 'Kage chamber.')
        mobs = patch.object(combat, 'MOBS_BY_ROOM', {})
        mobs.start()
        self.addCleanup(mobs.stop)
        custom = patch.object(reverse_summoning, 'DESTINATION_VNUM_BY_SUMMON_FAMILY', {})
        custom.start()
        self.addCleanup(custom.stop)

    def add_summon(self, owner=None, health=120, family='ninken_1', room=1):
        owner = owner or self.target
        mob = combat.Mob(55331, 55331, 'ninken', 20, health, 120, room, 0, 0,
                         summon_owner=owner.player.name,
                         summon_tier_key=family)
        combat.MOBS_BY_ROOM.setdefault(room, []).append(mob)
        return mob

    def test_hidden_spell_does_not_show_in_skill_lists_or_changelog(self):
        import changelog
        self.assertNotIn('reverse summoning jutsu', data_jutsu.JUTSU)
        self.assertNotIn('reverse summoning jutsu', data_jutsu.SHORTCUT_JUTSU)
        self.assertFalse(any('reverse summoning' in entry.lower()
                             for _, entry in changelog.CHANGELOG))

    def test_no_summon_cannot_escape_or_spend_energy(self):
        self.caster.handle_line('perform kamui Target')
        pocket = self.target.player.room_vnum
        before = (self.target.player.chakra, self.target.player.stamina)
        self.target.handle_line('perform reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, pocket)
        self.assertEqual((self.target.player.chakra, self.target.player.stamina), before)
        self.assertIn('No living summoned ally', ''.join(self.target_output))

    def test_zero_energy_cannot_cast_and_keeps_summon(self):
        self.caster.handle_line('perform kamui Target')
        pocket = self.target.player.room_vnum
        mob = self.add_summon()
        self.target.player.stamina = 0
        self.target.handle_line('per reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, pocket)
        self.assertIn(mob, combat.MOBS_BY_ROOM[1])
        self.assertIn('remaining chakra and stamina', ''.join(self.target_output))

    def test_live_summon_outside_pocket_enables_escape_and_saves(self):
        self.caster.handle_line('perform kamui Target')
        pocket = self.target.player.room_vnum
        self.add_summon(room=1)
        self.target.player.stamina = 120
        self.target.handle_line('anki')
        self.assertEqual(self.target.player.room_vnum, pocket)
        self.target.handle_line('perform reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, self.kage_vnum)
        self.assertEqual((self.target.player.chakra, self.target.player.stamina), (0, 0))
        self.assertNotIn('anki', self.target.player.cooldowns)
        self.assertIsNone(self.target.player.kamui_return_room_vnum)
        self.assertEqual(storage.load_player('Target').room_vnum, self.kage_vnum)
        self.assertEqual(storage.load_player('Target').chakra, 0)
        self.assertEqual(storage.load_player('Target').stamina, 0)
        self.assertIn(pocket, self.rooms)  # the caster's pocket persists
        self.caster.handle_line('perform kamui close')
        self.assertEqual(self.target.player.room_vnum, self.kage_vnum)

    def test_bare_phrase_works_and_owner_collapse_is_immediate(self):
        self.caster.handle_line('perform kamui self')
        pocket = self.caster.player.room_vnum
        self.add_summon(owner=self.caster, family='toad_1', room=1)
        self.caster.player.stamina = 70
        self.caster.handle_line('reverse summoning jutsu')
        self.assertEqual(self.caster.player.room_vnum, self.kage_vnum)
        self.assertEqual((self.caster.player.chakra, self.caster.player.stamina), (0, 0))
        self.assertNotIn(pocket, self.rooms)
        self.assertFalse(self.caster.player.kamui_pocket_dimension_active)
        self.assertIsNone(self.caster.player.kamui_pocket_dimension_vnum)
        self.assertEqual(storage.load_player('Caster').room_vnum, self.kage_vnum)

    def test_no_kamui_no_teleport_and_no_cost(self):
        self.add_summon()
        before = (self.target.player.chakra, self.target.player.stamina)
        self.target.handle_line('perform reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, 1)
        self.assertEqual((self.target.player.chakra, self.target.player.stamina), before)

    def test_future_contract_vnum_overrides_anki_destination(self):
        self.caster.handle_line('perform kamui Target')
        self.add_summon(family='ninken_2')
        self.rooms[188800] = world.Room(188800, 'Ninken Haven', 'An isolated place.')
        reverse_summoning.DESTINATION_VNUM_BY_SUMMON_FAMILY['ninken'] = 188800
        self.target.handle_line('perform reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, 188800)
        self.assertEqual(self.target.player.chakra, 0)

    def test_invalid_destination_does_not_spend_or_move(self):
        self.caster.handle_line('perform kamui Target')
        pocket = self.target.player.room_vnum
        self.add_summon()
        reverse_summoning.DESTINATION_VNUM_BY_SUMMON_FAMILY['ninken'] = 987654321
        before = (self.target.player.chakra, self.target.player.stamina)
        self.target.handle_line('perform reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, pocket)
        self.assertEqual((self.target.player.chakra, self.target.player.stamina), before)
        self.assertIn('No energy is spent', ''.join(self.target_output))

    def test_dead_summon_is_not_valid(self):
        self.caster.handle_line('perform kamui Target')
        pocket = self.target.player.room_vnum
        self.add_summon(health=0)
        self.target.handle_line('perform reverse summoning jutsu')
        self.assertEqual(self.target.player.room_vnum, pocket)


if __name__ == '__main__':
    unittest.main()
