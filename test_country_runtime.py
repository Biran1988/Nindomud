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


class LiveCountryInstallTests(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile
        from dataclasses import asdict
        from types import SimpleNamespace
        from unittest.mock import patch
        import combat
        import country_runtime as runtime
        import country_expansion as layout
        import olc
        import storage
        import world
        self.runtime=runtime
        self.layout=layout
        self.storage=storage
        self.world=world
        self.combat=combat
        self.olc=olc
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory=tmp.name
        rooms,hubs=mainland_roads.build_rooms()
        self.hubs=hubs
        registry={}
        def register(name,first,last,prototype=False):
            registry[name.casefold()]={"name":name,"vnum_start":first,
                "vnum_end":last,"creator":"Test","prototype":prototype}
        register("Mainland Road Network",20501,30500)
        for title,area,v,hub,direction,first,last in mainland_roads.DESTINATIONS:
            register(area,first,last)
            rooms[v]=Room(v,title+" existing village gate","Preserved gate description.")
            rooms[v].exits[mainland_roads.REVERSE[direction]]=hubs[hub]
        rooms[80001]=Room(80001,"Existing island gate","Preserved coastal settlement.")
        register("hidden island",80001,80050)
        rooms[39999]=Room(39999,"Builder room","Do not overwrite.")
        register("Unrelated",39999,40010,True)
        for c in layout.COUNTRIES:
            register(c.name+" Country",c.first,c.first+499,True)
        for room in rooms.values():
            room_flags.synchronize(room,legacy=True)
        self.original=deepcopy(rooms)
        self.mobs={}
        self.instances={}
        self.objects={1001:olc.default_object(1001,"A Healing Salve"),
                      1002:olc.default_object(1002,"A Basic Kunai")}
        def spawn(v,place):
            m=SimpleNamespace(template_vnum=v,room_vnum=place,health=100,
                              name=self.mobs[v]["short_desc"])
            self.instances.setdefault(place,[]).append(m)
            return m
        patches=[
            patch.object(storage,"DATA_DIR",self.directory),
            patch.object(storage,"ACCOUNTS_DIR",os.path.join(self.directory,"accounts")),
            patch.object(storage,"PLAYERS_DIR",os.path.join(self.directory,"players")),
            patch.object(world.WORLD,"rooms",rooms),
            patch.object(combat,"MOB_TEMPLATES",self.mobs),
            patch.object(combat,"MOBS_BY_ROOM",self.instances),
            patch.object(olc,"OBJECT_TEMPLATES",self.objects),
            patch.object(combat,"spawn_mob",side_effect=spawn),
            patch.object(runtime,"_active",None),
            patch.object(runtime,"_active_path",None),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        storage.ensure_dirs()
        storage.save_areas(registry)
        storage.save_world_state({"rooms":{str(v):asdict(r) for v,r in rooms.items()},
            "mobs":{},"items":{},"custom":{"preserve":True}})
        # Active player/mission references must retain their original highway VNUM.
        from pathlib import Path
        import json
        self.player_file=Path(storage.PLAYERS_DIR)/"test.json"
        self.player_file.write_text(json.dumps({"room_vnum":20675,
                                    "mission":{"target_room":20676}}),encoding="utf-8")
        self.original_player=self.player_file.read_bytes()

    def test_install_all_countries_as_live_and_preserve_on_reload(self):
        from world import OPPOSITE_DIRECTION
        rt=self.runtime
        self.assertTrue(rt.install_or_restore())
        rooms=self.world.WORLD.rooms
        registry=self.storage.load_areas()
        saved=self.storage.load_world_state()
        meta=saved[rt.META_KEY]
        self.assertFalse(meta["pending"])
        self.assertEqual(len(meta["removed"]),382)
        self.assertEqual(len(meta["retained"]),1146)
        self.assertEqual(sum(len(v) for v in meta["country_rooms"].values()),3750)
        self.assertEqual(saved["custom"],{"preserve":True})
        self.assertEqual(self.player_file.read_bytes(),self.original_player)
        self.assertTrue(registry["unrelated"]["prototype"])
        self.assertEqual(rooms[39999],self.original[39999])
        self.assertTrue({20675,20676}.issubset(rooms))
        for c in self.layout.COUNTRIES:
            with self.subTest(country=c.name):
                self.assertFalse(registry[(c.name+" Country").casefold()]["prototype"])
                self.assertTrue(set(range(c.first,c.first+375)).issubset(rooms))
                self.assertFalse(set(range(c.first+375,c.first+500)) & rooms.keys())
                self.assertIn(c.first,rooms[c.village].exits.values())
                self.assertEqual(rooms[c.village].description,self.original[c.village].description)
                for v in range(c.first,c.first+375):
                    for direction,dest in rooms[v].exits.items():
                        self.assertEqual(rooms[dest].exits[OPPOSITE_DIRECTION[direction]],v)
                    self.assertIn(str(v),saved["rooms"])
                if c.hub:
                    self.assertIn(c.first+24,rooms[self.hubs[c.hub]].exits.values())
                    self.assertNotIn(c.village,rooms[self.hubs[c.hub]].exits.values())
                    self.assertEqual(meta["borders"][str(c.first+24)][1],"chunin")
                else:
                    self.assertNotIn(c.first,meta["groups"]["mainland"]["allowed"])
        self.assertEqual(len(meta["caravans"]),5)
        for v in meta["caravans"]:
            route=self.mobs[v]["country_caravan_route"]
            self.assertTrue(all(b in rooms[a].exits.values() for a,b in zip(route,route[1:])))
            self.assertTrue(self.mobs[v]["shop_items"])
        self.assertIn("Fire Country",rt.read_sign(rooms[self.hubs["leaf_gate"]],"sign"))
        self.assertIn("Konoha",rt.read_sign(rooms[self.hubs["leaf_gate"]],"signpost"))
        self.assertTrue(rt.free_campfire(rooms[33013]))
        self.assertTrue(rt.installed())
        self.assertFalse(rt.install_or_restore())
        self.assertEqual(self.storage.load_world_state(),saved)
        self.assertEqual(self.storage.load_areas(),registry)
        self.assertEqual(self.player_file.read_bytes(),self.original_player)

    def test_collision_aborts_without_changing_registry_or_saved_world(self):
        self.world.WORLD.rooms[33001]=Room(33001,"Existing builder house","Preserve")
        before=self.storage.load_world_state()
        registry=self.storage.load_areas()
        with self.assertRaises(self.runtime.ExpansionError):
            self.runtime.install_or_restore()
        self.assertEqual(self.storage.load_world_state(),before)
        self.assertEqual(self.storage.load_areas(),registry)
        self.assertEqual(self.player_file.read_bytes(),self.original_player)

    def test_cooking_and_meat_classification(self):
        import cooking
        import consumables
        import item_types
        for raw,(dish,cost,xp,stamina) in self.runtime.MEALS.items():
            self.assertEqual(cooking.INGREDIENTS[raw.casefold()]["dish"],dish)
            self.assertEqual(cooking.COOKING_XP[raw.casefold()],xp)
            self.assertEqual(item_types.classify_item(raw),"food")
            self.assertTrue(consumables.find_consumable(dish)[1]["country_meal"])


if __name__=="__main__":
    unittest.main()
