"""
Combat engine (Section 16) + defeat/hospital flow (Sections 22-26).

Pulse model: normal attacks are automatic and resolved once per pulse
by `resolve_pulse()` (called from server.py's pulse_loop). Jutsu are
player-issued commands that resolve immediately when typed (subject to
their own cooldown), matching "players enter commands between combat
pulses" from the brief.

Mobs are plain in-memory instances (not persisted) spawned from
MOB_TEMPLATES -- `mset spawn` creates more of them at
runtime the same way.
"""

"""
Combat engine (Section 16) + defeat/hospital flow (Sections 22-26).

Pulse model: normal attacks are automatic and resolved once per pulse
by `resolve_pulse()` (called from server.py's pulse_loop). Jutsu are
player-issued commands that resolve immediately when typed (subject to
their own cooldown), matching "players enter commands between combat
pulses" from the brief.

Mob prototypes carry the full SMAUG-style stat block (see `mstat` in
olc.py) -- hit_dice/damage_dice are the SOURCE OF TRUTH for a mob's
health and attack damage, rolled per-instance at spawn (hit points) or
per-attack (damage), so two instances of the same template aren't
identical. Fields like armor_class/hit_roll/damage_roll/act_flags are
stored and displayed but not yet wired deeper into hit-chance math --
only the player side of that (derived_stats.py) is actually rolled
against right now; see olc.py's module docstring for the honest list of
what's cosmetic vs functional.

Mobs are plain in-memory instances (not persisted) spawned from
MOB_TEMPLATES -- `mset spawn` creates more of them at runtime the same
way.
"""

import itertools
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import config
import data_jutsu
import data_mangekyo
import data_passives
import data_weapons
import damage_messages
import derived_stats
import world
import dice
import inventory
import status_effects
import teams
from data_villages import VILLAGES
from models import Player

_id_counter = itertools.count(1)

# Sensible SMAUG-ish defaults for any prototype field not explicitly set.
DEFAULT_MOB_FIELDS = {
    "keywords": [], "short_desc": "", "long_desc": "", "description": "",
    "level": 1, "sex": "Neutral",
    "alignment": 0, "position": "Standing", "default_position": "Standing",
    "attributes": {"str": 13, "int": 13, "wis": 13, "dex": 13, "con": 13, "cha": 13, "luck": 13},
    # A builder's own real, fixed combat class (Taijutsu/Ninjutsu/
    # Genjutsu/Bukijutsu), per direct confirmation (Section 147
    # follow-up: "mset class genjutsu/ninjutsu ect"). None (the real
    # default) means spawn_mob keeps rolling one at random, exactly
    # as it already does today -- setting this field just lets a
    # builder fix a specific mob to always be one particular class.
    "primary_class": None,
    "hit_dice": "1d1+20", "mana": 100, "move": 100,
    "armor_class": 0, "hit_roll": 0, "damage_roll": 0, "damage_dice": "1d4+0", "attacks": 1,
    "act_flags": ["Npc"], "affected_by": [], "attack_verbs": ["hit"], "defenses": [],
    "resistant": [], "immune": [], "susceptible": [],
    "body_parts": ["head", "arms", "legs", "torso"],
    "gold": 0, "special_function": "None", "speaks": ["common"], "speaking": ["common"],
    "mob_programs": [],
    # Gameplay-critical fields combat.py actually resolves against:
    "experience_reward": 0, "ryo_reward": 0, "loot_items": [], "respawns": True,
    "enabled": True,  # immortal-only toggle -- disabled prototypes refuse to spawn
    # Shopkeeper fields -- a builder places a shopkeeper anywhere by
    # setting "shopkeeper" true; players can't attack them, and they sell
    # whatever object prototypes are added to "shop_items" at that
    # object's own oset-set "cost". "shop_buys_categories" optionally
    # restricts what item_types categories they'll buy FROM a player (empty
    # = buys anything, at half value; non-empty = only those categories,
    # full value -- a shopkeeper can hold more than one, e.g. both
    # "weapon" and "armor", to act as a combined weapon/blacksmith keeper).
    "shopkeeper": False, "shop_items": [], "shop_buys_categories": [],
    # Gambler/dealer flag -- a builder places a chou-han dealer anywhere
    # the same way (mset <vnum> gambler on). Like shopkeepers, gamblers
    # can't be attacked. See commands.cmd_gamble.
    "gambler": False,
    # Teacher field -- independent of shopkeeper/gambler (a mob can be
    # any combination of the three, or none). Holds the CLASS this mob
    # teaches directly ("ninjutsu"/"taijutsu"/"genjutsu"/"bukijutsu"),
    # per direct request/confirmation (Section 110: "lets change up the
    # prac system so skills cant be learned anywhere in game they must
    # goto a mob with a flag of teacheer" -> confirmed a teacher can
    # only teach skills matching their own class, confirmed the field
    # itself holds the class name directly rather than a separate
    # on/off + class-field pair). "" (falsy, same as the old False)
    # means "not a teacher at all". Like shopkeepers and gamblers,
    # teachers can't be attacked. See commands.cmd_practice's own
    # teacher-presence gate.
    "teacher": "",
}


@dataclass
class Mob:
    instance_id: int
    template_vnum: int
    name: str
    level: int
    health: int
    max_health: int
    room_vnum: int
    experience_reward: int
    ryo_reward: int
    damage_dice: str = "1d4+0"
    attacks: int = 1
    armor_class: int = 0
    hit_roll: int = 0
    respawns: bool = True
    loot_items: List[str] = field(default_factory=list)
    active_status_effects: Dict[str, dict] = field(default_factory=dict)
    # Mob stats/class parity (Section 86, per direct request: "give
    # mobs all that stats and classes that players do") -- scoped
    # down through direct confirmation to real numeric chakra/stamina
    # pools plus a primary_class and chakra_nature, explicitly NOT
    # jutsu-casting AI (mobs still never cast jutsu back at a player).
    # Needed so the elemental status effects Drained (chakra loss) and
    # Off Balance (stamina loss) have something real to act on when
    # inflicted on a mob, not just players. See
    # mob_chakra_for_level/mob_stamina_for_level below for the actual
    # level-scaled formula (mirrors the player's own exact growth
    # rate) and spawn_mob for where these get set on a freshly
    # spawned instance.
    chakra: int = 0
    maximum_chakra: int = 0
    stamina: int = 0
    maximum_stamina: int = 0
    primary_class: Optional[str] = None
    # Real attribute fields (Section 147, per direct request: "mopbs
    # must be able to wear gear too" -> confirmed full parity, not
    # just cosmetic). Baseline 10, same as a fresh player. strength/
    # dexterity/luck genuinely drive derived_stats.py's own real
    # formulas for mob combat now (see derive_mob_combat_attributes
    # and combat.py's own real hit/damage/dodge/crit resolution).
    # constitution/intelligence/wisdom are confirmed, deliberate
    # placeholders -- no real mechanical effect yet, matching how
    # Perception/Willpower already sit inert on players.
    strength: int = 10
    dexterity: int = 10
    intelligence: int = 10
    wisdom: int = 10
    luck: int = 10
    constitution: int = 10
    # A real, per-instance equipment dict (slot -> item name),
    # matching Player.equipment's own established shape exactly --
    # per-INSTANCE rather than per-template, since 'force <mob> wear'
    # equips one specific spawned mob, not every future copy of it.
    equipment: Dict[str, str] = field(default_factory=dict)
    chakra_nature: Optional[str] = None
    # Player shops (Section 75) -- which player this specific spawned
    # instance belongs to, if any. Per-INSTANCE, not per-template,
    # since every player shop reuses the same generic Shopkeeper
    # template but each has a different owner and stock.
    player_shop_owner: Optional[str] = None
    # Shadow Clone Jutsu (Section 78, per direct follow-up requests) --
    # which player this clone belongs to, if any. A real, independently
    # attackable Mob instance (not an abstract counter, per confirmed
    # design), using a per-CASTER template (see
    # _shadow_clone_template_vnum) so the clone's name/description
    # genuinely match that specific player, not a shared generic one.
    shadow_clone_owner: Optional[str] = None
    clone_element: str = "none"
    # Summoning contracts (Section 118, per direct request/
    # confirmation) -- which player this summon belongs to, if any,
    # and which real tier (data_summons.CONTRACT_TIERS, e.g.
    # "toad_3") it was summoned as. Mirrors shadow_clone_owner's own
    # established pattern exactly: a real, independently-attackable
    # Mob instance, not an abstract counter. summon_tier_key lets
    # combat resolve this specific summon's own unique mechanic (see
    # data_summons.tier_by_key) without needing to re-derive it from
    # the owner's current level, which could have changed since it
    # was actually summoned.
    summon_owner: Optional[str] = None
    summon_tier_key: Optional[str] = None
    # The Toad Stomach's own trap mechanic (Section 118, "trap"
    # tier mechanic) -- once applied to a mob, a real, meaningfully
    # large to-hit penalty against the player for the rest of that
    # fight. summon_trap_applied guards against re-applying (and
    # re-narrating) the same trap every single round.
    summon_trap_applied: bool = False
    summon_trap_to_hit_penalty: int = 0
    # Tailed Beasts (Section 127, per direct request/confirmation) --
    # which of the 9 real beasts (data_tailed_beasts.TAILED_BEASTS)
    # this specific live Mob instance is, or None for every ordinary
    # mob. tailed_beast_despawn_at is the real, absolute timestamp
    # this beast vanishes on its own if not sealed or killed by then
    # -- confirmed directly: a genuine 2 real hours from release.
    tailed_beast_key: Optional[str] = None
    tailed_beast_despawn_at: float = 0.0
    # The real "awaiting sealing" window (Section 127 continued, per
    # direct confirmation): once a beast reaches 0 HP, it's kept
    # alive/present here rather than being removed immediately --
    # this is the real, absolute timestamp it dies normally if nobody
    # casts the Sealing Jutsu on it in time. 0.0 means not currently
    # downed at all (either full health, or already resolved one way
    # or the other).
    tailed_beast_downed_until: float = 0.0
    # A genuine per-mob independent movement timer (Section 96, per
    # direct request: "mobs need to have their own movement timer
    # because they tend to shift all at once" -> confirmed to
    # "replace it with a real per-mob timer/cooldown"). Real Unix
    # timestamp -- 0.0 means "not yet scheduled", which
    # process_wander treats as "roll a fresh random interval right
    # now" the first time this mob is ever checked, so mobs spawned
    # at the exact same moment still desynchronize immediately rather
    # than sharing a starting value. Rescheduled with a fresh random
    # interval every time the mob actually wanders (see
    # WANDER_MIN_SECONDS/WANDER_MAX_SECONDS below).
    next_wander_at: float = 0.0


MOB_TEMPLATES: Dict[int, dict] = {}          # template_vnum -> full prototype dict
MOBS_BY_ROOM: Dict[int, List[Mob]] = {}       # room_vnum -> [Mob, ...]


def default_template(vnum: int, name: str = "a nondescript mob") -> dict:
    """A blank-ish prototype with every field defaulted -- what `mset
    create <vnum>` starts from, before individual `mset` field edits."""
    t = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
         for k, v in DEFAULT_MOB_FIELDS.items()}
    t["short_desc"] = name
    t["long_desc"] = f"{name.capitalize()} is here."
    t["keywords"] = name.split()
    return t


def register_template(vnum: int, name: str, level: int, max_health: int,
                       min_damage: int, max_damage: int,
                       experience_reward: int, ryo_reward: int,
                       loot_items: Optional[List[str]] = None) -> None:
    """Backward-compatible simple registration (used by content.py) --
    builds equivalent hit_dice/damage_dice strings so the mob still gets
    a full SMAUG-style prototype under the hood, visible via `mstat`."""
    t = default_template(vnum, name)
    t["level"] = level
    t["hit_dice"] = f"1d1+{max(0, max_health - 1)}"  # deterministic: 1d1 always rolls 1, so bonus = max_health - 1
    span = max(1, max_damage - min_damage + 1)
    t["damage_dice"] = f"1d{span}+{min_damage - 1}"  # rolls into [min_damage, max_damage]
    t["experience_reward"] = experience_reward
    t["ryo_reward"] = ryo_reward
    t["gold"] = ryo_reward
    t["loot_items"] = list(loot_items or [])
    MOB_TEMPLATES[vnum] = t


def mob_chakra_for_level(level: int) -> int:
    """Mirrors the player's own exact chakra growth (leveling.py:
    75 base at level 1, +CHAKRA_PER_LEVEL per level after) so a mob's
    resource pool feels consistent with a player at the same level."""
    import leveling
    return 75 + leveling.CHAKRA_PER_LEVEL * max(0, level - 1)


def mob_stamina_for_level(level: int) -> int:
    """Mirrors the player's own exact stamina growth (leveling.py:
    100 base at level 1, +STAMINA_PER_LEVEL per level after)."""
    import leveling
    return 100 + leveling.STAMINA_PER_LEVEL * max(0, level - 1)


def derive_mob_combat_attributes(hit_roll: int, damage_dice: str) -> tuple:
    """Per direct confirmation (Section 147): converts an EXISTING
    mob template's own real, hand-tuned flat combat values into the
    real attribute values that now drive mob combat math (see
    derived_stats.py's own real formulas, which every mob's combat
    resolution now goes through, matching a player's exact same
    math). Returns a real (strength, dexterity) tuple -- luck stays
    at the confirmed baseline of 10, since no existing mob field maps
    to it.

    dexterity = hit_roll + 10 (the real inverse of derived_stats.
    hit_roll's own dexterity - 10 formula) -- confirmed directly to
    take priority; armor_class is then whatever THIS SAME dexterity
    produces via derived_stats.armor_class, even where that changes
    an existing mob's own armor_class from what it is today.

    strength = 10 + dice.average(damage_dice) -- confirmed directly
    that the resulting damage_roll bonus stacks ON TOP of the
    existing damage_dice roll (not replacing it), a real, accepted
    damage increase across every existing mob as a deliberate side
    effect of this change."""
    import dice
    dexterity = hit_roll + 10
    strength = 10 + dice.average(damage_dice)
    return strength, dexterity


def spawn_mob(template_vnum: int, room_vnum: int) -> Optional[Mob]:
    t = MOB_TEMPLATES[template_vnum]
    if not t.get("enabled", True):
        return None
    max_hp = max(1, dice.roll(t["hit_dice"]))
    level = t["level"]
    max_chakra = mob_chakra_for_level(level)
    max_stamina = mob_stamina_for_level(level)
    import data_classes
    import biomes
    derived_strength, derived_dexterity = derive_mob_combat_attributes(t.get("hit_roll", 0), t["damage_dice"])
    mob = Mob(
        instance_id=next(_id_counter), template_vnum=template_vnum,
        name=t.get("short_desc") or f"mob {template_vnum}",
        level=level, health=max_hp, max_health=max_hp, room_vnum=room_vnum,
        experience_reward=t["experience_reward"], ryo_reward=t["ryo_reward"],
        damage_dice=t["damage_dice"], attacks=max(1, t.get("attacks", 1)),
        armor_class=t.get("armor_class", 0), hit_roll=t.get("hit_roll", 0),
        respawns=t.get("respawns", True), loot_items=list(t.get("loot_items", [])),
        chakra=max_chakra, maximum_chakra=max_chakra,
        stamina=max_stamina, maximum_stamina=max_stamina,
        primary_class=(t.get("primary_class") if t.get("primary_class") in data_classes.CLASSES
                       else None),
        chakra_nature=biomes.roll_chakra_nature(),
        strength=derived_strength, dexterity=derived_dexterity,
    )
    MOBS_BY_ROOM.setdefault(room_vnum, []).append(mob)
    return mob


def mobs_in_room(room_vnum: int) -> List[Mob]:
    return MOBS_BY_ROOM.get(room_vnum, [])


# Shopkeeper fields are looked up live from the mob's TEMPLATE, not
# cached on the Mob instance -- so a builder's `mset` edit (adding an
# item, changing shop_buys_categories, flipping the shopkeeper flag)
# takes effect immediately on already-placed instances, with no need
# to respawn them.
def is_shopkeeper(mob: Mob) -> bool:
    t = MOB_TEMPLATES.get(mob.template_vnum)
    return bool(t and t.get("shopkeeper", False))


def mob_shop_items(mob: Mob) -> List[int]:
    t = MOB_TEMPLATES.get(mob.template_vnum)
    return list(t.get("shop_items", [])) if t else []


def mob_shop_buys_categories(mob: Mob) -> List[str]:
    t = MOB_TEMPLATES.get(mob.template_vnum)
    return list(t.get("shop_buys_categories", [])) if t else []


# Gambler/dealer is its own independent flag -- unrelated to the
# shopkeeper system above (a mob can be a gambler, a shopkeeper, both,
# or neither). Looked up live from the template for the same reason as
# the shopkeeper fields: a builder's mset edit takes effect immediately
# on an already-placed mob, no respawn needed.
def is_gambler(mob: Mob) -> bool:
    t = MOB_TEMPLATES.get(mob.template_vnum)
    return bool(t and t.get("gambler", False))


# Teacher is its own independent flag -- see the DEFAULT_MOB_FIELDS
# comment for scope (flag only for now; actual teaching interaction is
# a future addition). Looked up live from the template for the same
# reason as shopkeeper/gambler.
def is_teacher(mob: Mob) -> bool:
    t = MOB_TEMPLATES.get(mob.template_vnum)
    return bool(t and t.get("teacher", ""))


def teacher_class(mob: Mob) -> str:
    """The class this mob teaches ("ninjutsu"/"taijutsu"/"genjutsu"/
    "bukijutsu"), per direct confirmation (Section 110: a teacher can
    only teach skills matching their own class). Returns "" if the
    mob isn't a teacher at all -- callers should check is_teacher(mob)
    first, or just treat an empty string as "no match" directly."""
    t = MOB_TEMPLATES.get(mob.template_vnum)
    return (t or {}).get("teacher", "")


