import random
import unittest
from collections import deque
from country_expansion import COUNTRIES, build_all, build_country, ground_spawn, sign_directions
from world import OPPOSITE_DIRECTION

class CountryExpansionTests(unittest.TestCase):
    def test_exact_vnums_and_connectivity(self):
        rooms, habitats=build_all()
        self.assertEqual(len(rooms),3750)
        for c in COUNTRIES:
            expected=set(range(c.first,c.first+375))
            self.assertEqual(expected & rooms.keys(),expected)
            self.assertFalse(set(range(c.first+375,c.first+500)) & rooms.keys())
            seen={c.first}
            pending=deque(seen)
            while pending:
                v=pending.popleft()
                for d,dest in rooms[v].exits.items():
                    self.assertIn(dest,expected)
                    self.assertEqual(rooms[dest].exits[OPPOSITE_DIRECTION[d]],v)
                    if dest not in seen:
                        seen.add(dest);pending.append(dest)
            self.assertEqual(seen,expected)
            self.assertEqual(sum(map(len,habitats[c.name].values())),350)
            for i in range(24):
                self.assertEqual(rooms[c.first+i].exits[c.outward],c.first+i+1)
    def test_ground_items_are_capped(self):
        c=COUNTRIES[1]
        rooms,h=build_country(c)
        r=rooms[h["forest"][0]]
        rng=random.Random(1)
        self.assertIsNotNone(ground_spawn(r,rng,1))
        self.assertIsNone(ground_spawn(r,rng,1))
        self.assertEqual(len(r.ground_items),1)
    def test_signs_follow_real_connections(self):
        c=COUNTRIES[1]
        rooms,h=build_country(c)
        result=sign_directions(rooms,c.first,{c.first+24:"Border"})
        self.assertEqual(result,{"Border":c.outward})

if __name__=="__main__":
    unittest.main()
