"""
Online Creation, SmaugFUSS-style (Sections 36-44): mset/oset/rset field
editors plus mstat/ostat/rstat full stat-block displays, and builder
audit logging.

Design honesty note: mob prototypes carry the full SMAUG-style stat
block (attributes, AC/hitroll/damroll, act flags, resistances, body
parts, etc.) shown by `mstat`. Of these, hit_dice and damage_dice are
genuinely load-bearing -- they drive a spawned mob's actual health and
attack damage (see combat.py). armor_class/hit_roll/damage_roll and all
the flag/resistance/body-part fields are stored and DISPLAYED but not
yet wired into hit-chance or damage-mitigation math; they're recorded
here in one place specifically so that wiring is a future addition, not
a rewrite. This mirrors the same honest-labeling pattern used for
player-side derived_stats.py.

Field editing here is single-line (`mset 1001 level 12`), not a real
interactive sub-editor, matching redit's original design note -- except
`rset` (room) still gets the interactive line editor for name/desc,
inherited unchanged from the old `redit`.
"""

import os
import time
import random
from typing import List, Optional

import colors
import combat
import spawn_points
import data_kekkei_genkai
import data_clans
import data_jutsu
import data_rarity
import areas
import biomes
import programs
import data_weapons
import item_types
import dice
import leveling
import status_effects
import storage
import tips
import world

STAFF_CAN_BUILD = {"builder", "area leader", "administrator", "implementor"}
# Editing a real player's stats (level, exp, ryo, attributes...) is a bigger
# deal than editing a mob prototype -- restrict it to admin-and-above,
# matching how real ROM/SMAUG codebases gate their `pset`-equivalent command
# more tightly than ordinary OLC.
STAFF_CAN_EDIT_PLAYERS = {"administrator", "implementor"}
# Enabling/disabling a vnum outright (mob/room/item) is a global,
# server-wide switch -- reserved for Implementor ("immortal") only,
# stricter even than the admin-level player-stat editor above.
STAFF_CAN_TOGGLE_VNUMS = {"implementor"}

AUDIT_LOG_PATH = os.path.join(storage.DATA_DIR, "olc_audit.log")

# --- Object prototypes (SmaugFUSS-style, oset/ostat) ----------------------

# Every valid wear_loc value an item can declare. "wielded" (weapons)
# and "tool" (job tools like fishing rods/pickaxes) are each their own
# dedicated command (wield/hold); everything else is armor, worn via
# 'wear'. head/hands/waist have no items yet (matching the existing
# "hide until a real item exists" pattern used for weapon types
# elsewhere), but are defined now so future armor can use them without
# revisiting this system.
WEAR_LOCATIONS = {"head", "body", "legs", "feet", "hands", "waist", "finger", "neck", "piercing", "back", "chakra aura", "wielded", "tool"}
ARMOR_WEAR_LOCATIONS = {"head", "body", "legs", "feet", "hands", "waist", "finger", "neck", "piercing", "back", "chakra aura"}

DEFAULT_OBJECT_FIELDS = {
    "keywords": [], "short_desc": "", "long_desc": "", "description": "",
    "item_type": "trash", "weapon_type": "", "extra_flags": [], "wear_flags": ["take"],
    # Where this item can actually be equipped -- "" means not
    # equippable at all (food, materials, misc). Set explicitly per
    # item rather than inferred from item_type or name, per explicit
    # request: previously ANY item could be equipped into ANY slot,
    # since the slot was determined solely by which command (wear/
    # wield/hold) the player happened to type, not by the item itself
    # -- e.g. 'wear sword' would put a sword in the body slot. See
    # WEAR_LOCATIONS below for the full valid set.
    "wear_loc": "",
    "values": [0, 0, 0, 0], "weight": 1, "cost": 0, "level": 0,
    "condition": 100, "enabled": True,  # immortal-only toggle
    # Scroll system -- set item_type to "scroll" and scroll_jutsu to a
    # data_jutsu.JUTSU key (blank = not yet inscribed) so a player can
    # 'read' it to learn that jutsu (see commands.cmd_read). Lets a
    # jutsu be delivered as a discoverable/craftable item rather than
    # only ever granted at character creation.
    "scroll_jutsu": "",
    # A container's own real capacity (Section 158, per direct
    # request: "have we added backpocks yet that can hold items" ->
    # confirmed a genuinely SEPARATE container with its own capacity,
    # not just a bump to the normal inventory limit). 0 (the real
    # default) means this item is NOT a container at all. A builder
    # sets this via 'oset <vnum> container_capacity <n>' to make any
    # item a real backpack holding up to n items -- confirmed
    # directly this should be a real, standalone, settable field so
    # different backpacks can hold different amounts, not one fixed
    # size for every backpack in the game.
    "container_capacity": 0,
    # Rarity (Borderlands-style, Common -> Legendary) -- set by the
    # immortal who creates the item, not derived automatically. See
    # data_rarity.py.
    "rarity": "common",
    # Armor set bonus -- set_vnums lists the OTHER object vnums that
    # must ALSO be worn at the same time as this one to complete the
    # set (this item's own vnum doesn't need to be listed). Once a
    # player is wearing this item AND every vnum in set_vnums
    # simultaneously, set_bonus_percent is added to their derived
    # combat stats (AC/hitroll/damroll/dodge/crit -- see
    # derived_stats.py). Bonus defaults to 25% but is settable per item.
    "set_vnums": [],
    "set_bonus_percent": 25,
    # Stat perks -- per explicit request for item data storing "stat
    # perks and flags". Prototype-level (every instance of this item
    # shares the same bonus), not per-instance -- see WEAR_LOCATIONS'
    # own comment above for the same reasoning: items are plain
    # strings with no per-instance data, and a name-suffix workaround
    # for a per-crafted-instance bonus was removed for causing real
    # bugs (broken exact-match lookups). This is the architecturally
    # sound alternative, matching how ROM/MUD affects traditionally
    # live on the prototype, set once by a builder via 'oset <vnum>
    # statbonus <stat> <value>'. Valid keys: STAT_BONUS_KEYS below.
    "stat_bonuses": {},
    # Declarative programs (see programs.py) -- wear/get triggers only,
    # no arbitrary code. Each entry: {"trigger", "action", "args"}.
    "item_programs": [],
}

STAT_BONUS_KEYS = {
    "hitroll", "damroll", "armor_class",
    "max_health", "max_chakra", "max_stamina",
    "strength", "dexterity", "intelligence", "wisdom", "luck", "constitution",
}

OBJECT_TEMPLATES = {}


def default_object(vnum: int, name: str = "an unfinished object") -> dict:
    o = {}
    for k, v in DEFAULT_OBJECT_FIELDS.items():
        if isinstance(v, list):
            o[k] = list(v)
        elif isinstance(v, dict):
            o[k] = dict(v)
        else:
            o[k] = v
    o["short_desc"] = name
    o["long_desc"] = f"{name.capitalize()} lies here."
    o["keywords"] = name.split()
    return o


def _log(staff_name: str, entity_type: str, entity_id, description: str) -> None:
    storage.ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {staff_name} | {entity_type} {entity_id} | {description}\n"
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


def can_build(session) -> bool:
    return session.account is not None and session.account.staff_level in STAFF_CAN_BUILD


def can_edit_players(session) -> bool:
    return session.account is not None and session.account.staff_level in STAFF_CAN_EDIT_PLAYERS


def can_toggle_vnums(session) -> bool:
    return session.account is not None and session.account.staff_level in STAFF_CAN_TOGGLE_VNUMS


def _require_builder(session) -> bool:
    if not can_build(session):
        session.send("You do not have builder access.")
        return False
    return True


def _require_admin(session) -> bool:
    if not can_edit_players(session):
        session.send("Editing player characters requires administrator access or higher.")
        return False
    return True


def _require_implementor(session) -> bool:
    if not can_toggle_vnums(session):
        session.send("Enabling/disabling vnums requires Implementor access.")
        return False
    return True


def _rule(width: int = 62) -> str:
    return "&W" + "-" * width + "&x"


def _fmt_list(items) -> str:
    return " ".join(str(i).title() for i in items) if items else "None"


def _fmt_programs(program_list) -> str:
    if not program_list:
        return "None"
    lines = []
    for i, prog in enumerate(program_list):
        if prog.get("trigger") == "speech":
            lines.append(f"    [{i}] on speech of '{prog.get('keyword', '')}': {prog.get('action')} \"{prog.get('args', '')}\"")
        else:
            lines.append(f"    [{i}] on {prog.get('trigger')}: {prog.get('action')} \"{prog.get('args', '')}\"")
    return "\n" + "\n".join(lines)


# ===========================================================================
# MSTAT / OSTAT / RSTAT -- full stat-block displays
# ===========================================================================