def is_immortal_mob(mob: Mob) -> bool:
    """Per direct request/confirmation (Section 150): "add an
    immortal mob flag" -- a mob carrying the real Immortal act flag
    genuinely cannot be attacked at all (plain attack or jutsu-
    based), matching the exact real "protected and cannot be
    attacked" refusal already used for shopkeepers/gamblers/
    teachers. Looked up live from the template, same as every other
    act-flag check here, so a builder's mset edit takes effect
    immediately on an already-placed mob."""
    t = MOB_TEMPLATES.get(mob.template_vnum)
    if not t:
        return False
    return "Immortal" in t.get("act_flags", [])


def is_wandering(mob: Mob) -> bool:
    t = MOB_TEMPLATES.get(mob.template_vnum)
    if not t:
        return False
    act_flags = t.get("act_flags", [])
    if "Sentinel" in act_flags:
        return False  # a hard override, matching Sentinel's own documented meaning -- see olc.VALID_MOB_ACT_FLAGS
    return "Wander" in act_flags


def _mob_is_being_fought(mob: Mob) -> bool:
    import session as session_module  # local import -- avoids a circular dependency at module load
    return any(s.combat_target is mob for s in session_module.ACTIVE_SESSIONS)


def _broadcast_to_room(room_vnum: int, text: str) -> None:
    """Sends text to every playing session physically standing in
    room_vnum right now -- used for mob movement messages (process_
    wander below), which have no owning Session the way player
    movement (commands.cmd_move's own session.broadcast_room) does."""
    import session as session_module
    for s in session_module.ACTIVE_SESSIONS:
        if s.player and s.player.room_vnum == room_vnum:
            s.send(text)


WANDER_MIN_SECONDS = 120.0  # 2 minutes -- matches the previously confirmed target average (2-4 min)
WANDER_MAX_SECONDS = 240.0  # 4 minutes


def process_wander() -> None:
    """Called once per pulse (server.py's pulse loop). Per direct
    request/confirmation ("mobs need to have their own movement timer
    because they tend to shift all at once" -> "replace it with a
    real per-mob timer/cooldown"), this is now a genuine per-mob
    independent countdown (Mob.next_wander_at) rather than every
    wandering mob rolling against the same shared per-pulse chance --
    each mob schedules its OWN next possible move at a fresh random
    point 2-4 minutes out, entirely independent of every other mob's
    own timer, removing any possible source of correlated movement.

    Any mob flagged Wander (see olc.VALID_MOB_ACT_FLAGS) whose own
    timer has come due moves through a random exit from its current
    room, in whatever direction is available -- skipped if it's
    mid-combat, has no exits, or every exit leads to a disabled room
    (in which case its timer is still rescheduled, so it doesn't spam
    a check every single pulse forever). Sentinel is a hard override
    that always suppresses wandering, even alongside Wander (see
    is_wandering above).

    Broadcasts a departure message to the room being left and an
    arrival message (with the opposite direction, i.e. where it
    arrived FROM) to the room being entered, per direct request --
    matching the same messages commands.cmd_move already sends for a
    player's own movement."""
    now = time.time()
    for room_vnum in list(MOBS_BY_ROOM.keys()):
        for mob in list(MOBS_BY_ROOM.get(room_vnum, [])):
            if not is_wandering(mob):
                continue
            if mob.next_wander_at == 0.0:
                # Never scheduled yet -- roll a fresh, genuinely random
                # interval right now, so mobs spawned at the same instant
                # still desynchronize immediately rather than sharing a
                # starting value.
                mob.next_wander_at = now + random.uniform(WANDER_MIN_SECONDS, WANDER_MAX_SECONDS)
                continue
            if now < mob.next_wander_at:
                continue
            # This mob's own timer has come due -- reschedule its NEXT
            # check regardless of whether it actually manages to move
            # this time (mid-combat, no exits, etc. all still consume
            # this attempt rather than checking again next pulse).
            mob.next_wander_at = now + random.uniform(WANDER_MIN_SECONDS, WANDER_MAX_SECONDS)
            if _mob_is_being_fought(mob):
                continue
            room = world.WORLD.get(mob.room_vnum)
            if not room or not room.exits:
                continue
            candidates = [
                (direction, dest) for direction, dest in room.exits.items()
                if world.WORLD.get(dest) and world.WORLD.get(dest).enabled and not world.WORLD.get(dest).apartment
            ]
            if not candidates:
                continue
            direction, destination = random.choice(candidates)
            _broadcast_to_room(mob.room_vnum, f"{mob.name.capitalize()} leaves {direction}.")
            MOBS_BY_ROOM[mob.room_vnum].remove(mob)
            mob.room_vnum = destination
            MOBS_BY_ROOM.setdefault(destination, []).append(mob)
            _broadcast_to_room(destination, f"{mob.name.capitalize()} arrives from the {world.OPPOSITE_DIRECTION.get(direction, direction)}.")


def find_mob(room_vnum: int, query: str) -> Optional[Mob]:
    """Per direct confirmation (Section 158): a real "N.keyword" prefix
    (e.g. "2.bandit") targets the Nth mob in the room matching
    "bandit", 1-indexed -- the same general disambiguation convention
    now used everywhere a name can be typed to target something. A
    bare query with no real "N." prefix still means "the first
    match", exactly as before."""
    index, keyword = inventory.parse_indexed_query(query)
    keyword = keyword.lower()
    matches = [mob for mob in mobs_in_room(room_vnum) if keyword in mob.name.lower()]
    if index > len(matches):
        return None
    return matches[index - 1] if matches else None


def remove_mob(mob: Mob) -> None:
    room_mobs = MOBS_BY_ROOM.get(mob.room_vnum, [])
    if mob in room_mobs:
        room_mobs.remove(mob)
    if mob.respawns:
        # A mob ALSO covered by a real spawn point (Section 102) skips the
        # normal timer-based respawn entirely -- the spawn point's own
        # independent area-reset sweep is the single, sole mechanism
        # responsible for bringing it back in that case. Without this
        # check, a genuine double-spawn was caught by direct testing:
        # both mechanisms independently restoring the exact same mob,
        # completely uncoordinated with each other.
        import spawn_points
        already_covered = any(
            p["kind"] == "mob" and p["vnum"] == mob.template_vnum and p["room_vnum"] == mob.room_vnum
            for p in spawn_points.list_spawn_points(mob.room_vnum)
        )
        if not already_covered:
            # A fresh instance becomes available after config.MOB_RESPAWN_SECONDS,
            # tracked by the pulse loop via _respawn_queue.
            _respawn_queue.append((time.time() + config.MOB_RESPAWN_SECONDS, mob.template_vnum, mob.room_vnum))


_respawn_queue: List[tuple] = []


def process_respawns() -> None:
    now = time.time()
    ready = [r for r in _respawn_queue if r[0] <= now]
    for r in ready:
        _respawn_queue.remove(r)
        spawn_mob(r[1], r[2])


# --- Damage / attack resolution ------------------------------------------

def _player_attack_damage(player: Player) -> int:
    base = random.randint(3, 7)
    dmg = base + player.strength // 4
    import commands as commands_module
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    dmg += derived_stats.damage_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "damage_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player))
    dmg += commands_module.equipped_weapon_type_damage_bonus(player)
    dmg += commands_module.equipped_weapon_damroll_bonus(player)
    for skill, pct in player.skill_proficiencies.items():
        if data_passives.is_passive(skill):
            dmg = int(dmg * data_passives.damage_multiplier(skill, pct))
    import village_perks
    dmg = int(dmg * village_perks.damage_multiplier(player.village))
    return status_effects.reduce_outgoing_damage(player.active_status_effects, dmg)


def _mob_attack_damage(mob: Mob) -> int:
    import commands as commands_module
    base = dice.roll(mob.damage_dice)
    strength_bonus = derived_stats.damage_roll(mob)
    equipment_bonus = commands_module.equipped_weapon_damroll_bonus(mob) + commands_module.equipped_weapon_type_damage_bonus(mob)
    return status_effects.reduce_outgoing_damage(mob.active_status_effects, max(0, base + strength_bonus + equipment_bonus))


def start_attack(session, mob: Mob) -> None:
    session.combat_target = mob
    session.player.recently_defeated_timer = 0.0


class PendingCast:
    """A hand-sign casting delay in progress, per direct request/
    design ("lets put a lag time before doing jutsu while your
    casting so mastery of handsigns will lowere that lag time").
    is_pvp distinguishes a mob-target cast from a PvP one, since they
    resolve through 2 genuinely different functions
    (use_jutsu/use_jutsu_on_player) with different signatures.
    start_combat_on_resolve is True only when this cast was the thing
    that STARTED the fight (the player wasn't already fighting
    anything) -- confirmed design ("it will not initiate combat until
    the jutsu itself has landed damage or a failed attempt"): combat
    doesn't actually begin (session.combat_target/pvp_target get set,
    which is what turns on the automatic per-pulse attack) until this
    cast resolves, hit or miss, not the moment it's begun."""

    def __init__(self, jutsu_key: str, target, is_pvp: bool, remaining_seconds: float, start_combat_on_resolve: bool = False):
        self.jutsu_key = jutsu_key
        self.target = target
        self.is_pvp = is_pvp
        self.remaining_seconds = remaining_seconds
        self.start_combat_on_resolve = start_combat_on_resolve


def begin_pending_cast(session, jutsu_key: str, target, is_pvp: bool, start_combat_on_resolve: bool = False) -> None:
    """Starts the casting delay for jutsu_key, per confirmed design:
    only Ninjutsu/Genjutsu jutsu use hand signs at all
    (data_handsigns.has_handsigns) -- everything else (Taijutsu,
    Bukijutsu) resolves with NO delay at all, exactly as it already
    did before this feature existed. The delay itself is based on the
    caster's own current Handsigns proficiency (0 if they don't know
    Handsigns at all yet, e.g. below level 20 -- confirmed design:
    Handsigns is UNIVERSAL at level 20, so anyone casting one of
    these before that point gets the full, slowest delay).

    Confirmed design: the hand-sign sequence is broadcast to
    EVERYONE in the room as it's performed, not just the caster --
    deliberate groundwork for a future counter-jutsu system, not
    built yet ("this will play into counter jutsu later because a
    player can see their opponents handsigns").

    start_combat_on_resolve: per a later direct report ("it will not
    initiate combat until the jutsu itself has landed damage or a
    failed attempt"), a cast that STARTS a fight (the player wasn't
    already fighting anything) does not set combat_target/pvp_target
    here -- that only happens once the cast actually resolves, hit
    or miss (see tick_pending_casts), so no automatic per-pulse
    attack can fire during the delay window at all."""
    import data_handsigns
    jutsu = data_jutsu.JUTSU[jutsu_key]
    player = session.player
    mastery = player.skill_proficiencies.get("Handsigns", 0)
    delay = data_handsigns.casting_delay_seconds(mastery)
    signs = data_handsigns.sequence_for(jutsu_key)

    session.pending_cast = PendingCast(jutsu_key, target, is_pvp, delay, start_combat_on_resolve)
    session.send(f"&WYou begin forming hand signs: {' -> '.join(signs)}...&x")
    room = world.WORLD.get(player.room_vnum)
    if room:
        from session import ACTIVE_SESSIONS
        for other in ACTIVE_SESSIONS:
            if other is not session and other.state.name == "PLAYING" and other.player and other.player.room_vnum == player.room_vnum:
                other.send(f"&W{player.name} forms hand signs: {' -> '.join(signs)}...&x")


def _check_jutsu_collisions() -> None:
    """A genuine pre-pass, run once per pulse BEFORE any individual
    PendingCast resolves, per direct request/confirmation (Section
    97: "A counter jutsu should be an opposing element only" +
    "finishes within 1 second of the other" + "Both jutsu are
    cancelled -- neither deals its normal damage/effect to the
    intended target, only the room effect happens"). Finds every
    mutual PvP pair -- A's pending cast targets B AND B's pending
    cast targets A, both genuinely still in the same room -- whose
    delays will finish within elemental_counters.COLLISION_WINDOW_
    SECONDS of each other and whose jutsu are of OPPOSING elements
    (per the confirmed 5-way cycle, not just any two elements). If
    found, both casts are cancelled outright -- neither ever reaches
    the normal resolution path in tick_pending_casts -- and the
    pair's own themed collision message is sent to the room, plus a
    real, temporary room-description addition (world.Room.
    temp_description_text/temp_description_until)."""
    import elemental_counters
    import time as time_module
    from session import ACTIVE_SESSIONS

    candidates = []
    for session in ACTIVE_SESSIONS:
        cast = session.pending_cast
        if cast is None or session.state.name != "PLAYING" or not cast.is_pvp:
            continue
        jutsu = data_jutsu.JUTSU.get(cast.jutsu_key)
        if not jutsu or jutsu.get("element", "none") == "none":
            continue
        candidates.append(session)

    already_collided = set()
    for session in candidates:
        if session in already_collided:
            continue
        cast = session.pending_cast
        target_session = cast.target
        if target_session not in candidates or target_session in already_collided:
            continue
        other_cast = target_session.pending_cast
        # Mutual: the target's own pending cast must be aimed back at THIS caster.
        if other_cast.target is not session:
            continue
        if session.player.room_vnum != target_session.player.room_vnum:
            continue
        if abs(cast.remaining_seconds - other_cast.remaining_seconds) > elemental_counters.COLLISION_WINDOW_SECONDS:
            continue

        my_element = data_jutsu.JUTSU[cast.jutsu_key]["element"]
        their_element = data_jutsu.JUTSU[other_cast.jutsu_key]["element"]
        if not (elemental_counters.is_counter(my_element, their_element)
                or elemental_counters.is_counter(their_element, my_element)):
            continue

        # Genuine collision -- cancel BOTH casts outright first (the
        # overpower path below, if it applies, re-resolves the winning
        # side's own jutsu for real afterward).
        already_collided.add(session)
        already_collided.add(target_session)
        session.pending_cast = None
        target_session.pending_cast = None

        if elemental_counters.is_counter(my_element, their_element):
            elemental_winner_session, elemental_loser_session = session, target_session
            elemental_winner_cast, elemental_loser_cast = cast, other_cast
        else:
            elemental_winner_session, elemental_loser_session = target_session, session
            elemental_winner_cast, elemental_loser_cast = other_cast, cast
        winner, loser = elemental_winner_session.player.name, elemental_loser_session.player.name

        # Overpower check (Section 98): only the elementally-favored side can
        # ever overpower -- its own combined power score must clear the
        # OPPOSING side's by OVERPOWER_THRESHOLD or more.
        winner_mastery = elemental_winner_session.player.skill_proficiencies.get(
            data_jutsu.JUTSU[elemental_winner_cast.jutsu_key]["display_name"], 0)
        loser_mastery = elemental_loser_session.player.skill_proficiencies.get(
            data_jutsu.JUTSU[elemental_loser_cast.jutsu_key]["display_name"], 0)
        winner_score = elemental_counters.power_score(elemental_winner_session.player.level, winner_mastery)
        loser_score = elemental_counters.power_score(elemental_loser_session.player.level, loser_mastery)
        overpowered = (winner_score - loser_score) >= elemental_counters.OVERPOWER_THRESHOLD

        effect = elemental_counters.collision_effect(my_element, their_element)
        message = effect["message"].format(winner=winner, loser=loser)
        if overpowered:
            message += f" &D({winner}'s superior skill lets it punch through, landing with reduced force.)&x"

        room = world.WORLD.get(session.player.room_vnum)
        if room:
            room.temp_description_text = effect["room_text"]
            room.temp_description_until = time_module.time() + elemental_counters.TEMP_DESCRIPTION_DURATION_SECONDS
            for other in ACTIVE_SESSIONS:
                if other.state.name == "PLAYING" and other.player and other.player.room_vnum == room.vnum:
                    other.send(message)

        if overpowered:
            other_target_session = elemental_loser_session
            if (
                other_target_session.state.name == "PLAYING"
                and other_target_session.player
                and other_target_session.player.room_vnum == elemental_winner_session.player.room_vnum
                and other_target_session.player.health > 0
            ):
                use_jutsu_on_player(
                    elemental_winner_session, elemental_winner_cast.jutsu_key, other_target_session,
                    damage_multiplier=elemental_counters.OVERPOWER_DAMAGE_MULTIPLIER,
                )


def resolve_illusion_walk_cast(session, target_session, grow_handsigns: bool = True) -> None:
    """The real, actual effect of an Illusion Walk cast landing --
    shared by both the normal delayed-cast path (tick_pending_casts,
    grow_handsigns=True since real hand signs were formed) and the
    instant-cast path via the Silent Genjutsu passive (Section 122,
    grow_handsigns=False since no hand signs were genuinely formed at
    all with that passive active). See tracking's own docstring/
    commands.py's own cmd_use_jutsu for the full confirmed design."""
    player = session.player
    if (
        target_session.state.name != "PLAYING"
        or not target_session.player
        or target_session.player.room_vnum != player.room_vnum
        or target_session.player.health <= 0
    ):
        session.send("&DYour target is no longer there!&x")
        return
    import data_kekkei_genkai
    if data_kekkei_genkai.sharingan_genjutsu_resistant(target_session.player):
        session.send(f"&Y{target_session.player.name}'s eyes see through your illusion completely!&x")
        target_session.send(f"&Y{player.name} tries to trap you in a genjutsu, but your Sharingan sees through it!&x")
        if grow_handsigns:
            grow_skill_from_usage(player, "Handsigns")
        return
    proficiency = player.skill_proficiencies.get("Illusion Walk", 0)
    if proficiency >= 90:
        illusion_range = 3
    elif proficiency >= 50:
        illusion_range = 2
    else:
        illusion_range = 1
    target_session.player.illusion_walk_caster = player.name
    target_session.player.illusion_walk_real_room_vnum = target_session.player.room_vnum
    target_session.player.illusion_walk_range = illusion_range
    target_session.player.illusion_walk_steps_taken = 0
    session.send(f"&YYou trap {target_session.player.name} in an illusion of endless walking!&x")
    target_session.send(f"&R{player.name}'s eyes lock with yours -- something feels wrong.&x")
    if grow_handsigns:
        grow_skill_from_usage(player, "Handsigns")


