"""Pre-2500 village layout migration to separately registered village areas."""
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

import areas
import apartments
import currency_piles
import storage
import village_room_relocation as relocation
import world
from models import Player


class VillageRoomRelocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(storage, 'DATA_DIR', self.tmp.name))
        self.stack.enter_context(patch.object(world.WORLD, 'rooms', {}))
        self.stack.enter_context(patch.object(areas, 'find_area', side_effect=self.area))
        relocation._read_moves.cache_clear()
        self.addCleanup(relocation._read_moves.cache_clear)
        storage.ensure_dirs()
        for vnum, title in ((2501, 'Iwa Kage Chamber'), (5001, 'Kiri Kage Chamber'),
                            (7501, 'Kumo Kage Chamber'), (10001, 'Suna Kage Chamber'),
                            (5, 'A Leaf Road')):
            world.WORLD.add_room(world.Room(vnum, title, 'Unchanged.'))

    @staticmethod
    def area(key):
        known = {'stone': (2501, 5000), 'water': (5001, 7500),
                 'cloud': (7501, 10000), 'sand': (10001, 12500)}
        return SimpleNamespace(vnum_start=known[key][0], vnum_end=known[key][1]) if key in known else None

    def save(self, *rooms):
        for room in rooms:
            world.WORLD.add_room(room)
        data={'rooms':{str(vnum):asdict(room) for vnum,room in world.WORLD.rooms.items()},
              'mobs':{'8888':{'short_desc':'a test mob'}},
              'items':{'9999':{'short_desc':'a test item'}}}
        storage.save_world_state(data)

    def test_four_villages_move_to_correct_area_with_exits_and_fields(self):
        old=[]
        for base, name in ((1100,'Iwa'),(1200,'Kiri'),(1300,'Kumo'),(1400,'Suna')):
            square=world.Room(base,name+' Village Square','Custom description!')
            square.exits['north']=base+10
            square.flags.append('no_mob')
            kage=world.Room(base+10,name+' Kage Chamber','Saved room data.')
            kage.exits['south']=base
            old.extend((square,kage))
        # An unrelated Leaf room with an exit to Iwa also gets its link corrected.
        world.WORLD.rooms[5].exits['west']=1100
        self.save(*old)
        storage.save_spawn_points({'points':{'mob:8888:1100':{'kind':'mob','vnum':8888,'room_vnum':1100,'total_cap':12}}})
        result=relocation.relocate_saved_rooms()
        self.assertEqual(len(result),8)
        for old_base,new_base in ((1100,2600),(1200,5100),(1300,7600),(1400,10100)):
            self.assertNotIn(old_base,world.WORLD.rooms)
            self.assertEqual(world.WORLD.get(new_base).description,'Custom description!')
            self.assertIn('no_mob',world.WORLD.get(new_base).flags)
            self.assertEqual(world.WORLD.get(new_base).exits['north'],new_base+10)
            self.assertEqual(world.WORLD.get(new_base+10).exits['south'],new_base)
        self.assertEqual(world.WORLD.get(5).exits['west'],2600)
        saved=storage.load_world_state()
        self.assertIn('2600',saved['rooms'])
        self.assertNotIn('1100',saved['rooms'])
        self.assertEqual(saved['mobs']['8888']['short_desc'],'a test mob')
        points=storage.load_spawn_points()['points']
        self.assertEqual(points['mob:8888:2600']['total_cap'],12)
        self.assertNotIn('mob:8888:1100',points)
        self.assertEqual(relocation.relocate_saved_rooms(),{})

    def test_existing_legacy_apartment_location_preserves_storage_vnum(self):
        house=world.Room(1171,"Kinto's customized apartment",'Private home')
        house.apartment=True
        house.owner='Kinto'
        self.save(house)
        relocation.relocate_saved_rooms()
        owner=Player('Kinto','Kinto',room_vnum=1171)
        owner.apartment_room_vnum=1171
        owner.hospital_vnum=1101
        owner.apartment_expansions={'storage':{'direction':'east','parent_vnum':1171,'cost':200000}}
        self.assertTrue(relocation.remap_player(owner))
        self.assertEqual(owner.room_vnum,2671)
        self.assertEqual(owner.hospital_vnum,1101) # only real rooms are moved
        self.assertEqual(owner.apartment_room_vnum,2671)
        self.assertEqual(owner.apartment_expansions['storage']['vnum'],11714)
        self.assertEqual(owner.apartment_expansions['storage']['parent_vnum'],2671)
        self.assertEqual(apartments.expansion_room_vnum(2671,'storage',owner),11714)
        self.assertEqual(relocation.remap_player(owner),False)

    def test_destination_collision_does_not_overwrite_any_room(self):
        self.save(world.Room(1100,'Iwa Village Square','Old Iwa'),
                  world.Room(1200,'Kiri Village Square','Old Kiri'),
                  world.Room(2600,'Builder Mine','Custom Stone content'))
        changes=relocation.relocate_saved_rooms()
        self.assertNotIn(1100,changes)
        self.assertEqual(changes[1200],5100)
        self.assertEqual(world.WORLD.get(2600).name,'Builder Mine')
        self.assertEqual(world.WORLD.get(1100).name,'Iwa Village Square')
        self.assertNotIn(1100,relocation.load_moves())

    def test_gathering_spots_move_out_of_leaf_without_affecting_other_rooms(self):
        mine=world.Room(2499,'a Small Mine','Many silver veins')
        woods=world.Room(2500,'a Small forest','A peaceful grove')
        mine.exits['east']=2500
        woods.exits['west']=2499
        self.save(mine,woods)
        changes=relocation.relocate_saved_rooms()
        self.assertEqual(changes,{2499:2700,2500:2701})
        self.assertEqual(world.WORLD.get(2700).exits['east'],2701)
        self.assertEqual(world.WORLD.get(2701).description,'A peaceful grove')
        self.assertNotIn(2499,world.WORLD.rooms)
        self.assertNotIn(2500,world.WORLD.rooms)

    def test_ledger_roundtrip_preserves_saved_world_on_reboot(self):
        self.save(world.Room(1120,'Iwa Mission Board','Saved user text'))
        relocation.relocate_saved_rooms()
        world.WORLD.rooms.clear()
        import world_persistence
        world_persistence.apply_saved_world()
        self.assertIsNotNone(world.WORLD.get(2620))
        self.assertIsNone(world.WORLD.get(1120))
        self.assertEqual(relocation.load_moves()[1120],2620)

    def test_ground_ryo_ledger_follows_moved_room(self):
        self.save(world.Room(1100,'Iwa Village Square','Saved user text'))
        relocation.relocate_saved_rooms()
        from pathlib import Path
        Path(currency_piles._ledger_path()).write_text('{"1100": [220, 80]}')
        currency_piles.restore_piles()
        self.assertEqual(world.WORLD.get(2600).ground_ryo,[220,80])

if __name__=='__main__':
    unittest.main()
