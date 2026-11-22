"""Restorative items cannot be used in combat or stacked with a running dose."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import consumables
import olc
from models import Player
from pill_crafting import encode_pill


class MedicalItemRestrictionsTests(unittest.TestCase):
    def setUp(self):
        self.player = Player("MedicTest", "MedicTest")
        self.player.health = 20
        self.player.chakra = 10
        self.player.stamina = 10
        self.player.inventory = []
        self.session = NS(player=self.player, send=Mock(),
                          combat_target=None, pvp_target=None)
        self.prototypes = {
            99021: self._medical("Battlefield Field Kit", level=50, heal=250),
            89: self._medical("Antidote Pill", level=25, heal=0),
        }
        self.prototypes[89]["extra_flags"] = []
        ctx = patch.object(olc, "OBJECT_TEMPLATES", self.prototypes)
        ctx.start()
        self.addCleanup(ctx.stop)

    @staticmethod
    def _medical(name, *, level, heal):
        proto = olc.default_object(99021, name)
        proto.update(item_type="medical", level=level,
                     heal_amount=heal, heal_duration=30, heal_flags=["health"],
                     extra_flags=[])
        return proto

    def _message(self):
        return self.session.send.call_args.args[0]

    def test_pve_and_pvp_combat_prevent_healing_use_and_eat(self):
        for target_attr in ("combat_target", "pvp_target"):
            for verb in ("use", "eat"):
                for name in ("A Healing Salve", "A Soldier Pill",
                             encode_pill("Medicinal", 50), "Battlefield Field Kit"):
                    with self.subTest(target=target_attr, verb=verb, item=name):
                        self.player.inventory = [name]
                        self.player.medical_healing = []
                        self.session.send.reset_mock()
                        setattr(self.session, target_attr, object())
                        consumables.consume(self.session, verb, name.split("\x1e")[0])
                        self.assertEqual(self.player.inventory, [name])
                        self.assertEqual(self.player.medical_healing, [])
                        self.assertIn("cannot use healing items while in combat",
                                      self._message())
                        setattr(self.session, target_attr, None)

    def test_one_active_treatment_blocks_more_of_same_and_other_kind(self):
        self.player.inventory = [
            "A Healing Salve", "A Healing Salve", "A Soldier Pill",
            encode_pill("Medicinal", 50),
        ]
        with patch.object(consumables.time, "time", return_value=1000):
            consumables.consume(self.session, "use", "healing salve")
        self.assertEqual(len(self.player.medical_healing), 1)
        self.assertEqual(self.player.inventory.count("A Healing Salve"), 1)
        for verb, name in (
            ("use", "healing salve"),
            ("eat", "soldier pill"),
            ("use", "medicinal pill"),
        ):
            with self.subTest(item=name):
                before = list(self.player.inventory)
                with patch.object(consumables.time, "time", return_value=1010):
                    consumables.consume(self.session, verb, name)
                self.assertEqual(self.player.inventory, before)
                self.assertEqual(len(self.player.medical_healing), 1)
                self.assertIn("already receiving medical treatment", self._message())

        # Healing progress itself is not cancelled by the anti-stack rule.
        restored = consumables.tick_medical_healing(self.player, now=1030)
        self.assertEqual(restored.get("health"), 35)
        self.assertEqual(self.player.medical_healing, [])
        with patch.object(consumables.time, "time", return_value=1031):
            consumables.consume(self.session, "eat", "soldier pill")
        self.assertEqual(len(self.player.medical_healing), 1)
        self.assertNotIn("A Soldier Pill", self.player.inventory)

    def test_in_progress_treatment_is_enforced_after_save_reload(self):
        self.player.inventory = ["A Healing Salve", "A Healing Salve"]
        with patch.object(consumables.time, "time", return_value=3000):
            consumables.consume(self.session, "eat", "healing salve")
        restored = Player.from_dict(self.player.to_dict())
        self.session.player = restored
        self.assertEqual(len(restored.medical_healing), 1)
        with patch.object(consumables.time, "time", return_value=3010):
            consumables.consume(self.session, "use", "healing salve")
        self.assertEqual(restored.inventory, ["A Healing Salve"])
        self.assertEqual(len(restored.medical_healing), 1)

    def test_antidote_is_cure_only_and_allowed_during_combat_and_treatment(self):
        self.player.inventory = [
            "A Healing Salve", "Antidote Pill", encode_pill("Antidote", 50),
        ]
        with patch.object(consumables.time, "time", return_value=4500):
            consumables.consume(self.session, "use", "healing salve")
        self.assertEqual(len(self.player.medical_healing), 1)
        self.session.combat_target = object()
        self.player.active_status_effects["poisoned"] = {"duration": 2}
        consumables.consume(self.session, "use", "antidote pill")
        self.assertNotIn("poisoned", self.player.active_status_effects)
        self.assertNotIn("Antidote Pill", self.player.inventory)
        self.assertEqual(len(self.player.medical_healing), 1)
        # Crafted antidotes also work in combat and don't consume when healthy.
        self.player.active_status_effects["poisoned"] = {"duration": 2}
        consumables.consume(self.session, "eat", "antidote")
        self.assertNotIn("poisoned", self.player.active_status_effects)
        self.assertNotIn(encode_pill("Antidote", 50), self.player.inventory)
        self.assertEqual(len(self.player.medical_healing), 1)

    def test_healing_continues_if_combat_begins_after_treatment_started(self):
        self.player.inventory = ["A Healing Salve", "A Healing Salve"]
        with patch.object(consumables.time, "time", return_value=8000):
            consumables.consume(self.session, "use", "healing salve")
        self.session.pvp_target = object()
        before = self.player.health
        gained = consumables.tick_medical_healing(self.player, now=8015)
        self.assertGreater(gained.get("health", 0), 0)
        self.assertGreater(self.player.health, before)
        consumables.consume(self.session, "use", "healing salve")
        self.assertIn("cannot use healing items while in combat", self._message())
        self.assertEqual(self.player.inventory, ["A Healing Salve"])


if __name__ == "__main__":
    unittest.main()