def resolve_amaterasu_cast(session, target_session, grow_handsigns: bool = True) -> None:
    """The real, actual effect of an Amaterasu cast landing (Section
    140) -- shared by both the normal delayed-cast path
    (tick_pending_casts, grow_handsigns=True) and the instant-cast
    path via the Silent Genjutsu passive (grow_handsigns=False),
    matching resolve_illusion_walk_cast's own exact established
    pattern. Inflicts a real, genuinely PERMANENT burn on the target
    AND sets their current room ablaze too (everyone in it except the
    caster), per direct confirmation."""
    player = session.player
    if (
        target_session.state.name != "PLAYING"
        or not target_session.player
        or target_session.player.health <= 0
    ):
        session.send("&DYour target is no longer there!&x")
        return
    import data_mangekyo
    target_session.player.mangekyo_amaterasu_burning = True
    room = world.WORLD.get(target_session.player.room_vnum)
    if room is not None:
        room.amaterasu_fire_caster = player.name
        room.amaterasu_fire_expires_at = time.time() + data_mangekyo.AMATERASU_ROOM_FIRE_DURATION_SECONDS
    session.send(f"&RBlack flames erupt around {target_session.player.name} -- Amaterasu will burn until sealed.&x")
    target_session.send(f"&R{player.name}'s Amaterasu engulfs you in inextinguishable black flame!&x")
    if grow_handsigns:
        grow_skill_from_usage(player, "Handsigns")


def resolve_kamui_limb_removal_cast(session, target_session) -> None:
    """The real, actual effect of Kamui: Limb Removal landing (Section
    140), after its own genuinely long, custom real delay (see
    begin_kamui_limb_removal_cast) -- a real, one-time burst of high
    damage (data_mangekyo.KAMUI_LIMB_REMOVAL_DAMAGE), confirmed
    directly to NOT be a lingering effect, just a single, massive
    hit if the long cast actually completes."""
    player = session.player
    if (
        target_session.state.name != "PLAYING"
        or not target_session.player
        or target_session.player.room_vnum != player.room_vnum
        or target_session.player.health <= 0
    ):
        session.send("&DYour target is no longer there!&x")
        return
    import data_mangekyo
    import random
    dmg = random.randint(*data_mangekyo.KAMUI_LIMB_REMOVAL_DAMAGE)
    dmg = status_effects.reduce_incoming_damage(target_session.player.active_status_effects, dmg)
    target_session.player.health -= dmg
    session.send(f"&RYour blade tears through space itself, severing {target_session.player.name}'s limb for {damage_messages.describe_damage(dmg)} damage!&x")
    target_session.send(f"&R{player.name}'s Kamui rips your limb away in an instant of pure agony -- {damage_messages.describe_damage(dmg)} damage!&x")
    if target_session.player.health <= 0:
        if try_trigger_izanagi(target_session):
            pass
        elif is_immortal_immune_to_defeat(target_session):
            clamp_immortal_health(target_session)
        else:
            handle_pvp_defeat(winner_session=session, loser_session=target_session)


def resolve_izanami_cast(session, target_session, grow_handsigns: bool = True) -> None:
    """The real, actual effect of an Izanami cast landing (Section
    140) -- traps the target in place, genuinely immune to attack
    (confirmed directly), with a real, fixed random number from 1-25
    set ONCE right here and never changed again. The caster is
    completely free to act normally elsewhere while it's running
    (confirmed directly -- not tied up or restricted in any way), so
    this deliberately does nothing at all to the caster's own state."""
    player = session.player
    if (
        target_session.state.name != "PLAYING"
        or not target_session.player
        or target_session.player.health <= 0
    ):
        session.send("&DYour target is no longer there!&x")
        return
    import data_mangekyo
    import random
    target_session.player.izanami_trapped = True
    target_session.player.izanami_target_number = random.randint(
        data_mangekyo.IZANAMI_NUMBER_MIN, data_mangekyo.IZANAMI_NUMBER_MAX
    )
    session.send(f"&R{target_session.player.name} is pulled into a recursive loop of your own making.&x")
    target_session.send(
        f"&RTime folds in on itself -- you're trapped, reliving the same moment over and over. "
        f"Guess the number ({data_mangekyo.IZANAMI_NUMBER_MIN}-{data_mangekyo.IZANAMI_NUMBER_MAX}) to break free: 'guess <number>'&x"
    )
    if grow_handsigns:
        grow_skill_from_usage(player, "Handsigns")


def resolve_kekkei_no_me_cast(session, grow_handsigns: bool = True) -> None:
    """The real, actual effect of a Kekkei no Me cast landing (Section
    140) -- a genuinely no-target, self-cast jutsu (unlike every other
    Mangekyo technique built so far). Transforms the caster's own
    CURRENT room in place (confirmed directly -- no one moves
    anywhere) into their own real, active chakra-nature element,
    lasting a real 90 seconds. If the caster has no real chakra
    nature at all yet, refuses cleanly rather than transforming into
    a nonexistent element."""
    player = session.player
    if not player.chakra_nature:
        session.send("&DYour own chakra nature hasn't awakened yet -- there's nothing to draw on.&x")
        return
    room = world.WORLD.get(player.room_vnum)
    if room is None:
        session.send("&DSomething's wrong with this room -- contact a builder.&x")
        return
    import data_mangekyo
    room.kekkei_no_me_caster = player.name
    room.kekkei_no_me_element = player.chakra_nature
    room.kekkei_no_me_expires_at = time.time() + data_mangekyo.KEKKEI_NO_ME_DURATION_SECONDS
    session.send(f"&RThe room itself bends to your will, awash in your own {player.chakra_nature} nature.&x")
    for s in session.active_sessions():
        if s is not session and s.player and s.player.room_vnum == player.room_vnum:
            s.send(f"&R{player.name}'s domain consumes the room -- {player.chakra_nature} chakra saturates the air, draining you!&x")
    if grow_handsigns:
        grow_skill_from_usage(player, "Handsigns")


def resolve_tsukuyomi_cast(session, target_session, grow_handsigns: bool = True) -> None:
    """The real, actual effect of a Tsukuyomi cast landing (Section
    140) -- moves BOTH the caster and target into a shared, real
    torture room in one action (mangekyo.open_tsukuyomi), unlike
    Kamui's own 2-step entry. A real, hidden random number from 5-10
    is rolled inside open_tsukuyomi itself, setting how many of the
    caster's own actions the technique lasts."""
    player = session.player
    if (
        target_session.state.name != "PLAYING"
        or not target_session.player
        or target_session.player.health <= 0
    ):
        session.send("&DYour target is no longer there!&x")
        return
    import mangekyo
    import world as world_module
    mangekyo.open_tsukuyomi(session, target_session, world_module)
    session.send(f"&RYour world dissolves into crimson -- you and {target_session.player.name} are pulled into Tsukuyomi.&x")
    target_session.send(f"&R{player.name}'s eyes consume your reality -- you're trapped in Tsukuyomi, frozen and defenseless.&x")
    if grow_handsigns:
        grow_skill_from_usage(player, "Handsigns")


def tick_pending_casts() -> None:
    """Counts down every in-progress PendingCast by one pulse, and
    resolves any that have finished by actually calling the real
    use_jutsu/use_jutsu_on_player at that point -- confirmed design,
    the jutsu genuinely doesn't happen until the delay elapses, not
    just a delayed message. If the target is no longer valid (a mob
    already dead/gone, a PvP target who's disconnected or left the
    room) by the time the delay finishes, the cast simply fizzles
    with no resource refund.

    A genuine counter-jutsu collision (Section 97, see
    _check_jutsu_collisions) is checked BEFORE any individual cast
    below gets a chance to resolve this same pulse -- a collided cast
    has already had its own session.pending_cast cleared to None by
    that point, so it's silently skipped here, exactly like any other
    already-resolved cast would be."""
    _check_jutsu_collisions()
    from session import ACTIVE_SESSIONS
    for session in ACTIVE_SESSIONS:
        cast = session.pending_cast
        if cast is None or session.state.name != "PLAYING":
            continue
        cast.remaining_seconds -= 1.0
        if cast.remaining_seconds > 0:
            continue

        session.pending_cast = None
        player = session.player
        if data_jutsu.JUTSU.get(cast.jutsu_key, {}).get("jutsu_type") in ("disguise", "item_illusion", "item_decoy", "chisei", "room_sleep"):
            import genjutsu
            genjutsu.resolve_cast(session, cast.jutsu_key, cast.target)
            grow_skill_from_usage(player, "Handsigns")
            continue
        if cast.jutsu_key == "illusion walk":
            resolve_illusion_walk_cast(session, cast.target, grow_handsigns=True)
            continue
        if cast.jutsu_key == "tsukuyomi":
            resolve_tsukuyomi_cast(session, cast.target, grow_handsigns=True)
            continue
        if cast.jutsu_key == "amaterasu":
            resolve_amaterasu_cast(session, cast.target, grow_handsigns=True)
            continue
        if cast.jutsu_key == "kamui limb removal":
            resolve_kamui_limb_removal_cast(session, cast.target)
            continue
        if cast.jutsu_key == "izanami":
            resolve_izanami_cast(session, cast.target, grow_handsigns=True)
            continue
        if cast.jutsu_key == "kekkei no me":
            resolve_kekkei_no_me_cast(session, grow_handsigns=True)
            continue
        if cast.is_pvp:
            target_session = cast.target
            if (
                target_session.state.name != "PLAYING"
                or not target_session.player
                or target_session.player.room_vnum != player.room_vnum
                or target_session.player.health <= 0
            ):
                session.send("&DYour hand signs falter -- your target is no longer there!&x")
                continue
            if cast.start_combat_on_resolve and session.pvp_target is None:
                start_pvp_attack(session, target_session)
            use_jutsu_on_player(session, cast.jutsu_key, target_session)
        else:
            mob = cast.target
            if mob not in mobs_in_room(player.room_vnum) or mob.health <= 0:
                session.send("&DYour hand signs falter -- your target is no longer there!&x")
                continue
            if cast.start_combat_on_resolve and session.combat_target is None:
                start_attack(session, mob)
            use_jutsu(session, cast.jutsu_key, mob)
        grow_skill_from_usage(player, "Handsigns")


def tick_effects_pulse(session) -> None:
    """Tick a player's status effects and report expiries. Called once per
    server pulse for EVERY connected player regardless of combat state --
    this used to only happen inside resolve_pulse() (i.e. only while
    actively fighting), which meant an effect outside combat, or one that
    outlived the fight it was applied in, never ticked down at all.

    Applies the 3 elemental damage/drain-over-time effects (Burning,
    Drained, Off Balance) BEFORE the duration decrement below, so each
    one deals its damage/drain on every remaining round it's active,
    including its final one -- confirmed as a genuine standalone
    per-round timer, deliberately different from the existing Bleeding
    effect (which only ticks when the target is hit again in combat)."""
    player = session.player
    import genjutsu
    genjutsu.tick_player(session)
    if "burning" in player.active_status_effects:
        dmg = status_effects.burning_damage()
        dmg = status_effects.reduce_incoming_damage(player.active_status_effects, dmg)
        player.health = max(0, player.health - dmg)
        session.send(f"&RThe fire burns you for {damage_messages.describe_damage(dmg)} damage!&x")
    if "drained" in player.active_status_effects:
        loss = min(player.chakra, status_effects.drained_chakra_loss())
        player.chakra -= loss
        session.send(f"&CYour chakra is drained by {loss}!&x")
    if "off_balance" in player.active_status_effects:
        loss = min(player.stamina, status_effects.off_balance_stamina_loss())
        player.stamina -= loss
        session.send(f"&YBeing off balance saps {loss} stamina!&x")

    expired = status_effects.tick_effects(player.active_status_effects)
    for name in expired:
        if name == "chisei" and player.chisei_chakra_bonus:
            player.maximum_chakra -= player.chisei_chakra_bonus
            player.chakra = min(player.chakra, player.maximum_chakra)
            player.chisei_chakra_bonus = 0
        session.send(f"You are no longer {status_effects.EFFECT_DEFS[name]['display_name'].lower()}.")


def tick_all_mob_effects() -> None:
    """Tick every spawned mob's status effects, once per pulse, regardless
    of whether anyone is currently fighting them. Also applies the 3
    elemental damage/drain-over-time effects (mirroring
    tick_effects_pulse's own player-side logic) -- now that mobs have
    real chakra/stamina fields (Section 86) for Drained/Off Balance to
    meaningfully act on, not just players."""
    for room_mobs in MOBS_BY_ROOM.values():
        for mob in room_mobs:
            if "burning" in mob.active_status_effects:
                mob.health = max(0, mob.health - status_effects.burning_damage())
            if "drained" in mob.active_status_effects:
                mob.chakra = max(0, mob.chakra - status_effects.drained_chakra_loss())
            if "off_balance" in mob.active_status_effects:
                mob.stamina = max(0, mob.stamina - status_effects.off_balance_stamina_loss())
            status_effects.tick_effects(mob.active_status_effects)


PASSIVE_GROWTH_CHANCE_PCT = 20  # per combat round
PASSIVE_GROWTH_AMOUNT = 1


USAGE_GROWTH_PER_HIT = 2  # matches SHADOW_CLONE_MASTERY_GAIN_PER_CAST's own established rate, for consistency


def grow_skill_from_usage(player: Player, skill_name: str) -> None:
    """Gives skill_name a CHANCE to raise its proficiency by
    USAGE_GROWTH_PER_HIT, but ONLY if it's already at or past its own
    practice cap (see data_jutsu.PRACTICE_CAP_PERCENT/
    DEFAULT_PRACTICE_CAP_PERCENT) -- below the cap, practice remains
    the normal, faster (and still guaranteed) way to raise it, and
    growing from usage there too would make practice pointless.

    Past the cap, growth is a genuine roll, not a guarantee, per
    direct request/confirmation ("Let's make practice % much lower to
    succeed when using a skill so mastery actually means something" ->
    clarified and confirmed exactly: "Chance to gain = (100 -
    current%), so 98% mastery only has a 2% chance per use to tick up
    at all, while 10% mastery has a 90% chance"). The closer to 100%
    a skill already is, the rarer any further gain becomes -- this is
    what makes true mastery (100%) a genuinely long grind rather than
    a fixed number of guaranteed hits away, at any proficiency level.

    Confirmed design (\"Make it so every skill/jutsu can only be
    practiced up to 50% after that they must raise it via usage\"): a
    jutsu grows on a landed HIT (called from use_jutsu, right after
    damage is confirmed dealt); a weapon skill grows on ANY attack
    made while that weapon type is equipped, hit or miss (called from
    the player-attack helpers). Silently does nothing for a skill
    that isn't in player.learned_skills at all, or that's already at
    100% -- this is meant to be called unconditionally from every
    relevant combat path, not gated by the caller."""
    if skill_name not in player.learned_skills:
        return
    current = player.skill_proficiencies.get(skill_name, 0)
    if current >= 100:
        return
    practice_cap = data_jutsu.PRACTICE_CAP_PERCENT.get(skill_name, data_jutsu.DEFAULT_PRACTICE_CAP_PERCENT)
    if current < practice_cap:
        return
    if random.randint(1, 100) > (100 - current):
        return
    player.skill_proficiencies[skill_name] = min(100, current + USAGE_GROWTH_PER_HIT)


def tick_passive_skill_growth(player: Player) -> list:
    """Passive skills gain proficiency automatically from being in
    combat -- never from `practice`. Called once per combat round.
    Returns messages for any skill that just grew."""
    messages = []
    for skill in player.learned_skills:
        if not data_passives.is_passive(skill):
            continue
        current = player.skill_proficiencies.get(skill, 0)
        if current >= 100:
            continue
        if random.randint(1, 100) <= PASSIVE_GROWTH_CHANCE_PCT:
            new_pct = min(100, current + PASSIVE_GROWTH_AMOUNT)
            player.skill_proficiencies[skill] = new_pct
            messages.append(f"&D(Your {skill} improves through combat experience: {new_pct}%.)&x")
    return messages


SHADOW_CLONE_UPKEEP_PER_CLONE = 25  # chakra per clone, per round -- halved from the original 50, per direct request ("Reduce bunching drain on chakra by half")
SHADOW_CLONE_HEALTH_PERCENT_OF_OWNER = 25  # confirmed design ("1/4 the players go") -- a clone's HP pool is a flat 25% of the CASTER's own current max health, fixed at summon time
SUMMON_HP_PER_LEVEL = 8  # flat HP per summoner level, multiplied by the tier's own base_modifier -- see combat.stat_for_summon_tier / data_summons.py's own docstring for the confirmed "level x modifier" design
SUMMON_DAMAGE_PER_LEVEL = 1.2  # flat damage per summoner level, multiplied by the tier's own base_modifier -- same formula, different flat scale, since a summon's own real per-hit damage should be meaningfully smaller than its own HP pool
TOAD_STOMACH_MOB_TO_HIT_PENALTY = 30  # a real, meaningfully large percentage-point penalty to a TRAPPED mob's own to-hit chance -- the Toad Stomach's whole point is battlefield control, not damage


def shadow_clone_count_for_mastery(mastery_pct: int) -> int:
    """How many clones Shadow Clone Jutsu actually summons, based on
    the caster's OWN mastery percent in that jutsu -- confirmed design
    ("The more mastery of this jutsu allows up to a max of 100% is 3
    clones"). An even 3-way split of the 0-100% range: under 34% is 1
    clone, 34-66% is 2, 67% and up is the full 3."""
    if mastery_pct >= 67:
        return 3
    if mastery_pct >= 34:
        return 2
    return 1


def _shadow_clone_template_vnum(player) -> int:
    """A fake, negative, per-CASTER vnum -- genuinely unique per
    player (never collides with any real, positive-vnum mob/item in
    the game), used only internally as this player's own personal
    clone template. Rebuilt fresh on every cast (see
    _register_shadow_clone_template) so a clone's look/examine text
    always reflects whatever the caster's OWN name/description
    currently is, even if it changed since an earlier clone from the
    same player was summoned."""
    return -1_000_000 - (abs(hash(player.name)) % 1_000_000)


