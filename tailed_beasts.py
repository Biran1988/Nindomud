"""
Tailed Beast release/roaming/despawn lifecycle (Section 127).

Per direct request/confirmation: "they are released in a random by
immortals with the release beast command that will randomly select a
tailed beast that hasn't been captured by a player using sealing
jutsu." Every real mechanic confirmed directly before building:

- 'unleash beast' (the staff command, see commands.py) picks ONE
  random beast from data_tailed_beasts.TAILED_BEASTS that is
  genuinely NOT currently sealed into any player (see
  is_beast_available below) -- if every single beast is currently
  held by some player, there's nothing left to release.
- Spawns at a genuinely random room anywhere in the whole world,
  confirmed directly (not a fixed starting point per village).
- Roams on its own, moving every 10-15 real minutes (confirmed
  directly: slower than an ordinary Wander mob's existing 2-4 min --
  "it should linger longer in each room before moving on"), and
  genuinely PAUSES this movement while actively fighting real
  players, exactly matching how an ordinary Wander mob already
  behaves (confirmed directly) -- resuming once left alone again.
- Automatically, unpromptedly attacks any real player found in its
  own room, confirmed directly ("destroys and kills everything in
  sight"), rather than only fighting back once attacked.
- Despawns automatically after a genuine 2 real hours if not killed
  or sealed by then, confirmed directly.

Capturing a beast (the Sealing Jutsu, a real killing blow that seals
it into the caster instead of an ordinary kill) and everything after
that -- mastery, rampage, Tailed Beast Mode -- are confirmed,
deliberate LATER stages of this same feature, not built in this
module yet.
"""

import random
import time
from typing import Optional

import data_tailed_beasts

BEAST_ROAM_MIN_SECONDS = 10 * 60.0   # confirmed directly: 10-15 real minutes between moves, slower than an ordinary Wander mob
BEAST_ROAM_MAX_SECONDS = 15 * 60.0
BEAST_LIFESPAN_SECONDS = 2 * 60 * 60.0  # confirmed directly: despawns after a genuine 2 real hours if unresolved

# The real, single base vnum for the 9 beast mob templates -- one per
# tail count, in ascending order (95000=Shukaku/1-tail through
# 95008=Kurama/9-tail). Confirmed genuinely free via a direct,
# comprehensive scan of MOB_TEMPLATES before choosing this range,
# learning from the earlier real Track Scroll vnum collision.
BEAST_TEMPLATE_VNUM_BASE = 95000


def _template_vnum_for(beast: dict) -> int:
    """The real, fixed mob-template vnum for this specific beast --
    one per tail count, ascending from BEAST_TEMPLATE_VNUM_BASE."""
    return BEAST_TEMPLATE_VNUM_BASE + (beast["tails"] - 1)


def register_all_beast_templates(combat_module) -> None:
    """(Re)registers all 9 real beast mob templates -- called once at
    real world startup (see content.py), matching every other
    hardcoded mob's own registration convention exactly. Uses
    combat.register_template, the same real function content.py's
    own mobs already use, so a beast gets a full, real SMAUG-style
    prototype (visible via mstat) like anything else."""
    for beast in data_tailed_beasts.TAILED_BEASTS:
        combat_module.register_template(
            _template_vnum_for(beast),
            beast["display_name"],
            level=100,
            max_health=beast["max_health"],
            min_damage=beast["min_damage"],
            max_damage=beast["max_damage"],
            experience_reward=0,  # a beast is never killed for ordinary XP -- it's either sealed (a real, separate reward) or driven off
            ryo_reward=0,
        )


def is_beast_available(beast_key: str, all_players_iter) -> bool:
    """Whether this specific beast is genuinely NOT currently sealed
    into any player -- confirmed directly: "a tailed beast that hasn't
    been captured by a player using sealing jutsu." all_players_iter
    is an iterable of every real Player to check (callers pass every
    online session's own player; a beast currently held by an
    OFFLINE jinchuriki is still genuinely unavailable, since sealing
    is confirmed to persist "even at death" -- so offline holders
    must be checked too, not just who's online right now)."""
    return not any(getattr(p, "jinchuriki_beast_key", None) == beast_key for p in all_players_iter)


def any_beast_currently_roaming(combat_module) -> bool:
    """Whether ANY Tailed Beast is currently a live, roaming mob
    somewhere in the world right now -- per direct request/
    confirmation: "if a beast has been spawned only 1 of that tail
    can be out at a time," confirmed as a genuine, global cap of ONE
    roaming beast total, regardless of which specific beast. Checked
    by 'unleash beast' as a real refusal case -- a second beast can't
    be released while one is already loose, whether or not it's
    currently downed-and-awaiting-sealing (that's still the same
    live mob instance, not yet resolved one way or the other)."""
    return any(
        getattr(mob, "tailed_beast_key", None)
        for room_mobs in combat_module.MOBS_BY_ROOM.values()
        for mob in room_mobs
    )