def cmd_mstat(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send(
            "Usage: mstat <vnum>  OR  mstat <mob name>  (matches a live mob in your room)  "
            "OR  mstat <player name>  (shows their score sheet)"
        )
        return

    live_mob = None
    if args[0].isdigit() and int(args[0]) in combat.MOB_TEMPLATES:
        vnum = int(args[0])
        t = combat.MOB_TEMPLATES[vnum]
    else:
        query = " ".join(args)
        live_mob = combat.find_mob(session.player.room_vnum, query)
        if not live_mob:
            target_player, live_session = _find_target_player(query)
            if target_player:
                import commands
                fighting_name = "Nobody"
                target_staff_level = None
                if live_session:
                    if live_session.combat_target:
                        fighting_name = live_session.combat_target.name
                    if live_session.account:
                        target_staff_level = live_session.account.staff_level
                else:
                    account = storage.load_account(target_player.name)
                    if account:
                        target_staff_level = account.staff_level
                lines = commands.build_score_lines(target_player, fighting_name, target_staff_level)
                if can_edit_players(session):
                    if target_player.bloodline_id:
                        bloodline_line = (
                            f"{data_kekkei_genkai.display_name(target_player.bloodline_id)} "
                            f"(Potential: {target_player.bloodline_potential}/100, "
                            f"Talent: {target_player.bloodline_talent}/100)"
                        )
                    else:
                        bloodline_line = "None"
                    lines.append("")
                    lines.append("&WKekkei Genkai status (admin-only, never shown to the player):&x")
                    lines.append(f"  Clan: {data_clans.display_name(target_player.clan)}")
                    lines.append(f"  Bloodline: {bloodline_line}")
                    lines.append(f"  Awakened: {'Yes' if target_player.bloodline_awakened else 'No'}")
                    if target_player.bloodline_id:
                        mastery_pct = data_kekkei_genkai.mastery_percent(target_player) * 100
                        lines.append(
                            f"  Mastery: {target_player.bloodline_mastery}/{target_player.bloodline_potential} "
                            f"({mastery_pct:.0f}%)  Stage-2 quest eligible: "
                            f"{'Yes' if data_kekkei_genkai.eligible_for_awakening_quest(target_player) else 'No'}"
                        )
                    else:
                        lines.append(f"  Mastery: {target_player.bloodline_mastery}")
                    if target_player.bloodline_id == "sharingan":
                        tomoe_cap = data_kekkei_genkai.max_tomoe_for_potential(target_player.bloodline_potential)
                        lines.append(f"  Tomoe: {target_player.bloodline_tomoe}/{tomoe_cap} (Potential-based cap)")
                        lines.append(f"  Sharingan active: {'Yes' if target_player.sharingan_active else 'No'}")
                        if target_player.copied_jutsu_key:
                            lines.append(f"  Copied jutsu ready: {target_player.copied_jutsu_key} (costs {target_player.copied_jutsu_cost} chakra)")
                session.send("\n".join(lines))
                return
            session.send(f"No mobile prototype '{args[0]}' exists, and no mob or player named '{query}' was found.")
            return
        vnum = live_mob.template_vnum
        t = combat.MOB_TEMPLATES.get(vnum)
        if not t:
            session.send(f"{live_mob.name} (instance #{live_mob.instance_id}) has no editable prototype on file (vnum {vnum} missing).")
            return
    a = t["attributes"]

    header = f"&WMobile: [{vnum}] {t['short_desc']}&x"
    if live_mob:
        header += f"  &D(instance #{live_mob.instance_id}, room {live_mob.room_vnum})&x"

    mob_class = live_mob.primary_class if live_mob else t.get("primary_class")
    class_label = mob_class if mob_class in world_classes() else "None"

    lines = [
        header,
        _rule(),
        f"&WKeywords:&x {' '.join(t['keywords'])}",
        f"&WShort:&x {t['short_desc']}",
        f"&WLong:&x {t['long_desc']}",
        f"&WDescription:&x {t['description'] or '(none set)'}",
        _rule(),
        (f"&WVnum:&x {vnum}   &WLevel:&x {t['level']}   &WClass:&x "
         f"{class_label}"),
        (f"&WSex:&x {t['sex']}   &WAlignment:&x {t['alignment']}   "
         f"&WPosition:&x {t['position']}   &WDefault Pos:&x {t['default_position']}"),
        _rule(),
        f"&C{'ATTRIBUTES'.center(62)}&x",
        _rule(),
        (f"&WStrength:&x {a['str']}   &WIntelligence:&x {a['int']}   &WWisdom:&x {a['wis']}   "
         f"&WDexterity:&x {a['dex']}"),
        f"&WConstitution:&x {a['con']}   &WCharisma:&x {a['cha']}   &WLuck:&x {a['luck']}",
        _rule(),
        f"&C{'COMBAT'.center(62)}&x",
        _rule(),
        f"&WHit Points:&x {t['hit_dice']}   &WMana:&x {t['mana']}   &WMovement:&x {t['move']}",
    ]
    if live_mob:
        hp_color = colors.resource_color(live_mob.health, live_mob.max_health)
        lines.append(f"&WCurrent HP:&x {hp_color}{live_mob.health}/{live_mob.max_health}&x")
    lines += [
        f"&WArmor Class:&x {t['armor_class']}   &WHit Roll:&x {t['hit_roll']}   &WDamage Roll:&x {t['damage_roll']}",
        f"&WDamage Dice:&x {t['damage_dice']}   &WAttacks:&x {t['attacks']}",
        _rule(),
        f"&C{'FLAGS AND BEHAVIOR'.center(62)}&x",
        _rule(),
        f"&WAct Flags:&x {_fmt_list(t['act_flags'])}",
        f"&WAffected By:&x {_fmt_list(t['affected_by'])}",
        f"&WAttacks:&x {_fmt_list(t['attack_verbs'])}",
        f"&WDefenses:&x {_fmt_list(t['defenses'])}",
        f"&WResistant:&x {_fmt_list(t['resistant'])}",
        f"&WImmune:&x {_fmt_list(t['immune'])}",
        f"&WSusceptible:&x {_fmt_list(t['susceptible'])}",
        f"&WBody Parts:&x {_fmt_list(t['body_parts'])}",
    ]
    if live_mob:
        if live_mob.active_status_effects:
            effect_strs = [
                f"&R{status_effects.EFFECT_DEFS.get(name, {}).get('display_name', name.title())}&x "
                f"({data['duration']} pulse(s) left)"
                for name, data in live_mob.active_status_effects.items()
            ]
            lines.append(f"&WActive Effects:&x {', '.join(effect_strs)}")
        else:
            lines.append("&WActive Effects:&x &Gnone&x")
    lines += [
        _rule(),
        f"&C{'OTHER INFORMATION'.center(62)}&x",
        _rule(),
        f"&WGold:&x {t['gold']}   &WCalculated XP (same-level):&x {leveling.mob_base_experience(t['level'])}   &WRyo:&x {t['ryo_reward']}",
        f"&WSpecial:&x {t['special_function']}",
        f"&WSpeaks:&x {_fmt_list(t['speaks'])}   &WSpeaking:&x {_fmt_list(t['speaking'])}",
        f"&WLoot Items:&x {_fmt_list(t['loot_items'])}",
        f"&WMob Programs:&x {_fmt_programs(t['mob_programs'])}",
        f"&WEnabled:&x {'&Gyes&x' if t.get('enabled', True) else '&Rno&x'}",
    ]
    if t.get("shopkeeper", False):
        stock_names = [OBJECT_TEMPLATES[v]["short_desc"] for v in t.get("shop_items", []) if v in OBJECT_TEMPLATES]
        buys = ", ".join(t.get("shop_buys_categories", [])) or "anything"
        lines.append(f"&WShopkeeper:&x &Gyes&x   &WBuys:&x {buys}")
        lines.append(f"&WStock:&x {_fmt_list(stock_names)}")
    if t.get("gambler", False):
        lines.append("&WGambler:&x &Gyes&x &D(runs chou-han -- see the 'gamble' command)&x")
    if t.get("teacher", ""):
        lines.append(f"&WTeacher:&x &G{t['teacher'].title()}&x &D(players must find a matching teacher to practice a {t['teacher'].title()} skill)&x")
    wandering = "Wander" in t.get("act_flags", []) and "Sentinel" not in t.get("act_flags", [])
    lines.append(f"&WTravel Mode:&x {'&Gwander&x' if wandering else '&Dstay&x'}")
    lines.append(_rule())
    session.send("\n".join(lines))


def cmd_ostat(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send("Usage: ostat <vnum|unique object name or keyword>")
        return
    query = " ".join(args).strip().lower()
    if query.isdigit() and int(query) in OBJECT_TEMPLATES:
        vnum = int(query)
    else:
        matches = []
        for candidate_vnum, candidate in OBJECT_TEMPLATES.items():
            names = [candidate.get("short_desc", ""), candidate.get("long_desc", "")]
            names.extend(candidate.get("keywords", []))
            if any(query == str(name).lower() or query in str(name).lower().split() for name in names):
                matches.append(candidate_vnum)
        if not matches:
            session.send(f"No object prototype matches '{query}'. Use 'ofind {query}' for a broader search.")
            return
        if len(matches) > 1:
            details = ", ".join(f"{v}: {OBJECT_TEMPLATES[v]['short_desc']}" for v in sorted(matches))
            session.send(f"'{query}' is ambiguous. Matching vnums: {details}")
            return
        vnum = matches[0]
    o = OBJECT_TEMPLATES[vnum]

    lines = [
        f"&WObject: [{vnum}] {o['short_desc']}&x",
        _rule(),
        f"&WKeywords:&x {' '.join(o['keywords'])}",
        f"&WShort:&x {o['short_desc']}",
        f"&WLong:&x {o['long_desc']}",
        f"&WDescription:&x {o['description'] or '(none set)'}",
        _rule(),
        f"&WVnum:&x {vnum}   &WItem Type:&x {o['item_type'].title()}   &WLevel:&x {o['level']}",
        f"&WWeight:&x {o['weight']}   &WCost:&x {o['cost']}   &WCondition:&x {o['condition']}%",
        (
            f"&WWeapon Type:&x {data_weapons.display_name(o['weapon_type'])}   "
            f"&WSkill:&x {data_weapons.WEAPON_TYPES.get(o['weapon_type'], {}).get('skill', 'None')}"
            if o.get("weapon_type") else "&WWeapon Type:&x None"
        ),
        (
            f"&WHitroll:&x {o.get('stat_bonuses', {}).get('hitroll', 0):+d}   "
            f"&WDamroll:&x {o.get('stat_bonuses', {}).get('damroll', 0):+d}   "
            f"&WDamage:&x {data_weapons.weapon_damage_bonus(o.get('weapon_type', ''))} "
            f"(from weapon_type '{o.get('weapon_type') or 'none'}')"
            if o.get("wear_loc") == "wielded" else None
        ),
        (
            f"&WScroll Jutsu:&x {data_jutsu.JUTSU[o['scroll_jutsu']]['display_name']}"
            if o.get("scroll_jutsu") else "&WScroll Jutsu:&x &D(not yet inscribed)&x"
        ),
        (
            f"&WSet:&x requires vnums {_fmt_list([str(v) for v in o.get('set_vnums', [])])} "
            f"also worn -- &G+{o.get('set_bonus_percent', 25)}%&x to combat stats when complete"
            if o.get("set_vnums") else "&WSet:&x &D(not part of a set)&x"
        ),
        f"&WItem Programs:&x {_fmt_programs(o.get('item_programs', []))}",
        _rule(),
        (
            f"&WStat Bonuses:&x "
            + (", ".join(f"{k.replace('_', ' ').title()} {v:+d}" for k, v in o.get("stat_bonuses", {}).items())
               or "&D(none)&x")
        ),
        f"&WExtra Flags:&x {_fmt_list(o['extra_flags'])}",
        f"&WWear Flags:&x {_fmt_list(o['wear_flags'])}",
        f"&WValues:&x {' '.join(str(v) for v in o['values'])}",
        f"&WEnabled:&x {'&Gyes&x' if o.get('enabled', True) else '&Rno&x'}",
        _rule(),
    ]
    session.send("\n".join(line for line in lines if line is not None))


def _requested_vnum_range(session, args: List[str], usage: str):
    """Parse an optional inclusive ``<low> <high>`` builder range."""
    if not args:
        return None
    if len(args) != 2 or not all(value.isdigit() for value in args):
        session.send(usage)
        return False
    low, high = map(int, args)
    if low > high:
        low, high = high, low
    return low, high


def cmd_mcreate(session, args: List[str]) -> None:
    """SMAUG FUSS convenience command for creating a mob prototype."""
    if len(args) < 2:
        session.send("Usage: mcreate <vnum> <name...>")
        return
    cmd_mset(session, ["create", *args])


def cmd_ocreate(session, args: List[str]) -> None:
    """SMAUG FUSS convenience command for creating an object prototype."""
    if len(args) < 2:
        session.send("Usage: ocreate <vnum> <name...>")
        return
    cmd_oset(session, ["create", *args])


def cmd_rcreate(session, args: List[str]) -> None:
    """Create, enter, and optionally name a room in one command."""
    if not args or not args[0].isdigit():
        session.send("Usage: rcreate <vnum> [room name...]")
        return
    cmd_rset(session, ["create", args[0]])
    vnum = int(args[0])
    if len(args) > 1 and vnum in world.WORLD.rooms:
        world.WORLD.rooms[vnum].name = " ".join(args[1:])
        _log(session.player.name, "room", vnum, f"name set to '{world.WORLD.rooms[vnum].name}'")


def cmd_minvoke(session, args: List[str]) -> None:
    """Load one mob instance into the current room (or a named room vnum)."""
    if not _require_builder(session):
        return
    if not args or not args[0].isdigit() or len(args) > 2 or (len(args) == 2 and not args[1].isdigit()):
        session.send("Usage: minvoke <mob vnum> [room vnum]")
        return
    vnum = int(args[0])
    room_vnum = int(args[1]) if len(args) == 2 else session.player.room_vnum
    cmd_mset(session, ["spawn", str(vnum), str(room_vnum)])


def cmd_oinvoke(session, args: List[str]) -> None:
    """Load one object instance on the ground in the selected room."""
    if not _require_builder(session):
        return
    if not args or not args[0].isdigit() or len(args) > 2 or (len(args) == 2 and not args[1].isdigit()):
        session.send("Usage: oinvoke <object vnum> [room vnum]")
        return
    vnum = int(args[0])
    room_vnum = int(args[1]) if len(args) == 2 else session.player.room_vnum
    prototype = OBJECT_TEMPLATES.get(vnum)
    room = world.WORLD.get(room_vnum)
    if not prototype:
        session.send(f"No object prototype {vnum} exists.")
        return
    if not room:
        session.send(f"Room {room_vnum} does not exist.")
        return
    room.ground_items.append(prototype["short_desc"])
    _log(session.player.name, "object", vnum, f"invoked in room {room_vnum}")
    session.send(f"{prototype['short_desc']} appears in room {room_vnum}.")


def cmd_mfind(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send("Usage: mfind <name or keyword>")
        return
    query = " ".join(args).lower()
    matches = [
        (vnum, mob) for vnum, mob in sorted(combat.MOB_TEMPLATES.items())
        if query in mob.get("short_desc", "").lower()
        or query in mob.get("long_desc", "").lower()
        or any(query in str(keyword).lower() for keyword in mob.get("keywords", []))
    ]
    session.send("Mobile matches:\n" + ("\n".join(f"  {v}: {m['short_desc']}" for v, m in matches) or "  None"))


def cmd_ofind(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send("Usage: ofind <name or keyword>")
        return
    query = " ".join(args).lower()
    matches = [
        (vnum, obj) for vnum, obj in sorted(OBJECT_TEMPLATES.items())
        if query in obj.get("short_desc", "").lower()
        or query in obj.get("long_desc", "").lower()
        or any(query in str(keyword).lower() for keyword in obj.get("keywords", []))
    ]
    session.send("Object matches:\n" + ("\n".join(f"  {v}: {o['short_desc']}" for v, o in matches) or "  None"))


def cmd_rfind(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send("Usage: rfind <name or description text>")
        return
    query = " ".join(args).lower()
    matches = [
        (vnum, room) for vnum, room in sorted(world.WORLD.rooms.items())
        if query in room.name.lower() or query in room.description.lower()
    ]
    session.send("Room matches:\n" + ("\n".join(f"  {v}: {r.name}" for v, r in matches) or "  None"))


def cmd_mlist(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    requested = _requested_vnum_range(session, args, "Usage: mlist [low_vnum high_vnum]")
    if requested is False:
        return
    rows = sorted(combat.MOB_TEMPLATES.items())
    if requested:
        rows = [(v, value) for v, value in rows if requested[0] <= v <= requested[1]]
    session.send("Mobile prototypes:\n" + ("\n".join(f"  {v}: {m['short_desc']} (level {m['level']})" for v, m in rows) or "  None"))


def cmd_olist(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    requested = _requested_vnum_range(session, args, "Usage: olist [low_vnum high_vnum]")
    if requested is False:
        return
    rows = sorted(OBJECT_TEMPLATES.items())
    if requested:
        rows = [(v, value) for v, value in rows if requested[0] <= v <= requested[1]]
    session.send("Object prototypes:\n" + ("\n".join(f"  {v}: {o['short_desc']} ({o['item_type']})" for v, o in rows) or "  None"))


def cmd_rlist(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    requested = _requested_vnum_range(session, args, "Usage: rlist [low_vnum high_vnum]")
    if requested is False:
        return
    rows = sorted(world.WORLD.rooms.items())
    if requested:
        rows = [(v, value) for v, value in rows if requested[0] <= v <= requested[1]]
    session.send("Rooms:\n" + ("\n".join(f"  {v}: {r.name}" for v, r in rows) or "  None"))


def cmd_rstat(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    vnum = int(args[0]) if args and args[0].isdigit() else session.player.room_vnum
    if vnum not in world.WORLD.rooms:
        session.send(f"Usage: rstat [vnum]  (room {vnum} does not exist)")
        return
    room = world.WORLD.get(vnum)

    lines = [
        f"&WRoom: [{vnum}] {room.name}&x",
        _rule(),
        f"&WDescription:&x {room.description}",
        _rule(),
        f"&WVnum:&x {vnum}   &WSector:&x {room.sector}",
        f"&WExits:&x " + (", ".join(f"{d}->{v}" for d, v in room.exits.items()) or "None"),
        f"&WFlags:&x {_fmt_list(room.flags)}",
        f"&WEnabled:&x {'&Gyes&x' if room.enabled else '&Rno&x'}",
    ]
    if room.apartment:
        lines.append(f"&WApartment:&x &Gyes&x   &WOwner:&x {room.owner or '&D(unclaimed)&x'}")
    lines.append(f"&WRoom Programs:&x {_fmt_programs(room.programs)}")
    lines.append(f"&WBiome:&x {room.biome}")
    lines.append(f"&WPvP Safe Zone:&x {'&Gyes&x' if room.safe else '&Rno (PvP enabled)&x'}")
    lines.append(_rule())
    session.send("\n".join(lines))


# ===========================================================================
# RSET -- room field editor (formerly redit; unchanged behavior/commands)
# ===========================================================================

EXIT_FLAG_NAMES = ["door", "locked", "keyitem", "passcode", "hidden"]

# Per direct user feedback ("shouldn't be able to set anything as a
# room flag, only real flags") -- both of these used to be fully
# freeform, silently accepting a typo or anything else with zero
# validation. Now the single source of truth for what's actually
# recognized; the real mechanical effect of each still lives in its
# own module (noted below), so if a new one is ever wired in there, it
# needs to be added here too or 'rset flags'/'oset extra_flags' will
# refuse to let staff set it.
VALID_ROOM_FLAGS = {
    "CapturePoint",        # territory.py -- makes this room a war/territory control point
    "accelerated_healing",  # regen.py -- faster regen in this room
}
VALID_ITEM_EXTRA_FLAGS = {
    "no_sac",  # commands.py -- protects this item from 'sacrifice'
    "no_take", # commands.py -- protects this item from 'get' -- for cosmetic room decoration (furniture, signs, plants) that's meant to stay put, placed via 'oset load'/spawn points and never picked up
}
VALID_MOB_ACT_FLAGS = {
    "Banker",       # commands.py -- lets a player 'bank'/'bank deposit'/'bank withdraw' at this mob
    "BountyOffice", # commands.py -- lets a player claim a bounty in person at this mob
    "Npc",          # content.py -- base flag every non-player mob carries; no mechanical check yet
    "Sentinel",     # content.py + combat.is_wandering -- a hard override blocking wander behavior, even if Wander is also set
    "Shopkeeper",   # content.py -- the real shop mechanism is a separate `shopkeeper` field (see combat.is_shopkeeper); this flag alone has no mechanical check
    "Garrison",     # content.py -- war/territory defender designation; no mechanical check yet
    "Trap",         # content.py -- war/territory trap designation; no mechanical check yet
    "Wander",       # combat.is_wandering/process_wander -- moves through a random available exit on its own independent timer (2-4 min, randomized per mob); replaces the old travel_mode field entirely
    "Mission",      # missions.py -- marks this mob as eligible for the dynamic C/B/A/S rank-request mission pool (see missions.pick_mission_mob); the mob's own level, weighed against the requesting player's level, determines which rank it can actually be offered for
    "Immortal",     # combat.is_immortal_mob -- per direct request (Section 150): genuinely CANNOT be attacked at all (plain attack or jutsu-based), matching the exact same real "protected and cannot be attacked" refusal already used for shopkeepers/gamblers/teachers -- not just a huge HP pool
}


def cmd_astat(session, args: List[str]) -> None:
    """Shows an area's full stat block -- by name, by a vnum (finds
    whichever area's reserved range contains it), or with no argument,
    the area containing the room you're standing in."""
    if not _require_builder(session):
        return

    query = " ".join(args).strip()
    if not query:
        area = areas.find_area_for_vnum(session.player.room_vnum)
        if not area:
            session.send(f"Room {session.player.room_vnum} isn't within any registered area.")
            return
    elif query.isdigit():
        area = areas.find_area_for_vnum(int(query))
        if not area:
            session.send(f"Vnum {query} isn't within any registered area.")
            return
    else:
        area = areas.find_area(query)
        if not area:
            session.send(f"No area named '{query}' exists. Use 'area list' to see every registered area.")
            return

    size = area.vnum_end - area.vnum_start + 1
    rooms_in_range = [v for v in world.WORLD.rooms if area.vnum_start <= v <= area.vnum_end]
    capture_points = [v for v in rooms_in_range if "CapturePoint" in world.WORLD.get(v).flags]

    lines = [
        f"&WArea: {area.name}&x",
        _rule(),
        f"&WVnum Range:&x {area.vnum_start}-{area.vnum_end}   &WSize:&x {size} reserved vnums",
        f"&WCreator:&x {area.creator}",
        f"&WRooms Built:&x {len(rooms_in_range)} of {size} ({len(rooms_in_range) * 100 // size}%)",
    ]
    income_text = f"&Y{area.income} ryo/tick&x" if area.income else "&D(none set)&x"
    lines.append(f"&WTerritory Income:&x {income_text}")
    if area.income:
        cap_text = ", ".join(str(v) for v in capture_points) if capture_points else "&D(none flagged yet)&x"
        lines.append(f"&WCapture Points:&x {cap_text}")
    reset_message_text = area.reset_message if area.reset_message else "&D(none set)&x"
    lines.append(f"&WReset Message:&x {reset_message_text}")
    lines.append(_rule())
    session.send("\n".join(lines))


def cmd_area(session, args: List[str]) -> None:
    """Builder tool for the area vnum-reservation registry (areas.py).
    'area create <name> [size]' auto-allocates the next free block
    (1000 room vnums by default) and reserves it exclusively for that
    area, so a later 'rset create <vnum>' by anyone else can't
    accidentally collide with it. 'area set <name> income <n>' sets
    the area's per-tick territory income (see territory.py) -- an area
    with income > 0 and at least one room flagged 'CapturePoint' (via
    'rset flags CapturePoint', already fully generic, nothing new
    needed there) becomes real, ownable war/territory content, no
    additional code required. 'area set <name> resetmsg <text|off>'
    sets (or clears) an area-wide atmospheric flavor line, shown
    periodically to any player standing in the area (see programs.
    process_random_triggers) -- 'off' clears it. A specific room's own
    override (set via 'rset resetmsg') always wins over the area's,
    per direct request ("room overrides area"). 'area list' shows
    every reservation. Deliberately room-vnums-only, not mobs/objects
    -- see areas.py's own docstring for the full reasoning."""
    if not _require_builder(session):
        return
    if not args:
        session.send("Usage: area create <name> [size]\n       area set <name> income <n>\n       area set <name> resetmsg <text|off>\n       area list")
        return

    subcommand = args[0].lower()

    if subcommand == "list":
        all_areas = areas.all_areas()
        if not all_areas:
            session.send("No areas have been registered.")
            return
        lines = ["&WRegistered areas:&x"]
        for entry in sorted(all_areas.values(), key=lambda e: e["vnum_start"]):
            income = entry.get("income", 0)
            income_text = f", &Y{income} ryo/tick&x territory income" if income else ""
            lines.append(
                f"  {entry['name']} ({entry['vnum_start']}-{entry['vnum_end']}) "
                f"-- created by {entry['creator']}{income_text}"
            )
        session.send("\n".join(lines))
        return

    if subcommand == "create":
        if len(args) < 2:
            session.send("Usage: area create <name> [size]")
            return
        size = areas.DEFAULT_BLOCK_SIZE
        name_parts = args[1:]
        if name_parts[-1].isdigit():
            size = int(name_parts[-1])
            name_parts = name_parts[:-1]
        if not name_parts:
            session.send("Usage: area create <name> [size]")
            return
        if size <= 0:
            session.send("Size must be a positive number of vnums.")
            return
        name = " ".join(name_parts)
        try:
            new_area = areas.create_area(name, session.player.name, size)
        except ValueError as e:
            session.send(str(e))
            return
        session.send(
            f"Area '{new_area.name}' created, reserving vnums "
            f"{new_area.vnum_start}-{new_area.vnum_end} ({size} rooms) exclusively for it."
        )
        return

    if subcommand == "set":
        usage = "Usage: area set <name> income <n>\n       area set <name> resetmsg <text|off>"
        field_index = next((i for i, a in enumerate(args) if a.lower() in ("income", "resetmsg")), None)
        if field_index is None or field_index == 0:
            session.send(usage)
            return
        field = args[field_index].lower()
        name = " ".join(args[1:field_index])
        value_words = args[field_index + 1:]
        if not name:
            session.send(usage)
            return

        if field == "income":
            if len(value_words) != 1 or not value_words[0].lstrip("-").isdigit():
                session.send("Usage: area set <name> income <n>")
                return
            income = int(value_words[0])
            if income < 0:
                session.send("Income can't be negative.")
                return
            updated = areas.set_income(name, income)
            if updated is None:
                session.send(f"No area named '{name}' exists.")
                return
            session.send(f"Area '{updated.name}' territory income set to {income} ryo/tick.")
            return

        # field == "resetmsg"
        if not value_words:
            session.send("Usage: area set <name> resetmsg <text|off>")
            return
        message_text = " ".join(value_words)
        if message_text.lower() == "off":
            updated = areas.set_reset_message(name, None)
            if updated is None:
                session.send(f"No area named '{name}' exists.")
                return
            session.send(f"Area '{updated.name}' reset message cleared.")
            return
        updated = areas.set_reset_message(name, message_text)
        if updated is None:
            session.send(f"No area named '{name}' exists.")
            return
        session.send(f"Area '{updated.name}' reset message set: {message_text}")
        return

    session.send("Usage: area create <name> [size]\n       area set <name> income <n>\n       area set <name> resetmsg <text|off>\n       area list")


def cmd_aset(session, args: List[str]) -> None:
    """'aset income <n>' / 'aset resetmsg <text|off>' -- shorthand for
    'area set <name> income <n>' / 'area set <name> resetmsg
    <text|off>', per direct request ("i want an aset command as
    shorthand for area set"). Per a direct follow-up ("instead of
    having to directly reference the area i want it to look at what
    area i am in an assume i mean the area im currently inside"), the
    area name is no longer required at all: if the first argument is
    itself a known field keyword (income/resetmsg), the area name was
    omitted, so this resolves areas.find_area_for_vnum(session.player.
    room_vnum) automatically and inserts it -- the exact same "no
    argument means wherever I'm standing" convention 'astat' already
    uses. An explicit area name is still accepted and still works
    (e.g. 'aset leaf income 25' from anywhere), for editing an area
    other than the one currently standing in. Dispatches straight into
    cmd_area's own existing "set" handling either way -- not a
    separate implementation, so it can never drift out of sync with
    'area set' (same validation, same error messages, same
    everything) -- except the bare, no-argument case and the "not
    standing in any registered area" case, both of which show their
    own usage/error text here rather than cmd_area's generic ones, so
    what's displayed matches what was actually typed. Deliberately
    doesn't shorthand 'area create'/'area list' -- the request was
    specifically for 'area set'."""
    if not _require_builder(session):
        return
    if not args:
        session.send("Usage: aset <name> income <n>\n       aset <name> resetmsg <text|off>\n       aset income <n>  (uses the area you're currently standing in)\n       aset resetmsg <text|off>  (uses the area you're currently standing in)")
        return

    if args[0].lower() in ("income", "resetmsg"):
        area = areas.find_area_for_vnum(session.player.room_vnum)
        if not area:
            session.send(f"Room {session.player.room_vnum} isn't within any registered area -- use 'aset <name> ...' to name one explicitly.")
            return
        cmd_area(session, ["set", area.name] + list(args))
        return

    cmd_area(session, ["set"] + list(args))


def cmd_rset(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send(
            "Usage: rset create|goto|name|desc|sector|exit|bexit|bunlink|flags|apartment|biome|resetmsg|safe|exitflag|show ...\n"
            "rset always acts on the room you're standing in. 'create'/'goto' teleport you to the target room first, so every other subcommand naturally follows.\n"
            "'rset name' or 'rset desc' with no text opens an interactive editor.\n"
            "'rset apartment on|off' marks this room as a purchasable apartment shell "
            "(see 'buy apartment' and 'recall').\n"
            f"'rset biome <type>' tags this room for elemental jutsu affinity. Valid: {', '.join(biomes.BIOME_TYPES)}.\n"
            "'rset resetmsg <text|off>' sets this room's own atmospheric flavor line, shown periodically -- overrides its area's own reset message (see 'area set <name> resetmsg') if that area has one too.\n"
            "'rset safe on|off' marks this room as a PvP-safe zone (blocks attacking other players here).\n"
            f"'rset exitflag <direction> <flag> [value]' -- flags: {', '.join(EXIT_FLAG_NAMES)}. "
            "door/locked/hidden take on|off; keyitem/passcode take the required item name/code "
            "(or 'off' to clear). A single exit can carry multiple flags at once."
        )
        return

    sub, rest = args[0].lower(), args[1:]

    if sub == "create":
        if not rest or not rest[0].isdigit():
            session.send("Usage: rset create <vnum>")
            return
        vnum = int(rest[0])
        if vnum in world.WORLD.rooms:
            session.send(f"Room {vnum} already exists. Use 'rset goto {vnum}' to edit it.")
            return
        world.WORLD.add_room(world.Room(vnum, "An Unfinished Room", "You see nothing special."))
        import commands
        session.player.room_vnum = vnum
        _log(session.player.name, "room", vnum, "created")
        area = areas.find_area_for_vnum(vnum)
        if area is None:
            session.send(
                f"You vanish in a puff of smoke. Room {vnum} created and now being edited. "
                f"&D(Note: {vnum} isn't within any registered area -- see 'area list'/'area create'.)&x"
            )
        elif area.creator not in (session.player.name, "system"):
            session.send(
                f"You vanish in a puff of smoke. Room {vnum} created and now being edited. "
                f"&D(Note: {vnum} is within '{area.name}', reserved by {area.creator}.)&x"
            )
        else:
            session.send(f"You vanish in a puff of smoke. Room {vnum} created and now being edited.")
        commands.cmd_look(session, [])
        commands._fire_enter_triggers(session)
        return

    if sub == "delete":
        if not rest or not rest[0].isdigit():
            session.send("Usage: rset delete <vnum>")
            return
        vnum = int(rest[0])
        if vnum not in world.WORLD.rooms:
            session.send(f"No room {vnum} exists.")
            return

        # Remove any real exit FROM another room that currently
        # leads INTO the room being deleted, so nobody can ever walk
        # into a room that no longer exists.
        exit_count = 0
        for other_room in world.WORLD.rooms.values():
            for direction, target_vnum in list(other_room.exits.items()):
                if target_vnum == vnum:
                    del other_room.exits[direction]
                    exit_count += 1

        # Remove any real spawn point(s) still targeting this room.
        spawn_point_count = 0
        for point in spawn_points.list_spawn_points(room_vnum=vnum):
            spawn_points.remove_spawn_point(point["kind"], point["vnum"], vnum)
            spawn_point_count += 1

        # If a builder is currently standing HERE, move them to
        # safety immediately (per direct confirmation) -- the same
        # real fallback already used at login for a missing room.
        import commands
        from data_villages import VILLAGES
        stranded_count = 0
        for other_session in session.active_sessions():
            if other_session.player and other_session.player.room_vnum == vnum:
                other_session.player.room_vnum = VILLAGES[other_session.player.village]["starting_room_vnum"]
                other_session.send("&Y(This room no longer exists -- you've been returned to your village.)&x")
                stranded_count += 1

        del world.WORLD.rooms[vnum]
        _log(session.player.name, "room", vnum, "deleted")
        session.send(
            f"Room {vnum} permanently deleted -- {exit_count} exit(s) leading to it, "
            f"{spawn_point_count} spawn point(s), and {stranded_count} stranded player(s) resolved."
        )
        return

    if sub == "goto":
        if not rest or not rest[0].isdigit() or int(rest[0]) not in world.WORLD.rooms:
            session.send("Usage: rset goto <existing vnum>")
            return
        import commands
        session.player.room_vnum = int(rest[0])
        session.send(f"You vanish in a puff of smoke. Now editing room {session.player.room_vnum}.")
        commands.cmd_look(session, [])
        commands._fire_enter_triggers(session)
        return

    room = world.WORLD.get(session.player.room_vnum)

    if sub == "name":
        if not rest:
            def _set_name(new_name, _room=room, _session=session):
                new_name = new_name.strip()
                if not new_name:
                    _session.send("Name unchanged.")
                    return
                old = _room.name
                _room.name = new_name
                _log(_session.player.name, "room", _room.vnum, f'name "{old}" -> "{new_name}"')
                _session.send(f"Room name set to '{new_name}'.")
            session.enter_single_line(
                f"Enter new name for room {room.vnum} (current: '{room.name}'):", _set_name
            )
            return
        old = room.name
        room.name = " ".join(rest)
        _log(session.player.name, "room", room.vnum, f'name "{old}" -> "{room.name}"')
        session.send("Room name set.")
        return

    if sub == "desc":
        if not rest:
            def _set_desc(new_text, _room=room, _session=session):
                _room.description = new_text or _room.description
                _log(_session.player.name, "room", _room.vnum, "description updated")
                _session.send("Room description updated.")
            session.enter_editor(
                _set_desc, initial_text=room.description,
                header=f"Editing description for room {room.vnum} ({room.name}).",
            )
            return
        room.description = " ".join(rest)
        _log(session.player.name, "room", room.vnum, "description updated")
        session.send("Room description set.")
        return

    if sub == "sector":
        if not rest:
            session.send("Usage: rset sector <type>")
            return
        room.sector = rest[0].lower()
        _log(session.player.name, "room", room.vnum, f"sector set to {room.sector}")
        session.send(f"Sector set to {room.sector}.")
        return

    if sub == "exit":
        if len(rest) != 2 or not rest[1].isdigit():
            session.send("Usage: rset exit <direction> <vnum>")
            return
        direction = world.normalize_direction(rest[0])
        if not direction:
            session.send("That isn't a valid direction.")
            return
        dest = int(rest[1])
        if dest not in world.WORLD.rooms:
            session.send(f"Room {dest} does not exist.")
            return
        room.exits[direction] = dest
        _log(session.player.name, "room", room.vnum, f"one-way exit {direction} -> {dest}")
        session.send(f"One-way exit {direction} -> {dest} created.")
        return

    if sub == "bexit":
        _do_bexit(session, room, rest)
        return

    if sub == "bunlink":
        _do_bunlink(session, room, rest)
        return

    if sub == "addprogram":
        if len(rest) < 2:
            session.send(f"Usage: rset addprogram <trigger> <action> <args...>\nTriggers: {', '.join(sorted(programs.ROOM_TRIGGERS))}\nActions: {', '.join(sorted(programs.ACTIONS))}")
            return
        trigger, action = rest[0].lower(), rest[1].lower()
        prog_args = " ".join(rest[2:])
        errors = programs.validate_program(trigger, action, prog_args, programs.ROOM_TRIGGERS)
        if errors:
            session.send("\n".join(errors))
            return
        room.programs.append({"trigger": trigger, "action": action, "args": prog_args})
        _log(session.player.name, "room", room.vnum, f"program added: {trigger} -> {action} {prog_args}")
        session.send(f"Program added to room {room.vnum}: on {trigger}, {action} \"{prog_args}\".")
        return

    if sub == "removeprogram":
        if len(rest) != 1 or not rest[0].isdigit():
            session.send("Usage: rset removeprogram <program index -- see rstat>")
            return
        index = int(rest[0])
        if not (0 <= index < len(room.programs)):
            session.send(f"Room {room.vnum} has no program at index {index}. Use 'rstat {room.vnum}' to see them.")
            return
        room.programs.pop(index)
        _log(session.player.name, "room", room.vnum, f"program removed at index {index}")
        session.send(f"Removed program {index} from room {room.vnum}.")
        return

    if sub == "safe":
        if not rest or rest[0].lower() not in ("on", "off"):
            session.send("Usage: rset safe on|off  (marks this room as a PvP-safe zone)")
            return
        room.safe = rest[0].lower() == "on"
        _log(session.player.name, "room", room.vnum, f"safe set to {room.safe}")
        session.send(f"Room {room.vnum} is now {'a PvP-safe zone' if room.safe else 'PvP-enabled'}.")
        return

    if sub == "exitflag":
        if len(rest) < 2:
            session.send(
                f"Usage: rset exitflag <direction> <flag> [value]\n"
                f"Flags: {', '.join(EXIT_FLAG_NAMES)}\n"
                "door/locked/hidden take on|off; keyitem/passcode take the required "
                "item name/code (or 'off'/'none' to clear)."
            )
            return
        direction, flag = rest[0].lower(), rest[1].lower()
        if direction not in room.exits:
            session.send(f"There is no exit to the {direction} to flag.")
            return
        if flag not in EXIT_FLAG_NAMES:
            session.send(f"'{flag}' isn't a valid exit flag. Valid: {', '.join(EXIT_FLAG_NAMES)}")
            return

        flags_here = room.exit_flags.setdefault(direction, [])

        if flag in ("door", "locked", "hidden"):
            if len(rest) < 3 or rest[2].lower() not in ("on", "off"):
                session.send(f"Usage: rset exitflag {direction} {flag} on|off")
                return
            turn_on = rest[2].lower() == "on"
            if turn_on and flag not in flags_here:
                flags_here.append(flag)
                if flag == "door":
                    room.exit_door_open[direction] = False  # starts closed
            elif not turn_on and flag in flags_here:
                flags_here.remove(flag)
            _log(session.player.name, "room", room.vnum, f"exit {direction} {flag} set to {turn_on}")
            session.send(f"Exit {direction}: {flag} is now {'on' if turn_on else 'off'}.")
            return

        # keyitem / passcode -- the value itself is the required item
        # name or code; "off"/"none" clears it and removes the flag.
        value = " ".join(rest[2:]).strip()
        if not value or value.lower() in ("off", "none"):
            if flag in flags_here:
                flags_here.remove(flag)
            if flag == "keyitem":
                room.exit_key_item.pop(direction, None)
            else:
                room.exit_passcode.pop(direction, None)
            _log(session.player.name, "room", room.vnum, f"exit {direction} {flag} cleared")
            session.send(f"Exit {direction}: {flag} requirement cleared.")
            return

        if flag not in flags_here:
            flags_here.append(flag)
        if flag == "keyitem":
            room.exit_key_item[direction] = value
        else:
            room.exit_passcode[direction] = value
        _log(session.player.name, "room", room.vnum, f"exit {direction} {flag} set to '{value}'")
        session.send(f"Exit {direction}: {flag} requirement set to '{value}'.")
        return

    if sub == "biome":
        if not rest or rest[0].lower() not in biomes.BIOME_TYPES:
            session.send(
                f"Usage: rset biome <type>\nValid: {', '.join(biomes.BIOME_TYPES)}"
            )
            return
        room.biome = rest[0].lower()
        _log(session.player.name, "room", room.vnum, f"biome set to {room.biome}")
        session.send(f"Room {room.vnum}'s biome is now {room.biome}.")
        return

    if sub == "resetmsg":
        if not rest:
            session.send("Usage: rset resetmsg <text|off>")
            return
        message_text = " ".join(rest)
        if message_text.lower() == "off":
            room.reset_message = None
            _log(session.player.name, "room", room.vnum, "reset message cleared")
            session.send(f"Room {room.vnum}'s reset message override cleared (falls back to its area's own, if any).")
            return
        room.reset_message = message_text
        _log(session.player.name, "room", room.vnum, f"reset message set to '{message_text}'")
        session.send(f"Room {room.vnum}'s reset message override set: {message_text}")
        return

    if sub == "apartment":
        if not rest or rest[0].lower() not in ("on", "off"):
            session.send("Usage: rset apartment on|off  (marks this room as a purchasable apartment shell)")
            return
        room.apartment = rest[0].lower() == "on"
        if not room.apartment:
            room.owner = None  # un-flagging a room also releases any claim on it
        _log(session.player.name, "room", room.vnum, f"apartment set to {room.apartment}")
        session.send(f"Room {room.vnum} apartment flag is now {'on' if room.apartment else 'off'}.")
        return

    if sub == "flags":
        if not rest:
            session.send(f"Usage: rset flags <flagname>  (toggles the flag on this room)\nValid: {', '.join(sorted(VALID_ROOM_FLAGS))}")
            return
        typed = rest[0]
        canonical = next((f for f in VALID_ROOM_FLAGS if f.lower() == typed.lower()), None)
        if canonical is None:
            session.send(f"'{typed}' isn't a recognized room flag. Valid: {', '.join(sorted(VALID_ROOM_FLAGS))}")
            return
        if canonical in room.flags:
            room.flags.remove(canonical)
            action = "removed from"
        else:
            room.flags.append(canonical)
            action = "added to"
        _log(session.player.name, "room", room.vnum, f"flag '{canonical}' {action} room")
        session.send(f"Flag '{canonical}' {action} room {room.vnum}.")
        return

    if sub == "show":
        cmd_rstat(session, [str(room.vnum)])
        return

    session.send("Unknown rset subcommand.")


def _do_bexit(session, room, rest: List[str], force: bool = False) -> None:
    force = "force" in rest
    rest = [a for a in rest if a != "force"]

    if len(rest) == 2:
        direction_raw, dest_raw = rest
        src_vnum = room.vnum
    elif len(rest) == 3:
        src_raw, direction_raw, dest_raw = rest
        if not src_raw.isdigit():
            session.send("Usage: rset bexit <direction> <vnum>  OR  rset bexit <src vnum> <direction> <dest vnum>")
            return
        src_vnum = int(src_raw)
    else:
        session.send("Usage: rset bexit <direction> <vnum>  OR  rset bexit <src vnum> <direction> <dest vnum>")
        return

    direction = world.normalize_direction(direction_raw)
    if not direction or not dest_raw.isdigit():
        session.send("Invalid direction or destination vnum.")
        return
    dest_vnum = int(dest_raw)

    if src_vnum not in world.WORLD.rooms:
        session.send(f"Room {src_vnum} doesn't exist -- the source room must already exist.")
        return

    dest_exists = dest_vnum in world.WORLD.rooms
    src_room = world.WORLD.get(src_vnum)
    dest_room = world.WORLD.get(dest_vnum) if dest_exists else None
    reverse = world.OPPOSITE_DIRECTION[direction]

    conflict = None
    if direction in src_room.exits and src_room.exits[direction] != dest_vnum:
        conflict = f"Room {src_vnum} already has a {direction} exit leading to room {src_room.exits[direction]}."
    elif dest_room and reverse in dest_room.exits and dest_room.exits[reverse] != src_vnum:
        conflict = f"Room {dest_vnum} already has a {reverse} exit leading to room {dest_room.exits[reverse]}."

    if conflict and not force:
        session.send(conflict + "\nBidirectional exit not created. Add 'force' to override.")
        return
    if conflict and force and not can_build(session):
        session.send("You do not have permission to force this change.")
        return

    auto_created = False
    if not dest_exists:
        world.WORLD.add_room(world.Room(dest_vnum, "An Unfinished Room", "You see nothing special."))
        _log(session.player.name, "room", dest_vnum, "auto-created via bexit")
        auto_created = True

    world.WORLD.link(src_vnum, direction, dest_vnum)
    _log(session.player.name, "room", f"{src_vnum}/{dest_vnum}",
         f"bidirectional exit {direction}/{reverse}" + (" (forced)" if conflict else ""))
    auto_created_note = f"\n(Room {dest_vnum} didn't exist yet -- created automatically as \"An Unfinished Room\".)" if auto_created else ""
    session.send(f"Room {src_vnum} {direction} -> {dest_vnum}\nRoom {dest_vnum} {reverse} -> {src_vnum}{auto_created_note}")


def _do_bunlink(session, room, rest: List[str]) -> None:
    if len(rest) != 1:
        session.send("Usage: rset bunlink <direction>")
        return
    direction = world.normalize_direction(rest[0])
    if not direction or direction not in room.exits:
        session.send("There is no such exit to remove.")
        return

    dest_vnum = room.exits.pop(direction)
    reverse = world.OPPOSITE_DIRECTION[direction]
    dest_room = world.WORLD.get(dest_vnum)
    if dest_room and dest_room.exits.get(reverse) == room.vnum:
        del dest_room.exits[reverse]
        session.send(f"Removed exits: room {room.vnum} {direction} <-> room {dest_vnum} {reverse}.")
    else:
        session.send("The reverse exit no longer points back to this room. Only the local exit was removed.")
    _log(session.player.name, "room", room.vnum, f"bunlink {direction}")


# ===========================================================================
# MSET -- mobile prototype field editor
# ===========================================================================

MOB_STRING_FIELDS = {"short_desc", "long_desc", "description", "sex",
                      "position", "default_position", "hit_dice", "damage_dice", "special_function",
                      "teacher", "primary_class"}
MOB_INT_FIELDS = {"level", "alignment", "mana", "move", "armor_class", "hit_roll",
                   "damage_roll", "attacks", "gold", "ryo_reward"}
MOB_LIST_FIELDS = {"keywords", "act_flags", "affected_by", "attack_verbs", "defenses",
                    "resistant", "immune", "susceptible", "body_parts", "speaks",
                    "speaking", "loot_items", "shop_buys_categories"}
MOB_ATTR_FIELDS = {"str", "int", "wis", "dex", "con", "cha", "luck"}
MOB_BOOL_FIELDS = {"shopkeeper", "gambler", "respawns", "enabled"}


def _field_list(title: str, fields, aliases=None) -> str:
    """Wrap an editor field category for ordinary 80-column MUD clients."""
    import textwrap

    aliases = aliases or {}
    names = [f"{name} ({aliases[name]})" if name in aliases else name
             for name in sorted(fields)]
    return f"&W{title}&x\n" + textwrap.fill(
        ", ".join(names), width=76, initial_indent="  ", subsequent_indent="  "
    )


def _mset_field_reference(player: bool = False) -> str:
    if player:
        return "\n".join([
            "&CPLAYER FIELDS&x  mset <player> <field> <value>",
            _field_list("Text", PLAYER_STRING_FIELDS, {"village_rank": "rank"}),
            _field_list("Numbers", PLAYER_INT_FIELDS),
            _field_list("On / off", PLAYER_BOOL_FIELDS),
            "&DPlayer edits require administrator access.&x",
            "&DSee 'mset fields mob' for mob prototypes.&x",
        ])
    return "\n".join([
        "&CMOB FIELDS&x  mset <vnum> <field> <value>",
        _field_list("Text", MOB_STRING_FIELDS, {
            "short_desc": "short", "long_desc": "long", "primary_class": "class",
        }),
        _field_list("Numbers", MOB_INT_FIELDS),
        _field_list("On / off", MOB_BOOL_FIELDS),
        _field_list("Lists (add a value; prefix with - to remove)", MOB_LIST_FIELDS,
                    {"act_flags": "act"}),
        _field_list("Attributes (numbers)", MOB_ATTR_FIELDS),
        "&DExample: mset 9001 class ninjutsu  |  mset 9001 act Wander&x",
        "&DUse 'mset <vnum> <field>' for its current value and valid options.&x",
        "&DShop stock: mset additem <mob vnum> <object vnum>. XP comes from mob level.&x",
        "&DUse 'mset fields player' for player fields.&x",
    ])


PLAYER_STRING_FIELDS = {"village", "primary_class", "clan", "village_rank", "position", "prompt_string"}
PLAYER_INT_FIELDS = {
    "level", "experience", "ryo", "health", "maximum_health", "chakra", "maximum_chakra",
    "stamina", "maximum_stamina", "strength", "wisdom", "constitution", "intelligence",
    "dexterity", "luck", "perception", "willpower", "chakra_control",
    "training_points", "practice_points", "mission_points", "age",
    "player_kills", "player_deaths", "room_vnum",
}
PLAYER_BOOL_FIELDS = {"color_enabled", "auto_loot_ryo", "auto_loot_gear", "auto_sac_corpse"}


def _find_target_player(name: str):
    """Returns (player, live_session_or_None). Prefers an online session
    (so the edit reflects immediately in their live game) and falls back
    to loading the saved file for an offline player."""
    import session as session_module

    name_lower = name.lower()
    for s in session_module.ACTIVE_SESSIONS:
        if s.player and s.player.name.lower() == name_lower:
            return s.player, s
    offline = storage.load_player(name)
    if offline:
        return offline, None
    return None, None


def cmd_silence(session, args: List[str]) -> None:
    """Silences a player for a set number of hours -- blocked from
    'ooc', village chat, and 'say' entirely for the duration (see the
    checks in cmd_ooc/cmd_village_chat/cmd_say). Confirmed design:
    ALL THREE, not just the public channels. Works on an offline
    target too -- the punishment is checked (and, if expired,
    auto-cleared) the moment they next try to use one of those
    commands, whether that's right now or after logging back in
    later."""
    if not _require_admin(session):
        return
    if len(args) < 2 or not args[-1].replace(".", "", 1).isdigit():
        session.send("Usage: silence <player name> <hours>")
        return
    hours = float(args[-1])
    target_name = " ".join(args[:-1])
    target, live_session = _find_target_player(target_name)
    if not target:
        session.send(f"No player named '{target_name}' is online or has a saved character.")
        return
    target.silenced_until = time.time() + hours * 3600
    session.send(f"You silence {target.name} for {hours} hour(s).")
    if live_session:
        live_session.send(f"&D(You have been silenced for {hours} hour(s) by staff.)&x")
    else:
        storage.save_player(target)


def cmd_unsilence(session, args: List[str]) -> None:
    """Lifts an active silence early -- the counterpart to cmd_silence."""
    if not _require_admin(session):
        return
    if not args:
        session.send("Usage: unsilence <player name>")
        return
    target_name = " ".join(args)
    target, live_session = _find_target_player(target_name)
    if not target:
        session.send(f"No player named '{target_name}' is online or has a saved character.")
        return
    if not target.silenced_until:
        session.send(f"{target.name} isn't silenced.")
        return
    target.silenced_until = 0.0
    session.send(f"You lift {target.name}'s silence.")
    if live_session:
        live_session.send("&D(Your silence has been lifted by staff.)&x")
    else:
        storage.save_player(target)


def cmd_levelup(session, args: List[str]) -> None:
    """Levels a player up exactly ONE level, per direct request
    ("add an immortal command to level upo a character 1 level at a
    time that is outside of mset...this is a reward but also to
    level a character narutrally so thye can train stats between
    level ups" -> confirmed: Administrator and above only, always
    requires a named target, never applies to the caller's own
    character).

    Genuinely routes through leveling.grant_experience() -- the exact
    same function real XP gain from combat/missions/jobs uses -- by
    granting precisely the XP gap needed to cross into the next
    level, rather than directly incrementing player.level. This
    means every real consequence of a genuine level-up happens
    correctly: max HP/chakra/stamina increase, a fresh full heal,
    new training points (for raising attributes) and practice points
    (for 'prac'), any jutsu that unlocks at the new level, and the
    same save-immediately-after behavior a real level-up already
    has. Confirmed design: this is meant to feel like the player
    actually earned the level (so they can go train stats/practice
    skills naturally with it), not just have a bare number changed.
    Works on an offline target too, matching silence/jail's own
    established pattern."""
    if not _require_admin(session):
        return
    if not args:
        session.send("Usage: levelup <player name>")
        return
    target_name = " ".join(args)
    target, live_session = _find_target_player(target_name)
    if not target:
        session.send(f"No player named '{target_name}' is online or has a saved character.")
        return

    import leveling
    if target.level >= leveling.MAX_LEVEL:
        session.send(f"{target.name} is already at the maximum level ({leveling.MAX_LEVEL}).")
        return

    xp_needed = leveling.xp_for_next_level(target.level) - target.experience
    level_before = target.level
    lines = leveling.grant_experience(target, xp_needed)

    session.send(f"You level up {target.name} to level {target.level}.")
    _log(session.player.name, "player", 0, f"leveled up {target.name} from {level_before} to {target.level}")
    if live_session:
        for line in lines:
            live_session.send(line)
        live_session.send_prompt()
    # grant_experience already saves internally on every level-up, including
    # for an offline target -- no separate explicit save needed here.


def cmd_jail(session, args: List[str]) -> None:
    """Jails a player for a set number of hours -- teleported to a
    dedicated jail cell (jail.py) with no exits, and blocked from
    leaving it via ordinary movement for the duration (see the check
    in commands.cmd_move). Confirmed design: automatic release once
    the timer is up, sent to their home village's own starting room,
    not back to wherever they were. Works on an offline target too --
    they're teleported the moment they NEXT log in and the jail is
    checked, not while genuinely offline (there's no session to move
    at that point)."""
    if not _require_admin(session):
        return
    if len(args) < 2 or not args[-1].replace(".", "", 1).isdigit():
        session.send("Usage: jail <player name> <hours>")
        return
    hours = float(args[-1])
    target_name = " ".join(args[:-1])
    target, live_session = _find_target_player(target_name)
    if not target:
        session.send(f"No player named '{target_name}' is online or has a saved character.")
        return
    import jail as jail_module
    target.jailed_until = time.time() + hours * 3600
    session.send(f"You jail {target.name} for {hours} hour(s).")
    if live_session:
        live_session.broadcast_room(f"{target.name} vanishes, dragged off to a jail cell!", exclude_self=True)
        target.room_vnum = jail_module.JAIL_CELL_VNUM
        live_session.send(f"&D(You have been jailed for {hours} hour(s) by staff.)&x")
    else:
        storage.save_player(target)


def cmd_unjail(session, args: List[str]) -> None:
    """Releases a jailed player early -- the counterpart to cmd_jail.
    Uses jail.release() so an early release behaves identically to a
    genuine timer expiry (sent to their home village's own starting
    room either way)."""
    if not _require_admin(session):
        return
    if not args:
        session.send("Usage: unjail <player name>")
        return
    target_name = " ".join(args)
    target, live_session = _find_target_player(target_name)
    if not target:
        session.send(f"No player named '{target_name}' is online or has a saved character.")
        return
    if not target.jailed_until:
        session.send(f"{target.name} isn't jailed.")
        return
    import jail as jail_module
    jail_module.release(target)
    session.send(f"You release {target.name} from jail.")
    if live_session:
        live_session.send("&D(You have been released from jail by staff.)&x")
    else:
        storage.save_player(target)


def _mset_player(session, target_name: str, field: str, value_args: List[str]) -> None:
    if not _require_admin(session):
        return
    target, live_session = _find_target_player(target_name)
    if not target:
        session.send(f"No player named '{target_name}' is online or has a saved character.")
        return
    if not field or not value_args:
        session.send("Usage: mset <player name> <field> <value...>")
        return
    value_text = " ".join(value_args)
    if field == "rank":
        field = "village_rank"  # shorter alias for the same field

    if field in PLAYER_STRING_FIELDS:
        if field == "village" and value_text.lower() not in world_villages():
            session.send(f"'{value_text}' isn't a known village. Valid: {', '.join(sorted(world_villages()))}")
            return
        if field == "primary_class" and value_text.lower() not in world_classes():
            session.send(f"'{value_text}' isn't a known class. Valid: {', '.join(sorted(world_classes()))}")
            return
        if field == "clan" and value_text.lower() not in data_clans.CLANS:
            session.send(f"'{value_text}' isn't a known clan. Valid: {', '.join(sorted(data_clans.CLANS.keys()))}")
            return
        if field == "position" and value_text.lower() not in ("standing", "resting", "sleeping"):
            session.send("Position must be one of: standing, resting, sleeping.")
            return
        if field == "position":
            value_text = value_text.lower()
        if field == "village_rank":
            import kage
            if value_text.lower() not in kage.RANK_ORDER:
                session.send(f"'{value_text}' isn't a known rank. Valid: {', '.join(kage.RANK_ORDER)}")
                return
            value_text = value_text.lower()
        setattr(target, field, value_text.lower() if field in ("village", "primary_class", "clan") else value_text)
        _finish_player_edit(session, target, live_session, field, value_text)
        return

    if field in PLAYER_INT_FIELDS:
        if not value_text.lstrip("-").isdigit():
            session.send(f"{field} must be a number.")
            return
        new_value = int(value_text)
        setattr(target, field, new_value)
        # Setting a current resource (health/chakra/stamina) above its
        # current max would leave an inconsistent character -- bump the
        # max up to match instead of silently allowing current > max.
        current_to_max = {"health": "maximum_health", "chakra": "maximum_chakra", "stamina": "maximum_stamina"}
        bumped_note = ""
        if field in current_to_max:
            max_field = current_to_max[field]
            if new_value > getattr(target, max_field):
                setattr(target, max_field, new_value)
                bumped_note = f" ({max_field} raised to {new_value} to match)"
        _finish_player_edit(session, target, live_session, field, value_text + bumped_note)
        return

    if field in PLAYER_BOOL_FIELDS:
        if value_text.lower() not in ("on", "off", "true", "false"):
            session.send(f"{field} must be on/off.")
            return
        setattr(target, field, value_text.lower() in ("on", "true"))
        _finish_player_edit(session, target, live_session, field, value_text)
        return

    session.send(
        f"Unknown field '{field}'.\n"
        f"String fields: {', '.join(sorted(PLAYER_STRING_FIELDS))}\n"
        f"Number fields: {', '.join(sorted(PLAYER_INT_FIELDS))}\n"
        f"On/off fields: {', '.join(sorted(PLAYER_BOOL_FIELDS))}"
    )


def _finish_player_edit(session, target, live_session, field: str, value_text) -> None:
    storage.save_player(target)
    _log(session.player.name, "player", target.name, f"{field} set to '{value_text}'")
    session.send(f"{target.name}'s {field} set to {value_text}.")
    if live_session:
        live_session.send(f"&D[Your {field} was changed by staff.]&x")


def world_villages():
    import data_villages
    return data_villages.VILLAGES.keys()


def world_classes():
    import data_classes
    return data_classes.CLASSES.keys()


def _mob_field_hint(field: str, t: dict, display: Optional[str] = None) -> Optional[str]:
    """Builds a field-specific hint for 'mset <vnum> <field>' with no
    value given. Returns None if `field` isn't a recognized mob field
    at all, so the caller can fall through to the normal "unknown
    field" refusal. `display` is the word the player actually typed
    (e.g. "short" for the short_desc field, an alias) -- shown in the
    hint text instead of the internal storage key, defaulting to
    `field` itself for every field with no separate alias."""
    display = display or field
    if field in MOB_BOOL_FIELDS:
        current = t.get(field, False)
        return f"'{display}' is on/off. Current: {'on' if current else 'off'}.\nUsage: mset <vnum> {display} on|off"
    if field in MOB_ATTR_FIELDS:
        return f"'{display}' is a number (attribute). Current: {t['attributes'].get(field, 0)}.\nUsage: mset <vnum> {display} <number>"
    if field in MOB_INT_FIELDS:
        return f"'{display}' is a number. Current: {t.get(field, 0)}.\nUsage: mset <vnum> {display} <number>"
    if field == "shop_buys_categories":
        current = t.get(field, [])
        return (
            f"'{display}' accepts item categories: {', '.join(sorted(item_types.BASE_SELL_PRICE.keys()))}. "
            f"Current: {', '.join(current) if current else '(none -- buys anything)'}\n"
            f"Usage: mset <vnum> {display} <category>   (or -<category> to remove one)"
        )
    if field in ("hit_dice", "damage_dice"):
        return f"'{display}' expects dice notation, e.g. '2d6+4'. Current: {t.get(field, '')}.\nUsage: mset <vnum> {display} <dice>"
    if field in MOB_LIST_FIELDS:
        current = t.get(field, [])
        current_text = ", ".join(current) if current else "(empty)"
        return (
            f"'{display}' is a list -- add one value at a time. Current: {current_text}\n"
            f"Usage: mset <vnum> {display} <value>   (or -<value> to remove one)"
        )
    if field in MOB_STRING_FIELDS:
        return f"'{display}' is free text. Current: '{t.get(field, '')}'.\nUsage: mset <vnum> {display} <text>"
    return None


def cmd_mset(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send(
            "Usage: mset create <vnum> <name...>\n"
            "       mset <vnum> <field> <value...>   (mob prototype -- add/set)\n"
            "       mset <vnum> <field>              (shows that field's valid options)\n"
            "       mset <vnum> <field> -<value>       (remove one item from a list field)\n"
            "       mset spawn <vnum> <room_vnum>\n"
            "       mset additem <mob vnum> <object vnum>   (stock an item for a shopkeeper)\n"
            "       mset removeitem <mob vnum> <object vnum>\n"
            "       mset addprogram <vnum> <trigger> <action> <args...>\n"
            "       mset removeprogram <vnum> <index>\n"
            "       mset list\n"
            "       mset fields [mob|player]           (readable field reference)\n"
            "       mset <player name> <field> <value...>   (edit a live/saved character -- admin+ only)\n"
            "\n"
            "Use 'mstat <vnum>' to view a mob's full stat block, or 'mset fields' for the complete field reference."
        )
        return

    sub = args[0].lower()

    if sub == "fields":
        if len(args) > 2 or (len(args) == 2 and args[1].lower() not in ("mob", "player")):
            session.send("Usage: mset fields [mob|player]")
            return
        session.send(_mset_field_reference(len(args) == 2 and args[1].lower() == "player"))
        return

    if sub == "list":
        if not combat.MOB_TEMPLATES:
            session.send("No mobile prototypes exist yet.")
            return
        lines = [f"  {vnum}: {t['short_desc']} (level {t['level']})"
                 for vnum, t in sorted(combat.MOB_TEMPLATES.items())]
        session.send("Mobile prototypes:\n" + "\n".join(lines))
        return

    if sub == "create":
        if len(args) < 3 or not args[1].isdigit():
            session.send("Usage: mset create <vnum> <name...>")
            return
        vnum = int(args[1])
        if vnum in combat.MOB_TEMPLATES:
            session.send(f"Mobile prototype {vnum} already exists. Edit it with 'mset {vnum} <field> <value>'.")
            return
        name = " ".join(args[2:])
        combat.MOB_TEMPLATES[vnum] = combat.default_template(vnum, name)
        _log(session.player.name, "mobile", vnum, f"prototype created: {name}")
        session.send(f"Mobile prototype {vnum} ({name}) created. Use 'mset {vnum} <field> <value>' to customize it.")
        return

    if sub == "delete":
        if len(args) != 2 or not args[1].isdigit():
            session.send("Usage: mset delete <vnum>")
            return
        vnum = int(args[1])
        if vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {vnum} exists.")
            return
        name = combat.MOB_TEMPLATES[vnum].get("short_desc", f"mob {vnum}")

        # Remove every currently-live spawned instance of this
        # template, wherever it's standing right now.
        instance_count = 0
        for room_vnum, mobs in list(combat.MOBS_BY_ROOM.items()):
            for mob in list(mobs):
                if mob.template_vnum == vnum:
                    combat.remove_mob(mob)
                    instance_count += 1

        # Remove any real spawn point(s) still targeting this template.
        spawn_point_count = 0
        for point in spawn_points.list_spawn_points():
            if point["kind"] == "mob" and point["vnum"] == vnum:
                spawn_points.remove_spawn_point("mob", vnum, point["room_vnum"])
                spawn_point_count += 1

        del combat.MOB_TEMPLATES[vnum]
        _log(session.player.name, "mobile", vnum, f"prototype deleted: {name}")
        session.send(
            f"Mobile prototype {vnum} ({name}) permanently deleted -- "
            f"{instance_count} live instance(s) and {spawn_point_count} spawn point(s) removed with it."
        )
        return

    if sub == "spawn":
        if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
            session.send("Usage: mset spawn <vnum> <room_vnum>")
            return
        vnum, room_vnum = int(args[1]), int(args[2])
        if vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {vnum} exists.")
            return
        if room_vnum not in world.WORLD.rooms:
            session.send(f"Room {room_vnum} does not exist.")
            return
        mob = combat.spawn_mob(vnum, room_vnum)
        _log(session.player.name, "mobile", vnum, f"spawned instance {mob.instance_id} in room {room_vnum}")
        session.send(f"Spawned {mob.name} in room {room_vnum}.")
        return

    if sub == "additem":
        if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
            session.send("Usage: mset additem <mob vnum> <object vnum>")
            return
        mob_vnum, obj_vnum = int(args[1]), int(args[2])
        if mob_vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {mob_vnum} exists.")
            return
        if obj_vnum not in OBJECT_TEMPLATES:
            session.send(f"No object prototype {obj_vnum} exists. Use 'oset create <vnum> <name>' first.")
            return
        t = combat.MOB_TEMPLATES[mob_vnum]
        if not t.get("shopkeeper", False):
            session.send(f"Mobile {mob_vnum} isn't flagged as a shopkeeper yet -- use 'mset {mob_vnum} shopkeeper on' first.")
            return
        if obj_vnum not in t["shop_items"]:
            t["shop_items"].append(obj_vnum)
        _log(session.player.name, "mobile", mob_vnum, f"added object {obj_vnum} to shop stock")
        session.send(f"Object {obj_vnum} ({OBJECT_TEMPLATES[obj_vnum]['short_desc']}) added to {t['short_desc']}'s stock.")
        return

    if sub == "removeitem":
        if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
            session.send("Usage: mset removeitem <mob vnum> <object vnum>")
            return
        mob_vnum, obj_vnum = int(args[1]), int(args[2])
        if mob_vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {mob_vnum} exists.")
            return
        t = combat.MOB_TEMPLATES[mob_vnum]
        if obj_vnum in t["shop_items"]:
            t["shop_items"].remove(obj_vnum)
            session.send(f"Object {obj_vnum} removed from {t['short_desc']}'s stock.")
        else:
            session.send(f"{t['short_desc']} doesn't stock object {obj_vnum}.")
        _log(session.player.name, "mobile", mob_vnum, f"removed object {obj_vnum} from shop stock")
        return

    if sub == "addprogram":
        if len(args) < 4 or not args[1].isdigit():
            session.send(
                f"Usage: mset addprogram <mob vnum> <trigger> <action> <args...>\n"
                f"       mset addprogram <mob vnum> speech <keyword> <action> <args...>\n"
                f"Triggers: {', '.join(sorted(programs.MOB_TRIGGERS))}\n"
                f"Actions: {', '.join(sorted(programs.ACTIONS))}"
            )
            return
        mob_vnum, trigger = int(args[1]), args[2].lower()
        if mob_vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {mob_vnum} exists.")
            return

        keyword = None
        if trigger == "speech":
            if len(args) < 5:
                session.send("Usage: mset addprogram <mob vnum> speech <keyword> <action> <args...>")
                return
            keyword, action = args[3].lower(), args[4].lower()
            prog_args = " ".join(args[5:])
        else:
            action = args[3].lower()
            prog_args = " ".join(args[4:])

        errors = programs.validate_program(trigger, action, prog_args, programs.MOB_TRIGGERS, keyword=keyword)
        if errors:
            session.send("\n".join(errors))
            return
        program = {"trigger": trigger, "action": action, "args": prog_args}
        if keyword:
            program["keyword"] = keyword
        combat.MOB_TEMPLATES[mob_vnum]["mob_programs"].append(program)
        _log(session.player.name, "mobile", mob_vnum, f"program added: {trigger} -> {action} {prog_args}")
        if keyword:
            session.send(f"Program added to mobile {mob_vnum}: on speech of '{keyword}', {action} \"{prog_args}\".")
        else:
            session.send(f"Program added to mobile {mob_vnum}: on {trigger}, {action} \"{prog_args}\".")
        return

    if sub == "removeprogram":
        if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
            session.send("Usage: mset removeprogram <mob vnum> <program index -- see mstat>")
            return
        mob_vnum, index = int(args[1]), int(args[2])
        if mob_vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {mob_vnum} exists.")
            return
        progs = combat.MOB_TEMPLATES[mob_vnum]["mob_programs"]
        if not (0 <= index < len(progs)):
            session.send(f"Mobile {mob_vnum} has no program at index {index}. Use 'mstat {mob_vnum}' to see them.")
            return
        removed = progs.pop(index)
        _log(session.player.name, "mobile", mob_vnum, f"program removed: {removed}")
        session.send(f"Removed program {index} from mobile {mob_vnum}.")
        return

    # mset <vnum> <field> <value...>  OR  mset <player name> <field> <value...>
    if not sub.isdigit():
        if len(args) < 3:
            session.send("Usage: mset <player name> <field> <value...>")
            return
        _mset_player(session, args[0], args[1].lower(), args[2:])
        return
    if int(sub) not in combat.MOB_TEMPLATES:
        session.send(f"No mobile prototype '{sub}' exists. Use 'mset create <vnum> <name>' first.")
        return
    vnum = int(sub)
    if len(args) < 2:
        session.send("Usage: mset <vnum> <field> <value...>\nUse 'mset fields' to see every field, or 'mset <vnum> <field>' to see one field's options.")
        return
    field_name = args[1].lower()
    field_display_name = field_name
    if field_name == "act":
        field_name = "act_flags"  # shorter alias for the same field
        field_display_name = field_name  # this alias's own established design: hint text shows the real field name
    if field_name == "short":
        field_name = "short_desc"  # per direct request -- "short" is the command word, short_desc is the underlying field
    if field_name == "long":
        field_name = "long_desc"  # per direct request -- "long" is the command word, long_desc is the underlying field
    if field_name == "class":
        field_name = "primary_class"  # per direct request -- "class" is the command word, primary_class is the underlying field
    if field_name in {"exp", "experience", "experience_reward"}:
        session.send(
            "Mob experience is calculated automatically from its level and the player's level. "
            "Set the mob's level instead; 'mstat' shows its same-level reward."
        )
        return
    if len(args) == 2:
        hint = _mob_field_hint(field_name, combat.MOB_TEMPLATES[vnum], field_display_name)
        if hint:
            session.send(hint)
        else:
            session.send(f"Unknown field '{args[1]}'. Use 'mset fields' to see every valid field.")
        return
    field, value_args = field_name, args[2:]
    t = combat.MOB_TEMPLATES[vnum]
    value_text = " ".join(value_args)

    if field in MOB_ATTR_FIELDS:
        if not value_text.lstrip("-").isdigit():
            session.send(f"{field} must be a number.")
            return
        t["attributes"][field] = int(value_text)
        _log(session.player.name, "mobile", vnum, f"attribute {field} set to {value_text}")
        session.send(f"{field} set to {value_text}.")
        return

    if field in MOB_STRING_FIELDS:
        if field in ("hit_dice", "damage_dice") and not dice.is_valid(value_text):
            session.send(f"'{value_text}' isn't valid dice notation (expected e.g. '2d6+4').")
            return
        if field == "teacher":
            teacher_value = value_text.strip().lower()
            if teacher_value in ("off", "none", ""):
                t[field] = ""
                _log(session.player.name, "mobile", vnum, "teacher cleared")
                session.send(f"{field_display_name} set.")
                return
            valid_classes = {"ninjutsu", "taijutsu", "genjutsu", "bukijutsu"}
            if teacher_value not in valid_classes:
                session.send(f"'{value_text}' isn't a real class. Valid: {', '.join(sorted(valid_classes))}, or 'off' to clear.")
                return
            value_text = teacher_value
        if field == "primary_class":
            class_value = value_text.strip().lower()
            valid_classes = {"ninjutsu", "taijutsu", "genjutsu", "bukijutsu"}
            if class_value not in valid_classes and class_value != "none":
                session.send(f"'{value_text}' isn't a real class. Valid: {', '.join(sorted(valid_classes))}, or 'none' to clear.")
                return
            value_text = None if class_value == "none" else class_value
        t[field] = value_text
        if field == "primary_class":
            for mobs in combat.MOBS_BY_ROOM.values():
                for mob in mobs:
                    if mob.template_vnum == vnum:
                        mob.primary_class = value_text
        _log(session.player.name, "mobile", vnum, f"{field} set to '{value_text}'")
        session.send(f"{field_display_name} set.")
        return

    if field in MOB_BOOL_FIELDS:
        if value_text.lower() not in ("on", "off", "true", "false"):
            session.send(f"{field} must be on/off.")
            return
        t[field] = value_text.lower() in ("on", "true")
        _log(session.player.name, "mobile", vnum, f"{field} set to {t[field]}")
        session.send(f"{field} is now {'on' if t[field] else 'off'}.")
        return

    if field in MOB_INT_FIELDS:
        if not value_text.lstrip("-").isdigit():
            session.send(f"{field} must be a number.")
            return
        t[field] = int(value_text)
        _log(session.player.name, "mobile", vnum, f"{field} set to {value_text}")
        session.send(f"{field} set to {value_text}.")
        return

    if field in MOB_LIST_FIELDS:
        if field == "shop_buys_categories" and not value_text.startswith("-"):
            if value_text.lower() not in item_types.BASE_SELL_PRICE:
                session.send(
                    f"'{value_text}' isn't a known item category. Valid: "
                    + ", ".join(sorted(item_types.BASE_SELL_PRICE.keys()))
                )
                return
        if field == "act_flags" and not value_text.startswith("-"):
            canonical = next((f for f in VALID_MOB_ACT_FLAGS if f.lower() == value_text.lower()), None)
            if canonical is None:
                session.send(f"'{value_text}' isn't a recognized mob flag. Valid: {', '.join(sorted(VALID_MOB_ACT_FLAGS))}")
                return
            value_text = canonical
        if value_text.startswith("-"):
            removed = value_text[1:].strip().lower()
            t[field] = [v for v in t[field] if v.lower() != removed]
            session.send(f"'{removed}' removed from {field}.")
        else:
            if value_text.lower() not in [v.lower() for v in t[field]]:
                t[field].append(value_text.lower() if field == "shop_buys_categories" else value_text)
            session.send(f"'{value_text}' added to {field}.")
        _log(session.player.name, "mobile", vnum, f"{field} updated")
        return

    session.send(f"Unknown field '{field}'. Use 'mset fields' to see every valid field.")


# ===========================================================================
# BLOODSTAT / BLOODSET -- Kekkei Genkai staff debug tools (Section [KKG])
# ===========================================================================
# Per the KKG design brief: players must never see any of this, but
# staff need to be able to inspect and manipulate it for testing. Both
# gated the same way editing any other player's data already is
# (_require_admin), not the lower builder tier -- this is sensitive,
# player-specific data, not a world-content prototype.

BLOODSET_FIELDS = {"bloodline", "potential", "talent", "awakened", "mastery", "tomoe"}


def cmd_bloodstat(session, args: List[str]) -> None:
    """Staff-only: shows a player's hidden Kekkei Genkai state --
    clan, bloodline (if any), Potential, Talent, awakened status, and
    mastery. Never shown to the player themselves anywhere else in the
    game (see data_kekkei_genkai.py's own docstring)."""
    if not _require_admin(session):
        return
    if not args:
        session.send("Usage: bloodstat <player>")
        return

    target, _live_session = _find_target_player(" ".join(args))
    if not target:
        session.send(f"No player named '{' '.join(args)}' found.")
        return

    if target.bloodline_id:
        bloodline_line = (
            f"{data_kekkei_genkai.display_name(target.bloodline_id)} "
            f"(Potential: {target.bloodline_potential}/100, Talent: {target.bloodline_talent}/100)"
        )
    else:
        bloodline_line = "None"

    lines = [
        f"&WKekkei Genkai status for {target.name}:&x",
        f"  Clan: {data_clans.display_name(target.clan)}",
        f"  Bloodline: {bloodline_line}",
        f"  Awakened: {'Yes' if target.bloodline_awakened else 'No'}",
    ]
    if target.bloodline_id:
        mastery_pct = data_kekkei_genkai.mastery_percent(target) * 100
        lines.append(
            f"  Mastery: {target.bloodline_mastery}/{target.bloodline_potential} "
            f"({mastery_pct:.0f}%)  Stage-2 quest eligible: "
            f"{'Yes' if data_kekkei_genkai.eligible_for_awakening_quest(target) else 'No'}"
        )
    else:
        lines.append(f"  Mastery: {target.bloodline_mastery}")
    if target.bloodline_id == "sharingan":
        tomoe_cap = data_kekkei_genkai.max_tomoe_for_potential(target.bloodline_potential)
        lines.append(f"  Tomoe: {target.bloodline_tomoe}/{tomoe_cap} (Potential-based cap)")
        lines.append(f"  Sharingan active: {'Yes' if target.sharingan_active else 'No'}")
        if target.copied_jutsu_key:
            lines.append(f"  Copied jutsu ready: {target.copied_jutsu_key} (costs {target.copied_jutsu_cost} chakra)")
    session.send("\n".join(lines))


def cmd_award(session, args: List[str]) -> None:
    """'award <player> <amount>' -- adds `amount` mission points to a
    player's current balance (mset can only overwrite it outright to
    an exact value, not adjust it relative to whatever it already is).
    A negative amount deducts instead. Matches exactly how a real
    mission completion grants points (missions.py): both the
    spendable mission_points balance and the lifetime mission_points_
    earned_total move together -- except the lifetime tracker only
    ever increases, even on a deduction, since it's meant to record
    real history, not net balance."""
    if not _require_admin(session):
        return
    if len(args) < 2:
        session.send("Usage: award <player> <amount>")
        return

    amount_text = args[-1]
    player_name = " ".join(args[:-1])
    if not amount_text.lstrip("-").isdigit():
        session.send("Amount must be a number.")
        return
    amount = int(amount_text)

    target, live_session = _find_target_player(player_name)
    if not target:
        session.send(f"No player named '{player_name}' is online or has a saved character.")
        return

    target.mission_points = max(0, target.mission_points + amount)
    target.mission_points_earned_total += max(0, amount)

    if live_session:
        live_session.send(
            f"&YYou {'gain' if amount >= 0 else 'lose'} {abs(amount)} mission point(s) "
            f"-- new balance: {target.mission_points}.&x"
        )
        live_session.send_prompt()
    else:
        storage.save_player(target)

    session.send(f"{target.name}'s mission points adjusted by {amount:+d} -- new balance: {target.mission_points}.")
    _log(session.player.name, "player", 0, f"awarded {target.name} {amount:+d} mission points")


def cmd_addtip(session, args: List[str]) -> None:
    """'addtip <text>' -- adds a new tip to the rotation shown to
    players with 'config tips on' (see server.py's own periodic
    display timer, tips.TIPS_INTERVAL_SECONDS). With no arguments,
    lists every tip currently in the rotation with its 1-indexed
    number, for use with 'remtip'."""
    if not _require_builder(session):
        return
    if not args:
        current_tips = tips.all_tips()
        if not current_tips:
            session.send("No tips have been added yet. Usage: addtip <text>")
            return
        lines = ["&WCurrent tips:&x"]
        for i, tip_text in enumerate(current_tips, start=1):
            lines.append(f"  {i}. {tip_text}")
        session.send("\n".join(lines))
        return

    text = " ".join(args)
    tips.add_tip(text)
    session.send(f"Tip added: {text}")
    _log(session.player.name, "tip", 0, f"added tip: {text}")


def cmd_remtip(session, args: List[str]) -> None:
    """'remtip <number>' -- removes a tip from the rotation by its
    1-indexed position, matching the numbering 'addtip' (with no
    arguments) shows."""
    if not _require_builder(session):
        return
    if not args or not args[0].isdigit():
        session.send("Usage: remtip <number> -- see 'addtip' with no arguments for the numbered list.")
        return

    index = int(args[0])
    current_tips = tips.all_tips()
    if index < 1 or index > len(current_tips):
        session.send(f"No tip numbered {index}. See 'addtip' with no arguments for the current list.")
        return

    removed_text = current_tips[index - 1]
    tips.remove_tip(index)
    session.send(f"Tip removed: {removed_text}")
    _log(session.player.name, "tip", 0, f"removed tip: {removed_text}")


def cmd_setkage(session, args: List[str]) -> None:
    """Implementor-only: appoints a player as their village's Kage --
    the one rank in the game that's NEVER reachable through the normal
    level/mission-based promotion ladder (kage.PROMOTION_LADDER), per
    explicit request. Intended for a player voted in by their
    community; the actual voting process happens outside the game, but
    only an Implementor can act on it and make it official. At most
    one Kage per village at a time -- appointing a new one automatically
    demotes whoever held it before back to Village Elder. 'setkage
    <player> remove' demotes without appointing a replacement."""
    if not _require_implementor(session):
        return
    if len(args) < 1:
        session.send("Usage: setkage <player>\n       setkage <player> remove")
        return

    player_name = args[0]
    is_remove = len(args) >= 2 and args[1].lower() == "remove"

    target, live_session = _find_target_player(player_name)
    if not target:
        session.send(f"No player named '{player_name}' found.")
        return

    def _demote_to_elder(p, p_session) -> None:
        p.village_rank = "village elder"
        import data_headbands
        data_headbands.apply_rank_headband(p, "village elder")
        if p_session:
            p_session.send("&YYou have been relieved of the Kage position -- you are once again a Village Elder.&x")
            p_session.send_prompt()
        else:
            storage.save_player(p)

    if is_remove:
        if target.village_rank != "kage":
            session.send(f"{target.name} isn't a Kage.")
            return
        _demote_to_elder(target, live_session)
        if live_session:
            storage.save_player(target)
        session.send(f"{target.name} has been relieved of the Kage position.")
        _log(session.player.name, "player", 0, f"removed {target.name} as Kage of {target.village}")
        return

    if target.village_rank == "kage":
        session.send(f"{target.name} is already the Kage of their village.")
        return
    if target.village_rank != "village elder":
        session.send(
            f"{target.name} must be a Village Elder first (currently: {target.village_rank}) "
            f"before being appointed Kage."
        )
        return

    # Demote any existing Kage of the SAME village first -- only one at a time.
    for existing in storage.all_players():
        if existing.village == target.village and existing.village_rank == "kage" and existing.name != target.name:
            existing_session = next(
                (s for s in __import__("session").ACTIVE_SESSIONS if s.player and s.player.name == existing.name),
                None,
            )
            live_existing = existing_session.player if existing_session else existing
            _demote_to_elder(live_existing, existing_session)
            if existing_session:
                storage.save_player(live_existing)
            session.send(f"{live_existing.name} has been relieved of the Kage position to make way.")

    target.village_rank = "kage"
    import data_headbands
    new_headband = data_headbands.apply_rank_headband(target, "kage")
    if live_session:
        live_session.send(
            f"&r*** By decree of an Implementor, you have been appointed Kage! ***&x\n"
            f"&YYou are equipped with {new_headband}.&x"
        )
        live_session.send_prompt()
    storage.save_player(target)

    session.send(f"{target.name} has been appointed Kage of their village.")
    _log(session.player.name, "player", 0, f"appointed {target.name} as Kage of {target.village}")

    import session as session_module
    for s in session_module.ACTIVE_SESSIONS:
        if s.state == session_module.State.PLAYING and s.player and s is not live_session:
            s.send(f"&r*** {target.name} has been appointed Kage! ***&x")
            s.send_prompt()


def cmd_bloodset(session, args: List[str]) -> None:
    """Staff-only: force-edits a player's hidden Kekkei Genkai state,
    for testing. 'bloodset <player> awaken' is a shortcut that calls
    data_kekkei_genkai.attempt_awaken() directly (the same function a
    future awakening quest would call), rather than just flipping the
    flag -- so staff testing exercises the real framework function,
    not a bypass of it."""
    if not _require_admin(session):
        return
    if len(args) < 2:
        session.send(
            "Usage: bloodset <player> bloodline <kkg_id|none>\n"
            "       bloodset <player> potential <0-100>\n"
            "       bloodset <player> talent <0-100>\n"
            "       bloodset <player> awakened <yes|no>\n"
            "       bloodset <player> mastery <int>\n"
            "       bloodset <player> tomoe <int>   (Sharingan-specific)\n"
            "       bloodset <player> awaken   (calls the real awakening framework function)\n"
            f"Known kekkei genkai: {', '.join(sorted(data_kekkei_genkai.KEKKEI_GENKAI.keys()))}"
        )
        return

    # The player name may itself contain spaces in theory, but every
    # other staff tool here assumes a single-word name -- matching
    # that existing convention rather than inventing a new parsing
    # rule just for this command.
    player_name, field, *rest = args
    target, live_session = _find_target_player(player_name)
    if not target:
        session.send(f"No player named '{player_name}' found.")
        return

    field = field.lower()

    if field == "awaken":
        result = data_kekkei_genkai.attempt_awaken(target)
        if not result["has_bloodline"]:
            session.send(f"{target.name} has no kekkei genkai to awaken.")
        elif result["already_awakened"]:
            session.send(f"{target.name}'s {data_kekkei_genkai.display_name(result['kekkei_genkai'])} was already awakened.")
        else:
            session.send(f"{target.name}'s {data_kekkei_genkai.display_name(result['kekkei_genkai'])} is now awakened.")
        storage.save_player(target)
        return

    if field not in BLOODSET_FIELDS:
        session.send(f"Unknown field '{field}'. Valid: {', '.join(sorted(BLOODSET_FIELDS))}, awaken")
        return
    if not rest:
        session.send(f"Usage: bloodset <player> {field} <value>")
        return
    value_text = " ".join(rest)

    if field == "bloodline":
        value_lower = value_text.lower()
        if value_lower == "none":
            target.bloodline_id = None
            target.bloodline_potential = 0
            target.bloodline_talent = 0
            target.bloodline_awakened = False
            target.bloodline_mastery = 0
            session.send(f"{target.name}'s kekkei genkai removed entirely.")
        elif value_lower in data_kekkei_genkai.KEKKEI_GENKAI:
            target.bloodline_id = value_lower
            # Assigning a bloodline directly (bypassing the normal
            # chargen roll) with no Potential/Talent set yet would
            # leave a 0/0 bloodline that can never progress -- roll
            # both now, same range as the real inheritance roll,
            # unless they're already set (e.g. re-assigning the same
            # bloodline shouldn't re-roll and discard prior testing).
            if target.bloodline_potential == 0:
                target.bloodline_potential = random.randint(1, 100)
            if target.bloodline_talent == 0:
                target.bloodline_talent = random.randint(1, 100)
            session.send(
                f"{target.name} now carries {data_kekkei_genkai.display_name(value_lower)} "
                f"(Potential {target.bloodline_potential}, Talent {target.bloodline_talent})."
            )
        else:
            session.send(
                f"'{value_text}' isn't a known kekkei genkai. Valid: "
                + ", ".join(sorted(data_kekkei_genkai.KEKKEI_GENKAI.keys()))
                + ", or 'none' to remove."
            )
            return
    elif field in ("potential", "talent"):
        if not value_text.lstrip("-").isdigit():
            session.send(f"'{value_text}' isn't a number.")
            return
        num = max(0, min(100, int(value_text)))
        setattr(target, f"bloodline_{field}", num)
        session.send(f"{target.name}'s {field} set to {num}.")
    elif field == "awakened":
        if value_text.lower() not in ("yes", "no", "true", "false"):
            session.send("Usage: bloodset <player> awakened <yes|no>")
            return
        target.bloodline_awakened = value_text.lower() in ("yes", "true")
        session.send(f"{target.name}'s awakened status set to {target.bloodline_awakened}.")
    elif field == "mastery":
        if not value_text.lstrip("-").isdigit():
            session.send(f"'{value_text}' isn't a number.")
            return
        target.bloodline_mastery = int(value_text)
        session.send(f"{target.name}'s mastery set to {target.bloodline_mastery}.")
    elif field == "tomoe":
        if not value_text.lstrip("-").isdigit():
            session.send(f"'{value_text}' isn't a number.")
            return
        target.bloodline_tomoe = int(value_text)
        session.send(f"{target.name}'s tomoe count set to {target.bloodline_tomoe}.")

    storage.save_player(target)


def cmd_awaken(session, args: List[str]) -> None:
    """Staff-only: force-awakens a player's Kekkei Genkai (if they
    have one) immediately, regardless of level -- there's no level
    gate to bypass here in the first place, since data_kekkei_genkai.
    attempt_awaken() itself has never checked level at all; the
    "Level 50" framing only exists conceptually, as a future awakening
    quest that isn't built yet and would presumably call this same
    function once it exists. This IS that same function -- a thin
    wrapper around attempt_awaken(), the exact mechanism a future
    quest would use, not a bypass of it. Same effect as 'bloodset
    <player> awaken', just reachable as its own dedicated command."""
    if not _require_admin(session):
        return
    if not args:
        session.send("Usage: awaken <player>")
        return

    target, _live_session = _find_target_player(" ".join(args))
    if not target:
        session.send(f"No player named '{' '.join(args)}' found.")
        return

    result = data_kekkei_genkai.attempt_awaken(target)
    if not result["has_bloodline"]:
        session.send(f"{target.name} has no kekkei genkai to awaken.")
    elif result["already_awakened"]:
        session.send(f"{target.name}'s {data_kekkei_genkai.display_name(result['kekkei_genkai'])} was already awakened.")
    else:
        session.send(f"{target.name}'s {data_kekkei_genkai.display_name(result['kekkei_genkai'])} is now awakened.")
    storage.save_player(target)


# ===========================================================================
# OSET -- object prototype field editor
# ===========================================================================

OBJECT_STRING_FIELDS = {"short_desc", "long_desc", "description", "item_type", "weapon_type", "scroll_jutsu", "rarity", "wear_loc"}
OBJECT_INT_FIELDS = {"weight", "cost", "level", "condition", "set_bonus_percent", "container_capacity"}
OBJECT_LIST_FIELDS = {"keywords", "extra_flags", "wear_flags", "set_vnums"}


def _object_field_hint(field: str, o: dict) -> Optional[str]:
    """Builds a field-specific hint for 'oset <vnum> <field>' with no
    value given. Returns None if `field` isn't a recognized object
    field at all, so the caller can fall through to the normal
    "unknown field" refusal."""
    if field == "item_type":
        return f"'item_type' is free text -- commonly: weapon, armor, tool, scroll, material, trash. Current: '{o.get('item_type', '')}'.\nUsage: oset <vnum> item_type <text>"
    if field == "weapon_type":
        import data_weapons
        return f"'weapon_type' should be one of: {', '.join(sorted(data_weapons.WEAPON_TYPES.keys()))}. Current: '{o.get('weapon_type', '')}'.\nUsage: oset <vnum> weapon_type <type>"
    if field == "rarity":
        import data_rarity
        return f"'rarity' should be one of: {', '.join(data_rarity.RARITY_ORDER)}. Current: '{o.get('rarity', '')}'.\nUsage: oset <vnum> rarity <tier>"
    if field == "wear_loc":
        return f"'wear_loc' is where this can be equipped -- head/body/legs/feet/hands/waist/finger (armor), or wielded/tool. Current: '{o.get('wear_loc', '')}'.\nUsage: oset <vnum> wear_loc <slot>\nLeave it blank on a weapon/tool item_type and it auto-fills."
    if field == "extra_flags":
        return f"'extra_flags' accepts: {', '.join(sorted(VALID_ITEM_EXTRA_FLAGS))}. Current: {', '.join(o.get('extra_flags', [])) or '(empty)'}\nUsage: oset <vnum> extra_flags <flag>   (or -<flag> to remove)"
    if field == "set_vnums":
        current = o.get("set_vnums", [])
        return f"'set_vnums' lists the OTHER object vnums that must also be worn to complete this item's armor set. Current: {', '.join(str(v) for v in current) if current else '(empty)'}\nUsage: oset <vnum> set_vnums <other vnum>   (or -<vnum> to remove)"
    if field == "statbonus":
        if o.get("wear_loc") == "wielded":
            return f"'statbonus' sets a per-instance stat perk applied to every instance of this item once equipped -- for a weapon, 'hitroll' and 'damroll' are the ones that usually matter most. Valid stats: {', '.join(sorted(STAT_BONUS_KEYS))}. Current: {o.get('stat_bonuses', {}) or '(none)'}\nUsage: oset <vnum> statbonus hitroll <number>\n       oset <vnum> statbonus damroll <number>   (0 clears either)"
        return f"'statbonus' sets a per-instance stat perk applied to every instance of this item once equipped. Valid stats: {', '.join(sorted(STAT_BONUS_KEYS))}. Current: {o.get('stat_bonuses', {}) or '(none)'}\nUsage: oset <vnum> statbonus <stat> <number>   (0 clears it)"
    if field == "value":
        return f"'value' sets one of 4 raw numeric slots for anything not covered by a named field. Current: {o.get('values', [0, 0, 0, 0])}\nUsage: oset <vnum> value <index 0-3> <number>"
    if field in OBJECT_INT_FIELDS:
        return f"'{field}' is a number. Current: {o.get(field, 0)}.\nUsage: oset <vnum> {field} <number>"
    if field in OBJECT_LIST_FIELDS:
        current = o.get(field, [])
        current_text = ", ".join(str(v) for v in current) if current else "(empty)"
        return f"'{field}' is a list -- add one value at a time. Current: {current_text}\nUsage: oset <vnum> {field} <value>   (or -<value> to remove one)"
    if field in OBJECT_STRING_FIELDS:
        return f"'{field}' is free text. Current: '{o.get(field, '')}'.\nUsage: oset <vnum> {field} <text>"
    return None


def cmd_oset(session, args: List[str]) -> None:
    if not _require_builder(session):
        return
    if not args:
        session.send(
            "Usage: oset create <vnum> <name...>\n"
            "       oset <vnum> <field> <value...>   (add/set)\n"
            "       oset <vnum> <field>              (shows that field's valid options)\n"
            "       oset <vnum> <field> -<value>       (remove one item from a list field)\n"
            "       oset <vnum> value <index> <number>  (set one of the 4 value slots)\n"
            f"       oset <vnum> statbonus <stat> <number>  (0 clears it; valid: {', '.join(sorted(STAT_BONUS_KEYS))})\n"
            "       oset addprogram <vnum> <trigger> <action> <args...>\n"
            "       oset removeprogram <vnum> <index>\n"
            "       oset list\n"
            "       oset fields                        (full list of every settable field)\n"
            "\n"
            "Use 'ostat <vnum>' to view an item's full stat block, or 'oset fields' for the complete field reference."
        )
        return

    sub = args[0].lower()

    if sub == "fields":
        session.send(
            f"String fields: {', '.join(sorted(OBJECT_STRING_FIELDS))}\n"
            f"Number fields: {', '.join(sorted(OBJECT_INT_FIELDS))}\n"
            f"List fields: {', '.join(sorted(OBJECT_LIST_FIELDS))}\n"
            "Armor sets: 'oset <vnum> set_vnums <other vnum>' lists what else must be worn "
            "at the same time to complete this item's set; 'oset <vnum> set_bonus_percent <n>' "
            "sets the bonus (default 25) each qualifying piece adds to derived combat stats once complete."
        )
        return

    if sub == "list":
        if not OBJECT_TEMPLATES:
            session.send("No object prototypes exist yet.")
            return
        lines = [f"  {vnum}: {o['short_desc']} ({o['item_type']})"
                 for vnum, o in sorted(OBJECT_TEMPLATES.items())]
        session.send("Object prototypes:\n" + "\n".join(lines))
        return

    if sub == "create":
        if len(args) < 3 or not args[1].isdigit():
            session.send("Usage: oset create <vnum> <name...>")
            return
        vnum = int(args[1])
        if vnum in OBJECT_TEMPLATES:
            session.send(f"Object prototype {vnum} already exists. Edit it with 'oset {vnum} <field> <value>'.")
            return
        name = " ".join(args[2:])
        OBJECT_TEMPLATES[vnum] = default_object(vnum, name)
        _log(session.player.name, "object", vnum, f"prototype created: {name}")
        session.send(f"Object prototype {vnum} ({name}) created. Use 'oset {vnum} <field> <value>' to customize it.")
        return

    if sub == "delete":
        if len(args) != 2 or not args[1].isdigit():
            session.send("Usage: oset delete <vnum>")
            return
        vnum = int(args[1])
        if vnum not in OBJECT_TEMPLATES:
            session.send(f"No object prototype {vnum} exists.")
            return
        name = OBJECT_TEMPLATES[vnum].get("short_desc", f"item {vnum}")

        # Remove this item from any real shopkeeper's own shop_items
        # list, so it stops being sold anywhere -- per direct
        # confirmation, a copy already sitting in a PLAYER's own
        # inventory is left completely untouched.
        shopkeeper_count = 0
        for mob_template in combat.MOB_TEMPLATES.values():
            shop_items = mob_template.get("shop_items")
            if shop_items and vnum in shop_items:
                shop_items.remove(vnum)
                shopkeeper_count += 1

        del OBJECT_TEMPLATES[vnum]
        _log(session.player.name, "object", vnum, f"prototype deleted: {name}")
        session.send(
            f"Object prototype {vnum} ({name}) permanently deleted -- removed from "
            f"{shopkeeper_count} shopkeeper's stock. Any copies already in a player's inventory are untouched."
        )
        return

    if sub == "load":
        if len(args) != 2 or not args[1].isdigit():
            session.send("Usage: oset load <vnum>  (places one instance on the ground in the room you're standing in)")
            return
        vnum = int(args[1])
        if vnum not in OBJECT_TEMPLATES:
            session.send(f"No object prototype {vnum} exists.")
            return
        room = world.WORLD.get(session.player.room_vnum)
        room.ground_items.append(OBJECT_TEMPLATES[vnum]["short_desc"])
        _log(session.player.name, "object", vnum, f"loaded onto the ground in room {room.vnum}")
        session.send(f"{OBJECT_TEMPLATES[vnum]['short_desc']} appears on the ground.")
        return

    if sub == "addprogram":
        if len(args) < 4 or not args[1].isdigit():
            session.send(f"Usage: oset addprogram <object vnum> <trigger> <action> <args...>\nTriggers: {', '.join(sorted(programs.ITEM_TRIGGERS))}\nActions: {', '.join(sorted(programs.ACTIONS))}")
            return
        obj_vnum, trigger, action = int(args[1]), args[2].lower(), args[3].lower()
        prog_args = " ".join(args[4:])
        if obj_vnum not in OBJECT_TEMPLATES:
            session.send(f"No object prototype {obj_vnum} exists.")
            return
        errors = programs.validate_program(trigger, action, prog_args, programs.ITEM_TRIGGERS)
        if errors:
            session.send("\n".join(errors))
            return
        OBJECT_TEMPLATES[obj_vnum]["item_programs"].append({"trigger": trigger, "action": action, "args": prog_args})
        _log(session.player.name, "object", obj_vnum, f"program added: {trigger} -> {action} {prog_args}")
        session.send(f"Program added to object {obj_vnum}: on {trigger}, {action} \"{prog_args}\".")
        return

    if sub == "removeprogram":
        if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
            session.send("Usage: oset removeprogram <object vnum> <program index -- see ostat>")
            return
        obj_vnum, index = int(args[1]), int(args[2])
        if obj_vnum not in OBJECT_TEMPLATES:
            session.send(f"No object prototype {obj_vnum} exists.")
            return
        progs = OBJECT_TEMPLATES[obj_vnum]["item_programs"]
        if not (0 <= index < len(progs)):
            session.send(f"Object {obj_vnum} has no program at index {index}. Use 'ostat {obj_vnum}' to see them.")
            return
        progs.pop(index)
        _log(session.player.name, "object", obj_vnum, f"program removed at index {index}")
        session.send(f"Removed program {index} from object {obj_vnum}.")
        return

    if not sub.isdigit() or int(sub) not in OBJECT_TEMPLATES:
        session.send(f"No object prototype '{sub}' exists. Use 'oset create <vnum> <name>' first.")
        return
    vnum = int(sub)
    if len(args) < 2:
        session.send("Usage: oset <vnum> <field> <value...>\nUse 'oset fields' to see every field, or 'oset <vnum> <field>' to see one field's options.")
        return
    if len(args) == 2:
        hint = _object_field_hint(args[1].lower(), OBJECT_TEMPLATES[vnum])
        if hint:
            session.send(hint)
        else:
            session.send(f"Unknown field '{args[1]}'. Use 'oset fields' to see every valid field.")
        return
    field, value_args = args[1].lower(), args[2:]
    o = OBJECT_TEMPLATES[vnum]
    value_text = " ".join(value_args)

    if field == "value":
        if len(value_args) != 2 or not value_args[0].isdigit() or not value_args[1].lstrip("-").isdigit():
            session.send("Usage: oset <vnum> value <index 0-3> <number>")
            return
        idx = int(value_args[0])
        if not 0 <= idx <= 3:
            session.send("Value index must be 0-3.")
            return
        o["values"][idx] = int(value_args[1])
        _log(session.player.name, "object", vnum, f"value[{idx}] set to {value_args[1]}")
        session.send(f"Value slot {idx} set to {value_args[1]}.")
        return

    if field == "statbonus":
        if len(value_args) != 2 or not value_args[1].lstrip("-").isdigit():
            session.send(
                "Usage: oset <vnum> statbonus <stat> <number>   (0 clears it)\n"
                f"Valid stats: {', '.join(sorted(STAT_BONUS_KEYS))}\n"
                "Positive is always beneficial for every stat here -- e.g. 'statbonus "
                "armor_class 8' makes Armor Class 8 points BETTER (lower), even "
                "though Armor Class itself always displays as lower-is-better."
            )
            return
        stat_key, amount_text = value_args[0].lower(), value_args[1]
        if stat_key not in STAT_BONUS_KEYS:
            session.send(f"'{stat_key}' isn't a known stat. Valid: {', '.join(sorted(STAT_BONUS_KEYS))}")
            return
        amount = int(amount_text)
        if amount == 0:
            o["stat_bonuses"].pop(stat_key, None)
            _log(session.player.name, "object", vnum, f"stat bonus {stat_key} cleared")
            session.send(f"{stat_key.replace('_', ' ').title()} bonus cleared on object {vnum}.")
        else:
            o["stat_bonuses"][stat_key] = amount
            _log(session.player.name, "object", vnum, f"stat bonus {stat_key} set to {amount}")
            session.send(f"{stat_key.replace('_', ' ').title()} bonus set to {amount:+d} on object {vnum}.")
        return

    if field in OBJECT_STRING_FIELDS:
        if field == "weapon_type" and value_text and value_text.lower() not in data_weapons.WEAPON_TYPES:
            session.send(
                f"'{value_text}' isn't a known weapon type. Valid: "
                + ", ".join(sorted(data_weapons.WEAPON_TYPES.keys()))
            )
            return
        if field == "wear_loc" and value_text and value_text.lower() not in WEAR_LOCATIONS:
            session.send(
                f"'{value_text}' isn't a known wear location. Valid: "
                + ", ".join(sorted(WEAR_LOCATIONS))
                + " (or blank for 'not equippable')."
            )
            return
        if field == "wear_loc":
            value_text = value_text.lower()
        if field == "scroll_jutsu":
            if value_text and value_text.lower() not in data_jutsu.JUTSU:
                session.send(
                    f"'{value_text}' isn't a known jutsu. Valid: "
                    + ", ".join(sorted(data_jutsu.JUTSU.keys()))
                    + " (or blank for 'not yet inscribed')."
                )
                return
            value_text = value_text.lower()
        if field == "rarity":
            if value_text.lower() not in data_rarity.RARITY_TIERS:
                session.send(
                    f"'{value_text}' isn't a known rarity. Valid: "
                    + ", ".join(data_rarity.RARITY_ORDER)
                )
                return
            value_text = value_text.lower()
        o[field] = value_text
        if field == "item_type" and not o.get("wear_loc"):
            if value_text == "weapon":
                o["wear_loc"] = "wielded"
            elif value_text == "tool":
                o["wear_loc"] = "tool"
        _log(session.player.name, "object", vnum, f"{field} set to '{value_text}'")
        session.send(f"{field} set.")
        return

    if field in OBJECT_INT_FIELDS:
        if not value_text.lstrip("-").isdigit():
            session.send(f"{field} must be a number.")
            return
        o[field] = int(value_text)
        _log(session.player.name, "object", vnum, f"{field} set to {value_text}")
        session.send(f"{field} set to {value_text}.")
        return

    if field in OBJECT_LIST_FIELDS:
        if field == "set_vnums" and not value_text.startswith("-"):
            if not value_text.isdigit():
                session.send("set_vnums entries must be object vnums (numbers).")
                return
            if int(value_text) not in OBJECT_TEMPLATES:
                session.send(f"Note: object {value_text} doesn't exist yet -- add it anyway once it's created.")
        if field == "extra_flags" and not value_text.startswith("-"):
            canonical = next((f for f in VALID_ITEM_EXTRA_FLAGS if f.lower() == value_text.lower()), None)
            if canonical is None:
                session.send(f"'{value_text}' isn't a recognized item flag. Valid: {', '.join(sorted(VALID_ITEM_EXTRA_FLAGS))}")
                return
            value_text = canonical
        if value_text.startswith("-"):
            removed = value_text[1:].strip().lower()
            o[field] = [v for v in o[field] if v.lower() != removed]
            session.send(f"'{removed}' removed from {field}.")
        else:
            if value_text.lower() not in [v.lower() for v in o[field]]:
                o[field].append(value_text)
            session.send(f"'{value_text}' added to {field}.")
        _log(session.player.name, "object", vnum, f"{field} updated")
        return

    session.send(f"Unknown field '{field}'. Use 'oset fields' to see every valid field.")


# ===========================================================================
# VNUM -- immortal-only enable/disable toggle for mobs, rooms, and items
# ===========================================================================
#
# This is a global, server-wide switch, distinct from ordinary OLC editing:
# disabling a mob prototype stops it from spawning or respawning at all
# (existing live instances are left alone -- this matches ROM/SMAUG
# behavior where a reset toggle doesn't retroactively kill things already
# in the world); disabling a room blocks ordinary players from walking
# into it (staff can still pass through to work on it) and shows a
# DISABLED marker on `look`/`rstat` for staff; disabling an item prototype
# is currently bookkeeping only, since there's no live "spawn this item
# into the world" mechanic yet for oset objects (honest limitation, not
# hidden) -- it's still tracked so that future spawning code has
# something to check.

def cmd_vnum(session, args: List[str]) -> None:
    if not _require_implementor(session):
        return
    if len(args) != 3 or args[0].lower() not in ("mob", "room", "item") or args[2].lower() not in ("on", "off"):
        session.send(
            "Usage: vnum <mob|room|item> <vnum> <on|off>\n"
            "Globally enables or disables a prototype -- disabled mobs stop "
            "spawning/respawning, disabled rooms are closed to ordinary players, "
            "disabled items are flagged (no live spawn mechanic exists for items yet)."
        )
        return

    kind, vnum_text, state_text = args[0].lower(), args[1], args[2].lower()
    if not vnum_text.isdigit():
        session.send("Vnum must be a number.")
        return
    vnum = int(vnum_text)
    enabled = state_text == "on"

    if kind == "mob":
        if vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {vnum} exists.")
            return
        combat.MOB_TEMPLATES[vnum]["enabled"] = enabled
        target_desc = combat.MOB_TEMPLATES[vnum]["short_desc"]
    elif kind == "room":
        if vnum not in world.WORLD.rooms:
            session.send(f"Room {vnum} does not exist.")
            return
        world.WORLD.get(vnum).enabled = enabled
        target_desc = world.WORLD.get(vnum).name
    else:  # item
        if vnum not in OBJECT_TEMPLATES:
            session.send(f"No object prototype {vnum} exists.")
            return
        OBJECT_TEMPLATES[vnum]["enabled"] = enabled
        target_desc = OBJECT_TEMPLATES[vnum]["short_desc"]

    _log(session.player.name, kind, vnum, f"{'enabled' if enabled else 'disabled'}")
    session.send(f"{kind.title()} {vnum} ({target_desc}) is now {'&Genabled&x' if enabled else '&Rdisabled&x'}.")