def _register_shadow_clone_template(player) -> int:
    """(Re)builds this player's own personal shadow-clone template --
    short_desc/keywords set to the player's OWN exact name (confirmed
    design: "genuinely indistinguishable at a glance", not "<name>'s
    shadow clone"), long_desc/description mirroring the player's own
    current description text. Rebuilt on every single cast rather
    than cached, so it can never go stale if the player's own
    description changes between casts. act_flags includes "Sentinel"
    (no wander -- a clone should stay put, not roam off) plus a
    dedicated "ShadowClone" flag used only to detect/skip these mobs
    in display code that needs to treat them specially (the health-%
    room-listing suppression -- see commands.cmd_look)."""
    vnum = _shadow_clone_template_vnum(player)
    template = default_template(vnum, player.name)
    template["short_desc"] = player.name
    template["long_desc"] = f"{player.name} is here."
    template["description"] = player.description if player.description else f"You see nothing special about {player.name}."
    template["keywords"] = [player.name]
    template["level"] = player.level
    template["act_flags"] = ["Npc", "Sentinel", "ShadowClone"]
    template["experience_reward"] = 0
    template["ryo_reward"] = 0
    MOB_TEMPLATES[vnum] = template
    return vnum


def is_shadow_clone(mob) -> bool:
    """Whether a spawned Mob instance is a shadow clone, for display
    code that needs to treat these specially (see
    commands.cmd_look's room-listing health-% suppression, confirmed
    design: a clone's line in a room listing must look exactly like a
    real player's, with no health-% tag at all)."""
    return bool(mob.shadow_clone_owner)


def spawn_shadow_clones(player, count: int, element: str = "none") -> List["Mob"]:
    """Spawns `count` real, independently-attackable Mob instances in
    the CASTER's own current room, each a genuine copy of the
    caster's name/description via _register_shadow_clone_template,
    each with a fixed HP pool of SHADOW_CLONE_HEALTH_PERCENT_OF_OWNER%
    of the caster's own CURRENT max health (confirmed design -- set
    once at summon time, not tied to the caster's health changing
    afterward). Does NOT dismiss any pre-existing clones first --
    callers are expected to have already called dismiss_shadow_clones
    if replacing an earlier batch (see use_shadow_clone_jutsu)."""
    vnum = _register_shadow_clone_template(player)
    clone_hp = max(1, player.maximum_health * SHADOW_CLONE_HEALTH_PERCENT_OF_OWNER // 100)
    clones = []
    for _ in range(count):
        clone = spawn_mob(vnum, player.room_vnum)
        if clone is None:
            continue
        clone.health = clone_hp * (2 if element == "sand" else 1)
        clone.max_health = clone.health
        clone.shadow_clone_owner = player.name
        clone.clone_element = element
        if element != "none":
            clone.name = f"{player.name}'s {element} clone"
        clone.respawns = False  # a popped clone never comes back on its own -- only a fresh cast makes more
        clones.append(clone)
    return clones


def dismiss_shadow_clones(player) -> int:
    """Removes every currently-summoned clone belonging to this
    player from whatever room each one is actually in (a clone may
    have been left behind if the player moved rooms after summoning
    them -- confirmed design: clones persist independently, not
    bound to follow the caster around). Returns how many were
    removed. Safe to call even if the player has no clones at all
    (returns 0)."""
    removed = 0
    for room_vnum, room_mobs in list(MOBS_BY_ROOM.items()):
        still_here = []
        removed_here = 0
        for mob in room_mobs:
            if mob.shadow_clone_owner == player.name:
                removed_here += 1
            else:
                still_here.append(mob)
        if removed_here:
            MOBS_BY_ROOM[room_vnum] = still_here
            removed += removed_here
    return removed


def active_shadow_clones(player) -> List["Mob"]:
    """Every currently-live clone belonging to this player, across
    every room (a clone doesn't follow the caster if they move away
    from it -- see dismiss_shadow_clones' own note). Used for the
    per-round upkeep tick and the caster's own combat-round attack
    loop, both of which need the real, live set rather than a cached
    count that could go stale the moment a clone is popped by someone
    else's attack."""
    return [
        mob for room_mobs in MOBS_BY_ROOM.values() for mob in room_mobs
        if mob.shadow_clone_owner == player.name
    ]


def _summon_template_vnum(tier_key: str) -> int:
    """A fake, negative, per-TIER vnum -- genuinely distinct from the
    shadow clone range (-1,000,000 to -2,000,000, see
    _shadow_clone_template_vnum) so the two can never collide.
    Per-tier rather than per-caster (unlike a shadow clone), since
    every player's own Gamabunta should look identical -- a fixed
    offset from a large negative base, keyed only by the tier's own
    stable string key."""
    return -3_000_000 - (abs(hash(tier_key)) % 1_000_000)


def _register_summon_template(tier: dict) -> int:
    """(Re)builds the real mob template for one specific summon tier
    (see data_summons.CONTRACT_TIERS) -- short_desc/keywords/
    long_desc genuinely reflect that tier's own real display_name
    (e.g. "Gamabunta"), not the summoner's own name, since this is a
    per-tier template shared by every player who ever summons that
    same tier. act_flags includes "Sentinel" (no wander) plus a
    dedicated "Summon" flag, mirroring ShadowClone's own established
    display-suppression convention (see commands.cmd_look)."""
    vnum = _summon_template_vnum(tier["key"])
    template = default_template(vnum, tier["display_name"])
    template["short_desc"] = tier["display_name"]
    template["long_desc"] = f"{tier['display_name']} is here, ready to fight alongside its summoner."
    template["description"] = f"A real, living {tier['display_name']}, bound by summoning contract."
    template["keywords"] = tier["display_name"].lower().split()
    template["act_flags"] = ["Npc", "Sentinel", "Summon"]
    template["experience_reward"] = 0
    template["ryo_reward"] = 0
    MOB_TEMPLATES[vnum] = template
    return vnum


def stat_for_summon_tier(summoner_level: int, tier: dict, per_level: float) -> int:
    """The real, level-scaled stat formula confirmed directly
    ("the strength of the toad is at your currently level x any
    summon appropriate base modifier") -- the SUMMONER's own current
    level, times a flat per-stat scale, times that tier's own
    base_modifier (a higher-tier/rarer summon has a higher modifier,
    so two summons at the same summoner level are still genuinely
    different in real strength). Always at least 1, so a very
    low-level summoner's summon is never truly stat-less."""
    return max(1, round(summoner_level * per_level * tier["base_modifier"]))


def dismiss_summon(player) -> int:
    """Removes this player's own currently-active summon (there is
    ever only ONE, per direct confirmation: "A real, single summon at
    a time -- summoning a new one dismisses whatever was already
    there") from whatever room it's actually in. Returns how many
    were removed (0 or 1 -- a list-based removal for genuine symmetry
    with dismiss_shadow_clones' own return shape, even though only
    one can ever exist). Safe to call with no active summon at all."""
    removed = 0
    for room_vnum, room_mobs in list(MOBS_BY_ROOM.items()):
        still_here = []
        removed_here = 0
        for mob in room_mobs:
            if mob.summon_owner == player.name:
                removed_here += 1
            else:
                still_here.append(mob)
        if removed_here:
            MOBS_BY_ROOM[room_vnum] = still_here
            removed += removed_here
    return removed


def reset_summon_round_state(player) -> None:
    """Clears the per-fight summon flags (Section 118) -- Manda's own
    flee-lock and Enma's own weapon buff -- the instant a real PvE
    fight actually ends, whichever way it ends (the mob died, the
    player was defeated, the mob was left behind, or the mob was
    somehow already gone). Called from every genuine "PvE fight has
    ended" moment, so a bind or weapon buff from one fight can never
    bleed into a completely unrelated later one. Does NOT touch the
    active summon itself (see dismiss_summon for that) -- a summon
    stays out across fights until genuinely dismissed or replaced,
    matching the same persistence Shadow Clone Jutsu's own clones
    already have."""
    player.summon_flee_locked = False
    player.summon_weapon_buff_active = False


def active_summon(player):
    """This player's own currently-active summon Mob, or None. There
    is ever only one (see dismiss_summon's own docstring), so this
    returns a single Mob (or None), not a list."""
    for room_mobs in MOBS_BY_ROOM.values():
        for mob in room_mobs:
            if mob.summon_owner == player.name:
                return mob
    return None


def spawn_summon(player, tier: dict) -> "Mob":
    """Summons a real, independently-attackable Mob instance of the
    given tier (see data_summons.CONTRACT_TIERS) into the player's
    OWN current room. Does NOT dismiss any pre-existing summon first
    -- callers are expected to have already called dismiss_summon if
    replacing an earlier one (see use_summoning_jutsu), mirroring
    spawn_shadow_clones' own established convention exactly. HP/
    damage are both derived from stat_for_summon_tier, fixed at
    summon time (not tied to the summoner's own level changing
    afterward, matching the same "set once" precedent shadow clones
    already established)."""
    vnum = _register_summon_template(tier)
    hp = stat_for_summon_tier(player.level, tier, SUMMON_HP_PER_LEVEL)
    mob = spawn_mob(vnum, player.room_vnum)
    if mob is None:
        return None
    mob.health = hp
    mob.max_health = hp
    mob.summon_owner = player.name
    mob.summon_tier_key = tier["key"]
    mob.respawns = False  # a popped/dismissed summon never comes back on its own -- only a fresh cast makes a new one
    return mob


def tick_shadow_clone_upkeep(player) -> list:
    """Charges the CURRENTLY LIVE set of this player's clones (see
    active_shadow_clones) their per-round chakra upkeep (see
    SHADOW_CLONE_UPKEEP_PER_CLONE). Called every pulse regardless of
    combat state (confirmed design: "Clones can be summoned before
    combat and persist until unsigned or chakra runs out") -- matching
    tick_effects_pulse's own established always-ticks precedent, NOT
    gated behind resolve_pulse/combat state the way this used to be
    when clones were still an abstract counter. If the player can't
    afford the full upkeep for every currently-live clone, clones are
    dismissed one at a time (cheapest possible response to a chakra
    shortfall) until what remains is affordable, rather than an
    all-or-nothing dismissal."""
    clones = active_shadow_clones(player)
    if not clones:
        return []
    messages = []
    while clones:
        cost = len(clones) * SHADOW_CLONE_UPKEEP_PER_CLONE
        if player.chakra >= cost:
            player.chakra -= cost
            messages.append(f"&CYour {len(clones)} shadow clone{'s' if len(clones) != 1 else ''} use {cost} chakra to remain active.&x")
            return messages
        popped = clones.pop()
        room_mobs = MOBS_BY_ROOM.get(popped.room_vnum, [])
        if popped in room_mobs:
            room_mobs.remove(popped)
        if clones:
            messages.append(f"&RYou don't have enough chakra to sustain all your shadow clones -- one dispels! ({len(clones)} remaining.)&x")
        else:
            messages.append("&RYou don't have enough chakra to sustain your shadow clone -- it dispels!&x")
    return messages


def tick_sharingan_upkeep(player) -> list:
    """Charges the Sharingan's per-round chakra+stamina upkeep while
    commands.cmd_sharingan has it toggled on (see that command for the
    ability itself; the actual dodge bonus is applied at the two
    dodge_chance call sites in resolve_pulse/resolve_pvp_pulse below,
    not here). Chakra cost scales down with tomoe count (commands.
    sharingan_chakra_upkeep) -- less taxing with more tomoe open, per
    direct request; stamina cost stays flat regardless of tomoe count.
    Called once per combat round, same pattern as
    tick_passive_skill_growth above. If the player can't afford the
    upkeep, it turns itself off automatically rather than draining a
    resource into the negatives. Idle upkeep is charged separately by
    regen.tick_sharingan_idle."""
    if not player.sharingan_active:
        return []
    import commands
    chakra_cost = commands.sharingan_chakra_upkeep(player.bloodline_tomoe)
    if player.chakra < chakra_cost or player.stamina < commands.SHARINGAN_STAMINA_UPKEEP:
        player.sharingan_active = False
        return ["&RYour chakra and stamina give out -- your Sharingan fades back to black.&x"]
    player.chakra -= chakra_cost
    player.stamina -= commands.SHARINGAN_STAMINA_UPKEEP
    return [f"&CYour Sharingan uses {chakra_cost} chakra and {commands.SHARINGAN_STAMINA_UPKEEP} stamina to remain active.&x"]


def tick_sharingan_mastery_gain(player) -> list:
    """Rolls the Sharingan's small, Talent-scaled per-round chance to
    gain mastery (data_kekkei_genkai.tick_mastery_gain) while it's
    actively toggled on -- per explicit design confirmation, only once
    the bloodline is already formally awakened (bloodline_awakened),
    it doesn't silently accumulate before that. Called once per combat
    round, same pattern as tick_sharingan_upkeep above -- costs
    nothing and rolls nothing at all while not actively fighting.
    Silent on every round that doesn't cross a new tomoe threshold;
    only narrates the discrete, already-player-visible milestone of
    gaining a new tomoe, never a raw mastery number or percentage --
    same security posture the rest of this framework was built
    around, see data_kekkei_genkai.py's own docstring."""
    if not player.sharingan_active or not player.bloodline_awakened:
        return []
    import data_kekkei_genkai
    result = data_kekkei_genkai.tick_mastery_gain(player)
    if result["tomoe_increased"]:
        return [f"&RYour Sharingan sharpens -- you now command {result['new_tomoe']} tomoe.&x"]
    return []


def tick_automatic_bloodline_awakening(player) -> list:
    """"The first quest" -- the real, live, automatic awakening
    check, per direct request/confirmation (Section 112: "turn the
    sharingan unlock quest into something that is automatic that has
    a chance of awakening... this is the first quest not the
    second"). Called once per combat round (both PvE and PvP), same
    pattern as tick_sharingan_upkeep/tick_sharingan_mastery_gain
    above -- rolls nothing and costs nothing at all while not
    actively fighting, matching direct confirmation this should only
    ever trigger in combat.

    Applies to any of the 5 kekkei genkai, not just Sharingan (see
    data_kekkei_genkai.attempt_automatic_awakening's own docstring
    for the full eligibility/chance design). On a genuine awakening,
    the player themselves gets a real narration line, AND every
    other connected, playing session gets a genuinely global
    broadcast -- confirmed exact wording, deliberately generic so it
    never reveals WHICH of the 5 bloodlines actually awakened,
    matching the hidden-by-design posture the rest of this framework
    already has."""
    import data_kekkei_genkai
    result = data_kekkei_genkai.attempt_automatic_awakening(player)
    if not result["awakened_this_call"]:
        return []

    import session as session_module
    for s in session_module.ACTIVE_SESSIONS:
        if s.state.name == "PLAYING":
            s.send(f"&Y{player.name}'s bloodline has awakened!&x")
            s.send_prompt()
    return ["&RSomething within you stirs and awakens -- your bloodline has awakened!&x"]


def _jutsu_damage_bonus(player: Player) -> int:
    """The stat/equipment-driven bonus added ON TOP of a jutsu's own
    base damage roll (roll_jutsu_damage), per direct correction
    ("justsu damage should be based on strength and a players
    damroll + weapon damroll + weapon damage"). Mirrors the FULL
    stat/equipment contribution a regular weapon attack gets
    (_player_attack_damage) -- Strength's own direct contribution,
    the real player-level damroll (derived_stats.damage_roll, a
    genuine pre-existing Strength-based derived stat that had never
    actually been wired into ANY combat path before this turn -- now
    fixed for both regular attacks and jutsu at once, confirmed
    directly), the wielded weapon's own intrinsic damage-by-type
    bonus, and the wielded weapon's own damroll bonus. Everything
    except the base 3-7 roll (the jutsu already supplies its own base
    via roll_jutsu_damage) and passive multipliers (jutsu apply their
    own separate multiplier chain already, in use_jutsu/
    use_jutsu_on_player, not here)."""
    import commands as commands_module
    import data_personality
    import tailed_beasts
    bonus = player.strength // 4
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    bonus += derived_stats.damage_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "damage_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player))
    bonus += commands_module.equipped_weapon_type_damage_bonus(player)
    bonus += commands_module.equipped_weapon_damroll_bonus(player)
    return bonus


def _kekkei_no_me_damage_multiplier(player: Player, jutsu: dict) -> float:
    """The real, confirmed +50% damage multiplier (Section 140,
    data_mangekyo.KEKKEI_NO_ME_ELEMENT_DAMAGE_BONUS_PCT) for the
    caster's own jutsu, ONLY while standing in a room they themselves
    transformed with Kekkei no Me, AND only when the jutsu being cast
    genuinely matches that room's own element. Checked live at the
    moment of each real cast (not precomputed/cached), since the room
    could expire or the caster could leave between casts. Returns
    1.0 (no change) in every other case."""
    room = world.WORLD.get(player.room_vnum)
    if room is None or room.kekkei_no_me_caster != player.name:
        return 1.0
    if jutsu.get("element") != room.kekkei_no_me_element:
        return 1.0
    import data_mangekyo
    return 1.0 + (data_mangekyo.KEKKEI_NO_ME_ELEMENT_DAMAGE_BONUS_PCT / 100.0)


def roll_jutsu_damage(jutsu: dict) -> "tuple[int, bool]":
    """Rolls this jutsu's damage, returning (amount, was_explosive).
    Every ordinary jutsu (no "explosive_chance_pct" field at all)
    just rolls its own damage range normally, was_explosive always
    False. Explosive Tag Kunai is the one confirmed exception -- a
    SINGLE roll picks EITHER the normal damage range OR the bigger
    explosive_damage range, never both on the same throw (confirmed
    design: "A single roll picks ONE outcome")."""
    if "explosive_chance_pct" in jutsu and random.randint(1, 100) <= jutsu["explosive_chance_pct"]:
        lo, hi = jutsu["explosive_damage"]
        return random.randint(lo, hi), True
    lo, hi = jutsu["damage"]
    return random.randint(lo, hi), False


def _genjutsu_hit_bonus(player, jutsu):
    return 12 if jutsu.get("class_requirement") == "genjutsu" and "chisei" in player.active_status_effects else 0


def _mirror_illusion_damage(jutsu, target, rolled):
    """Insect Eyes reflects the opponent's actual offensive strength."""
    if jutsu.get("jutsu_type") != "mirror":
        return rolled
    if isinstance(target, Mob):
        import dice
        return max(1, rolled + dice.average(target.damage_dice) * max(1, target.attacks))
    return max(1, rolled + max(0, derived_stats.damage_roll(target)) + max(1, target.strength // 3))


def _genjutsu_impact(jutsu, target):
    if jutsu.get("stamina_drain"):
        target.stamina = max(0, target.stamina - jutsu["stamina_drain"])


def _try_counter_kunai(session, target_session, target, attacker_name: str, jutsu_display_name: str) -> bool:
    """Whether target (a player defending against a jutsu_type
    "thrown" attack) successfully blocks it with Counter Kunai --
    confirmed design: works against ANY thrown jutsu (Throw Shuriken/
    Throw Kunai/Explosive Tag Kunai), not just kunai-specific ones;
    fully blocks (zero damage), not a reduction; consumes one of the
    DEFENDER'S OWN kunai from their inventory, same requires_item
    convention as the attacking jutsu itself. Returns False (does
    nothing at all) if the defender doesn't know Counter Kunai or
    isn't carrying a kunai right now -- this is genuinely passive, so
    a defender with no kunai on hand just takes the hit normally,
    exactly as if this ability didn't exist for them this time."""
    if "Counter Kunai" not in target.learned_skills:
        return False
    held_kunai = next((item for item in target.inventory if "kunai" in item.lower()), None)
    if not held_kunai:
        return False
    target.inventory.remove(held_kunai)
    session.send(f"&C{target.name} whips out a kunai and deflects your {jutsu_display_name} completely!&x")
    target_session.send(f"&CYou whip out a kunai and deflect {attacker_name}'s {jutsu_display_name} completely!&x")
    return True


def _sharingan_dodge_bonus(defender) -> int:
    """The Sharingan's active dodge bonus (see commands.
    cmd_sharingan/tick_sharingan_upkeep above) for whoever is about to
    be attacked -- 0 if they don't have it toggled on right now.
    Amplified at tomoe 6 (the capstone stage), per the fuller
    progression table's "major perception/combat bonus" description."""
    import commands
    if not defender.sharingan_active:
        return 0
    if defender.bloodline_tomoe >= 6:
        return commands.SHARINGAN_DODGE_BONUS_PERCENT_TOMOE_6
    return commands.SHARINGAN_DODGE_BONUS_PERCENT


def _accuracy_penalty_from_effects(attacker) -> int:
    """The total to-hit percentage penalty from every active status
    effect on the attacker that carries an "accuracy_penalty" field
    (narakumi, and the older "confused" effect -- defined with this
    same field for years but never actually wired into any of the
    game's to-hit calculations until now). Returns a POSITIVE number
    meant to be SUBTRACTED at the call site, matching how every other
    to_hit modifier here is a plain additive term (this one's just
    negative). Works for both a player attacker and a mob attacker --
    both carry active_status_effects in the same shape."""
    total = 0
    for name, effect_state in attacker.active_status_effects.items():
        defn = status_effects.EFFECT_DEFS.get(name, {})
        total += defn.get("accuracy_penalty", 0)
    return total


def _is_action_blocked(attacker) -> bool:
    """Whether attacker's active status effects include one that
    carries blocks_action=True (stunned, genjutsu_locked, and the new
    paralyzed) -- confirmed and wired for real (Section 87), the same
    "documented but never actually checked" gap already found and
    fixed once this session for accuracy_penalty. Confirmed design:
    checked at PER-ROUND attack resolution (both a regular attack and
    a jutsu cast), not the initial attack/perform command -- an
    already-ongoing fight continues normally, individual rounds are
    what get skipped while blocked. Works for both a player and a mob
    attacker, both carry active_status_effects in the same shape.

    Also checks tsukuyomi_frozen (Section 140, per direct
    confirmation: the target is genuinely frozen in place, unable to
    act, for the whole real duration) -- a direct Player field rather
    than a generic status effect, since it's tied to a real, active
    Mangekyo technique rather than an ordinary combat status."""
    if getattr(attacker, "tsukuyomi_frozen", False):
        return True
    for name in attacker.active_status_effects:
        if status_effects.EFFECT_DEFS.get(name, {}).get("blocks_action", False):
            return True
    return False


def _sharingan_hitroll_bonus(attacker) -> int:
    """The 3-tomoe Sharingan's active hitroll bonus for whoever is
    about to attack -- 0 unless they're actively toggled on AND have
    reached at least 3 tomoe (data_kekkei_genkai.tick_mastery_gain),
    per direct design confirmation. Same shape as _sharingan_dodge_
    bonus above, just offense instead of defense. Amplified at tomoe 6
    (the capstone stage)."""
    import commands
    if not (attacker.sharingan_active and attacker.bloodline_tomoe >= 3):
        return 0
    if attacker.bloodline_tomoe >= 6:
        return commands.SHARINGAN_HITROLL_BONUS_PERCENT_TOMOE_6
    return commands.SHARINGAN_HITROLL_BONUS_PERCENT


SUMMON_WEAPON_BUFF_HITROLL_BONUS = 15
SUMMON_WEAPON_BUFF_DAMAGE_PERCENT = 20

def _summon_weapon_buff_hitroll_bonus(attacker) -> int:
    """Enma's own real "weapon_buff" mechanic (Section 118) -- a flat
    hitroll bonus for whoever currently has an active weapon-buff
    summon out, checked the same inline way _sharingan_hitroll_bonus
    already is. 0 for anyone without the flag set (see combat.
    _resolve_summon_round, the only place that ever sets it)."""
    return SUMMON_WEAPON_BUFF_HITROLL_BONUS if attacker.summon_weapon_buff_active else 0


def _summon_weapon_buff_damage_percent(attacker) -> int:
    """Enma's own real damage-side bonus, applied as a genuine
    percentage increase to the attacker's own raw damage roll --
    0 for anyone without the flag set."""
    return SUMMON_WEAPON_BUFF_DAMAGE_PERCENT if attacker.summon_weapon_buff_active else 0


def _sharingan_predict_and_reduce_damage(defender, dmg: int) -> int:
    """The 3-tomoe Sharingan's Movement Prediction perk, per direct
    design confirmation ("chance outside of dodge to block an attack
    but not dodge... when it fails it will say you weren't fast enough
    to counter" / "reduces damage by a set amount/percentage rather
    than blocking it entirely"). Callers are expected to only call
    this AFTER the normal dodge roll has already failed -- Prediction
    is a genuinely separate roll, not a second chance at the same
    dodge, and it never fully negates the attack the way a dodge does,
    only cuts its damage. Returns the (possibly reduced) damage
    unchanged if the player doesn't have Prediction available at all
    (not actively toggled, or under 3 tomoe) or the roll itself
    fails -- callers distinguish the two cases by comparing the
    returned value to the original `dmg` they passed in, same pattern
    already used elsewhere in this module rather than a separate
    boolean return. The chance itself is amplified at tomoe 6 (the
    capstone stage, "Sharingan Insight / Predictive Counter" per the
    fuller progression table) -- the damage reduction percentage
    stays the same throughout, only the odds of triggering it improve."""
    import commands
    if not (defender.sharingan_active and defender.bloodline_tomoe >= 3):
        return dmg
    chance = (
        commands.SHARINGAN_PREDICTION_CHANCE_PERCENT_TOMOE_6
        if defender.bloodline_tomoe >= 6
        else commands.SHARINGAN_PREDICTION_CHANCE_PERCENT
    )
    if random.randint(1, 100) <= chance:
        return int(dmg * (1 - commands.SHARINGAN_PREDICTION_DAMAGE_REDUCTION_PERCENT / 100))
    return dmg


def _roll_extra_attacks(player) -> int:
    """How many EXTRA attacks (beyond the guaranteed first) a player
    gets this combat round, per explicit request for Second/Third/
    Fourth/Fifth Attack (data_jutsu.MULTI_ATTACK_SKILLS). Cascading,
    not four independent rolls -- Third Attack is only even attempted
    if Second Attack's own roll already succeeded this round
    (thematically, a third swing shouldn't happen without a second one
    landing first), and so on down the chain. Each skill's own
    proficiency is its % chance of triggering -- a freshly-granted
    skill at 0% contributes nothing until trained up."""
    extra = 0
    for skill_name, _level_req, _required_class in data_jutsu.MULTI_ATTACK_SKILLS:
        if skill_name not in player.learned_skills:
            break
        proficiency = player.skill_proficiencies.get(skill_name, 0)
        if random.randint(1, 100) <= proficiency:
            extra += 1
        else:
            break
    return extra


def _player_attack_mob_once(session, player, mob) -> None:
    """One single attack (to-hit roll through any bleeding tick) from
    player against mob -- extracted so resolve_pulse can call this
    once per attack a player has earned this round (see
    _roll_extra_attacks), rather than duplicating the whole sequence
    inline for each one. Behavior is identical to what resolve_pulse
    always did for its one guaranteed attack.

    Confirmed design (reversed from an earlier turn): automatic
    attacks fire normally during a hand-sign cast, including any
    extra attacks per round -- a character with something like third
    attack was otherwise strictly worse off casting jutsu at all,
    since every one of those extra swings was lost for the whole
    delay. The jutsu itself still lands separately once it resolves;
    this is purely about whether the ORDINARY automatic attack is
    also suppressed while it forms. _is_action_blocked (stun/
    paralysis) still correctly suppresses it -- only the pending-cast
    lockout is gone."""
    if _is_action_blocked(player):
        session.send("You are unable to act!")
        return
    import commands as commands_module
    import weather
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    player_hit_roll = derived_stats.hit_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "hit_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player)) + commands_module.equipped_weapon_hitroll_bonus(player) + _summon_weapon_buff_hitroll_bonus(player)
    mob_armor_class = derived_stats.armor_class(mob) - commands_module.equipped_armor_class_bonus(mob)
    to_hit = derived_stats.to_hit_chance(player_hit_roll, mob_armor_class) + weather.combat_accuracy_modifier() + _sharingan_hitroll_bonus(player) - _accuracy_penalty_from_effects(player)
    to_hit = max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, to_hit))
    attack_verb = data_weapons.attack_verb_for_item(player.equipment.get("wielded", ""))
    weapon_skill = data_weapons.skill_for_item(player.equipment.get("wielded", ""))
    if weapon_skill:
        grow_skill_from_usage(player, weapon_skill)
    if random.randint(1, 100) > to_hit:
        session.send(f"You {attack_verb} at {mob.name} but miss!")
        return
    dmg = _player_attack_damage(player)
    dmg = int(dmg * (100 + _summon_weapon_buff_damage_percent(player)) / 100)
    is_crit = random.randint(1, 100) <= derived_stats.critical_chance(player, set_bonus + data_personality.personality_bonus_percent(player, "critical_chance"))
    if is_crit:
        dmg = int(dmg * 1.5)
    dmg = commands_module.reduce_weapon_damage(mob, data_weapons.weapon_type_for_item(player.equipment.get("wielded", "")), dmg)
    mob.health -= dmg
    if is_crit:
        session.send(f"&YCritical hit!&x You {attack_verb} {mob.name} for {damage_messages.describe_damage(dmg)} damage.")
    else:
        session.send(f"You {attack_verb} {mob.name} for {damage_messages.describe_damage(dmg)} damage.")
    if "bleeding" in mob.active_status_effects:
        bleed = status_effects.bleeding_damage()
        mob.health -= bleed
        session.send(f"{mob.name} bleeds for {damage_messages.describe_damage(bleed)} damage.")


SHADOW_CLONE_DAMAGE_SCALE = 0.5  # a clone hits for half what the player's own attack would


def _clone_attack_mob_once(session, player, mob, clone=None) -> None:
    """One single attack from ONE shadow clone against mob -- same
    to-hit math and weapon as the player's own attack (confirmed
    design: "using the player's own stats/weapon"), but damage scaled
    down (SHADOW_CLONE_DAMAGE_SCALE) so 3 clones don't simply
    quadruple the player's own damage output. Called once per active
    clone, each round, from resolve_pulse -- see
    active_shadow_clones(player)."""
    import commands as commands_module
    import weather
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    player_hit_roll = derived_stats.hit_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "hit_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player)) + commands_module.equipped_weapon_hitroll_bonus(player)
    mob_armor_class = derived_stats.armor_class(mob) - commands_module.equipped_armor_class_bonus(mob)
    to_hit = derived_stats.to_hit_chance(player_hit_roll, mob_armor_class) + weather.combat_accuracy_modifier() + _sharingan_hitroll_bonus(player) - _accuracy_penalty_from_effects(player)
    to_hit = max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, to_hit))
    attack_verb = data_weapons.attack_verb_for_item(player.equipment.get("wielded", ""))
    element = getattr(clone, "clone_element", "none")
    clone_label = f"{element} clone" if element != "none" else "shadow clone"
    if random.randint(1, 100) > to_hit:
        session.send(f"Your {clone_label} {attack_verb}s at {mob.name} but misses!")
        return
    dmg = int(_player_attack_damage(player) * SHADOW_CLONE_DAMAGE_SCALE)
    if element == "earth":
        dmg = round(dmg * 1.25)
    dmg = commands_module.reduce_weapon_damage(mob, data_weapons.weapon_type_for_item(player.equipment.get("wielded", "")), dmg)
    mob.health -= dmg
    session.send(f"Your {clone_label} {attack_verb}s {mob.name} for {damage_messages.describe_damage(dmg)} damage.")
    clone_effect = {"lightning": "paralyzed", "water": "drained", "sand": "entangled"}.get(element)
    if clone_effect and random.randint(1, 100) <= 20:
        status_effects.apply_effect(mob.active_status_effects, clone_effect, source=f"{element} clone", duration_override=2)
        session.send(status_effects.EFFECT_DEFS[clone_effect]["message"].format(target=mob.name))
    if "bleeding" in mob.active_status_effects:
        bleed = status_effects.bleeding_damage()
        mob.health -= bleed
        session.send(f"{mob.name} bleeds for {damage_messages.describe_damage(bleed)} damage.")