def pick_random_available_beast(all_players_iter) -> Optional[dict]:
    """A genuinely random beast from every one that's currently
    available (see is_beast_available) -- None if every single one is
    already sealed into some player, confirmed as the correct real
    refusal case rather than releasing an already-held beast again."""
    players = list(all_players_iter)
    available = [b for b in data_tailed_beasts.TAILED_BEASTS if is_beast_available(b["key"], players)]
    if not available:
        return None
    return random.choice(available)


def release_beast(beast: dict, world_module, combat_module) -> "combat_module.Mob":
    """Spawns a real, live instance of this beast at a genuinely
    random room anywhere in the whole world (confirmed directly),
    with a fresh real 2-hour despawn timer and its own real roaming
    schedule. Returns the spawned Mob.

    Per direct request/confirmation: "tailed beast cannot spawn in
    safe rooms" -- every real safe room (room.safe) is excluded from
    the candidate pool entirely, so a beast is guaranteed to never
    spawn in one. Falls back to every room if, somehow, every single
    room in the world were safe (a genuine defensive fallback that
    should never actually trigger in real play)."""
    candidates = [vnum for vnum, room in world_module.WORLD.rooms.items() if not room.safe]
    if not candidates:
        candidates = list(world_module.WORLD.rooms.keys())
    room_vnum = random.choice(candidates)
    vnum = _template_vnum_for(beast)
    mob = combat_module.spawn_mob(vnum, room_vnum)
    mob.tailed_beast_key = beast["key"]
    mob.tailed_beast_despawn_at = time.time() + BEAST_LIFESPAN_SECONDS
    mob.next_wander_at = time.time() + random.uniform(BEAST_ROAM_MIN_SECONDS, BEAST_ROAM_MAX_SECONDS)
    return mob


def process_tailed_beasts(combat_module, world_module, session_module) -> None:
    """Called once per real pulse (server.py's own pulse loop),
    alongside the existing process_wander -- handles every currently-
    live Tailed Beast's own real despawn timer, roaming movement, and
    unprompted attack on any real player found in its room. Genuinely
    separate from process_wander (rather than just flagging beasts
    Wander) since a beast needs its OWN real interval, its OWN
    despawn, and unprompted attacking -- none of which ordinary
    Wander mobs do."""
    now = time.time()
    for room_vnum in list(combat_module.MOBS_BY_ROOM.keys()):
        for mob in list(combat_module.MOBS_BY_ROOM.get(room_vnum, [])):
            if not getattr(mob, "tailed_beast_key", None):
                continue

            if mob.tailed_beast_downed_until != 0.0:
                if now >= mob.tailed_beast_downed_until:
                    combat_module._broadcast_to_room(mob.room_vnum, f"&D{mob.name} finally falls still and dies.&x")
                    combat_module.remove_mob(mob)
                continue

            if now >= mob.tailed_beast_despawn_at:
                combat_module._broadcast_to_room(
                    mob.room_vnum, f"&D{mob.name} vanishes as its chakra fades back into the wilds.&x"
                )
                combat_module.remove_mob(mob)
                continue

            # Unprompted attack on any real player genuinely in this room right now.
            for s in session_module.ACTIVE_SESSIONS:
                if (s.player and s.player.room_vnum == mob.room_vnum
                        and s.player.health > 0 and s.combat_target is not mob):
                    s.combat_target = mob
                    s.player.recently_defeated_timer = 0.0
                    s.send(f"&R{mob.name} turns on you without warning!&x")

            if combat_module._mob_is_being_fought(mob):
                continue
            if now < mob.next_wander_at:
                continue
            mob.next_wander_at = now + random.uniform(BEAST_ROAM_MIN_SECONDS, BEAST_ROAM_MAX_SECONDS)

            room = world_module.WORLD.get(mob.room_vnum)
            if not room or not room.exits:
                continue
            candidates = [
                (direction, dest) for direction, dest in room.exits.items()
                if world_module.WORLD.get(dest) and world_module.WORLD.get(dest).enabled
                and not world_module.WORLD.get(dest).apartment
            ]
            if not candidates:
                continue
            direction, destination = random.choice(candidates)
            combat_module._broadcast_to_room(mob.room_vnum, f"&R{mob.name} rampages {direction}, leaving destruction behind!&x")
            combat_module.MOBS_BY_ROOM[mob.room_vnum].remove(mob)
            mob.room_vnum = destination
            combat_module.MOBS_BY_ROOM.setdefault(destination, []).append(mob)
