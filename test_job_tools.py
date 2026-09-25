"""Focused checks for tool wear, the corrected VNUMs, and gemcutting."""

from types import SimpleNamespace
from unittest.mock import patch

import commands
import content
import cooking
import gemcutter
import inventory
import models
import olc
import playershops
import tool_durability


def session_for(player):
    sent = []
    session = SimpleNamespace(player=player, account=SimpleNamespace(staff_level="builder"),
                              send=sent.append, sent=sent, pending=None)
    session.is_busy = lambda: session.pending is not None
    session.start_timed_action = lambda _label, _delay, fn: setattr(session, "pending", fn)
    return session


def resolve(session):
    callback = session.pending
    assert callback is not None
    session.pending = None
    callback()


def test_vnums_gems_and_cutting():
    content._register_shared_items()
    assert (content._ITEM_VNUMS["hoe_copper"], content._ITEM_VNUMS["chisel_copper"]) == (20802, 20803)
    assert all(olc.OBJECT_TEMPLATES[content._ITEM_VNUMS[key]]["wear_loc"] == "tool"
               for key in ("hoe_copper", "chisel_copper"))
    for raw_key, cut_key, rarity, strength in (
        ("rough_quartz", "cut_quartz", "uncommon", 2),
        ("raw_sapphire", "cut_sapphire", "epic", 5),
        ("raw_ruby", "cut_ruby", "epic", 5),
        ("raw_diamond", "cut_diamond", "legendary", 8),
    ):
        raw = olc.OBJECT_TEMPLATES[content._ITEM_VNUMS[raw_key]]
        cut = olc.OBJECT_TEMPLATES[content._ITEM_VNUMS[cut_key]]
        assert raw["rarity"] == cut["rarity"] == rarity
        assert cut["gem_bonuses"] == {"hitroll": strength, "damroll": strength}

    player = models.Player(name="Cutter", account_name="Cutter", stamina=500)
    player.inventory = ["A Rough Quartz", "A Raw Sapphire"]
    session = session_for(player)
    commands.cmd_gemcut(session, ["quartz"])
    assert session.pending is None and "hold a copper chisel" in session.sent[-1]
    player.equipment["tool"] = "A Copper Chisel"
    commands.cmd_gemcut(session, ["sapphire"])
    assert session.pending is None and "level 25" in session.sent[-1]
    commands.cmd_gemcut(session, ["quartz"])
    assert "A Rough Quartz" in player.inventory and player.equipment["tool"] == "A Copper Chisel"
    resolve(session)
    assert "A Cut Quartz" in player.inventory and "A Rough Quartz" not in player.inventory
    assert player.equipment["tool"] == "A Copper Chisel [249/250 uses]"
    assert any("Hitroll +2" in message and "future weapon upgrades" in message for message in session.sent)
    assert gemcutter.RECIPES["a rough quartz"][0] == "A Cut Quartz"
    with patch.object(olc, "_log"):
        olc.cmd_ostat(session, [str(content._ITEM_VNUMS["cut_quartz"])])
    assert any("Gem Bonuses" in message and "Hitroll +2" in message for message in session.sent)
    player.learned_skills.append("Examine")
    player.skill_proficiencies["Examine"] = 40
    commands.cmd_examine(session, ["cut", "quartz"])
    assert any("Future Weapon Gem Bonus" in message for message in session.sent)