def _summon_attack_mob_once(session, player, summon, mob) -> None:
    """One single attack from a player's own active summon against
    mob -- per direct request/confirmation (Section 118), ONLY for a
    summon whose own tier mechanic is genuinely "fighter" (an
    ordinary independent combatant); every other mechanic (trap/
    bind/healer/safety_net/flee_lock/weapon_buff) is a deliberately
    DIFFERENT kind of battle role and never calls this at all. Uses
    the summon's own real, tier-scaled damage (stat_for_summon_tier),
    genuinely separate math from both the player's own attack and a
    shadow clone's scaled-down copy of it, since a summon is its own
    real creature, not an echo of the summoner."""
    import data_summons
    tier = data_summons.tier_by_key(summon.summon_tier_key)
    to_hit = 70  # a summon's own real, tier-independent base accuracy -- deliberately simple, not derived from the player's own stats
    if random.randint(1, 100) > to_hit:
        session.send(f"{summon.name} attacks {mob.name} but misses!")
        return
    dmg = stat_for_summon_tier(player.level, tier, SUMMON_DAMAGE_PER_LEVEL)
    mob.health -= dmg
    session.send(f"{summon.name} attacks {mob.name} for {damage_messages.describe_damage(dmg)} damage.")


def _resolve_summon_round(session, player, mob) -> None:
    """The real per-round dispatcher for a player's own active summon
    (Section 118) -- checked once per combat round (PvE only for the
    round-by-round mechanics below; see handle_pvp_defeat/cmd_flee
    for the 2 mechanics that matter at a different moment instead).
    Does nothing at all if the player has no active summon.

    Per direct confirmation, every contract's own TOP tier has a
    genuinely different battle role, not just bigger numbers:
      "fighter"     -- an ordinary attack (_summon_attack_mob_once).
      "healer"      -- heals the player instead of attacking at all,
                        every round it's out (SLUG_HEAL_PERCENT-scaled
                        via the tier's own heal_percent).
      "trap"        -- Toad Stomach: restrains the MOB (a real,
                        meaningfully large to-hit PENALTY applied to
                        the mob's own attacks for the rest of this
                        fight), but never deals ongoing damage of its
                        own at all -- a pure battlefield-control role,
                        matching the request's own "could be a room
                        trap instead of an actual mob that fights
                        along with you" framing.
      "bind"        -- Manda: poisons the mob (real damage-over-time,
                        ticked here) AND hard-locks the PLAYER's own
                        flee attempts to fail for the rest of the
                        fight (checked directly in cmd_flee).
      "weapon_buff" -- Enma: never attacks independently at all --
                        applies a real hitroll/damage bonus to the
                        PLAYER's own attacks instead, refreshed each
                        round it's out.
    "safety_net" and "flee_lock" are deliberately NOT resolved here --
    their own real effect only matters at a genuinely different
    moment (an about-to-happen defeat, or the opponent's own flee
    attempt), so they're checked directly at THOSE call sites
    instead, not on this per-round PvE tick."""
    summon = active_summon(player)
    if summon is None or summon.health <= 0:
        return
    import data_summons
    tier = data_summons.tier_by_key(summon.summon_tier_key)
    if tier is None:
        return
    mechanic = tier["mechanic"]

    if mechanic == "fighter":
        if mob.health > 0:
            _summon_attack_mob_once(session, player, summon, mob)
    elif mechanic == "healer":
        heal_percent = tier.get("heal_percent", 10)
        heal_amount = max(1, player.maximum_health * heal_percent // 100)
        healed = min(heal_amount, player.maximum_health - player.health)
        if healed > 0:
            player.health += healed
            session.send(f"{summon.name} tends to your wounds, healing you for {healed} HP.")
    elif mechanic == "trap":
        if not getattr(mob, "summon_trap_applied", False):
            mob.summon_trap_applied = True
            mob.summon_trap_to_hit_penalty = TOAD_STOMACH_MOB_TO_HIT_PENALTY
            session.send(f"&Y{summon.name} closes around {mob.name}, trapping it in a crushing stomach!&x")
    elif mechanic == "bind":
        player.summon_flee_locked = True
        if "bleeding" not in mob.active_status_effects:
            status_effects.apply_effect(mob.active_status_effects, "bleeding", source="summon_bind")
        bleed = status_effects.bleeding_damage()
        mob.health -= bleed
        session.send(f"{summon.name} coils tight, poison seeping into {mob.name} for {damage_messages.describe_damage(bleed)} damage!")
    elif mechanic == "weapon_buff":
        player.summon_weapon_buff_active = True


def resolve_pulse(session) -> None:
    """One automatic-attack round for a session actively fighting a mob.
    Assumes tick_effects_pulse()/tick_all_mob_effects() have already run
    for this pulse (server.py's pulse_loop does this before calling here;
    tests simulating pulses should do the same)."""
    player = session.player
    mob = session.combat_target
    if mob is None:
        return
    if mob.room_vnum != player.room_vnum or mob.health <= 0:
        session.combat_target = None
        reset_summon_round_state(player)
        return

    if player.jinchuriki_beast_key and player.rampage_until == 0.0:
        import tailed_beasts as tailed_beasts_module
        tailed_beasts_module.tick_jinchuriki_mastery(player)
        if tailed_beasts_module.check_rampage_trigger(player):
            tailed_beasts_module.trigger_rampage(player)
            session.send("&RSomething inside you SNAPS -- the beast's chakra floods your body, and you lose all control!&x")

    session.send("")  # blank line so each round doesn't blur into the last

    for message in tick_passive_skill_growth(player):
        session.send(message)
    for message in tick_sharingan_upkeep(player):
        session.send(message)
    for message in tick_sharingan_mastery_gain(player):
        session.send(message)
    for message in tick_automatic_bloodline_awakening(player):
        session.send(message)

    if _is_action_blocked(player):
        session.send("You are stunned and can't act this round!" if "stunned" in player.active_status_effects else "You cannot act this round!")
    else:
        _player_attack_mob_once(session, player, mob)
        if mob.health > 0:
            for _ in range(_roll_extra_attacks(player)):
                if mob.health <= 0:
                    break
                _player_attack_mob_once(session, player, mob)
        for clone in active_shadow_clones(player):
            if mob.health <= 0:
                break
            if clone.room_vnum == player.room_vnum:
                _clone_attack_mob_once(session, player, mob, clone)
        _resolve_summon_round(session, player, mob)

    if mob.health <= 0:
        handle_mob_defeat(session, mob)
        return
    if _is_action_blocked(mob):
        session.send(f"{mob.name} is trapped in the illusion and cannot attack this round.")
        return

    import commands as commands_module
    import weather
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    player_armor_class = derived_stats.armor_class(player, set_bonus + data_personality.personality_bonus_percent(player, "armor_class") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player)) - commands_module.equipped_armor_class_bonus(player)
    mob_hit_roll = derived_stats.hit_roll(mob) + commands_module.equipped_weapon_hitroll_bonus(mob)
    mob_to_hit = derived_stats.to_hit_chance(mob_hit_roll, player_armor_class) + weather.combat_accuracy_modifier() - _accuracy_penalty_from_effects(mob)
    if mob.summon_trap_applied:
        mob_to_hit -= mob.summon_trap_to_hit_penalty
    mob_to_hit = max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, mob_to_hit))
    if random.randint(1, 100) > mob_to_hit:
        session.send(f"&C{mob.name} attacks you but misses!&x")
        return

    if player.kamui_intangibility_rounds_left > 0:
        player.kamui_intangibility_rounds_left -= 1
        session.send(f"&R{mob.name}'s attack passes straight through you!&x")
        return

    if random.randint(1, 100) <= derived_stats.dodge_chance(player, set_bonus + data_personality.personality_bonus_percent(player, "dodge_chance")) + weather.night_dodge_bonus() + _sharingan_dodge_bonus(player):
        session.send(f"&CYou dodge {mob.name}'s attack!&x")
        return

    for _ in range(mob.attacks):
        if player.health <= 0:
            break
        dmg = _mob_attack_damage(mob)
        if "frightened" in mob.active_status_effects:
            dmg = int(dmg * (1 - status_effects.EFFECT_DEFS["frightened"]["damage_penalty_pct"] / 100))
        if player.sharingan_active and player.bloodline_tomoe >= 3:
            reduced = _sharingan_predict_and_reduce_damage(player, dmg)
            if reduced < dmg:
                dmg = reduced
            else:
                session.send("&RYou weren't fast enough to counter!&x")
        dmg = commands_module.reduce_weapon_damage(player, data_weapons.weapon_type_for_item(mob.equipment.get("wielded", "")), dmg)
        dmg = status_effects.reduce_incoming_damage(player.active_status_effects, dmg)
        player.health -= dmg
        session.send(f"{mob.name} strikes you for {damage_messages.describe_damage(dmg)} damage.")

    if player.health <= 0:
        if try_trigger_izanagi(session):
            pass
        elif is_immortal_immune_to_defeat(session):
            clamp_immortal_health(session)
        else:
            handle_player_defeat(session)
    elif player.wimpy_percent > 0 and (player.health / player.maximum_health * 100) <= player.wimpy_percent:
        session.send(f"&Y(Your health has dropped to your wimpy threshold of {player.wimpy_percent}%!)&x")
        commands_module.cmd_flee(session, [])