MASTERY_GAIN_CHANCE_PER_ROUND = 0.02  # confirmed directly: "a small, slow gain per real combat round," genuinely taking a long time to reach 100 at this rate
RAMPAGE_IMMUNITY_MASTERY_PCT = 65  # confirmed directly: at/above this mastery, rampage becomes genuinely impossible
RAMPAGE_CHANCE_PER_ROUND = 1.0 / 1000.0  # confirmed directly: "1 in 1000 per combat round," only while below the immunity threshold
RAMPAGE_STAT_BOOST_PCT = 50  # confirmed directly: "+50%" to HP/chakra/stamina AND damage/hit roll/armor class while rampaging


def tick_jinchuriki_mastery(player) -> bool:
    """Rolls the real, flat per-round chance (MASTERY_GAIN_CHANCE_PER_
    ROUND) for a jinchuriki to gain +1 real mastery -- mirrors the
    existing bloodline mastery-gain precedent (data_kekkei_genkai.
    tick_mastery_gain) in spirit, confirmed directly, but genuinely
    simpler: a single flat rate, no Potential/Talent split, since
    jinchuriki mastery is confirmed as a plain 0-100 scale with no
    hidden ceiling. Callers (combat.py) are expected to have already
    confirmed player.jinchuriki_beast_key is set before calling this.
    Returns True if mastery genuinely increased this call, for the
    caller to decide whether to narrate it."""
    if player.jinchuriki_mastery >= 100:
        return False
    if random.random() < MASTERY_GAIN_CHANCE_PER_ROUND:
        player.jinchuriki_mastery = min(100, player.jinchuriki_mastery + 1)
        return True
    return False


def check_rampage_trigger(player) -> bool:
    """Rolls the real, confirmed rampage chance for this specific
    combat round -- genuinely impossible at or above
    RAMPAGE_IMMUNITY_MASTERY_PCT (confirmed directly: 65%), otherwise
    a flat, tiny RAMPAGE_CHANCE_PER_ROUND (confirmed directly: 1 in
    1000) regardless of exactly how far below 65% they are. Callers
    are expected to have already confirmed player.jinchuriki_beast_
    key is set and the player is genuinely in a combat round before
    calling this."""
    if player.jinchuriki_mastery >= RAMPAGE_IMMUNITY_MASTERY_PCT:
        return False
    return random.random() < RAMPAGE_CHANCE_PER_ROUND


def trigger_rampage(player) -> None:
    """Begins a real rampage -- per direct confirmation (Section 127
    continued): "They cannot do any commands they auto attack
    everything and gain temporary tailed beast powers stat boost and
    hp chakra stamina boosts while the rampage is active." Sets the
    real, confirmed 5-10 real-minute duration (a genuinely fresh
    random roll each time this specific rampage begins, not a fixed
    module-level constant) and marks the player as rampaging --
    checked directly by commands.dispatch (blocking all commands) and
    combat's own per-round resolution (auto-attacking everyone in the
    room, players and mobs alike, confirmed directly) for its own
    real duration."""
    player.rampage_until = time.time() + random.uniform(5 * 60.0, 10 * 60.0)
    player.tailed_beast_mode_active = False  # defensive safeguard, per direct confirmation -- can't naturally co-occur (rampage requires <65% mastery, Mode requires 100%), but handled explicitly regardless
    boost = RAMPAGE_STAT_BOOST_PCT
    for max_attr, cur_attr in (("maximum_health", "health"), ("maximum_chakra", "chakra"), ("maximum_stamina", "stamina")):
        max_before = getattr(player, max_attr)
        added = max_before * boost // 100
        setattr(player, max_attr, max_before + added)
        setattr(player, cur_attr, getattr(player, cur_attr) + added)


