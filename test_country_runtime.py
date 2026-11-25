import unittest
from copy import deepcopy
import mainland_roads
import room_flags
from country_runtime import shorten_mainland, TARGET_ROOMS, ExpansionError
from world import Room

class CountryRuntimeTests(unittest.TestCase):
    def test_reduce_exactly_and_keep_referenced_anchors(self):
        original,hubs=mainland_roads.build_rooms()
        rooms=deepcopy(original)
        for room in rooms.values():
            room_flags.synchronize(room,legacy=True)
        # External exit and mission/port reference are not deleted.
        protected={20674,20675}
        target=20676
        direction=next(d for d in ("north","east","south","west","up")
                       if d not in rooms[target].exits)
        rooms[target].exits[direction]=39999
        rooms[39999]=Room(39999,"Existing Landmark","Existing builder content")
        removed=shorten_mainland(rooms,original,protected)
        self.assertEqual(len(removed),382)
        self.assertEqual(len(set(original)&set(rooms)),TARGET_ROOMS)
        self.assertFalse(removed & (protected|{target}|set(hubs.values())))
        self.assertEqual(rooms[target].exits[direction],39999)
        self.assertTrue(all(v not in removed for r in rooms.values() for v in r.exits.values()))

    def test_no_overwrite_when_target_impossible(self):
        original,_=mainland_roads.build_rooms()
        rooms=deepcopy(original)
        with self.assertRaises(ExpansionError):
            shorten_mainland(rooms,original,set(original))
        self.assertEqual(rooms,original)

if __name__=="__main__":
    unittest.main()