def _can_use_jutsu(player, jutsu, jutsu_key: str = None) -> bool:
    """Whether player is allowed to cast jutsu at all right now, before
    any cooldown/resource checks. Every normal jutsu requires it to be
    in player.learned_skills (granted automatically at level-up, see
    leveling.py) -- but a jutsu carrying a "kkg_gate" key bypasses that
    entirely and checks the named Kekkei Genkai condition instead,
    since data_jutsu.py's own docstring confirms jutsu are no longer
    class-gated at all and every player already knows every normal
    jutsu regardless of class -- a kkg_gate jutsu needs its own
    distinct gate or it would be available to everyone, defeating the
    whole point of it being tomoe-locked. A jutsu the player has
    copied via the 5-tomoe Copy Jutsu perk (player.copied_jutsu_key)
    is also always usable, regardless of either check -- that's a
    one-time grant for exactly that jutsu, not a permanent unlock.

    A jutsu carrying a real "element" (Section 85, per direct
    clarification: "a person cant cast jutsu that is not theire
    element") is a genuine HARD GATE, not a bonus-if-matching
    condition -- confirmed directly after an earlier design that
    assumed off-element casting was allowed (just weaker) turned out
    to be wrong. Only castable if that element matches the player's
    OWN chakra nature, primary OR secondary (matching the same
    "either nature counts" rule already used for the reveal
    mechanism's own eligibility elsewhere) -- checked here so even a
    copied or Kekkei-Genkai-gated elemental jutsu would still need a
    real matching nature (though no jutsu combines both gates today)."""
    if jutsu.get("jutsu_type") == "elemental_clone" and player.skill_proficiencies.get("Shadow Clone Jutsu", 0) < 100:
        return False
    if jutsu.get("requires_water"):
        import fishing
        room = world.WORLD.get(player.room_vnum)
        if room is None or not fishing.can_fish_here(room.biome):
            return False
    if jutsu.get("element", "none") != "none":
        if jutsu["element"] not in (player.chakra_nature, player.chakra_nature_secondary):
            return False
    if jutsu_key is not None and player.copied_jutsu_key == jutsu_key:
        return True
    gate = jutsu.get("kkg_gate")
    if gate == "mangekyo_technique":
        # Genuinely generic (Section 140): checks the jutsu's own real
        # "mangekyo_roster_key" (falling back to jutsu_key itself for
        # a single-jutsu technique like Amaterasu, where the 2 happen
        # to be identical) against BOTH of the player's real, rolled
        # eye techniques. Kamui is confirmed to be 3 SEPARATE real
        # jutsu sharing the one roster key "kamui" -- this lets all 3
        # gate correctly without needing 3 separate roster entries.
        roster_key = jutsu.get("mangekyo_roster_key", jutsu_key)
        return roster_key in (player.mangekyo_eye_1, player.mangekyo_eye_2)
    return jutsu["display_name"].lower() in [s.lower() for s in player.learned_skills]


SHADOW_CLONE_MASTERY_GAIN_PER_CAST = 2


def use_shadow_clone_jutsu(session) -> None:
    """'shadow clone jutsu' (or 'perform shadow clone jutsu') -- no
    target needed, unlike every other jutsu, since this summons real,
    independently-attackable clone Mobs (see spawn_shadow_clones)
    rather than attacking anything. Dispatched from
    commands.cmd_use_jutsu/cmd_perform BEFORE the normal target-lookup
    logic runs (see jutsu_type == "summon" check there), since a
    summon-type jutsu has nothing to target at all. Confirmed usable
    outside combat entirely -- clones persist independently (see
    tick_shadow_clone_upkeep, ticked every server pulse regardless of
    combat state) until dismissed or their upkeep can no longer be
    afforded.

    Casting while clones are already active dismisses them first, then
    resummons fresh at whatever the current mastery's clone count is
    -- so a recast after mastery has since grown correctly raises the
    clone count to match, rather than stacking additional clones on
    top of an earlier batch."""
    player = session.player
    jutsu = data_jutsu.JUTSU["shadow clone jutsu"]
    now = time.time()

    if not _can_use_jutsu(player, jutsu, "shadow clone jutsu") or jutsu["display_name"] not in player.learned_skills:
        session.send("You don't know that jutsu.")
        return
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use jutsu right now!")
        return

    cooldown_ready_at = player.cooldowns.get("shadow clone jutsu", 0)
    if now < cooldown_ready_at:
        session.send(f"&WShadow Clone Jutsu&x is still recovering ({cooldown_ready_at - now:.1f}s).")
        return
    if player.chakra < jutsu["chakra_cost"]:
        session.send("You don't have enough chakra.")
        return

    player.chakra -= jutsu["chakra_cost"]
    player.cooldowns["shadow clone jutsu"] = now + jutsu["cooldown"]

    mastery = player.skill_proficiencies.get("Shadow Clone Jutsu", 0)
    new_mastery = min(100, mastery + SHADOW_CLONE_MASTERY_GAIN_PER_CAST)
    player.skill_proficiencies["Shadow Clone Jutsu"] = new_mastery

    dismiss_shadow_clones(player)
    clone_count = shadow_clone_count_for_mastery(new_mastery)
    spawn_shadow_clones(player, clone_count)

    plural = "clone" if clone_count == 1 else "clones"
    verb = "puffs" if clone_count == 1 else "puff"
    session.send(
        f"&WYou form a hand sign and shout, \"Shadow Clone Jutsu!\"&x\n"
        f"{clone_count} shadow {plural} {verb} into existence beside you, ready to fight!\n"
        f"&D(Shadow Clone Jutsu mastery: {new_mastery}%. Upkeep: {clone_count * SHADOW_CLONE_UPKEEP_PER_CLONE} chakra/round.)&x"
    )


def use_elemental_clone_jutsu(session, jutsu_key: str) -> None:
    """One elemental clone, sharing the existing live-clone cap and upkeep."""
    player = session.player
    jutsu = data_jutsu.JUTSU[jutsu_key]
    if player.skill_proficiencies.get("Shadow Clone Jutsu", 0) < 100:
        session.send("Master Shadow Clone Jutsu to 100% before creating elemental clones.")
        return
    if not _can_use_jutsu(player, jutsu, jutsu_key):
        session.send(f"You need {jutsu['element'].capitalize()} chakra nature and must know {jutsu['display_name']}.")
        return
    if _is_action_blocked(player) or getattr(session, "pending_cast", None) is not None:
        session.send("You are unable to form the clone right now.")
        return
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use jutsu right now!")
        return
    now = time.time()
    if now < player.cooldowns.get(jutsu_key, 0):
        session.send(f"{jutsu['display_name']} is still recovering.")
        return
    cost = round(jutsu["chakra_cost"] * (100 - derived_stats.chakra_control_cost_discount_percent(player.chakra_control)) / 100)
    if player.chakra < cost:
        session.send("You don't have enough chakra.")
        return
    player.chakra -= cost
    player.cooldowns[jutsu_key] = now + jutsu["cooldown"]
    dismiss_shadow_clones(player)
    spawned = spawn_shadow_clones(player, 1, element=jutsu["clone_element"])
    if not spawned:
        player.chakra += cost
        player.cooldowns.pop(jutsu_key, None)
        session.send("There is no space to summon a clone here.")
        return
    grow_skill_from_usage(player, jutsu["display_name"])
    session.send(f"&CYou form hand signs and create {spawned[0].name}!&x (Upkeep: {SHADOW_CLONE_UPKEEP_PER_CLONE} chakra/round.)")


def use_barrier(session) -> None:
    """Level-35 general defensive buff, active for five combat pulses."""
    player = session.player
    jutsu = data_jutsu.JUTSU["barrier"]
    if not _can_use_jutsu(player, jutsu, "barrier"):
        session.send("You don't know Barrier.")
        return
    if _is_action_blocked(player) or getattr(session, "pending_cast", None) is not None:
        session.send("You are unable to raise a barrier right now.")
        return
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use jutsu right now!")
        return
    now = time.time()
    if now < player.cooldowns.get("barrier", 0):
        session.send("Barrier is still recovering.")
        return
    if player.chakra < jutsu["chakra_cost"]:
        session.send("You don't have enough chakra.")
        return
    player.chakra -= jutsu["chakra_cost"]
    player.cooldowns["barrier"] = now + jutsu["cooldown"]
    status_effects.apply_effect(player.active_status_effects, "barrier", source="barrier")
    grow_skill_from_usage(player, "Barrier")
    session.send("&CA chakra barrier rises around you, reducing incoming damage by 10% for five pulses.&x")


def use_jutsu(session, jutsu_key: str, mob: Mob) -> None:
    player = session.player
    if _is_action_blocked(player):
        session.send("You are unable to act!")
        return
    jutsu = data_jutsu.JUTSU.get(jutsu_key)
    now = time.time()

    if jutsu is None or not _can_use_jutsu(player, jutsu, jutsu_key):
        session.send("You don't know that jutsu.")
        return
    if jutsu.get("jutsu_type") == "ambush" and mob.health < mob.max_health:
        session.send(f"{mob.name} is hurt and alert; you cannot sneak up on them.")
        return
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use jutsu right now!")
        return

    cooldown_ready_at = player.cooldowns.get(jutsu_key, 0)
    import commands as commands_module
    jutsu_color = commands_module.CLASS_WHO_COLOR.get(jutsu["class_requirement"], "&W")
    colored_name = f"{jutsu_color}{jutsu['display_name']}&x"
    if now < cooldown_ready_at:
        session.send(f"{colored_name} is still recovering ({cooldown_ready_at - now:.1f}s).")
        return
    is_copied_cast = player.copied_jutsu_key == jutsu_key
    chakra_cost = player.copied_jutsu_cost if is_copied_cast else jutsu["chakra_cost"]
    stamina_cost = jutsu["stamina_cost"]
    discount_pct = derived_stats.chakra_control_cost_discount_percent(player.chakra_control)
    if discount_pct and jutsu["class_requirement"] in ("genjutsu", "ninjutsu"):
        chakra_cost = round(chakra_cost * (100 - discount_pct) / 100)
    if player.chakra < chakra_cost:
        session.send("You don't have enough chakra.")
        return
    if player.stamina < stamina_cost:
        session.send("You don't have enough stamina.")
        return

    if jutsu.get("requires_item"):
        held_kunai = next((item for item in player.inventory if jutsu["requires_item"] in item.lower()), None)
        if not held_kunai:
            session.send(f"You don't have a {jutsu['requires_item']} to throw.")
            return

    player.chakra -= chakra_cost
    player.stamina -= stamina_cost
    if is_copied_cast:
        player.copied_jutsu_key = None
        player.copied_jutsu_cost = 0
    player.cooldowns[jutsu_key] = now + jutsu["cooldown"]

    if jutsu.get("requires_item"):
        player.inventory.remove(held_kunai)
        room = world.WORLD.get(player.room_vnum)
        if room:
            room.ground_items.append(held_kunai)

    import weather
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    player_hit_roll = derived_stats.hit_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "hit_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player)) + commands_module.equipped_weapon_hitroll_bonus(player)
    mob_armor_class = derived_stats.armor_class(mob) - commands_module.equipped_armor_class_bonus(mob)
    to_hit = derived_stats.to_hit_chance(player_hit_roll, mob_armor_class) + weather.combat_accuracy_modifier() + _sharingan_hitroll_bonus(player) - _accuracy_penalty_from_effects(player)
    to_hit += _genjutsu_hit_bonus(player, jutsu)
    to_hit = max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, to_hit))
    if random.randint(1, 100) > to_hit:
        session.send(f"You use {colored_name} on {mob.name}, but it misses!")
        return

    dmg, was_explosive = roll_jutsu_damage(jutsu)
    dmg = _mirror_illusion_damage(jutsu, mob, dmg)
    dmg += _jutsu_damage_bonus(player)
    if jutsu.get("jutsu_type") == "ambush":
        dmg = max(1, round(dmg * jutsu["ambush_multiplier"]))
    import village_perks
    dmg_mult = village_perks.damage_multiplier(player.village)
    if dmg_mult != 1.0:
        dmg = int(dmg * dmg_mult)
    kekkei_no_me_mult = _kekkei_no_me_damage_multiplier(player, jutsu)
    if kekkei_no_me_mult != 1.0:
        dmg = int(dmg * kekkei_no_me_mult)

    import biomes
    room = world.WORLD.get(player.room_vnum)
    biome_mult = biomes.damage_modifier(room.biome if room else "none", jutsu.get("element", "none"))
    if biome_mult != 1.0:
        dmg = int(dmg * biome_mult)

    dmg = status_effects.reduce_outgoing_damage(player.active_status_effects, dmg)
    mob.health -= dmg
    _genjutsu_impact(jutsu, mob)
    grow_skill_from_usage(player, jutsu["display_name"])
    perk_note = f" &Y(x{dmg_mult:g} village perk)&x" if dmg_mult != 1.0 else ""
    if biome_mult > 1.0:
        biome_note = f" &C({room.biome} boosts {jutsu.get('element')})&x"
    elif biome_mult < 1.0:
        biome_note = f" &D({room.biome} weakens {jutsu.get('element')})&x"
    else:
        biome_note = ""
    if was_explosive:
        session.send(f"&RThe kunai detonates!&x You use {colored_name} on {mob.name} for {damage_messages.describe_damage(dmg)} explosive damage!{perk_note}{biome_note}")
    else:
        session.send(f"You use {colored_name} on {mob.name} for {damage_messages.describe_damage(dmg)} damage!{perk_note}{biome_note}")

    if jutsu["effect"] and random.randint(1, 100) <= jutsu.get("effect_chance_pct", 100):
        status_effects.apply_effect(mob.active_status_effects, jutsu["effect"], source=jutsu_key)
        session.send(status_effects.EFFECT_DEFS[jutsu["effect"]]["message"].format(target=mob.name))

    if jutsu.get("jutsu_type") == "area":
        for other in list(mobs_in_room(player.room_vnum)):
            if other is mob or other.health <= 0 or is_shadow_clone(other):
                continue
            if (is_shopkeeper(other) or is_gambler(other)
                    or is_teacher(other) or is_immortal_mob(other)):
                continue
            other.health -= dmg
            session.send(f"{jutsu['display_name']} also strikes {other.name} for {damage_messages.describe_damage(dmg)} damage!")
            if other.health <= 0:
                handle_mob_defeat(session, other)

    if mob.health <= 0:
        handle_mob_defeat(session, mob)


