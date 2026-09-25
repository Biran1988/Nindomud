"""
Phase 7 content: builds out each village with a Kage chamber, mission
board, a combat/mission area ("Outskirts") with respawning mobs, and
three shops (a General Store, a Weapons Shop, and a Blacksmith) --
linked onto the existing village square from Section 25/49. Call
`populate()` once at startup after `world.WORLD`, `combat`, and `olc`
are importable.

Shops are real shopkeeper MOBS (per the "shopkeeper flag" system --
see olc.py's mset additem/removeitem and combat.py's is_shopkeeper()),
not a hardcoded room-based dict. A builder can place a shopkeeper
anywhere the same way these are built: `mset <vnum> shopkeeper on`,
then `mset additem <vnum> <object vnum>` for each item they should
carry, priced at that object's own oset-set `cost`. The item prototypes
registered below (kunai, sword, shuriken, consumables, armor pieces)
are ordinary object prototypes -- nothing here is special-cased beyond
what any builder-made shopkeeper could also do.

SHOPS (the old room-vnum -> plain dict structure) is kept only as a
legacy fallback path in commands.py's cmd_list/cmd_buy/cmd_sell; it's
no longer populated by this module.
"""

import chunin_exam
import combat
import data_headbands
import data_villages
import territory
import farming
import fishing
import lumberjack
import mining
import cooking
import olc
import playershops
import spawn_points
import world
from world import Room, WORLD

# Legacy fallback -- see module docstring. No longer populated here.
SHOPS = {}

_VILLAGE_ROOMS = {
    "leaf": dict(square=None, hospital=None, kage=1, board=None, outskirts=None, shop=None,
                 weapons_shop=None, blacksmith=None, apartment_district=None, mob_template=5001),
    "stone": dict(square=None, hospital=None, kage=2501, board=None, outskirts=None, shop=None,
                  weapons_shop=None, blacksmith=None, apartment_district=None, mob_template=5002),
    "water": dict(square=None, hospital=None, kage=5001, board=None, outskirts=None, shop=None,
                  weapons_shop=None, blacksmith=None, apartment_district=None, mob_template=5003),
    "cloud": dict(square=None, hospital=None, kage=7501, board=None, outskirts=None, shop=None,
                  weapons_shop=None, blacksmith=None, apartment_district=None, mob_template=5004),
    "sand": dict(square=None, hospital=None, kage=10001, board=None, outskirts=None, shop=None,
                 weapons_shop=None, blacksmith=None, apartment_district=None, mob_template=5005),
}

# Shared object prototypes every village's shopkeepers draw from -- one
# set of vnums, not duplicated per village. weapon_type is set where the
# weapon-proficiency system (data_weapons.py) applies.
_ITEM_VNUMS_EXAM = {"heaven_scroll": 20800, "earth_scroll": 20801}

_ITEM_VNUMS = {
    "kunai": 9700, "sword": 9701, "shuriken": 9702, "salve": 9703, "pill": 9704,
    "rice_ball": 9705, "ramen": 9706, "canteen": 9707, "tea": 9708,
    "shirt": 9709, "pants": 9710, "sandals": 9711,
    "war_club": 9712, "spear": 9713, "chain_sickle": 9714,
    "rod_kindling": 20000, "rod_birch": 20001, "rod_oak": 20002, "rod_ironwood": 20003,
    "rod_masterwork_oak": 20004, "rod_heartwood": 20005,
    "iron_ingot": 9724, "sturdy_oak_log": 9725, "steel_ingot": 9726,
    "masterwork_oak_log": 9727, "chakra_steel_ingot": 9728,
    "ore_iron": 20400, "ore_steel": 20401, "ore_chakra_steel": 20402,
    # Miner loot table
    "rough_quartz": 9731,
    "raw_sapphire": 9732, "raw_ruby": 9733, "raw_diamond": 9734,
    "pickaxe_copper": 20100, "pickaxe_iron": 20101, "pickaxe_steel": 20102,
    "pickaxe_chakra_steel": 20103, "pickaxe_blacksteel": 20104, "pickaxe_diamond_tipped": 20105,
    # Lumberjack loot table
    "kindling": 9736, "birch_branch": 9737, "ironwood_log": 9738, "heartwood_log": 9739,
    "yew_log": 9758, "alloy_ingot": 9759,
    "weeds": 9760,
    "pot_copper": 20500, "pot_iron": 20501, "pot_steel": 20502,
    "pot_chakra_steel": 20503, "pot_blacksteel": 20504, "pot_diamond_studded": 20505,
    "cooked_minnow": 9762, "cooked_sardine": 9763, "cooked_trout": 9764, "cooked_bass": 9765,
    "cooked_salmon": 9766, "cooked_swordfish": 9767, "cooked_koi": 9768, "leviathan_fillet": 9769,
    "hoe_copper": 20300, "hoe_iron": 20301, "hoe_steel": 20302,
    "hoe_chakra_steel": 20303, "hoe_blacksteel": 20304, "hoe_diamond_bladed": 20305,
    "gem_quartz": 9790, "gem_jade": 9791, "gem_amber": 9792, "gem_garnet": 9793,
    "gem_amethyst": 9794, "gem_topaz": 9795, "gem_sapphire": 9796, "gem_emerald": 9797,
    "gem_ruby": 9798, "gem_diamond": 9799,
    # Weaponsmith crafted goods
    "iron_kunai_smith": 9740, "steel_sword_smith": 9741, "chakra_steel_shuriken_smith": 9742,
    # Armorsmith crafted goods
    "iron_shirt_smith": 9743, "steel_pants_smith": 9744, "chakra_steel_sandals_smith": 9745,
    # Gemcutter crafted goods
    "cut_quartz": 9746, "cut_sapphire": 9747, "cut_ruby": 9748, "cut_diamond": 9749,
    # Lumberjack tools (Mining's own moved to the new 20100+ range)
    "axe_copper": 20200, "axe_iron": 20201, "axe_steel": 20202,
    "axe_chakra_steel": 20203, "axe_blacksteel": 20204, "axe_diamond_edged": 20205,
    "genin_study_scroll": 9750,
    "track_scroll": 9771,
    "chakra_paper": 9801,
}