def process_rampages(combat_module, session_module) -> None:
    """Called once per real pulse (server.py's own pulse loop) --
    resolves every currently-rampaging jinchuriki's own real "auto
    attack everything" round, per direct confirmation (Section 127
    continued): "They cannot do any commands they auto attack
    everything." Genuinely independent of the player's own combat_
    target/pvp_target (a rampage overrides normal targeting
    entirely) -- attacks every real player AND every real mob
    physically in the same room, confirmed directly ("Genuinely
    everyone in the room -- both real players and real mobs,
    indiscriminately"), one real attack each per pulse, reusing the
    exact same real single-target attack functions ordinary combat
    already uses so the real damage math is identical. Automatically
    ends the rampage (clearing rampage_until) the instant its own
    real duration expires, matching how commands.dispatch's own
    inline check already does for a player who happens to type
    something mid-rampage."""
    now = time.time()
    for s in list(session_module.ACTIVE_SESSIONS):
        player = s.player
        if not player or not player.rampage_until:
            continue
        if now >= player.rampage_until:
            player.rampage_until = 0.0
            boost = RAMPAGE_STAT_BOOST_PCT
            for max_attr, cur_attr in (("maximum_health", "health"), ("maximum_chakra", "chakra"), ("maximum_stamina", "stamina")):
                max_now = getattr(player, max_attr)
                # max_now = original * (1 + boost/100), so original = max_now / (1 + boost/100).
                original_max = max_now * 100 // (100 + boost)
                removed = max_now - original_max
                setattr(player, max_attr, original_max)
                setattr(player, cur_attr, max(1, getattr(player, cur_attr) - removed))
            s.send("&YThe beast's rage finally subsides -- you're back in control.&x")
            continue
        if player.health <= 0:
            continue

        for mob in list(combat_module.mobs_in_room(player.room_vnum)):
            if mob.health > 0:
                combat_module._player_attack_mob_once(s, player, mob)
                if mob.health <= 0:
                    combat_module.handle_mob_defeat(s, mob)

        for other in list(session_module.ACTIVE_SESSIONS):
            if (other is not s and other.player and other.player.room_vnum == player.room_vnum
                    and other.player.health > 0):
                combat_module._player_attack_target_once(s, player, other, other.player)
                if other.player.health <= 0:
                    if combat_module.is_immortal_immune_to_defeat(other):
                        combat_module.clamp_immortal_health(other)
                    else:
                        combat_module.handle_pvp_defeat(winner_session=s, loser_session=other)


def rampage_bonus_percent(player) -> int:
    """The real, flat rampage combat bonus (per direct confirmation:
    "Damage output, hit roll, and armor class") -- RAMPAGE_STAT_
    BOOST_PCT while genuinely rampaging right now, 0 otherwise.
    Applies identically to all 3 confirmed stats, unlike the
    personality-trait bonus (which varies by stat) -- callers add
    this alongside that one in the same real bonus_percent
    parameter every derived_stats.py formula already accepts."""
    if player.rampage_until and time.time() < player.rampage_until:
        return RAMPAGE_STAT_BOOST_PCT
    return 0


MODE_BASE_BONUS_PCT = 25.0  # confirmed directly: "a base +25% at 1-tail"
MODE_BONUS_PER_TAIL_PCT = 3.75  # confirmed directly: scaling up to roughly 55% at 9-tails (25 + 8*3.75 = 55)


def mode_bonus_percent(player) -> int:
    """The real, tail-count-scaled Tailed Beast Mode combat bonus --
    confirmed directly ("more refined, less raw" than the rampage's
    own flat +50%): 25% at 1-tail (Shukaku) up to 55% at 9-tails
    (Kurama), applied identically to damage/hit roll/armor class,
    same real shape as rampage_bonus_percent but genuinely smaller
    and with absolutely no downside. 0 unless the player genuinely
    has a beast sealed AND has the Mode toggled on right now (Mode
    can only ever be toggled on at 100% mastery in the first place --
    see commands.cmd_tailed_beast_mode -- but this checks the live
    toggle state directly, not mastery again, since the toggle itself
    is the real, single source of truth once already on)."""
    if not player.tailed_beast_mode_active or not player.jinchuriki_beast_key:
        return 0
    beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY.get(player.jinchuriki_beast_key)
    if not beast:
        return 0
    return round(MODE_BASE_BONUS_PCT + (beast["tails"] - 1) * MODE_BONUS_PER_TAIL_PCT)


BOMB_DAMAGE_MULTIPLIER = 2.5  # a real, meaningful multiple of the beast's own top real per-hit damage, so the Bomb reads as a genuine signature technique, not just another ordinary attack


def bomb_damage(player) -> int:
    """The real, tail-count-scaled damage for a Tailed Beast Bomb
    cast, per direct confirmation ("with its own real damage scaling
    by tail count too") -- computed proportionally from the caster's
    own specific beast's own real max_damage stat (data_tailed_
    beasts.py, already tail-count-scaled), so a 9-tail's Bomb
    genuinely, meaningfully outdamages a 1-tail's. 0 if the caster
    somehow has no real beast at all (a genuine safety fallback,
    should never actually happen given the real gates already checked
    before this is ever called)."""
    beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY.get(player.jinchuriki_beast_key)
    if not beast:
        return 0
    return round(beast["max_damage"] * BOMB_DAMAGE_MULTIPLIER)