def use_jutsu_on_player(session, jutsu_key: str, target_session, damage_multiplier: float = 1.0) -> None:
    """PvP-enabled jutsu casting, per direct request ("make jutsu pvp
    enabled"). Mirrors use_jutsu's structure (gate/cooldown/resource
    checks, to-hit, damage, effect application) but against another
    player instead of a mob, layering in the full set of Sharingan
    perks a defender might have active: dodge (tomoe 1), Movement
    Prediction on a failed dodge (tomoe 3), genjutsu resistance
    shortening any incoming genjutsu-class effect's duration (tomoe 4
    -- this is the very first path in the whole game that can ever
    exercise that perk, since no jutsu could target a player before
    this function existed), and Copy Jutsu (tomoe 5, see below).

    damage_multiplier defaults to 1.0 (every ordinary cast) -- the
    ONLY caller that ever passes something else is
    _check_jutsu_collisions' own overpower path (Section 98, per
    direct confirmation: "still lands, but at reduced strength"),
    which passes elemental_counters.OVERPOWER_DAMAGE_MULTIPLIER."""
    player = session.player
    if _is_action_blocked(player):
        session.send("You are unable to act!")
        return
    jutsu = data_jutsu.JUTSU.get(jutsu_key)
    now = time.time()

    if jutsu is None or not _can_use_jutsu(player, jutsu, jutsu_key):
        session.send("You don't know that jutsu.")
        return
    if status_effects.has_effect(player.active_status_effects, "silenced"):
        session.send("You are silenced and cannot use jutsu right now!")
        return

    target = target_session.player
    if jutsu.get("jutsu_type") == "ambush" and target.health < target.maximum_health:
        session.send(f"{target.name} is hurt and alert; you cannot sneak up on them.")
        return
    if target.izanami_trapped:
        session.send(f"{target.name} is lost in a loop, untouched by reality -- you cannot reach them.")
        return
    cooldown_ready_at = player.cooldowns.get(jutsu_key, 0)
    import commands as commands_module
    jutsu_color = commands_module.CLASS_WHO_COLOR.get(jutsu["class_requirement"], "&W")
    colored_name = f"{jutsu_color}{jutsu['display_name']}&x"
    silent_to_target = (
        jutsu["class_requirement"] == "genjutsu"
        and commands_module.has_silent_genjutsu(player)
        and player.skill_proficiencies.get("Silent Genjutsu", 0) >= 100
    )
    if now < cooldown_ready_at:
        session.send(f"{colored_name} is still recovering ({cooldown_ready_at - now:.1f}s).")
        return
    is_copied_cast = player.copied_jutsu_key == jutsu_key
    chakra_cost = player.copied_jutsu_cost if is_copied_cast else jutsu["chakra_cost"]
    stamina_cost = jutsu["stamina_cost"]
    discount_pct = derived_stats.chakra_control_cost_discount_percent(player.chakra_control)
    if discount_pct and jutsu["class_requirement"] in ("genjutsu", "ninjutsu"):
        chakra_cost = round(chakra_cost * (100 - discount_pct) / 100)
    if player.chakra < chakra_cost:
        session.send("You don't have enough chakra.")
        return
    if player.stamina < stamina_cost:
        session.send("You don't have enough stamina.")
        return

    if jutsu.get("requires_item"):
        held_kunai = next((item for item in player.inventory if jutsu["requires_item"] in item.lower()), None)
        if not held_kunai:
            session.send(f"You don't have a {jutsu['requires_item']} to throw.")
            return

    caster_chakra_cost = jutsu["chakra_cost"]  # the jutsu's real cost -- NOT chakra_cost above, which may be a discounted copied-cast price
    player.chakra -= chakra_cost
    player.stamina -= stamina_cost
    if is_copied_cast:
        player.copied_jutsu_key = None
        player.copied_jutsu_cost = 0
    player.cooldowns[jutsu_key] = now + jutsu["cooldown"]

    if jutsu.get("requires_item"):
        player.inventory.remove(held_kunai)
        room = world.WORLD.get(player.room_vnum)
        if room:
            room.ground_items.append(held_kunai)

    import weather
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    player_hit_roll = derived_stats.hit_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "hit_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player)) + commands_module.equipped_weapon_hitroll_bonus(player)
    target_set_bonus = commands_module.equipped_set_bonus_percent(target)
    target_armor_class = derived_stats.armor_class(target, target_set_bonus + data_personality.personality_bonus_percent(target, "armor_class") + tailed_beasts.rampage_bonus_percent(target) + tailed_beasts.mode_bonus_percent(target)) - commands_module.equipped_armor_class_bonus(target)
    to_hit = derived_stats.to_hit_chance(player_hit_roll, target_armor_class) + weather.combat_accuracy_modifier() + _sharingan_hitroll_bonus(player) - _accuracy_penalty_from_effects(player) + _genjutsu_hit_bonus(player, jutsu)
    to_hit = max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, to_hit))
    if random.randint(1, 100) > to_hit:
        session.send(f"You use {colored_name} on {target.name}, but it misses!")
        if not silent_to_target:
            target_session.send(f"&C{player.name} uses {colored_name} on you, but it misses!&x")
        return

    if target.kamui_intangibility_rounds_left > 0:
        target.kamui_intangibility_rounds_left -= 1
        session.send(f"&R{colored_name} passes straight through {target.name}!&x")
        if not silent_to_target:
            target_session.send(f"&R{player.name}'s {colored_name} passes straight through you!&x")
        return

    if random.randint(1, 100) <= derived_stats.dodge_chance(target, target_set_bonus + data_personality.personality_bonus_percent(target, "dodge_chance")) + weather.night_dodge_bonus() + _sharingan_dodge_bonus(target):
        session.send(f"&C{target.name} dodges your {colored_name}!&x")
        if not silent_to_target:
            target_session.send(f"&CYou dodge {player.name}'s {colored_name}!&x")
        return

    if jutsu.get("jutsu_type") == "thrown" and _try_counter_kunai(session, target_session, target, player.name, jutsu["display_name"]):
        return

    dmg, was_explosive = roll_jutsu_damage(jutsu)
    dmg = _mirror_illusion_damage(jutsu, target, dmg)
    dmg += _jutsu_damage_bonus(player)
    if jutsu.get("jutsu_type") == "ambush":
        dmg = max(1, round(dmg * jutsu["ambush_multiplier"]))
    import village_perks
    dmg_mult = village_perks.damage_multiplier(player.village)
    if dmg_mult != 1.0:
        dmg = int(dmg * dmg_mult)
    kekkei_no_me_mult = _kekkei_no_me_damage_multiplier(player, jutsu)
    if kekkei_no_me_mult != 1.0:
        dmg = int(dmg * kekkei_no_me_mult)
    if damage_multiplier != 1.0:
        dmg = max(1, int(dmg * damage_multiplier))

    import biomes
    room = world.WORLD.get(player.room_vnum)
    biome_mult = biomes.damage_modifier(room.biome if room else "none", jutsu.get("element", "none"))
    if biome_mult != 1.0:
        dmg = int(dmg * biome_mult)

    if target.sharingan_active and target.bloodline_tomoe >= 3:
        reduced = _sharingan_predict_and_reduce_damage(target, dmg)
        if reduced < dmg:
            dmg = reduced
        elif not silent_to_target:
            target_session.send("&RYou weren't fast enough to counter!&x")

    dmg = status_effects.reduce_outgoing_damage(player.active_status_effects, dmg)
    dmg = status_effects.reduce_incoming_damage(target.active_status_effects, dmg)
    target.health -= dmg
    _genjutsu_impact(jutsu, target)
    grow_skill_from_usage(player, jutsu["display_name"])
    perk_note = f" &Y(x{dmg_mult:g} village perk)&x" if dmg_mult != 1.0 else ""
    if biome_mult > 1.0:
        biome_note = f" &C({room.biome} boosts {jutsu.get('element')})&x"
    elif biome_mult < 1.0:
        biome_note = f" &D({room.biome} weakens {jutsu.get('element')})&x"
    else:
        biome_note = ""
    if was_explosive:
        session.send(f"&RThe kunai detonates!&x You use {colored_name} on {target.name} for {damage_messages.describe_damage(dmg)} explosive damage!{perk_note}{biome_note}")
        if silent_to_target:
            target_session.send(f"&RYou feel a sudden, sharp pain -- {damage_messages.describe_damage(dmg)} damage!&x")
        else:
            target_session.send(f"&RThe kunai detonates!&x {player.name} uses {colored_name} on you for {damage_messages.describe_damage(dmg)} explosive damage!{perk_note}{biome_note}")
    else:
        session.send(f"You use {colored_name} on {target.name} for {damage_messages.describe_damage(dmg)} damage!{perk_note}{biome_note}")
        if silent_to_target:
            target_session.send(f"&RSomething washes over you -- {damage_messages.describe_damage(dmg)} damage!&x")
        else:
            target_session.send(f"{player.name} uses {colored_name} on you for {damage_messages.describe_damage(dmg)} damage!{perk_note}{biome_note}")

    if jutsu["effect"] and random.randint(1, 100) <= jutsu.get("effect_chance_pct", 100):
        import data_kekkei_genkai
        effect_duration = status_effects.EFFECT_DEFS[jutsu["effect"]]["duration"]
        if jutsu["class_requirement"] == "genjutsu" and data_kekkei_genkai.sharingan_genjutsu_resistant(target):
            effect_duration = data_kekkei_genkai.reduced_genjutsu_duration(effect_duration)
        status_effects.apply_effect(target.active_status_effects, jutsu["effect"], source=jutsu_key, duration_override=effect_duration)
        target_session.send(status_effects.EFFECT_DEFS[jutsu["effect"]]["message"].format(target="You"))
        session.send(status_effects.EFFECT_DEFS[jutsu["effect"]]["message"].format(target=target.name))

    # 5-tomoe Copy Jutsu, per exact direct design confirmation
    # ("sharingan copy has a chance to copy the other users jutsu when
    # toggled on but has a cost of double the other users chakra to
    # copy"). Rolled on the DEFENDER's side -- being cast AT is what
    # gives the Sharingan something to read and copy. Cost is fixed at
    # copy time to double what the ORIGINAL caster (player, not
    # target) paid, so it can never drift if the source jutsu's own
    # cost changes later, and is explicitly NOT the target's own
    # normal cost for that jutsu.
    if target.sharingan_active and target.bloodline_tomoe >= 5 and target.health > 0:
        if random.randint(1, 100) <= commands_module.SHARINGAN_COPY_JUTSU_CHANCE_PERCENT:
            target.copied_jutsu_key = jutsu_key
            target.copied_jutsu_cost = caster_chakra_cost * 2
            target_session.send(
                f"&RYour Sharingan copies {colored_name}! You can now cast it once "
                f"for &Y{target.copied_jutsu_cost}&R chakra.&x"
            )

    if target.health <= 0:
        if try_trigger_izanagi(target_session):
            pass
        elif is_immortal_immune_to_defeat(target_session):
            clamp_immortal_health(target_session)
        else:
            handle_pvp_defeat(winner_session=session, loser_session=target_session)


# --- Defeat handling -------------------------------------------------

def _experience_reward(player: Player, mob: Mob) -> int:
    """Calculated reward for this player's level against this mob.

    Prototype ``experience_reward`` values are retained only for old saved
    world compatibility; rewards now come entirely from mob/player levels.
    """
    import leveling
    return leveling.mob_kill_experience(player.level, mob.level)


def handle_mob_defeat(session, mob: Mob) -> None:
    player = session.player
    if is_shadow_clone(mob):
        # A defeated shadow clone bypasses XP/ryo/bounty/corpse/mob-
        # program logic entirely -- genuinely zero reward through
        # every path, per confirmed design ("Shadow clones poof
        # without a corpse"). This also sidesteps a real edge case a
        # corpse would otherwise hit: a player with the (non-default)
        # auto-sacrifice-corpse preference on would still net a flat
        # +1 ryo from that separate mechanism even with the clone's
        # own ryo_reward correctly at 0.
        session.send(f"&Y{mob.name} dispels in a puff of smoke!&x")
        room_mobs = MOBS_BY_ROOM.get(mob.room_vnum, [])
        if mob in room_mobs:
            room_mobs.remove(mob)
        session.combat_target = None
        reset_summon_round_state(player)
        return

    if getattr(mob, "tailed_beast_key", None) and mob.tailed_beast_downed_until == 0.0:
        mob.health = 0
        mob.tailed_beast_downed_until = time.time() + 60.0  # confirmed directly: a real 1-minute window
        session.combat_target = None
        reset_summon_round_state(player)
        session.send(
            f"&R{mob.name} collapses, defeated -- but still breathes. Someone must seal it now, or it will die!&x"
        )
        _broadcast_to_room(mob.room_vnum, f"&R{mob.name} collapses, gravely wounded -- it must be sealed quickly!&x")
        return

    import corpses
    import leveling  # local import to avoid circular dependency at module load
    import village_perks

    player.npc_kills += 1
    session.send(f"&GYou have defeated {mob.name}!&x")
    session.send(f"&r{mob.name.capitalize()} is DEAD!&x")

    t = MOB_TEMPLATES.get(mob.template_vnum)
    if t and t.get("mob_programs"):
        import programs
        programs.fire_programs(session, t["mob_programs"], "death", speaker_name=mob.name.capitalize())

    import bounties
    bounty_id, bounty_entry = bounties.find_bounty_for_mob(mob.template_vnum)
    if bounty_id is not None and bounties.claim_bounty(bounty_id, player.name):
        player.ryo += bounty_entry["reward_ryo"]
        player.mission_points += bounty_entry["reward_mission_points"]
        player.mission_points_earned_total += bounty_entry["reward_mission_points"]
        session.send(
            f"&r*** BINGO BOOK BOUNTY CLAIMED (#{bounty_id}) ***&x\n"
            f"&Y{bounty_entry['reward_ryo']:,} ryo and {bounty_entry['reward_mission_points']} "
            f"mission point(s) added to your account.&x"
        )

    ryo_mult = village_perks.ryo_multiplier(player.village)
    corpse_ryo = int(mob.ryo_reward * ryo_mult) if ryo_mult != 1.0 else mob.ryo_reward
    corpse = corpses.spawn_corpse(mob.name, mob.room_vnum, corpse_ryo, mob.loot_items)
    if not corpse.is_empty():
        session.send(f"{mob.name.capitalize()} leaves behind a corpse." + (f" &Y(x{ryo_mult:g} ryo village perk)&x" if ryo_mult != 1.0 else ""))

    if player.auto_loot_ryo and corpse.ryo > 0:
        taken = corpses.loot_ryo(player, corpse)
        session.send(f"You automatically loot {taken} ryo from the corpse.")
    if player.auto_loot_gear and corpse.items:
        taken = corpses.loot_gear(player, corpse)
        for item in taken:
            session.send(f"You automatically loot {item} from the corpse.")
    if player.auto_sac_corpse:
        forfeited_ryo, forfeited_items = corpses.sacrifice(player, corpse)
        msg = f"The corpse crumbles to dust, yielding {corpses.SACRIFICE_RYO_REWARD} ryo."
        if forfeited_ryo or forfeited_items:
            parts = []
            if forfeited_ryo:
                parts.append(f"{forfeited_ryo} ryo")
            if forfeited_items:
                parts.append(f"{len(forfeited_items)} item(s)")
            msg += f" ({' and '.join(parts)} left on it were forfeited.)"
        session.send(msg)

    session.combat_target = None
    reset_summon_round_state(player)
    remove_mob(mob)

    if session.group and len(session.group.members) > 1:
        qualifying = [
            m for m in session.group.members
            if m.player and m.player.room_vnum == mob.room_vnum and m.player.health > 0
        ]
    else:
        qualifying = [session]

    if len(qualifying) > 1:
        for member_a in qualifying:
            for member_b in qualifying:
                if member_a is member_b:
                    continue
                counts = member_a.player.combat_partner_counts
                counts[member_b.player.name] = counts.get(member_b.player.name, 0) + 1

    for member_session in qualifying:
        member_player = member_session.player
        member_base_xp = _experience_reward(member_player, mob)
        share = member_base_xp // len(qualifying) if qualifying else 0
        member_multiplier = village_perks.xp_multiplier(member_player.village)
        member_xp = int(share * member_multiplier)
        team_bonus_applied = member_player.team_name and any(
            other.player and other is not member_session and other.player.team_name == member_player.team_name
            for other in qualifying
        )
        if team_bonus_applied:
            member_xp = int(member_xp * (1 + teams.TEAM_XP_BONUS_PCT / 100))
        loyal_bonus_applied = member_player.personality_trait == "loyal" and len(qualifying) > 1
        if loyal_bonus_applied:
            import data_personality
            member_xp = int(member_xp * (1 + data_personality.LOYAL_GROUP_XP_BONUS_PCT / 100))
        if not member_xp:
            continue
        perk_suffix = f" &Y(x{member_multiplier:g} village perk)&x" if member_multiplier != 1.0 else ""
        team_suffix = f" &C(+{teams.TEAM_XP_BONUS_PCT}% team bonus)&x" if team_bonus_applied else ""
        loyal_suffix = f" &C(+{data_personality.LOYAL_GROUP_XP_BONUS_PCT}% loyal bonus)&x" if loyal_bonus_applied else ""
        if member_session is session:
            session.send(f"You gain {member_xp} experience.{perk_suffix}{team_suffix}{loyal_suffix}")
        else:
            member_session.send(f"You gain {member_xp} experience from the group's kill.{perk_suffix}{team_suffix}{loyal_suffix}")
        for line in leveling.grant_experience(member_player, member_xp):
            member_session.send(line)

    import missions  # local import to avoid circular dependency
    for line in missions.on_mob_defeated(player, mob.template_vnum):
        session.send(line)