def _register_shared_items() -> None:
    if _ITEM_VNUMS["kunai"] in olc.OBJECT_TEMPLATES:
        return  # already registered (e.g. populate() called twice)

    def make(vnum, name, item_type, cost, weapon_type="", rarity="", wear_loc=None):
        obj = olc.default_object(vnum, name)
        obj["item_type"] = item_type
        obj["cost"] = cost
        if weapon_type:
            obj["weapon_type"] = weapon_type
        if rarity:
            obj["rarity"] = rarity
        # Auto-derive for weapons/tools (always the same slot regardless
        # of which specific weapon/tool it is) -- explicit wear_loc
        # still wins if passed, e.g. for armor, where it varies per item.
        if wear_loc is not None:
            obj["wear_loc"] = wear_loc
        elif item_type == "weapon":
            obj["wear_loc"] = "wielded"
        elif item_type == "tool":
            obj["wear_loc"] = "tool"
        olc.OBJECT_TEMPLATES[vnum] = obj

    make(_ITEM_VNUMS["kunai"], "A Basic Kunai", "weapon", 15, weapon_type="kunai")
    make(_ITEM_VNUMS["sword"], "A Basic Ninja Sword", "weapon", 40, weapon_type="sword")
    make(_ITEM_VNUMS["shuriken"], "A Throwing Shuriken", "weapon", 10, weapon_type="shuriken")
    make(_ITEM_VNUMS["war_club"], "A Wooden War Club", "weapon", 35, weapon_type="blunt")
    make(_ITEM_VNUMS["spear"], "A Bamboo Spear", "weapon", 45, weapon_type="polearm")
    make(_ITEM_VNUMS["chain_sickle"], "A Chain Sickle", "weapon", 60, weapon_type="exotic")
    make(_ITEM_VNUMS["salve"], "A Healing Salve", "medical", 25)
    make(_ITEM_VNUMS["pill"], "A Soldier Pill", "medical", 30)
    make(_ITEM_VNUMS["chakra_paper"], "A Sheet of Chakra Paper", "misc", 20)
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["chakra_paper"]]["long_desc"] = "A blank sheet of chakra paper lies here, waiting to react."
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["chakra_paper"]]["description"] = (
        "A thin sheet of paper made from a rare tree, sensitive to chakra. Channel your "
        "own chakra into it and it will react -- crumpling, burning, dampening, or splitting, "
        "depending on what it reveals about your own elemental nature. It's consumed the "
        "instant it reacts."
    )
    make(_ITEM_VNUMS["rice_ball"], "A Rice Ball", "food", 5)
    make(_ITEM_VNUMS["ramen"], "A Bowl of Ramen", "food", 12)
    make(_ITEM_VNUMS["canteen"], "A Canteen of Water", "drink", 5)
    make(_ITEM_VNUMS["tea"], "A Cup of Green Tea", "drink", 6)
    make(_ITEM_VNUMS["genin_study_scroll"], "A Genin Study Scroll", "scroll", 0)
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["genin_study_scroll"]]["scroll_jutsu"] = "shadow shuriken technique"
    make(_ITEM_VNUMS["track_scroll"], "A Track Scroll", "scroll", 500)
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["track_scroll"]]["scroll_jutsu"] = "track"
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["track_scroll"]]["long_desc"] = "A weathered scroll, sealed with a hunter-nin's own mark, lies here."
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["track_scroll"]]["description"] = (
        "A hunter-nin's own training scroll, teaching a technique for picking up and "
        "following a trail across real distance -- reading it unlocks the Track jutsu."
    )
    make(_ITEM_VNUMS["shirt"], "A Basic Ninja Shirt", "armor", 20, wear_loc="body")
    make(_ITEM_VNUMS["pants"], "Basic Ninja Pants", "armor", 20, wear_loc="legs")
    make(_ITEM_VNUMS["sandals"], "A Basic Ninja Sandals", "armor", 15, wear_loc="feet")

    # A real item prototype for each village's headband, for EVERY
    # rank tier (data_headbands.RANK_HEADBAND_TITLE). The
    # academy-student tier keeps its EXACT original vnum/name (no
    # rank word, no stat suffix, since its bonus is 0) so nothing
    # about the original starting headband changes; the 7 higher
    # tiers are for promotions (currently disabled game-wide except
    # for the user's own future mob-program-driven academy-student ->
    # genin promotion, but wired in correctly for when the rest
    # aren't). See data_headbands.py's own docstring for the full
    # "colored via existing rarity tiers, stat-boosted via the
    # existing crafted-item name-suffix mechanism" design.
    for _village_data in data_villages.VILLAGES.values():
        make(
            _village_data["default_headband_vnum"],
            f"A {_village_data['village_short_name']} Headband",
            "armor", 25, wear_loc="head",
        )
    _headband_vnum = 20700
    _RANK_COST = {
        "genin": 100, "chunin": 500, "special jonin": 2000,
        "jonin": 8000, "elite jonin": 30000, "village elder": 100000, "kage": 500000,
    }
    for _village_data in data_villages.VILLAGES.values():
        for _rank in data_headbands.RANK_ORDER:
            if _rank == "academy student":
                continue  # already registered above, at its own fixed vnum
            _name = data_headbands.headband_base_name(_village_data["village_short_name"], _rank)
            make(_headband_vnum, _name, "armor", _RANK_COST[_rank],
                 rarity=data_headbands.RANK_HEADBAND_RARITY[_rank], wear_loc="head")
            _ac_bonus = data_headbands.RANK_HEADBAND_AC_BONUS.get(_rank, 0)
            if _ac_bonus:
                olc.OBJECT_TEMPLATES[_headband_vnum]["stat_bonuses"]["armor_class"] = _ac_bonus
            _headband_vnum += 1

    # Fishing tools -- just one rod for now (crafting revamp).
    make(_ITEM_VNUMS["rod_kindling"], "A Kindling Fishing Rod", "tool", 50)

    # Every fish (fishing.FIND_TABLE -- 8 species, single non-tiered
    # items now, per the crafting revamp). Registered directly from
    # the table so item prototypes stay in sync with fishing.py.
    _FISH_COST = [2, 6, 30, 36, 200, 300, 2000, 20000]
    for _fish_index, (_fish_name, _req, _weight, _xp) in enumerate(fishing.FIND_TABLE):
        _fish_vnum = 20006 + _fish_index
        _display = " ".join(word.capitalize() for word in _fish_name.split())
        make(_fish_vnum, _display, "misc", _FISH_COST[_fish_index])

    # Cooked fish dishes (cooking.INGREDIENTS)
    for _dish_index, (_raw, _data) in enumerate(cooking.INGREDIENTS.items()):
        _dish_vnum = 20050 + _dish_index
        make(_dish_vnum, _data["dish"], "food", _data["base_cost"])

    make(_ITEM_VNUMS["iron_ingot"], "An Iron Ingot", "material", 200)
    make(_ITEM_VNUMS["sturdy_oak_log"], "A Sturdy Oak Log", "material", 300)
    make(_ITEM_VNUMS["steel_ingot"], "A Steel Ingot", "material", 2000)
    make(_ITEM_VNUMS["masterwork_oak_log"], "A Masterwork Oak Log", "material", 3000)
    make(_ITEM_VNUMS["chakra_steel_ingot"], "A Chakra Steel Ingot", "material", 60000)

    # Smeltable ore (mining.SMELTING_RECIPES) -- the raw form of the
    # ingots above. Priced as a fraction of the ingot's own cost, same
    # "raw material cheaper than the processed good" economics as
    # every other tier ladder.
    make(_ITEM_VNUMS["ore_iron"], "An Iron Ore", "material", 80)
    make(_ITEM_VNUMS["ore_steel"], "A Steel Ore", "material", 800)
    make(_ITEM_VNUMS["ore_chakra_steel"], "A Chakra Steel Ore", "material", 8000)

    # Gems -- each a single, non-tiered item, level-gated by
    # mining.FIND_TABLE rather than a rarity roll (Section 79 revamp).
    make(_ITEM_VNUMS["rough_quartz"], "A Rough Quartz", "material", 50)
    make(_ITEM_VNUMS["raw_sapphire"], "A Raw Sapphire", "material", 800)
    make(_ITEM_VNUMS["raw_ruby"], "A Raw Ruby", "material", 1200)
    make(_ITEM_VNUMS["raw_diamond"], "A Raw Diamond", "material", 50000)

    # Lumberjack loot table
    make(_ITEM_VNUMS["kindling"], "A Bundle of Kindling", "material", 1, rarity="common")
    make(_ITEM_VNUMS["birch_branch"], "A Birch Branch", "material", 2, rarity="common")
    make(_ITEM_VNUMS["ironwood_log"], "An Ironwood Log", "material", 600, rarity="rare")
    make(_ITEM_VNUMS["heartwood_log"], "An Ancient Heartwood Log", "material", 40000, rarity="legendary")

    # Mining tools -- deliberately just Copper for now (Section 79
    # crafting revamp, per explicit request): no tiered pickaxes,
    # Mining level itself now gates which materials are reachable
    # (see mining.FIND_TABLE) rather than the tool.
    make(_ITEM_VNUMS["pickaxe_copper"], "A Copper Pickaxe", "tool", 50)

    # Lumberjack tools
    # Lumberjack tools -- just one axe for now (crafting revamp).
    make(_ITEM_VNUMS["axe_copper"], "A Copper Axe", "tool", 50)

    # Lumberjack finds (lumberjack.FIND_TABLE) -- single, non-tiered
    # items registered directly from that table.
    _WOOD_COST = [1, 2, 300, 600, 3000, 40000]
    for _wood_index, (_wood_name, _req, _weight, _xp) in enumerate(lumberjack.FIND_TABLE):
        _wood_vnum = 20206 + _wood_index
        _wood_display = " ".join(word.capitalize() for word in _wood_name.split())
        make(_wood_vnum, _wood_display, "material", _WOOD_COST[_wood_index])

    # Master Fishing Rod materials (kept for now, may be used by future crafting)
    make(_ITEM_VNUMS["yew_log"], "A Yew Log", "material", 40000)
    make(_ITEM_VNUMS["alloy_ingot"], "An Alloy Ingot", "material", 20000)
    make(_ITEM_VNUMS["weeds"], "A Bundle of Weeds", "material", 1)

    # Cooking tool and dishes
    # Cooking tools -- just one pot for now (crafting revamp).
    make(_ITEM_VNUMS["pot_copper"], "A Copper Cooking Pot", "tool", 30)
    make(_ITEM_VNUMS["cooked_minnow"], "A Cooked Minnow", "food", 4)
    make(_ITEM_VNUMS["cooked_sardine"], "A Cooked Sardine", "food", 6)
    make(_ITEM_VNUMS["cooked_trout"], "A Cooked Trout", "food", 30)
    make(_ITEM_VNUMS["cooked_bass"], "A Cooked Bass", "food", 36)
    make(_ITEM_VNUMS["cooked_salmon"], "A Cooked Salmon", "food", 200)
    make(_ITEM_VNUMS["cooked_swordfish"], "A Cooked Swordfish", "food", 300)
    make(_ITEM_VNUMS["cooked_koi"], "A Cooked Golden Koi", "food", 2000, rarity="epic")
    make(_ITEM_VNUMS["leviathan_fillet"], "A Leviathan Fillet", "food", 20000, rarity="legendary")

    # Farming tools
    # Farming tools -- just one hoe for now (crafting revamp).
    make(_ITEM_VNUMS["hoe_copper"], "A Copper Hoe", "tool", 50)

    # Farming finds (farming.FIND_TABLE) -- single, non-tiered items.
    _CROP_COST = [2, 2, 15, 15, 100, 100, 1000, 10000]
    for _crop_index, (_crop_name, _req, _weight, _xp) in enumerate(farming.FIND_TABLE):
        _crop_vnum = 20306 + _crop_index
        _crop_display = " ".join(word.capitalize() for word in _crop_name.split())
        make(_crop_vnum, _crop_display, "food", _CROP_COST[_crop_index])

    # Random gem finds (gems.py) -- a rare bonus during Mining, distinct
    # from the raw ore-table gems above that still feed Gemcutter.
    make(_ITEM_VNUMS["gem_quartz"], "A Quartz", "misc", 15, rarity="uncommon")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_quartz"]]["long_desc"] = "A clear quartz crystal lies here."
    make(_ITEM_VNUMS["gem_jade"], "A Jade", "misc", 25, rarity="uncommon")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_jade"]]["long_desc"] = "A smooth green jade stone lies here."
    make(_ITEM_VNUMS["gem_amber"], "An Amber", "misc", 60, rarity="rare")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_amber"]]["long_desc"] = "A golden orange piece of amber lies here."
    make(_ITEM_VNUMS["gem_garnet"], "A Garnet", "misc", 70, rarity="rare")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_garnet"]]["long_desc"] = "A deep red garnet lies here."
    make(_ITEM_VNUMS["gem_amethyst"], "An Amethyst", "misc", 90, rarity="rare")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_amethyst"]]["long_desc"] = "A purple amethyst crystal lies here."
    make(_ITEM_VNUMS["gem_topaz"], "A Topaz", "misc", 100, rarity="rare")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_topaz"]]["long_desc"] = "A golden yellow topaz lies here."
    make(_ITEM_VNUMS["gem_sapphire"], "A Sapphire", "misc", 400, rarity="epic")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_sapphire"]]["long_desc"] = "A brilliant blue sapphire lies here."
    make(_ITEM_VNUMS["gem_emerald"], "An Emerald", "misc", 500, rarity="epic")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_emerald"]]["long_desc"] = "A vivid green emerald lies here."
    make(_ITEM_VNUMS["gem_ruby"], "A Ruby", "misc", 600, rarity="epic")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_ruby"]]["long_desc"] = "A deep red ruby lies here."
    make(_ITEM_VNUMS["gem_diamond"], "A Diamond", "misc", 5000, rarity="legendary")
    olc.OBJECT_TEMPLATES[_ITEM_VNUMS["gem_diamond"]]["long_desc"] = "A brilliant clear diamond lies here, catching the light."

    # Chunin Exam scrolls (chunin_exam.py). NOT no_sac protected --
    # per an earlier, explicit request, every item in the game must be
    # sacrificeable, with no exceptions (verified directly by
    # test_every_registered_item_can_be_sacrificed, which exercises
    # every single registered item). A player CAN accidentally
    # sacrifice a scroll they worked to obtain; that's a real, known
    # risk, kept consistent with that established rule rather than
    # quietly carving out an exception to it.
    make(_ITEM_VNUMS_EXAM["heaven_scroll"], chunin_exam.HEAVEN_SCROLL, "trash", 500, rarity="epic")
    make(_ITEM_VNUMS_EXAM["earth_scroll"], chunin_exam.EARTH_SCROLL, "trash", 500, rarity="epic")