def test_each_job_tool_wears_on_failed_attempts_and_kitchen_exception():
    content._register_shared_items()
    player = models.Player(name="Worker", account_name="Worker", stamina=1000)
    session = session_for(player)
    job_cases = [
        ("A Kindling Fishing Rod", commands.cmd_fish, commands.fishing, "attempt_catch", "river"),
        ("A Copper Pickaxe", commands.cmd_mine, commands.mining, "attempt_mine", "mountain"),
        ("A Copper Axe", commands.cmd_chop, commands.lumberjack, "attempt_chop", "forest"),
        ("A Copper Hoe", commands.cmd_farm, commands.farming, "attempt_farm", "plains"),
    ]
    for tool, handler, module, attempt, biome in job_cases:
        player.equipment["tool"] = tool
        with patch.object(commands.world.WORLD, "get", return_value=SimpleNamespace(biome=biome)), \
             patch.object(module, attempt, return_value={"failed": True}):
            handler(session, [])
            resolve(session)
        assert tool_durability.uses_left(player.equipment["tool"])[0] == 249

    fish = next(iter(cooking.INGREDIENTS))
    player.equipment["tool"] = "A Copper Cooking Pot"
    player.inventory.append(fish)
    with patch.object(commands.world.WORLD, "get", return_value=None), \
         patch.object(cooking, "attempt_cook", return_value={"burned": True}):
        commands.cmd_cook(session, [fish])
        resolve(session)
    assert tool_durability.uses_left(player.equipment["tool"])[0] == 249

    player.equipment.pop("tool")
    player.inventory.append(fish)
    kitchen = SimpleNamespace(apartment_room_type="kitchen", owner=player.name)
    with patch.object(commands.world.WORLD, "get", return_value=kitchen), \
         patch.object(cooking, "attempt_cook", return_value={"burned": True}):
        commands.cmd_cook(session, [fish])
        resolve(session)
    assert "tool" not in player.equipment


def test_tool_breaks_at_250_and_used_copy_keeps_wear_when_moved():
    content._register_shared_items()
    player = models.Player(name="Worker", account_name="Worker")
    player.equipment["tool"] = "A Copper Hoe"
    session = session_for(player)
    for _ in range(249):
        assert commands._use_held_job_tool(session, player.equipment["tool"])
    assert player.equipment["tool"] == "A Copper Hoe [1/250 uses]"
    saved = models.Player.from_dict(player.to_dict())
    player.equipment["tool"] = "A Copper Hoe"
    assert tool_durability.uses_left(player.equipment["tool"])[0] == 250
    session = session_for(saved)
    commands.cmd_remove(session, ["hoe"])
    assert saved.inventory == ["A Copper Hoe [1/250 uses]"]
    recipient = models.Player(name="Recipient", account_name="Recipient")
    moved = saved.inventory.pop()
    assert inventory.add_item(recipient.inventory, moved)[0]
    recipient_session = session_for(recipient)
    commands.cmd_hold(recipient_session, ["hoe"])
    assert recipient.equipment["tool"] == "A Copper Hoe [1/250 uses]"
    assert commands._use_held_job_tool(recipient_session, recipient.equipment["tool"])
    assert "tool" not in recipient.equipment
    assert any("breaks" in message for message in recipient_session.sent)
    assert playershops.item_vnum_for_stock("A Copper Hoe [1/250 uses]") is None
    assert playershops.stock_item_name({"item_name": "A Copper Hoe [1/250 uses]", "item_vnum": None}) == "A Copper Hoe [1/250 uses]"


def test_builder_sets_tool_uses_and_replacing_tool_cancels_attempt():
    content._register_shared_items()
    vnum = content._ITEM_VNUMS["chisel_copper"]
    proto = olc.OBJECT_TEMPLATES[vnum]
    old = proto["max_uses"]
    player = models.Player(name="Builder", account_name="Builder", stamina=100)
    session = session_for(player)
    try:
        with patch.object(olc, "_log"):
            olc.cmd_oset(session, [str(vnum), "uses", "2"])
            olc.cmd_oset(session, [str(vnum), "uses", "0"])
        assert proto["max_uses"] == 2
        player.equipment["tool"] = "A Copper Chisel"
        player.inventory.append("A Rough Quartz")
        commands.cmd_gemcut(session, ["quartz"])
        player.equipment["tool"] = "A Copper Hoe"
        resolve(session)
        assert player.inventory == ["A Rough Quartz"]
        player.equipment["tool"] = "A Copper Chisel"
        commands.cmd_gemcut(session, ["quartz"])
        resolve(session)
        assert player.equipment["tool"] == "A Copper Chisel [1/2 uses]"
        player.inventory.append("A Rough Quartz")
        commands.cmd_gemcut(session, ["quartz"])
        resolve(session)
        assert "tool" not in player.equipment
        assert player.inventory.count("A Cut Quartz") == 2
    finally:
        proto["max_uses"] = old
