"""Focused coverage for configurable medical recovery and armor resistance."""

from types import SimpleNamespace
from unittest.mock import patch

import combat
import commands
import consumables
import models
import olc


def _session(player, staff="builder"):
    messages = []
    return SimpleNamespace(player=player, account=SimpleNamespace(staff_level=staff),
                           send=messages.append, messages=messages)


def test_medical_builder_flags_ticks_and_save():
    player = models.Player(name="Medic", account_name="Medic")
    session = _session(player)
    proto = olc.default_object(991101, "a fine poultice")
    olc.OBJECT_TEMPLATES[991101] = proto
    try:
        with patch.object(olc, "_log"):
            for field, value in [("itemtype", "medical"), ("heal", "90"),
                                 ("healtime", "10"), ("healflags", "health"),
                                 ("healflags", "chakra"), ("healflags", "stamina")]:
                olc.cmd_oset(session, ["991101", field, value])
            olc.cmd_oset(session, ["991101", "healflags", "-stamina"])
            olc.cmd_oset(session, ["991101", "healtime", "0"])
            assert proto["heal_duration"] == 10
            olc.cmd_oset(session, ["991101", "healflags", "invalid"])
            assert proto["heal_flags"] == ["health", "chakra"]

        player.health, player.chakra, player.stamina = 5, 15, 20
        player.inventory.append("a fine poultice")
        with patch.object(consumables.time, "time", return_value=1000):
            consumables.consume(session, "use", "fine poultice")
        assert (player.health, player.chakra, player.stamina) == (5, 15, 20)
        assert "a fine poultice" not in player.inventory
        loaded = models.Player.from_dict(player.to_dict())
        assert consumables.tick_medical_healing(loaded, now=1005) == {"health": 45, "chakra": 45}
        assert (loaded.health, loaded.chakra, loaded.stamina) == (50, 60, 20)
        loaded.health = 10
        assert consumables.tick_medical_healing(loaded, now=1010) == {"health": 45, "chakra": 15}
        assert loaded.health == 55 and loaded.medical_healing == []

        # Independent doses stack and never defer capped healing to later damage.
        loaded.health = 90
        loaded.medical_healing = [dict(resources=["health"], amount=20, duration=10,
                                      started_at=1000, applied=0) for _ in range(2)]
        assert consumables.tick_medical_healing(loaded, now=1005) == {"health": 10}
        loaded.health = 80
        assert consumables.tick_medical_healing(loaded, now=1010) == {"health": 20}
    finally:
        olc.OBJECT_TEMPLATES.pop(991101, None)


def test_legacy_medical_and_missing_configuration():
    player = models.Player(name="Medic", account_name="Medic", health=25, chakra=25)
    session = _session(player)
    player.inventory.extend(["A Healing Salve", "A Soldier Pill"])
    with patch.object(consumables.time, "time", return_value=2000):
        consumables.consume(session, "use", "healing salve")
        consumables.consume(session, "use", "soldier pill")
    assert (player.health, player.chakra) == (25, 25)
    assert {tuple(e["resources"]) for e in player.medical_healing} == {("health",), ("chakra",)}
    assert consumables.tick_medical_healing(player, now=2030) == {"health": 35, "chakra": 40}
    proto = olc.default_object(991102, "an empty remedy")
    proto["item_type"] = "medical"
    olc.OBJECT_TEMPLATES[991102] = proto
    try:
        player.inventory.append("an empty remedy")
        consumables.consume(session, "use", "empty remedy")
        assert "an empty remedy" in player.inventory
    finally:
        olc.OBJECT_TEMPLATES.pop(991102, None)


def test_weapon_resistance_stacks_and_reaches_combat():
    helm = olc.default_object(991103, "a warded helm")
    helm["item_type"], helm["wear_loc"] = "armor", "head"
    helm["weapon_resistances"] = {"sword": 25}
    coat = olc.default_object(991104, "a warded coat")
    coat["item_type"], coat["wear_loc"] = "armor", "body"
    coat["weapon_resistances"] = {"sword": 20}
    blade = olc.default_object(991105, "a test blade")
    blade["item_type"], blade["weapon_type"], blade["wear_loc"] = "weapon", "sword", "wielded"
    olc.OBJECT_TEMPLATES.update({991103: helm, 991104: coat, 991105: blade})
    try:
        builder = _session(models.Player(name="Builder", account_name="Builder"))
        with patch.object(olc, "_log"):
            olc.cmd_oset(builder, ["991103", "resist", "sword", "25"])
            olc.cmd_oset(builder, ["991103", "resist", "kunai", "101"])
            assert helm["weapon_resistances"] == {"sword": 25}
        attacker = models.Player(name="Attacker", account_name="Attacker")
        attacker.equipment["wielded"] = "a test blade"
        defender = models.Player(name="Defender", account_name="Defender", health=500, maximum_health=500)
        defender.equipment["head"], defender.equipment["body"] = "a warded helm", "a warded coat"
        assert commands.reduce_weapon_damage(defender, "sword", 100) == 60
        assert commands.reduce_weapon_damage(defender, "kunai", 100) == 100
        assert commands.reduce_weapon_damage(defender, None, 100) == 100
        source, target = _session(attacker), _session(defender)
        with patch.object(combat.random, "randint", return_value=50), \
             patch.object(combat, "_player_attack_damage", return_value=100), \
             patch.object(combat.derived_stats, "to_hit_chance", return_value=100), \
             patch.object(combat.derived_stats, "critical_chance", return_value=0), \
             patch.object(combat.derived_stats, "dodge_chance", return_value=0):
            combat._player_attack_target_once(source, attacker, target, defender)
        assert defender.health == 440
        mob = combat.Mob(9911, 9911, "Practice Mob", 1, 500, 500, 1, 0, 0)
        mob.equipment["head"] = "a warded helm"
        with patch.object(combat.random, "randint", return_value=50), \
             patch.object(combat, "_player_attack_damage", return_value=100), \
             patch.object(combat.derived_stats, "to_hit_chance", return_value=100), \
             patch.object(combat.derived_stats, "critical_chance", return_value=0):
            combat._player_attack_mob_once(source, attacker, mob)
        assert mob.health == 425
    finally:
        for vnum in (991103, 991104, 991105):
            olc.OBJECT_TEMPLATES.pop(vnum, None)


def test_farming_requires_held_hoe():
    player = models.Player(name="Farmer", account_name="Farmer")
    player.inventory.append("A Copper Hoe")
    session = _session(player)
    session.is_busy = lambda: False
    commands.cmd_farm(session, [])
    assert any("need to hold a hoe" in message for message in session.messages)
    assert player.inventory == ["A Copper Hoe"]