def try_trigger_izanagi(session) -> bool:
    """Whether Izanagi (Section 140, if rolled and actively toggled
    on) genuinely saves this session's own player from a real defeat
    right now. Per direct confirmation: a deliberate stance the
    player activated themselves in advance (session.player.
    izanagi_active), NOT automatic -- but once active, the very next
    time HP would hit 0 while it's on, it's instead restored to FULL
    HP and the stance is consumed, with a real, once-per-real-day
    cooldown starting from that moment. Checked BEFORE even
    is_immortal_immune_to_defeat at every real defeat-check site,
    since a player's own genuine, deliberate choice should take
    priority over a staff-only safety net that isn't a real choice at
    all. Returns True if it fired (caller should skip the normal
    defeat flow entirely, same contract as the immortal check)."""
    player = session.player
    if not player.izanagi_active:
        return False
    player.izanagi_active = False
    player.health = player.maximum_health
    player.izanagi_cooldown_until = time.time() + data_mangekyo.IZANAGI_COOLDOWN_SECONDS
    session.send("&RFate itself refuses to claim you -- Izanagi tears you back from the brink, whole again.&x")
    return True


def is_immortal_immune_to_defeat(session) -> bool:
    """Whether this session's own real account is staff (builder or
    higher) -- per direct request/confirmation (Section 128):
    "Immortals can't die they stop at 1 hp." Same real bar already
    used for doors/goto/transfer (session.account.staff_level !=
    "player"). If True, callers are expected to clamp player.health
    to 1 and skip calling handle_player_defeat entirely, rather than
    letting a real defeat (hospital respawn, XP/ryo loss, bounty
    claims, etc.) ever actually happen to a staff member."""
    return session.account is not None and session.account.staff_level != "player"


def clamp_immortal_health(session) -> None:
    """If this session's own real account is staff, clamps their
    health to a real minimum of 1 whenever it would otherwise be 0 or
    below -- the actual real mechanism behind "stop at 1 hp." Callers
    check is_immortal_immune_to_defeat's own return value themselves
    to decide whether to skip handle_player_defeat; this function
    only handles the real health-clamping half of it, so a caller
    that already knows a player is staff can call this directly
    without a redundant second check."""
    if session.player.health <= 0:
        session.player.health = 1


def handle_player_defeat(session) -> None:
    player = session.player

    if session.duel is not None and session.duel.accepted:
        # A duel ends ONLY on a genuine defeat (confirmed design, no
        # yield/concede) -- and confirmed to carry NO penalties at
        # all, unlike a normal PvP defeat. end_duel handles the
        # return-to-origin-room trip and the partial heal for BOTH
        # combatants; nothing below this branch should ever run for
        # a duel loss.
        import duel as duel_module
        duel_module.end_duel(session.duel, session)
        return

    summon = active_summon(player)
    if summon is not None and summon.health > 0:
        import data_summons
        tier = data_summons.tier_by_key(summon.summon_tier_key)
        if tier and tier["mechanic"] == "safety_net":
            heal_percent = tier.get("heal_percent", 20)
            heal_amount = max(1, player.maximum_health * heal_percent // 100)
            player.health = min(player.maximum_health, heal_amount)
            session.send(
                f"&Y{summon.name} shields you from the killing blow at the last instant, "
                f"then dissolves back into the summoning realm, its own strength spent!&x"
            )
            dismiss_summon(player)
            return

    session.send("&RYour vision darkens as you collapse.&x")

    if player.level < 100:
        loss = int(player.experience * 0.01)
        import leveling
        min_xp_for_level = leveling.cumulative_xp_for_level(player.level)
        new_xp = max(min_xp_for_level, player.experience - loss)
        actual_loss = player.experience - new_xp
        player.experience = new_xp
        if actual_loss:
            session.send(f"You lose {actual_loss} experience points.")
    else:
        session.send("You are level 100 and do not lose any experience.")

    ryo_loss = int(player.ryo * 0.05)
    player.ryo -= ryo_loss
    if ryo_loss:
        session.send(f"You lose {ryo_loss} ryo.")

    village = VILLAGES[player.village]
    player.room_vnum = village["hospital_room_vnum"]
    player.health = int(player.maximum_health * 0.25)
    player.chakra = int(player.maximum_chakra * 0.25)
    player.stamina = int(player.maximum_stamina * 0.25)
    status_effects.apply_effect(player.active_status_effects, "recently defeated", source="defeat")

    session.combat_target = None
    reset_summon_round_state(player)
    session.send(f"Village medics recover you and transport you to the {village['village_short_name']} Village Hospital.")


# --- PvP combat -------------------------------------------------------
#
# Deliberately parallel to the mob-combat path above rather than
# integrated into it -- session.pvp_target is a separate attribute from
# session.combat_target (Mob-only), so none of the extensively-tested
# mob-combat internals above needed to change at all. Blocked entirely
# in PvP-safe rooms (Room.safe -- see world.py/content.py for which
# rooms default to safe); checked both when an attack is initiated and
# every pulse afterward, so walking into a safe room mid-fight ends it.

def start_pvp_attack(session, target_session) -> None:
    """Mutual aggro -- both sessions start attacking each other, mirroring
    how mob combat is a two-sided exchange each pulse."""
    session.pvp_target = target_session
    target_session.pvp_target = session


def _player_attack_target_once(session, player, target_session, target) -> None:
    """One single PvP attack (to-hit roll through the damage/miss/dodge
    messages to both sides) from player against target -- extracted so
    resolve_pvp_pulse can call this once per attack a player has
    earned this round (see _roll_extra_attacks), rather than
    duplicating the whole sequence inline for each one. Behavior is
    identical to what resolve_pvp_pulse always did for its one
    guaranteed attack; the defeat/wimpy check that used to live
    inline here now happens once in resolve_pvp_pulse itself, after
    every attack this round, not inside each individual swing.

    Confirmed design (reversed from an earlier turn): automatic
    attacks fire normally during a hand-sign cast, matching
    _player_attack_mob_once's own identical reversal -- see that
    function's docstring for the full reasoning."""
    if _is_action_blocked(player):
        session.send("You are unable to act!")
        return
    import commands as commands_module
    import weather
    import data_personality
    import tailed_beasts
    set_bonus = commands_module.equipped_set_bonus_percent(player)
    player_hit_roll = derived_stats.hit_roll(player, set_bonus + data_personality.personality_bonus_percent(player, "hit_roll") + tailed_beasts.rampage_bonus_percent(player) + tailed_beasts.mode_bonus_percent(player)) + commands_module.equipped_weapon_hitroll_bonus(player) + _summon_weapon_buff_hitroll_bonus(player)
    target_set_bonus = commands_module.equipped_set_bonus_percent(target)
    target_armor_class = derived_stats.armor_class(target, target_set_bonus + data_personality.personality_bonus_percent(target, "armor_class") + tailed_beasts.rampage_bonus_percent(target) + tailed_beasts.mode_bonus_percent(target)) - commands_module.equipped_armor_class_bonus(target)
    to_hit = derived_stats.to_hit_chance(player_hit_roll, target_armor_class) + weather.combat_accuracy_modifier() + _sharingan_hitroll_bonus(player) - _accuracy_penalty_from_effects(player)
    to_hit = max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, to_hit))
    attacker_wielded = player.equipment.get("wielded", "")
    attack_verb = data_weapons.attack_verb_for_item(attacker_wielded)
    weapon_skill = data_weapons.skill_for_item(attacker_wielded)
    if weapon_skill:
        grow_skill_from_usage(player, weapon_skill)
    if random.randint(1, 100) > to_hit:
        session.send(f"You {attack_verb} at {target.name} but miss!")
        target_session.send(f"&C{player.name} attacks you but misses!&x")
        return

    dmg = _player_attack_damage(player)
    dmg = int(dmg * (100 + _summon_weapon_buff_damage_percent(player)) / 100)
    is_crit = random.randint(1, 100) <= derived_stats.critical_chance(player, set_bonus + data_personality.personality_bonus_percent(player, "critical_chance"))
    if is_crit:
        dmg = int(dmg * 1.5)

    if target.kamui_intangibility_rounds_left > 0:
        target.kamui_intangibility_rounds_left -= 1
        session.send(f"&RYour attack passes straight through {target.name}!&x")
        target_session.send(f"&R{player.name}'s attack passes straight through you!&x")
        return

    if random.randint(1, 100) <= derived_stats.dodge_chance(target, target_set_bonus + data_personality.personality_bonus_percent(target, "dodge_chance")) + weather.night_dodge_bonus() + _sharingan_dodge_bonus(target):
        session.send(f"&C{target.name} dodges your attack!&x")
        target_session.send(f"&CYou dodge {player.name}'s attack!&x")
        return

    if target.sharingan_active and target.bloodline_tomoe >= 3:
        reduced = _sharingan_predict_and_reduce_damage(target, dmg)
        if reduced < dmg:
            dmg = reduced
        else:
            target_session.send("&RYou weren't fast enough to counter!&x")

    dmg = commands_module.reduce_weapon_damage(target, data_weapons.weapon_type_for_item(attacker_wielded), dmg)
    dmg = status_effects.reduce_incoming_damage(target.active_status_effects, dmg)
    target.health -= dmg
    if is_crit:
        session.send(f"&YCritical hit!&x You {attack_verb} {target.name} for {damage_messages.describe_damage(dmg)} damage.")
    else:
        session.send(f"You {attack_verb} {target.name} for {damage_messages.describe_damage(dmg)} damage.")
    target_session.send(f"{player.name} {data_weapons.attack_verb_for_item_third_person(attacker_wielded)} you for {damage_messages.describe_damage(dmg)} damage.")


def _clone_attack_target_once(session, player, target_session, target, clone) -> None:
    """A live clone assists in PvP under the same safety and defense rules."""
    import commands as commands_module
    import weather
    element = clone.clone_element
    label = f"{element} clone" if element != "none" else "shadow clone"
    to_hit = derived_stats.to_hit_chance(
        derived_stats.hit_roll(player),
        derived_stats.armor_class(target) - commands_module.equipped_armor_class_bonus(target),
    ) + weather.combat_accuracy_modifier() - _accuracy_penalty_from_effects(player)
    if random.randint(1, 100) > max(derived_stats.TO_HIT_MIN_PCT, min(derived_stats.TO_HIT_MAX_PCT, to_hit)):
        session.send(f"Your {label} attacks {target.name} but misses!")
        return
    if target.kamui_intangibility_rounds_left > 0:
        target.kamui_intangibility_rounds_left -= 1
        return
    if random.randint(1, 100) <= derived_stats.dodge_chance(target) + weather.night_dodge_bonus() + _sharingan_dodge_bonus(target):
        target_session.send(f"&CYou dodge {player.name}'s {label}!&x")
        return
    damage = int(_player_attack_damage(player) * SHADOW_CLONE_DAMAGE_SCALE * (1.25 if element == "earth" else 1))
    damage = commands_module.reduce_weapon_damage(target, data_weapons.weapon_type_for_item(player.equipment.get("wielded", "")), damage)
    damage = status_effects.reduce_incoming_damage(target.active_status_effects, damage)
    target.health -= damage
    session.send(f"Your {label} strikes {target.name} for {damage_messages.describe_damage(damage)} damage.")
    target_session.send(f"{player.name}'s {label} strikes you for {damage_messages.describe_damage(damage)} damage.")
    clone_effect = {"lightning": "paralyzed", "water": "drained", "sand": "entangled"}.get(element)
    if clone_effect and random.randint(1, 100) <= 20:
        status_effects.apply_effect(target.active_status_effects, clone_effect, source=f"{element} clone", duration_override=2)
        target_session.send(status_effects.EFFECT_DEFS[clone_effect]["message"].format(target="you"))


def _resolve_ninken_flee_lock(session, player, target_session, target) -> None:
    """The Ninken pack's own real, PvP-only mechanic (Section 118) --
    a hard flee-lock against the SUMMONER's own chosen opponent,
    specifically. Reuses the same summon_flee_locked field Manda's
    own "bind" mechanic already uses (see combat._resolve_summon_
    round and commands.cmd_flee's own check), but sets it on the
    TARGET here, not the summoner -- confirmed directly this
    mechanic only makes sense in real PvP, unlike the other 5, which
    all fire during ordinary PvE combat instead."""
    summon = active_summon(player)
    if summon is None or summon.health <= 0:
        return
    import data_summons
    tier = data_summons.tier_by_key(summon.summon_tier_key)
    if tier and tier["mechanic"] == "flee_lock":
        if not target.summon_flee_locked:
            target.summon_flee_locked = True
            session.send(f"&Y{summon.name} circles {target.name}, cutting off any chance of escape!&x")
            target_session.send(f"&R{summon.name} circles you -- you won't be able to flee this fight!&x")


def resolve_pvp_pulse(session) -> None:
    """One automatic-attack round for a session's ongoing PvP fight, if
    any. Assumes tick_effects_pulse() has already run for this pulse,
    same as resolve_pulse()."""
    player = session.player
    target_session = session.pvp_target
    if target_session is None:
        return
    target = target_session.player
    if (
        target is None
        or target.room_vnum != player.room_vnum
        or target.health <= 0
        or player.health <= 0
    ):
        session.pvp_target = None
        target_session.pvp_target = None
        reset_summon_round_state(player)
        reset_summon_round_state(target)
        return

    room = world.WORLD.get(player.room_vnum)
    if room and room.safe:
        session.send("&DThe safety of this area causes you to stand down.&x")
        target_session.send(f"&D{player.name} stands down -- this area is PvP-safe.&x")
        session.pvp_target = None
        target_session.pvp_target = None
        reset_summon_round_state(player)
        reset_summon_round_state(target)
        return
    if target.izanami_trapped:
        return

    if player.jinchuriki_beast_key and player.rampage_until == 0.0:
        import tailed_beasts as tailed_beasts_module
        tailed_beasts_module.tick_jinchuriki_mastery(player)
        if tailed_beasts_module.check_rampage_trigger(player):
            tailed_beasts_module.trigger_rampage(player)
            session.send("&RSomething inside you SNAPS -- the beast's chakra floods your body, and you lose all control!&x")

    session.send("")
    if _is_action_blocked(player):
        session.send("You are stunned and can't act this round!" if "stunned" in player.active_status_effects else "You cannot act this round!")
        return

    import commands as commands_module
    for message in tick_passive_skill_growth(player):
        session.send(message)
    for message in tick_sharingan_upkeep(player):
        session.send(message)
    for message in tick_sharingan_mastery_gain(player):
        session.send(message)
    for message in tick_automatic_bloodline_awakening(player):
        session.send(message)
    _resolve_ninken_flee_lock(session, player, target_session, target)

    _player_attack_target_once(session, player, target_session, target)
    if target.health > 0:
        for _ in range(_roll_extra_attacks(player)):
            if target.health <= 0:
                break
            _player_attack_target_once(session, player, target_session, target)
    for clone in active_shadow_clones(player):
        if target.health <= 0:
            break
        if clone.room_vnum == player.room_vnum:
            _clone_attack_target_once(session, player, target_session, target, clone)

    if target.health <= 0:
        if try_trigger_izanagi(target_session):
            pass
        elif is_immortal_immune_to_defeat(target_session):
            clamp_immortal_health(target_session)
        else:
            handle_pvp_defeat(winner_session=session, loser_session=target_session)
    elif target.wimpy_percent > 0 and (target.health / target.maximum_health * 100) <= target.wimpy_percent:
        target_session.send(
            f"&Y(Your health has dropped to your wimpy threshold of {target.wimpy_percent}%!)&x"
        )
        commands_module.cmd_flee(target_session, [])


def handle_pvp_defeat(winner_session, loser_session, skip_mangekyo_check: bool = False) -> None:
    winner = winner_session.player
    loser = loser_session.player

    if not skip_mangekyo_check:
        import data_kekkei_genkai
        if data_kekkei_genkai.eligible_for_mangekyo_betrayal(winner, loser):
            loser.health = 1
            loser.downed_by = winner.name
            winner_session.pvp_target = None
            loser_session.pvp_target = None
            reset_summon_round_state(winner)
            reset_summon_round_state(loser)
            winner_session.send(
                f"&RYou stand over {loser.name}, utterly defeated at your feet.&x\n"
                f"&YSomething stirs within you -- a choice, and a cost. Finish them for the power you seek? "
                f"Type 'yes' to end their life, or 'no' to let them live.&x"
            )
            loser_session.send(
                f"&R{winner.name} stands over you, victorious. You are utterly at their mercy...&x"
            )
            return

    winner.player_kills += 1
    loser.player_deaths += 1

    winner_session.send(f"&GYou have defeated {loser.name} in combat!&x")
    winner_session.send(f"&r{loser.name} is DEAD!&x")

    import bounties
    bounty_id, bounty_entry = bounties.find_bounty_for_player(loser.name)
    if bounty_id is not None and bounties.claim_bounty(bounty_id, winner.name):
        winner.ryo += bounty_entry["reward_ryo"]
        winner.mission_points += bounty_entry["reward_mission_points"]
        winner.mission_points_earned_total += bounty_entry["reward_mission_points"]
        winner_session.send(
            f"&r*** BINGO BOOK BOUNTY CLAIMED (#{bounty_id}) ***&x\n"
            f"&Y{bounty_entry['reward_ryo']:,} ryo and {bounty_entry['reward_mission_points']} "
            f"mission point(s) added to your account.&x"
        )

    import chunin_exam
    stolen = chunin_exam.steal_scroll_on_pvp_defeat(winner, loser)
    if stolen:
        winner_session.send(f"&YYou snatch {stolen} from {loser.name}!&x")
        loser_session.send(f"&r{winner.name} takes your {stolen}!&x")

    winner_session.pvp_target = None
    loser_session.pvp_target = None
    reset_summon_round_state(winner)
    reset_summon_round_state(loser)

    handle_player_defeat(loser_session)  # reuses the existing XP/ryo loss + hospital respawn