def _make_shopkeeper(vnum: int, name: str, room_vnum: int, item_keys, buys_categories) -> None:
    t = combat.default_template(vnum, name)
    t["level"] = 1
    t["hit_dice"] = "1d1+9999"  # irrelevant -- shopkeepers can't be attacked
    t["act_flags"] = ["Npc", "Sentinel", "Shopkeeper"]
    t["shopkeeper"] = True
    t["shop_items"] = [_ITEM_VNUMS[key] for key in item_keys]
    t["shop_buys_categories"] = list(buys_categories)
    combat.MOB_TEMPLATES[vnum] = t
    # Per direct request/confirmation (Section 138): no longer auto-spawned --
    # content.py's own hardcoded startup call was unconditionally re-registering
    # this spawn point every server restart, silently undoing a staff member's
    # real, deliberate removal. The mob's own real template still registers
    # here (spawnable via 'spawnpoint add'), it just no longer auto-spawns.


def populate() -> None:
    from data_villages import VILLAGES
    from kage import kage_title
    import areas

    areas.ensure_single_village_areas()
    _register_shared_items()

    # Shopkeeper mob template vnums: village index * 10 + role, in the
    # 6000 block (distinct from the 5000-block bandit templates).
    village_index = {"leaf": 0, "stone": 1, "water": 2, "cloud": 3, "sand": 4}

    for village, rooms in _VILLAGE_ROOMS.items():
        v = VILLAGES[village]
        short = v["village_short_name"]

        # Per direct request/confirmation (Section 143): "convert
        # these into 1 leaf village not expansions...give each area
        # 2500 vnums to work with no expansions so that they are
        # single areas...create a single room for each that will be
        # the hokage room in this new are its ok to wipe old areas in
        # this one instance." Every OTHER real room this loop used to
        # build (mission board, shops, gambling den, roulette room,
        # apartments, Main Street, gathering spots) is genuinely gone
        # -- confirmed directly this is fine to wipe entirely. Every
        # real MOB TEMPLATE below is confirmed to STAY registered
        # exactly as before (shopkeeper, villager, banker, gambling
        # attendant, bandit, mission targets, etc.) -- they simply
        # won't spawn anywhere until staff places them via
        # 'spawnpoint add' at whatever new rooms they build.
        kage_room = Room(rooms["kage"], f"{short} Kage Chamber",
            f"The office of {kage_title(village)}. Try 'say mission' or 'ask kage promotion'.")
        kage_room.safe = True
        kage_room.flags.append("accelerated_healing")
        WORLD.add_room(kage_room)

        attendant_vnum = 6000 + village_index[village] * 10 + 4
        attendant = combat.default_template(attendant_vnum, f"a {short} gambling den attendant")
        attendant["level"] = 1
        attendant["hit_dice"] = "1d1+9999"  # irrelevant -- can't be attacked, same as shopkeepers
        attendant["act_flags"] = ["Npc", "Sentinel"]
        attendant["gambler"] = True
        combat.MOB_TEMPLATES[attendant_vnum] = attendant
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        roulette_attendant_vnum = 6000 + village_index[village] * 10 + 8
        roulette_attendant = combat.default_template(roulette_attendant_vnum, f"a {short} roulette croupier")
        roulette_attendant["level"] = 1
        roulette_attendant["hit_dice"] = "1d1+9999"  # irrelevant -- can't be attacked, same as shopkeepers
        roulette_attendant["act_flags"] = ["Npc", "Sentinel"]
        roulette_attendant["gambler"] = True
        combat.MOB_TEMPLATES[roulette_attendant_vnum] = roulette_attendant
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        if village == "leaf":
            # The one generic Shopkeeper template every player shop
            # reuses -- shop_items stays empty (real stock lives on the
            # OWNER's own shop_stock, not the shared template), and it
            # doesn't buy anything either (player shops only sell what
            # their owner stocked, not buy from random players).
            shopkeeper_template = combat.default_template(
                playershops.SHOPKEEPER_TEMPLATE_VNUM, "a shopkeeper"
            )
            shopkeeper_template["level"] = 1
            shopkeeper_template["hit_dice"] = "1d1+9999"  # irrelevant -- can't be attacked, same as other shopkeepers
            shopkeeper_template["act_flags"] = ["Npc", "Sentinel", "Shopkeeper"]
            shopkeeper_template["shopkeeper"] = True
            shopkeeper_template["shop_items"] = []
            shopkeeper_template["shop_buys_categories"] = []
            combat.MOB_TEMPLATES[playershops.SHOPKEEPER_TEMPLATE_VNUM] = shopkeeper_template

        combat.register_template(
            rooms["mob_template"], f"a wandering bandit near {short}",
            level=3, max_health=40, min_damage=3, max_damage=6,
            experience_reward=70, ryo_reward=10,
            loot_items=["A Basic Kunai"],
        )
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add',
        # and can set its own spawn caps via 'spawnpoint cap' at that point.

        # Higher mission-rank targets (Section 69) -- C/B/A/S, one each,
        # reusing the existing Outskirts room rather than building new
        # areas. Mob-granted xp/ryo stay modest since the MISSION itself
        # layers a much bigger bonus reward on top, same as D-Rank.
        # All 4 flagged Mission (Section: dynamic rank-request missions)
        # -- these form the real pool missions.pick_mission_mob() draws
        # from when a player requests a C/B/A/S rank mission.
        combat.register_template(
            rooms["mob_template"] + 100, f"a rogue ninja near {short}",
            level=15, max_health=150, min_damage=8, max_damage=14,
            experience_reward=150, ryo_reward=30,
        )
        combat.MOB_TEMPLATES[rooms["mob_template"] + 100]["act_flags"] = ["Npc", "Mission"]
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        combat.register_template(
            rooms["mob_template"] + 200, f"a missing-nin near {short}",
            level=30, max_health=350, min_damage=15, max_damage=25,
            experience_reward=400, ryo_reward=80,
        )
        combat.MOB_TEMPLATES[rooms["mob_template"] + 200]["act_flags"] = ["Npc", "Mission"]
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        combat.register_template(
            rooms["mob_template"] + 300, f"an elite mercenary near {short}",
            level=55, max_health=700, min_damage=30, max_damage=45,
            experience_reward=1000, ryo_reward=200,
        )
        combat.MOB_TEMPLATES[rooms["mob_template"] + 300]["act_flags"] = ["Npc", "Mission"]
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        combat.register_template(
            rooms["mob_template"] + 400, f"a legendary rogue near {short}",
            level=85, max_health=1500, min_damage=60, max_damage=90,
            experience_reward=3000, ryo_reward=500,
        )
        combat.MOB_TEMPLATES[rooms["mob_template"] + 400]["act_flags"] = ["Npc", "Mission"]
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        idx = village_index[village]
        _make_shopkeeper(
            6000 + idx * 10 + 1, f"a {short} general store shopkeeper", rooms["shop"],
            ["kunai", "shuriken", "salve", "pill", "chakra_paper", "rice_ball", "ramen", "canteen", "tea",
             "rod_kindling", "axe_copper", "pickaxe_copper", "pot_copper", "hoe_copper"],
            buys_categories=[],
        )
        _make_shopkeeper(
            6000 + idx * 10 + 2, f"a {short} weapons shopkeeper", rooms["weapons_shop"],
            ["kunai", "sword", "shuriken", "war_club", "spear", "chain_sickle"],
            buys_categories=["weapon"],
        )
        _make_shopkeeper(
            6000 + idx * 10 + 3, f"a {short} blacksmith", rooms["blacksmith"],
            ["shirt", "pants", "sandals"],
            buys_categories=["armor"],
        )
        villager = combat.default_template(6000 + idx * 10 + 5, f"a {short} villager")
        villager["level"] = 1
        villager["hit_dice"] = "1d1+9999"  # can't be attacked, matching shopkeepers/gambling den attendants
        villager["act_flags"] = ["Npc", "Sentinel"]
        combat.MOB_TEMPLATES[6000 + idx * 10 + 5] = villager
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        # Bingo Book office -- lets any player use 'place bounty' here
        # (see commands.cmd_place), closing the gap where the
        # BountyOffice flag existed but no actual mob anywhere in the
        # game used it. One per village, at the village square (same
        # high-visibility spot as the villager above), not gated to
        # Leaf only like the gambling den -- posting a bounty is a
        # core, village-agnostic feature.
        bounty_office = combat.default_template(6000 + idx * 10 + 6, f"a {short} Bingo Book office attendant")
        bounty_office["level"] = 1
        bounty_office["hit_dice"] = "1d1+9999"  # can't be attacked, matching shopkeepers/villager above
        bounty_office["act_flags"] = ["Npc", "Sentinel", "BountyOffice"]
        combat.MOB_TEMPLATES[6000 + idx * 10 + 6] = bounty_office
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

        # Banker -- lets any player deposit/withdraw ryo safely away
        # from death-penalty loss and PvP (see bank.py, commands.
        # cmd_bank). One per village, at the village square, same
        # placement as the Bingo Book office right above.
        banker = combat.default_template(6000 + idx * 10 + 7, f"a {short} banker")
        banker["level"] = 1
        banker["hit_dice"] = "1d1+9999"  # can't be attacked, matching shopkeepers/villager above
        banker["act_flags"] = ["Npc", "Sentinel", "Banker"]
        combat.MOB_TEMPLATES[6000 + idx * 10 + 7] = banker
        # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

    # --- War/territory system: garrison mob templates (Section 79) ---
    # One real, fightable mob template per village+tier combo (15
    # total), driven directly from territory.py's own tier/vnum
    # definitions so these can never drift out of sync with what
    # territory.buy_garrison() actually spawns. Not spawned anywhere
    # here -- a garrison mob only exists once a village's treasury pays
    # to station one at a specific capture point (see cmd_garrison).
    for _village_key in data_villages.VILLAGES:
        _village_short = data_villages.VILLAGES[_village_key]["village_short_name"]
        for _tier_key, _tier_info in territory.GARRISON_TIERS.items():
            _garrison_vnum = territory.garrison_mob_vnum(_village_key, _tier_key)
            combat.register_template(
                _garrison_vnum, f"a {_village_short} {_tier_info['display_name'].lower()}",
                level=_tier_info["level"], max_health=_tier_info["max_health"],
                min_damage=_tier_info["min_damage"], max_damage=_tier_info["max_damage"],
                experience_reward=_tier_info["level"] * 5, ryo_reward=_tier_info["level"] * 2,
            )
            combat.MOB_TEMPLATES[_garrison_vnum]["act_flags"] = ["Npc", "Garrison"]

    # Trap/bomb mob templates (10 total, 5 villages x 2 types) -- same
    # driven-from-territory.py reasoning as garrison mobs above. Given
    # modest, killable HP (not unkillable like garrison/shopkeepers),
    # so an enemy who actually spots one can fight and disarm it
    # rather than only ever being able to walk into it blind. Zero
    # attack damage of their own -- their real "damage" is the
    # trigger-on-entry hit (territory.check_trap_trigger), not normal
    # mob combat, so they shouldn't also independently attack back.
    for _village_key in data_villages.VILLAGES:
        _village_short = data_villages.VILLAGES[_village_key]["village_short_name"]
        for _trap_key, _trap_info in territory.TRAP_TYPES.items():
            _trap_vnum = territory.trap_mob_vnum(_village_key, _trap_key)
            combat.register_template(
                _trap_vnum, f"a {_village_short} {_trap_info['display_name'].lower()}",
                level=20, max_health=150, min_damage=0, max_damage=0,
                experience_reward=50, ryo_reward=10,
            )
            combat.MOB_TEMPLATES[_trap_vnum]["act_flags"] = ["Npc", "Trap"]

    # --- Chunin Exam: Forest of Death (shared, not per-village) --------
    # See chunin_exam.py's own docstring for the full design reasoning.
    if not areas.find_area("forest-of-death"):
        try:
            areas.register_area("forest-of-death", 60000, 60099, "system")
        except ValueError:
            pass  # registered by a concurrent/earlier call in the same startup

    entrance = Room(chunin_exam.ENTRANCE_VNUM, "Forest of Death -- Entrance",
        "A massive iron fence, strung with warning signs, marks the edge of "
        "this sealed training ground. Beyond it, the trees grow close and "
        "dark. Genin gather here before an exam attempt, and the only way "
        "back out before finishing is to survive the trip.")
    entrance.safe = True
    WORLD.add_room(entrance)

    forest_names = [
        ("Forest of Death -- Deep Woods",
         "Thick undergrowth and looming trees swallow the light here. "
         "Something is always moving just out of sight."),
        ("Forest of Death -- Ravine",
         "A steep ravine cuts through the forest floor, its bottom lost "
         "in shadow. The air is heavy with the smell of damp earth."),
        ("Forest of Death -- Clearing",
         "A rare gap in the canopy lets sunlight reach the ground, "
         "illuminating claw marks scored deep into the surrounding bark."),
    ]
    for vnum, (name, desc) in zip(chunin_exam.FOREST_VNUMS, forest_names):
        room = Room(vnum, name, desc)
        room.biome = "forest"
        WORLD.add_room(room)

    tower = Room(chunin_exam.TOWER_VNUM, "Forest of Death -- Tower",
        "A weathered stone tower rises at the heart of the forest, its "
        "entrance marked with the sigil of the exam proctors. This is "
        "where an exam attempt is completed.")
    tower.safe = True
    WORLD.add_room(tower)

    WORLD.link(chunin_exam.ENTRANCE_VNUM, "north", chunin_exam.FOREST_VNUMS[0])
    WORLD.link(chunin_exam.FOREST_VNUMS[0], "east", chunin_exam.FOREST_VNUMS[1])
    WORLD.link(chunin_exam.FOREST_VNUMS[1], "north", chunin_exam.FOREST_VNUMS[2])
    WORLD.link(chunin_exam.FOREST_VNUMS[2], "west", chunin_exam.TOWER_VNUM)
    WORLD.link(chunin_exam.FOREST_VNUMS[0], "north", chunin_exam.TOWER_VNUM)  # a shortcut, so the forest isn't a single forced path

    combat.register_template(
        chunin_exam.HEAVEN_GUARDIAN_VNUM, "a Heaven Scroll guardian", level=15,
        max_health=250, min_damage=8, max_damage=18,
        experience_reward=400, ryo_reward=200,
        loot_items=[chunin_exam.HEAVEN_SCROLL],
    )
    # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

    combat.register_template(
        chunin_exam.EARTH_GUARDIAN_VNUM, "an Earth Scroll guardian", level=15,
        max_health=250, min_damage=8, max_damage=18,
        experience_reward=400, ryo_reward=200,
        loot_items=[chunin_exam.EARTH_SCROLL],
    )
    # No hardcoded spawn point (Section 138) -- staff adds it via 'spawnpoint add'.

    # Legendary Kage-sold items (Section 76, per explicit request) --
    # registered once here, same as every other piece of shipped item
    # content, before spawn_points.apply_all() runs.
    import legendary_items
    legendary_items.register_all(olc, combat)

    # Restore builder-created prototypes before applying the saved world so
    # every snapshot reference resolves safely.
    spawn_points.restore_custom_templates()

    # Apply the manually-saved room/mob/item snapshot over hardcoded content.
    import world_persistence
    world_persistence.apply_saved_world()

    # Spawn points are the FINAL reconciliation pass. Reapply their latest
    # authoritative prototypes, then restore only genuinely missing mobs and
    # items. This ordering prevents a stale world snapshot from making a
    # registered spawn disappear after reboot.
    spawn_points.restore_custom_templates()
    spawn_points.apply_all()

    # Persistent Teams (Section 82, per explicit request) -- loads
    # whatever teams already exist in teams.json back into memory.
    # Order relative to the rest of populate() doesn't actually
    # matter (teams don't reference any room/mob/item content at
    # all), but placed last to match this function's own established
    # convention of loading player-created persistent state after
    # every static system exists.
    import teams
    teams.load_all()

    # OOC chat log (Section 93, per direct request) -- persisted
    # across restarts, matching teams.load_all()'s own pattern.
    import chatlog
    chatlog.load_all()

    # The Duel Arena (Section 89, per direct request) -- a genuine,
    # permanent 10-room area, built the same way as every other static
    # room in the game.
    import duel_arena
    duel_arena.build_arena(world)

    # The Jail Cell (Section 94, per direct request) -- a genuine,
    # permanent, exit-less room, built the same way as every other
    # static room in the game.
    import jail
    jail.build_jail(world)

    # Tailed Beasts (Section 127, per direct request/confirmation) --
    # registers all 9 real beast mob templates so they're ready the
    # instant an immortal uses 'unleash beast', matching every other
    # hardcoded mob's own registration convention.
    import tailed_beasts
    tailed_beasts.register_all_beast_templates(combat)


def register_default_spawn_points_for_testing() -> None:
    """TEST-ONLY. Per direct request/confirmation (Section 138): "i
    dont want any hardcoded spawnpoitns at all staff will add the
    spawnpoints and if there are spawnpoiitns mobs will spawn" -- the
    real game (populate(), above) genuinely has zero hardcoded
    add_spawn_point calls anymore; staff builds the entire spawn
    layout manually via 'spawnpoint add', and content.py's own
    hardcoded startup code will never silently undo a real removal
    again.

    Per direct correction (Section 143): every village is now
    genuinely a SINGLE real room (the Kage/Hokage chamber) -- every
    other room this helper used to reference (shop, mission board,
    outskirts, gambling den) no longer exists at all until staff
    builds one themselves, so every real mob below spawns at that one
    genuinely real room instead. This is the CORRECT, current state
    of the game, not a placeholder -- there is no separate
    "already-configured server" to simulate anymore.

    This function exists ONLY so the existing test suite (which
    assumes a banker/shopkeeper/villager/bandit/etc. is already
    present) doesn't need a wholesale rewrite. Call this once after
    populate() in a test's own setup, then spawn_points.apply_all()
    to actually spawn from what it just registered. Never called by
    the real game itself (main.py, session.py)."""
    from data_villages import VILLAGES
    village_index = {"leaf": 0, "stone": 1, "water": 2, "cloud": 3, "sand": 4}

    for village, rooms in _VILLAGE_ROOMS.items():
        idx = village_index[village]
        kage_room = rooms["kage"]

        # Every real mob template spawns at the one room that
        # genuinely exists per village (Section 143) -- the Kage
        # room. 3 real shopkeepers.
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 1, kage_room)
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 2, kage_room)
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 3, kage_room)
        # Villager, gambling attendant, banker.
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 5, kage_room)
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 6, kage_room)
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 7, kage_room)
        # Gambling den + roulette room attendants.
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 4, kage_room)
        spawn_points.add_spawn_point("mob", 6000 + idx * 10 + 8, kage_room)
        # 5 mission-target tiers.
        for offset in (0, 100, 200, 300, 400):
            spawn_points.add_spawn_point("mob", rooms["mob_template"] + offset, kage_room)

    # Chunin Exam forest guardians.
    import chunin_exam
    spawn_points.add_spawn_point("mob", chunin_exam.HEAVEN_GUARDIAN_VNUM, chunin_exam.FOREST_VNUMS[0])
    spawn_points.add_spawn_point("mob", chunin_exam.EARTH_GUARDIAN_VNUM, chunin_exam.FOREST_VNUMS[2])
