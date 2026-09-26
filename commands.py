"""
Command parser and handlers.

Covers: movement, social commands, equipment,
prompt/password management, score/who display, real combat
(auto-attacks via the pulse loop + jutsu commands), training/practice,
missions, Kage interactions, shop buying, and staff OLC commands.
"""

import random
import re
import time
from typing import List, Optional

import colors
import combat
import chunin_exam
import config
import data_headbands
import consumables
import content
import corpses
import data_crafting
import fishing
import groups
import teams
import inventory
import jobs
import lumberjack
import cooking
import farming
import tool_durability
import gems
import mining
import armorsmith
import weaponsmith
import gemcutter
import apartments
import auction
import playershops
import weather
import data_appearance
import data_clans
import biomes
import data_jutsu
import data_rarity
import data_passives
import data_shops
import data_weapons
import damage_messages
import derived_stats
import help_system
import item_types
import kage
import legendary_items
import leveling
import missions
import security
import roulette
import slots
import status_effects
import storage
import village_perks
import olc
import programs
import world
from models import Player
from data_villages import VILLAGES
from prompt import PRESETS

WORLD = world.WORLD

TRAINABLE_ATTRIBUTES = [
    "strength", "wisdom", "constitution", "intelligence", "dexterity",
    "luck", "perception", "willpower", "chakra_control",
]
TRAIN_ATTRIBUTE_NAMES = {
    "str": "strength", "wis": "wisdom", "con": "constitution",
    "int": "intelligence", "dex": "dexterity", "luk": "luck",
    "per": "perception", "wil": "willpower", "cc": "chakra_control",
    "chakractrl": "chakra_control", "chakracontrol": "chakra_control",
}


BARE_NAME_JUTSU_CATEGORIES = ("taijutsu", "bukijutsu")  # physical, not chakra-incantation


def has_silent_genjutsu(player) -> bool:
    """Whether player has learned the Silent Genjutsu passive
    (Section 122, level 75) -- the single real gate every place this
    passive's effects apply (bare-name dispatch, skipping hand signs,
    hiding the target's own cast message at 100% mastery) checks
    against. Always on once learned, per direct confirmation -- no
    toggle exists."""
    return "Silent Genjutsu" in player.learned_skills



def dispatch_line(session, line: str) -> None:
    """Top-level entry point: try a Taijutsu/Bukijutsu jutsu command first
    (these can be used by bare name -- e.g. 'dynamic entry <target>' or
    'throw shuriken <target>'), then fall back to ordinary single-word
    verb commands. Ninjutsu and Genjutsu are NOT matched here -- they
    require 'perform <name>' (see cmd_perform), reflecting that they take
    a deliberate hand seal / incantation rather than a reflexive physical
    strike or thrown weapon."""
    words = line.split()
    if not words:
        return
    lower_words = [w.lower() for w in words]

    if world.normalize_direction(lower_words[0]):
        dispatch(session, words[0], words[1:])
        return

    jutsu_key, consumed = data_jutsu.match_prefix(lower_words)
    if jutsu_key:
        jutsu_class = data_jutsu.JUTSU[jutsu_key]["class_requirement"]
        if jutsu_class in BARE_NAME_JUTSU_CATEGORIES or (
            jutsu_class == "genjutsu" and session.player and has_silent_genjutsu(session.player)
        ):
            cmd_use_jutsu(session, jutsu_key, words[consumed:])
            return

    verb, args = words[0], words[1:]
    dispatch(session, verb, args)


def dispatch(session, verb: str, args: List[str]) -> None:
    verb = verb.lower()

    if session.player and verb not in ("look", "l", "say", "ooc"):
        player = session.player
        if player.downed_by:
            session.send("&RYou're gravely wounded and at someone's mercy -- you can't do that right now.&x")
            return
        if player.frozen_until and time.time() < player.frozen_until:
            session.send("&RYou're gravely wounded and can't move.&x")
            return
        if player.rampage_until:
            if time.time() < player.rampage_until:
                session.send("&RYou're consumed by the beast's rage -- you have no control over your own body!&x")
                return
            player.rampage_until = 0.0

    direction = world.normalize_direction(verb)
    if direction:
        cmd_move(session, direction)
        return

    if verb.startswith("@"):
        cmd_emote(session, [verb] + args)
        return

    handler = COMMANDS.get(verb)
    if not handler:
        session.send("Huh?")
        return
    handler(session, args)


# --- Movement --------------------------------------------------------

def _wake_and_stand(session) -> None:
    """Auto-cancel resting/sleeping the moment a player moves or fights,
    since those positions only ever affect regen rate, not combat itself."""
    player = session.player
    if player.position != "standing":
        previous = player.position
        player.position = "standing"
        session.send(f"You stop {previous} and stand up.")


def _broadcast_globally(message: str) -> None:
    """Sends message to every connected, playing session -- matches
    kage.py's own real "has been promoted" announcement pattern
    exactly, since no shared global-broadcast function exists yet."""
    import session as session_module
    for s in session_module.ACTIVE_SESSIONS:
        if s.state.name == "PLAYING":
            s.send(message)
            s.send_prompt()


def _fire_enter_triggers(session) -> None:
    """Fires the destination room's 'enter' programs, then each mob
    present's 'greet' programs, in that order. Shared by every way a
    player can arrive in a new room -- walking (cmd_move) and recall.
    Also checks for a war/territory trap in the new room (see
    territory.check_trap_trigger)."""
    player = session.player
    room = WORLD.get(player.room_vnum)
    if room and room.programs:
        programs.fire_programs(session, room.programs, "enter", speaker_name=room.name)
    for mob in combat.mobs_in_room(player.room_vnum):
        t = combat.MOB_TEMPLATES.get(mob.template_vnum)
        if t and t.get("mob_programs"):
            programs.fire_programs(session, t["mob_programs"], "greet", speaker_name=mob.name.capitalize())

    import territory
    trap_message = territory.check_trap_trigger(player)
    if trap_message:
        session.send(trap_message)


def cmd_move(session, direction: str) -> None:
    player = session.player

    if player.illusion_walk_caster is not None:
        player.stamina = max(0, player.stamina // 2)
        if player.stamina <= ILLUSION_WALK_STAMINA_FLOOR:
            caster_name = player.illusion_walk_caster
            player.illusion_walk_caster = None
            player.illusion_walk_real_room_vnum = None
            player.illusion_walk_range = 0
            player.illusion_walk_steps_taken = 0
            session.send(
                f"&YExhausted, the illusion shatters -- you can see {caster_name} again, real and solid in front of you!&x"
            )
            cmd_look(session, [])
            return
        player.illusion_walk_steps_taken += 1
        if player.illusion_walk_steps_taken > player.illusion_walk_range:
            player.illusion_walk_steps_taken = 0
            session.send(f"&YThe world snaps back into focus -- you're still exactly where you started!&x")
            real_room = WORLD.get(player.illusion_walk_real_room_vnum)
            if real_room:
                session.send(f"&C{real_room.name}&x")
                session.send(real_room.description)
            return
        import areas
        area = areas.find_area_for_vnum(player.illusion_walk_real_room_vnum)
        candidates = []
        if area:
            candidates = [
                vnum for vnum in WORLD.rooms.keys()
                if vnum != player.illusion_walk_real_room_vnum and area.vnum_start <= vnum <= area.vnum_end
            ]
        if not candidates:
            fake_room = WORLD.get(player.illusion_walk_real_room_vnum)
        else:
            fake_room = WORLD.get(random.choice(candidates))
        session.send(f"&YYou walk {direction}.&x")
        if fake_room:
            session.send(f"&C{fake_room.name}&x")
            session.send(fake_room.description)
        return

    room = WORLD.get(player.room_vnum)

    if player.jailed_until:
        if time.time() >= player.jailed_until:
            import jail as jail_module
            jail_module.release(player)
            session.send("&GYour jail sentence is up. You are released.&x")
            cmd_look(session, [])
            return
        else:
            remaining_minutes = int((player.jailed_until - time.time()) / 60) + 1
            session.send(f"&DYou are jailed for {remaining_minutes} more minute(s) and cannot leave.&x")
            return

    if session.combat_target is not None:
        session.send("You can't leave while you're fighting!")
        return
    if status_effects.has_effect(player.active_status_effects, "entangled"):
        session.send("You're entangled and can't move!")
        return

    _wake_and_stand(session)

    if direction not in room.exits:
        session.send("You can't go that way.")
        return

    is_staff = session.account is not None and session.account.staff_level != "player"
    if "door" in room.exit_flags.get(direction, []) and not room.exit_door_open.get(direction, False) and not is_staff:
        session.send(f"The door to the {direction} is closed.")
        return
    if not is_staff:
        for mob in combat.mobs_in_room(player.room_vnum):
            t = combat.MOB_TEMPLATES.get(mob.template_vnum)
            if t and t.get("mob_programs") and programs.check_level_gate(session, t["mob_programs"], direction, speaker_name=mob.name.capitalize()):
                return

    destination_vnum = room.exits[direction]
    destination = WORLD.get(destination_vnum)
    if destination and not destination.enabled and not is_staff:
        session.send("That area is currently closed.")
        return
    if destination and destination.apartment and destination.owner and destination.owner != player.name and not is_staff:
        session.send("The door is locked. This is someone's private home.")
        return

    session.broadcast_room(f"{player.name} leaves {direction}.", exclude_self=True)
    player.room_vnum = room.exits[direction]
    session.broadcast_room(f"{player.name} arrives from the {world.OPPOSITE_DIRECTION.get(direction, direction)}.", exclude_self=True)

    if session.trade is not None:
        import trade as trade_module
        other = session.trade.other(session)
        trade_module.cancel_trade(session.trade)
        session.send("&DYou walk away, cancelling the trade.&x")
        other.send(f"&D{player.name} walks away, cancelling the trade.&x")

    cmd_look(session, [])
    _fire_enter_triggers(session)


def cmd_open(session, args: List[str]) -> None:
    player = session.player
    room = WORLD.get(player.room_vnum)
    if not args:
        session.send("Open what direction?")
        return
    direction = world.normalize_direction(args[0])
    if not direction or direction not in room.exits or "door" not in room.exit_flags.get(direction, []):
        session.send("There's no door that way.")
        return
    if room.exit_door_open.get(direction, False):
        session.send("It's already open.")
        return
    if "locked" in room.exit_flags.get(direction, []):
        session.send("It's locked.")
        return
    room.exit_door_open[direction] = True
    session.send(f"You open the door to the {direction}.")


def cmd_close(session, args: List[str]) -> None:
    player = session.player
    room = WORLD.get(player.room_vnum)
    if not args:
        session.send("Close what direction?")
        return
    direction = world.normalize_direction(args[0])
    if not direction or direction not in room.exits or "door" not in room.exit_flags.get(direction, []):
        session.send("There's no door that way.")
        return
    if not room.exit_door_open.get(direction, False):
        session.send("It's already closed.")
        return
    room.exit_door_open[direction] = False
    session.send(f"You close the door to the {direction}.")


def cmd_unlock(session, args: List[str]) -> None:
    player = session.player
    room = WORLD.get(player.room_vnum)
    if not args:
        session.send("Unlock what direction?")
        return
    direction = world.normalize_direction(args[0])
    flags_here = room.exit_flags.get(direction, []) if direction else []
    if not direction or direction not in room.exits or "door" not in flags_here:
        session.send("There's no door that way.")
        return
    if "locked" not in flags_here:
        session.send("It isn't locked.")
        return

    if "keyitem" in flags_here:
        required = room.exit_key_item.get(direction, "")
        if not any(_item_matches(required, item) for item in player.inventory):
            session.send(f"You don't have the right key.")
            return
    elif "passcode" in flags_here:
        given = " ".join(args[1:]).strip()
        if given != room.exit_passcode.get(direction, ""):
            session.send("That's not the right passcode.")
            return

    flags_here.remove("locked")
    session.send(f"You unlock the door to the {direction}.")


def cmd_lock(session, args: List[str]) -> None:
    player = session.player
    room = WORLD.get(player.room_vnum)
    if not args:
        session.send("Lock what direction?")
        return
    direction = world.normalize_direction(args[0])
    flags_here = room.exit_flags.get(direction, []) if direction else []
    if not direction or direction not in room.exits or "door" not in flags_here:
        session.send("There's no door that way.")
        return
    if room.exit_door_open.get(direction, False):
        session.send("You'll need to close it first.")
        return
    if "locked" in flags_here:
        session.send("It's already locked.")
        return
    flags_here.append("locked")
    session.send(f"You lock the door to the {direction}.")


FLEE_SUCCESS_CHANCE = 75  # percent -- the "low level" flee: a flat
# chance, no stat scaling yet. A higher-tier version that flees AND
# lands a free attack on the way out is planned as a later addition,
# per the request that introduced this command.


def cmd_wimpy(session, args: List[str]) -> None:
    """Sets (or shows) the wimpy auto-flee threshold -- a percentage of
    max health at or below which combat.py automatically attempts
    cmd_flee on the player's behalf, both in PvE and PvP (see
    resolve_pulse/resolve_pvp_pulse). 0 disables it, the default --
    nothing changes for a player who never sets one."""
    player = session.player
    if not args:
        if player.wimpy_percent > 0:
            session.send(f"Your wimpy threshold is currently {player.wimpy_percent}%.")
        else:
            session.send("Your wimpy threshold is currently disabled. Usage: wimpy <0-100>")
        return
    if not args[0].isdigit() or not (0 <= int(args[0]) <= 100):
        session.send("Usage: wimpy <0-100>  (0 disables it)")
        return
    percent = int(args[0])
    player.wimpy_percent = percent
    if percent == 0:
        session.send("Wimpy disabled -- you will no longer auto-flee.")
    else:
        session.send(
            f"Wimpy set to {percent}% -- you'll attempt to flee once your health "
            f"drops to or below that."
        )


def cmd_auction(session, args: List[str]) -> None:
    """The Auction House (auction.py) -- list an item from inventory
    for other players to bid on, with an optional instant buyout
    price. A listing resolves periodically (not the instant it
    technically expires, same as weather/mob-respawn). No escrow: a
    bid just records a promise, checked again for real ryo at
    resolution time -- see auction.py's own docstring for the full
    reasoning. Works whether the seller/winning bidder are online or
    offline when a listing actually resolves."""
    player = session.player
    usage = (
        "Usage: auction list | auction sell <item> <starting bid> [buyout price] [duration minutes]\n"
        "       auction bid <id> <amount> | auction buyout <id> | auction cancel <id>"
    )

    if not args:
        session.send(usage)
        return

    subcommand = args[0].lower()

    if subcommand == "list":
        listings = auction.all_listings()
        if not listings:
            session.send("There are no active auction listings.")
            return
        lines = ["&WActive Auction Listings:&x"]
        now = time.time()
        for auction_id, entry in sorted(listings.items(), key=lambda kv: int(kv[0])):
            remaining = max(0, entry["expires_at"] - now)
            bidder_str = f" (high bidder: {entry['current_bidder']})" if entry["current_bidder"] else " (no bids yet)"
            buyout_str = f", buyout {entry['buyout_price']:,} ryo" if entry["buyout_price"] else ""
            lines.append(
                f"  #{auction_id}: {entry['item_name']} -- seller {entry['seller']}, "
                f"current bid {entry['current_bid']:,} ryo{bidder_str}{buyout_str}, "
                f"{auction.format_duration(remaining)} left"
            )
        session.send("\n".join(lines))
        return

    if subcommand == "sell":
        if auction.has_active_listing(player.name):
            session.send("You already have an active auction listing -- wait for it to sell, buyout, or be cancelled first.")
            return

        rest = args[1:]
        numeric_trailing = []
        while rest and rest[-1].isdigit() and len(numeric_trailing) < 3:
            numeric_trailing.insert(0, rest.pop())
        item_query = " ".join(rest)
        if not item_query or not numeric_trailing:
            session.send(usage)
            return

        starting_bid = int(numeric_trailing[0])
        buyout_price = int(numeric_trailing[1]) if len(numeric_trailing) >= 2 else None
        duration_minutes = int(numeric_trailing[2]) if len(numeric_trailing) >= 3 else None

        if starting_bid <= 0:
            session.send("Starting bid must be a positive amount.")
            return
        if buyout_price is not None and buyout_price <= starting_bid:
            session.send("Buyout price must be higher than the starting bid.")
            return

        duration_seconds = auction.DEFAULT_DURATION_SECONDS
        if duration_minutes is not None:
            duration_seconds = duration_minutes * 60
            if not (auction.MIN_DURATION_SECONDS <= duration_seconds <= auction.MAX_DURATION_SECONDS):
                session.send(
                    f"Duration must be between {auction.MIN_DURATION_SECONDS // 60} and "
                    f"{auction.MAX_DURATION_SECONDS // 60} minutes."
                )
                return

        match = find_indexed_item(item_query, player.inventory)
        if not match:
            session.send("You aren't carrying that.")
            return

        player.inventory.remove(match)
        auction_id = auction.create_listing(player.name, match, starting_bid, duration_seconds, buyout_price)
        session.send(
            f"You list {rarity_colored_name(match)} for auction (#{auction_id}), "
            f"starting bid {starting_bid:,} ryo."
        )
        return

    if subcommand == "bid":
        if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
            session.send("Usage: auction bid <id> <amount>")
            return
        ok, message = auction.place_bid(int(args[1]), player.name, int(args[2]))
        session.send(message)
        return

    if subcommand == "buyout":
        if len(args) != 2 or not args[1].isdigit():
            session.send("Usage: auction buyout <id>")
            return
        ok, message = auction.buyout_listing(int(args[1]), player.name)
        session.send(message)
        return

    if subcommand == "cancel":
        if len(args) != 2 or not args[1].isdigit():
            session.send("Usage: auction cancel <id>")
            return
        ok, message = auction.cancel_listing(int(args[1]), player.name)
        if ok:
            player.inventory.append(message)  # message holds the returned item's name on success
            session.send(f"You cancel the listing and get back {rarity_colored_name(message)}.")
        else:
            session.send(message)
        return

    session.send(usage)


def cmd_flee(session, args: List[str]) -> None:
    """Escapes an ongoing fight (PvE or PvP) -- themed as using the
    Body Replacement Technique (Kawarimi), the classic Naruto
    substitution/escape jutsu, rather than a generic "you run away."
    Not guaranteed: FLEE_SUCCESS_CHANCE governs it, and a failed
    attempt still costs the round (the fight continues, the next pulse
    resolves normally). On success, moves to a random valid exit --
    same door-open/closed rules as normal movement, so fleeing can't
    bypass a closed door -- and clears combat state on both sides for
    PvP, notifying the other player."""
    player = session.player
    if session.combat_target is None and session.pvp_target is None:
        session.send("You aren't fighting anyone.")
        return
    if player.summon_flee_locked:
        session.send("&RYou're bound tight and can't get away!&x")
        return

    room = WORLD.get(player.room_vnum)
    is_staff = session.account is not None and session.account.staff_level != "player"
    valid_exits = [
        (direction, dest_vnum) for direction, dest_vnum in room.exits.items()
        if is_staff or "door" not in room.exit_flags.get(direction, [])
        or room.exit_door_open.get(direction, False)
    ]
    if not valid_exits:
        session.send("There's nowhere to flee to!")
        return

    if random.randint(1, 100) > FLEE_SUCCESS_CHANCE:
        session.send("&RYou attempt the Body Replacement Technique to escape, but fumble it!&x")
        return

    direction, destination_vnum = random.choice(valid_exits)

    if session.pvp_target is not None:
        opponent = session.pvp_target
        session.pvp_target = None
        opponent.pvp_target = None
        opponent.send(f"&Y{player.name} uses the Body Replacement Technique and flees {direction}!&x")
        combat.reset_summon_round_state(opponent.player)
    session.combat_target = None
    combat.reset_summon_round_state(player)

    player.room_vnum = destination_vnum
    session.send(f"&YYou use the Body Replacement Technique, substituting yourself with a nearby log, and flee {direction}!&x")
    cmd_look(session, [])


def _find_downed_target_for(attacker_name: str):
    """The (session, player) of whoever currently has downed_by
    pointing at attacker_name, or (None, None) if nobody does -- see
    combat.handle_pvp_defeat's own Mangekyo betrayal branch (Section
    116), which is the only place downed_by is ever set."""
    import session as session_module
    for s in session_module.ACTIVE_SESSIONS:
        if s.player and s.player.downed_by == attacker_name:
            return s, s.player
    return None, None


def cmd_finish_downed_yes(session, args: List[str]) -> None:
    """'yes' -- per direct request/confirmation (Section 116), the
    attacker's real choice to finish off their own downed, most-
    grouped partner and claim the Mangekyo Sharingan. Genuinely a
    no-op (falls through to "Huh?"-style silence, matches ordinary
    unmatched-command behavior) for anyone with nobody currently
    downed by them -- 'yes' isn't reserved as a special word outside
    this one real, active decision."""
    player = session.player
    downed_session, downed_player = _find_downed_target_for(player.name)
    if not downed_session:
        session.send("Yes what?")
        return

    import data_kekkei_genkai
    import data_mangekyo
    player.bloodline_mangekyo = True
    player.mangekyo_eye_1, player.mangekyo_eye_2 = data_mangekyo.roll_two_eye_techniques()
    eye_1_name = data_mangekyo.TECHNIQUE_ROSTER[player.mangekyo_eye_1]["display_name"]
    eye_2_name = data_mangekyo.TECHNIQUE_ROSTER[player.mangekyo_eye_2]["display_name"]
    session.send(
        f"&RYou end {downed_player.name}'s life without hesitation. Power floods through you -- "
        f"the Mangekyo Sharingan is yours.&x"
    )
    session.send(f"&RYour eyes have awakened: {eye_1_name} and {eye_2_name}.&x")

    xp_loss = int(downed_player.experience * 0.25)
    downed_player.experience = max(0, downed_player.experience - xp_loss)
    ryo_loss = downed_player.ryo // 2
    downed_player.ryo -= ryo_loss
    for skill_name in list(downed_player.skill_proficiencies.keys()):
        current = downed_player.skill_proficiencies[skill_name]
        downed_player.skill_proficiencies[skill_name] = int(current * 0.75)

    downed_player.downed_by = None
    downed_player.frozen_until = time.time() + 24 * 60 * 60
    downed_player.health = 1

    downed_session.send(
        f"&R{player.name} shows no mercy. Everything goes dark...&x\n"
        f"&YYou lose {xp_loss:,} experience, {ryo_loss:,} ryo, and feel your training slip -- "
        f"every skill you've practiced is noticeably duller.&x\n"
        f"&RYou are gravely wounded and will need 24 hours to recover. Only 'look', 'say', "
        f"and 'ooc' work until then.&x"
    )
    downed_session.send_prompt()


def cmd_finish_downed_no(session, args: List[str]) -> None:
    """'no' -- per direct request/confirmation (Section 116), the
    attacker's choice to spare their downed, most-grouped partner.
    Falls all the way through to a completely ordinary PvP defeat by
    directly reusing combat.handle_pvp_defeat -- the exact same code
    a ordinary, non-Mangekyo-eligible kill would run -- so a spared
    loss carries the SAME real consequences (kill count, bounty
    claim, scroll theft, XP/ryo loss, hospital respawn) as any other
    PvP defeat, nothing special or reduced. Genuinely a no-op for
    anyone with nobody currently downed by them."""
    player = session.player
    downed_session, downed_player = _find_downed_target_for(player.name)
    if not downed_session:
        session.send("No what?")
        return

    session.send(f"&YYou can't bring yourself to do it. You let {downed_player.name} live.&x")
    downed_session.send(f"&Y{player.name} hesitates, then lets you live.&x")
    downed_player.downed_by = None

    import combat as combat_module
    combat_module.handle_pvp_defeat(winner_session=session, loser_session=downed_session, skip_mangekyo_check=True)


def cmd_release(session, args: List[str]) -> None:
    """'release <target>' -- per direct request/confirmation (Section
    120): ends the caster's own active Illusion Walk genjutsu on
    someone early, the ONLY way it ever ends besides the illusion's
    own snap-back-and-repeat cycle (no in-game "Kai"/release
    mechanic for the VICTIM to break it themselves exists yet,
    confirmed as a deliberate future gap). Only the actual caster of
    a given Illusion Walk can release it -- releasing someone else's
    victim, or someone not actually under the effect at all, is
    refused."""
    player = session.player
    if not args:
        session.send("Release who from Illusion Walk?")
        return
    query = " ".join(args).lower()
    target_session = next(
        (s for s in session.active_sessions() if s.player and query in s.player.name.lower()),
        None,
    )
    if not target_session or target_session.player.illusion_walk_caster != player.name:
        session.send("You aren't holding anyone in an Illusion Walk by that name.")
        return

    target_session.player.illusion_walk_caster = None
    target_session.player.illusion_walk_real_room_vnum = None
    target_session.player.illusion_walk_range = 0
    target_session.player.illusion_walk_steps_taken = 0
    session.send(f"&YYou release {target_session.player.name} from the illusion.&x")
    target_session.send(f"&YThe illusion around you shatters -- you're back in reality.&x")


def cmd_unleash(session, args: List[str]) -> None:
    """'unleash beast' releases a random unsealed Tailed Beast for staff."""
    if [arg.lower() for arg in args] != ["beast"]:
        session.send("Usage: unleash beast")
        return
    if not olc._require_builder(session):
        return
    import tailed_beasts
    import storage
    import world as world_module
    if tailed_beasts.any_beast_currently_roaming(combat):
        session.send("A Tailed Beast is already loose in the world -- it must be sealed, killed, or despawn before another can be released.")
        return
    online_players = [s.player for s in session.active_sessions() if s.player]
    online_names = {p.name for p in online_players}
    offline_players = [p for p in storage.all_players() if p.name not in online_names]
    beast = tailed_beasts.pick_random_available_beast(online_players + offline_players)
    if beast is None:
        session.send("Every Tailed Beast is already sealed into a player -- there's nothing left to release.")
        return
    mob = tailed_beasts.release_beast(beast, world_module, combat)
    session.send(f"&RYou unleash {beast['display_name']} into the world at room {mob.room_vnum}!&x")
    _broadcast_globally(f"&R{beast['display_name']} has been unleashed upon the world!&x")


def cmd_rest(session, args: List[str]) -> None:
    player = session.player
    if session.combat_target is not None:
        session.send("You can't rest while you're fighting!")
        return
    if player.position == "resting":
        session.send("You are already resting.")
        return
    player.position = "resting"
    session.send("You sit down and rest, recovering a bit faster than usual.")


def cmd_sleep(session, args: List[str]) -> None:
    player = session.player
    if session.combat_target is not None:
        session.send("You can't sleep while you're fighting!")
        return
    if player.position == "sleeping":
        session.send("You are already sleeping.")
        return
    player.position = "sleeping"
    session.send("You lie down and drift off to sleep, recovering much faster than usual.")


def cmd_stand(session, args: List[str]) -> None:
    player = session.player
    if player.position == "standing":
        session.send("You are already standing.")
        return
    _wake_and_stand(session)


EXIT_COLOR = "&G"  # the direction word (e.g. "North")
CARDINAL_ORDER = ["north", "east", "south", "west"]
DIAGONAL_ORDER = ["northeast", "southeast", "southwest", "northwest"]
VERTICAL_ORDER = ["up", "down"]
EXIT_COLUMN_GAP = 4  # spaces between one column and the next


EXIT_MAX_ROWS_PER_COLUMN = 2  # wrap into a new column after this many rows, however many columns that takes


def _format_exits(room, is_staff: bool = False) -> List[str]:
    """Exits packed into as many side-by-side columns as needed to keep
    the display compact, rather than one column per direction-group
    (which wasted vertical space -- e.g. all 4 cardinals present used
    to take a full 4-row-tall single column even with room to spare
    horizontally). Order is still cardinals (N/E/S/W) first, then
    diagonals (NE/SE/SW/NW), then up/down last, as one continuous
    sequence -- only directions that actually exist are included, wrapping
    into a new column every EXIT_MAX_ROWS_PER_COLUMN entries. Shows only
    the direction word (e.g. "North"), not the destination room's name --
    removed on explicit request. A "hidden"-flagged exit (see olc.py's
    `rset exitflag`) is skipped entirely for regular players, but shown
    to staff with a "(hidden)" marker so they can still see and manage
    it. A closed door shows "(closed)" so players know to `open` it."""
    if not room.exits:
        return [f"{EXIT_COLOR}Exits: none&x"]

    directions = []
    for direction in CARDINAL_ORDER + DIAGONAL_ORDER + VERTICAL_ORDER:
        if direction not in room.exits:
            continue
        flags_here = room.exit_flags.get(direction, [])
        if "hidden" in flags_here and not is_staff:
            continue
        label = direction.title()
        if "door" in flags_here and not room.exit_door_open.get(direction, False):
            label += " (closed)"
        if is_staff and "hidden" in flags_here:
            label += " (hidden)"
        directions.append(label)
    if not directions:
        return [f"{EXIT_COLOR}Exits: none&x"]

    columns = [
        directions[i:i + EXIT_MAX_ROWS_PER_COLUMN]
        for i in range(0, len(directions), EXIT_MAX_ROWS_PER_COLUMN)
    ]
    col_widths = [max(len(entry) for entry in col) for col in columns]
    max_rows = min(EXIT_MAX_ROWS_PER_COLUMN, len(directions))

    lines = [f"{EXIT_COLOR}Exits:&x"]
    for row in range(max_rows):
        parts = []
        for col, width in zip(columns, col_widths):
            if row < len(col):
                direction_title = col[row]
                pad = " " * (width - len(direction_title))
                parts.append(f"{EXIT_COLOR}{direction_title}&x{pad}")
        lines.append("  " + (" " * EXIT_COLUMN_GAP).join(parts))
    return lines


def cmd_look(session, args: List[str]) -> None:
    player = session.player
    if player.illusion_walk_caster is not None and not args:
        import areas
        area = areas.find_area_for_vnum(player.illusion_walk_real_room_vnum)
        candidates = []
        if area:
            candidates = [
                vnum for vnum in WORLD.rooms.keys()
                if vnum != player.illusion_walk_real_room_vnum and area.vnum_start <= vnum <= area.vnum_end
            ]
        fake_room = WORLD.get(random.choice(candidates)) if candidates else WORLD.get(player.illusion_walk_real_room_vnum)
        if fake_room:
            session.send(f"&C{fake_room.name}&x")
            session.send(fake_room.description)
        return
    room = WORLD.get(player.room_vnum)
    if room is None:
        # Same root cause as the login-time check in
        # Session._enter_world (a room that only existed in memory,
        # e.g. builder-created via 'rset create', vanished on a server
        # restart) -- but guarded here too in case it happens mid-
        # session instead, so this degrades gracefully instead of
        # crashing on room.name below.
        from data_villages import VILLAGES
        player.room_vnum = VILLAGES[player.village]["starting_room_vnum"]
        session.send("&Y(That room no longer exists -- you've been returned to your village.)&x")
        room = WORLD.get(player.room_vnum)

    is_staff = session.account is not None and session.account.staff_level != "player"

    if args:
        query = " ".join(args).lower()
        if query in ("self", "me") or query in player.name.lower():
            lines = [f"&C{player.name}&x"]
            lines.append(player.description if player.description else "You haven't set a description.")
            session.send("\n".join(lines))
            return
        for other in session.active_sessions():
            if other.player and other is not session and other.player.room_vnum == player.room_vnum \
                    and query in other.player.name.lower():
                if player.illusion_walk_caster is not None:
                    session.send("You don't see anyone here by that name.")
                    return
                target = other.player
                lines = [f"&C{target.name}&x"]
                lines.append(target.description if target.description else f"{target.name} hasn't set a description.")
                session.send("\n".join(lines))
                return
        mob = combat.find_mob(player.room_vnum, query)
        if mob:
            mob_template = combat.MOB_TEMPLATES.get(mob.template_vnum, {})
            mob_description = mob_template.get("description")
            lines = [f"&C{mob.name}&x"]
            lines.append(mob_description if mob_description else f"{mob.name} hasn't set a description.")
            session.send("\n".join(lines))
            return
        inv_match = find_indexed_item(query, player.inventory)
        if inv_match:
            session.send(f"{rarity_colored_name(inv_match)}\nYou are carrying it.")
            return
        ground_match = find_indexed_item(query, room.ground_items)
        if ground_match:
            session.send(f"{rarity_colored_name(ground_match)}\nIt's lying here on the ground.")
            return
        session.send("You don't see that here.")
        return

    room_header = f"&C{room.name}&x"
    if is_staff and player.staff_show_vnums:
        flag_suffix = f" | {', '.join(room.flags)}" if room.flags else ""
        if not room.enabled:
            flag_suffix += " | &RDISABLED&x&D"
        room_header += f" &D[{room.vnum}{flag_suffix}]&x"

    lines = [room_header, ""]
    if room.description:
        lines.append(f"&Y{room.description}&x")
        lines.append("")
    if room.temp_description_text:
        if time.time() >= room.temp_description_until:
            room.temp_description_text = ""
            room.temp_description_until = 0.0
        else:
            lines.append(room.temp_description_text)
            lines.append("")
    lines.extend(_format_exits(room, is_staff))
    lines.append("")
    for other in session.active_sessions():
        if other.player and other is not session and other.player.room_vnum == player.room_vnum:
            afk_tag = " &R[AFK]&x" if other.player.afk else ""
            lines.append(f"  &G{other.player.name}&x is here.{afk_tag}")
    mobs = combat.mobs_in_room(player.room_vnum)
    for mob in mobs:
        if combat.is_shadow_clone(mob):
            lines.append(f"  {mob.name} is here.")
            continue
        lines.append(f"  {mob.name} is here.{_staff_vnum_suffix(session, mob=mob)}")
    for corpse in corpses.corpses_in_room(player.room_vnum):
        contents = []
        if corpse.ryo > 0:
            contents.append(f"{corpse.ryo} ryo")
        if corpse.items:
            contents.append(f"{len(corpse.items)} item(s)")
        detail = f" ({', '.join(contents)})" if contents else " (empty)"
        lines.append(f"  &D{corpse.name}&x is here.{detail}")
    if room.ground_items:
        ground_counts = inventory.slot_counts(room.ground_items)
        for name, count in ground_counts.items():
            proto = _find_object_prototype_by_name(name)
            long_desc = proto.get("long_desc") if proto else None
            if long_desc:
                shown_line = f"{long_desc} (x{count})" if count > 1 else long_desc
                lines.append(f"  {shown_line}{_staff_vnum_suffix(session, item_name=name)}")
            else:
                shown = f"{rarity_colored_name(name)} (x{count})" if count > 1 else rarity_colored_name(name)
                lines.append(f"  {shown} is lying here.{_staff_vnum_suffix(session, item_name=name)}")
    session.send("\n".join(lines))


# --- Social ------------------------------------------------------------

def _is_silenced(session) -> bool:
    """Whether player is CURRENTLY silenced (Section 94, per direct
    request: "Create a silence command...player will remain silenced
    ...for time automatically being released when timer is up").
    Auto-clears an expired silence the moment it's checked -- there's
    no separate background sweep needed, since a silence only ever
    matters at the exact moment the player tries to say/ooc/vchat
    something, which is exactly when this gets called."""
    player = session.player
    if not player.silenced_until:
        return False
    if time.time() >= player.silenced_until:
        player.silenced_until = 0.0
        return False
    remaining_minutes = int((player.silenced_until - time.time()) / 60) + 1
    session.send(f"&DYou are silenced for {remaining_minutes} more minute(s) and cannot speak.&x")
    return True


def cmd_say(session, args: List[str]) -> None:
    if not args:
        session.send("Say what?")
        return
    if _is_silenced(session):
        return
    import chat_moderation
    if chat_moderation.record_and_check_spam(session):
        session.send("&D(You're talking too fast! You have been silenced for 10 minutes.)&x")
        return
    message = chat_moderation.censor(" ".join(args))
    player = session.player
    session.send(f"&gYou say, '{message}'&x")
    session.broadcast_room(f"&g{player.name} says, '{message}'&x", exclude_self=True)

    village_rooms = content._VILLAGE_ROOMS.get(player.village)
    if village_rooms and player.room_vnum == village_rooms["kage"] and "mission" in message.lower():
        session.send(kage.handle_mission_redirect(player))

    for mob in combat.mobs_in_room(player.room_vnum):
        t = combat.MOB_TEMPLATES.get(mob.template_vnum)
        if t and t.get("mob_programs"):
            if programs.fire_speech_programs(session, t["mob_programs"], message, speaker_name=mob.name.capitalize(), mob_template=t):
                break  # only one mob responds per utterance, even if several are listening


def cmd_restore(session, args: List[str]) -> None:
    if not olc._require_admin(session):
        return
    if args:
        session.send("Usage: restore (restores every online player)")
        return
    import admin_actions
    count = admin_actions.restore_online()
    session.send(f"Restored HP, chakra, and stamina for {count} online player(s).")


def cmd_respawn(session, args: List[str]) -> None:
    if not olc._require_admin(session):
        return
    if args:
        session.send("Usage: respawn (restores missing mob populations worldwide)")
        return
    import admin_actions
    count = admin_actions.respawn_missing()
    session.send(f"Respawned {count} missing mob(s). Existing mobs were left untouched.")


def cmd_emotes(session, args: List[str]) -> None:
    import emotes
    session.send_paginated(emotes.list_text())


def cmd_emote(session, args: List[str], ooc: bool = False) -> None:
    import emotes
    if len(args) != 1 or not args[0].startswith("@"):
        session.send("Usage: @yawn or ooc @yawn (no extra words). Type 'emotes' for the list.")
        return
    name = args[0][1:].lower()
    phrases = emotes.EMOTES.get(name)
    if phrases is None:
        session.send("Unknown emote. Type 'emotes' for the list.")
        return
    if _is_silenced(session):
        return
    import chat_moderation
    if chat_moderation.record_and_check_spam(session):
        session.send("&D(You're talking too fast! You have been silenced for 10 minutes.)&x")
        return
    own, other = phrases
    prefix = "&M[OOC]&x " if ooc else ""
    session.send(f"{prefix}You {own}")
    message = f"{prefix}{session.player.name} {other}"
    if ooc:
        session.broadcast_all(message, exclude_self=True)
        import chatlog
        chatlog.record(session.player.name, f"[emote] {other}")
    else:
        session.broadcast_room(message, exclude_self=True)


def cmd_ooc(session, args: List[str]) -> None:
    if not args:
        session.send("OOC what?")
        return
    if args[0].startswith("@"):
        cmd_emote(session, args, ooc=True)
        return
    if _is_silenced(session):
        return
    import chat_moderation
    if chat_moderation.record_and_check_spam(session):
        session.send("&D(You're talking too fast! You have been silenced for 10 minutes.)&x")
        return
    message = chat_moderation.censor(" ".join(args))
    player = session.player
    session.send(f"&M[OOC] You:&x {message}")
    session.broadcast_all(f"&M[OOC] {player.name}:&x {message}", exclude_self=True)
    import chatlog
    chatlog.record(player.name, message)


def cmd_village_chat(session, args: List[str]) -> None:
    if not args:
        session.send("Say what to your village?")
        return
    if _is_silenced(session):
        return
    import chat_moderation
    if chat_moderation.record_and_check_spam(session):
        session.send("&D(You're talking too fast! You have been silenced for 10 minutes.)&x")
        return
    message = chat_moderation.censor(" ".join(args))
    player = session.player
    village_name = VILLAGES[player.village]["village_short_name"]
    session.send(f"&C[{village_name}] You:&x {message}")
    session.broadcast_village(player.village, f"&C[{village_name}] {player.name}:&x {message}", exclude_self=True)


def cmd_chatlog(session, args: List[str]) -> None:
    """Shows the last 25 OOC messages (chatlog.py), per direct request
    ("add a command in game that shows the last 25 ooc chats by
    typing chatlog"). Persisted across restarts. Oldest first, most
    recent last, matching how a natural scrollback reads."""
    import chatlog
    if not chatlog.ENTRIES:
        session.send("No OOC chat has been logged yet.")
        return
    lines = [f"&M[OOC] {entry['speaker']}:&x {entry['message']}" for entry in chatlog.ENTRIES]
    session.send("\n".join(lines))


def cmd_ask(session, args: List[str]) -> None:
    if len(args) < 2:
        session.send("Ask whom about what?")
        return
    topic = " ".join(args[1:]).lower()
    player = session.player
    village_rooms = content._VILLAGE_ROOMS.get(player.village)
    if village_rooms and player.room_vnum == village_rooms["kage"] and "promotion" in topic:
        session.send(kage.handle_promotion_request(player))
        return
    session.send("There is no one here to ask about that.")


VILLAGE_FULL_NAME_COLORS = {
    "leaf": (34, 118),    # Konohagakure
    "cloud": (33, 255),   # Kumogakure
    "water": (38, 67),    # Kirigakure
    "sand": (214, 220),   # Sunagakure
    "stone": (130, 244),  # Iwagakure
}
CLASS_WHO_LABEL = {"taijutsu": "Tai", "ninjutsu": "Nin", "genjutsu": "Gen", "bukijutsu": "Buk"}
CLASS_WHO_COLOR = {
    "taijutsu": "&R",   # red -- physical combat
    "ninjutsu": "&B",   # blue -- chakra techniques
    "genjutsu": "&M",   # magenta -- illusion
    "bukijutsu": "&Y",  # yellow -- weapons/steel
}
RANK_WHO_LABEL = {
    "academy student": "Student", "genin": "Genin", "chunin": "Chunin",
    "special jonin": "Sp.Jonin", "jonin": "Jonin", "elite jonin": "El.Jonin",
    "village elder": "V.Elder",
}
# Colored low-to-high, so rank is visible at a glance without reading the text.
RANK_WHO_COLOR = {
    "academy student": "&D",   # dim gray -- lowest
    "genin": "&G",              # green
    "chunin": "&C",             # cyan
    "special jonin": "&B",      # blue
    "jonin": "&Y",              # yellow
    "elite jonin": "&M",        # magenta
    "village elder": "&R",       # red -- top shinobi rank, just below Kage
}
KAGE_WHO_COLOR = "&O"  # orange -- above every other rank color
WHO_LEADER_STAFF_LEVELS = {"helper", "builder", "area leader", "administrator", "implementor"}  # all immortals
WHO_NAME_COLORS = ["&G", "&C", "&B", "&Y", "&O", "&M"]  # cycled per shinobi line for visual variety
WHO_RANK_WIDTH = 8
WHO_CLASS_WIDTH = 3
WHO_LEVEL_COLOR = "&C"  # confirmed directly: a new "Lv 42" field, right after Village and before Rank
WHO_VILLAGE_WIDTH = max(len(v["village_name"]) for v in VILLAGES.values())
WHO_CLAN_WIDTH = max(len("None"), max((len(k) for k in data_clans.CLANS), default=0))  # confirmed directly (Section 139): sized to the longest real clan name
NEW_CHARACTER_LEVEL_THRESHOLD = 5  # shown with a [NEW] tag at or below this level


def village_name_colored(village: str) -> str:
    """Full village name (Konohagakure, not 'Leaf'/'Konoha'), colored
    with the exact same per-village xterm-256 alternating scheme as
    the who-list (see _who_village_name below) -- but with no fixed-
    width padding or trailing reset, since this is meant for a single
    banner line, not a table column that needs to line up with the
    rows after it."""
    full_name = VILLAGES.get(village, {}).get("village_name", village.title())
    color_a, color_b = VILLAGE_FULL_NAME_COLORS.get(village, (255, 255))
    letters = []
    for i, ch in enumerate(full_name):
        color = color_a if i % 2 == 0 else color_b
        letters.append(f"&[{color}]{ch}")
    return "".join(letters) + "&x"


def _who_village_name(village: str) -> str:
    """Full village name (Konohagakure, not 'Leaf'/'Konoha'), each
    letter alternating between the village's two assigned xterm-256
    colors, then padded with plain spaces (after the color reset, so
    they don't inherit any color) to WHO_VILLAGE_WIDTH -- village full
    names vary in length, so without this the rank/class columns after
    it wouldn't line up from one line to the next."""
    full_name = VILLAGES.get(village, {}).get("village_name", village.title())
    color_a, color_b = VILLAGE_FULL_NAME_COLORS.get(village, (255, 255))
    letters = []
    for i, ch in enumerate(full_name):
        color = color_a if i % 2 == 0 else color_b
        letters.append(f"&[{color}]{ch}")
    padding = " " * (WHO_VILLAGE_WIDTH - len(full_name))
    return "".join(letters) + "&D" + padding


def _who_banner(fill_char: str, fill_color: str, label: str, width: int = 68, label_color: str = None) -> str:
    inner_visible = f"[ {label} ]"
    pad = max(0, width - len(inner_visible))
    left = pad // 2
    right = pad - left
    inner = f"[ {label_color or fill_color}{label}{fill_color} ]"
    return f"{fill_color}{fill_char * left}{inner}{fill_char * right}&D"


def _who_tags(p) -> str:
    tags = ""
    if p.afk:
        tags += " &R[AFK]&D"
    if p.level <= NEW_CHARACTER_LEVEL_THRESHOLD:
        tags += " &G[NEW]&D"
    return tags


def cmd_who(session, args: List[str]) -> None:
    online = [s for s in session.active_sessions() if s.player]

    lines = [_who_banner("=", "&Y", "SHINOBI ONLINE", label_color="&C")]

    for s in online:
        p = s.player
        village_display = _who_village_name(p.village)
        level_label = f"{WHO_LEVEL_COLOR}{p.level:>5}&W"
        village_info = VILLAGES.get(p.village)
        clan_text = (p.clan.title() if p.clan and p.clan != "none" else "None").ljust(WHO_CLAN_WIDTH)
        if p.village_rank == "kage" and village_info:
            rank_label = f"{KAGE_WHO_COLOR}{'Kage'.center(WHO_RANK_WIDTH)}&W"
            name_text = f"{p.name}, the {village_info['kage_title']} of {village_info['village_name']}"
        else:
            # Staff shown here too now (Section 139: no more separate
            # section), using their real rank badge, not a false Kage
            # title.
            rank_text = RANK_WHO_LABEL.get(p.village_rank, p.village_rank.title()).ljust(WHO_RANK_WIDTH)
            rank_color = RANK_WHO_COLOR.get(p.village_rank, "&W")
            rank_label = f"{rank_color}{rank_text}&W"
            name_text = p.name
        lines.append(f"&W[{village_display}&W][{rank_label}][{level_label}]&W[{clan_text}]&Y {name_text}&D{_who_tags(p)}")

    count = len(online)
    noun = "shinobi is" if count == 1 else "shinobi are"
    lines.append(f"&Y{count} {noun} currently online.&x")
    session.send("\n".join(lines))


def cmd_whois(session, args: List[str]) -> None:
    """Shows an online player's description plus basic info -- village,
    level, class, rank, clan -- matching the same identity fields the
    who-list already treats as defining for a player. Unlike 'look',
    which only finds a player standing in the same room, 'whois'
    looks server-wide across every online player, same as 'who' does."""
    if not args:
        session.send("Usage: whois <player name>")
        return
    query = " ".join(args).lower()
    match = next(
        (s for s in session.active_sessions() if s.player and query in s.player.name.lower()),
        None,
    )
    if match is None:
        session.send(f"No player named '{' '.join(args)}' is currently online.")
        return

    p = match.player
    village_display = _who_village_name(p.village)
    rank_text = RANK_WHO_LABEL.get(p.village_rank, p.village_rank.title())
    lines = [f"&C{p.name}&x"]
    lines.append(p.description if p.description else f"{p.name} hasn't set a description.")
    lines.append("")
    lines.append(f"&WVillage:&x {village_display}   &WLevel:&x {p.level}   &WClass:&x {p.primary_class.capitalize()}")
    lines.append(f"&WRank:&x {rank_text}   &WClan:&x {p.clan.title() if p.clan and p.clan != 'none' else 'None'}")
    session.send("\n".join(lines))


SHARINGAN_DODGE_BONUS_PERCENT = 15  # added on top of normal dodge_chance while active -- tomoe 1-5; tomoe 6 uses its own amplified value below
SHARINGAN_DODGE_BONUS_PERCENT_TOMOE_6 = 25  # the tomoe-6 capstone's amplified version -- "major perception/combat bonus" per the fuller progression table

# 3-tomoe perks, per direct follow-up request and design confirmation:
# a hitroll bonus (same shape as tomoe 1's dodge bonus, just offense
# instead of defense) plus Movement Prediction -- a genuinely separate
# roll from dodge, only checked when the dodge roll itself already
# failed ("chance outside of dodge"), reducing the attack's damage
# rather than blocking it outright ("reduces damage by a set amount/
# percentage rather than blocking it entirely"). Passive, not player-
# triggered, but its own real cost: unlocking it bumps chakra upkeep
# back up ("passive but increases upkeep").
SHARINGAN_HITROLL_BONUS_PERCENT = 10  # added on top of normal to-hit while active, tomoe 3-5
ILLUSION_WALK_STAMINA_FLOOR = 10  # per direct confirmation (Section 121): stamina halves every real movement check-in (including the snap-back step); reaching this floor releases the victim early, distinct from the normal range-based snap-back
SHARINGAN_HITROLL_BONUS_PERCENT_TOMOE_6 = 18  # the tomoe-6 capstone's amplified version
SHARINGAN_PREDICTION_CHANCE_PERCENT = 25  # chance to reduce damage on a failed dodge, tomoe 3-5
SHARINGAN_PREDICTION_CHANCE_PERCENT_TOMOE_6 = 40  # the tomoe-6 capstone's amplified version -- "predictive counter" per the table
SHARINGAN_PREDICTION_DAMAGE_REDUCTION_PERCENT = 40  # how much damage a successful Prediction cuts -- unchanged by tomoe count, tomoe 3's own specific perk

# 4-tomoe perk: genjutsu resistance. Genjutsu
# resistance reduces (not fully negates) the duration of any incoming
# genjutsu-sourced status effect -- built correctly wired even though
# no jutsu can currently target a player at all (see combat.
# use_jutsu_on_player, new this pass), same "build the hook ahead of
# what will eventually use it" discipline data_kekkei_genkai.
# attempt_awaken/eligible_for_awakening_quest were already built with.
SHARINGAN_GENJUTSU_RESIST_REDUCTION_PERCENT = 50  # how much shorter an incoming genjutsu effect's duration becomes, tomoe 4+

# 5-tomoe perk: Copy Jutsu, per direct design confirmation ("sharingan
# copy has a chance to copy the other users jutsu when toggled on but
# has a cost of double the other users chakra to copy"). A chance,
# each time an opponent casts a jutsu against this player, to copy
# that exact jutsu into a one-use cast of their own -- at DOUBLE what
# the original caster paid for it, not what it would normally cost
# this player.
SHARINGAN_COPY_JUTSU_CHANCE_PERCENT = 20  # chance to copy an opponent's jutsu on being hit by one, tomoe 5+

# Per-round COMBAT chakra upkeep while the Sharingan is active, keyed
# by tomoe count -- lower with more tomoe at first, per direct request
# ("the technique becomes less taxing with more eyes open"), but
# tomoe 3 bumps it back up -- Movement Prediction is real, ongoing
# upkeep of its own, on top of what came before ("passive but
# increases upkeep"). Tomoe 4 drops back down (genjutsu resistance is
# a passive check, not an ongoing drain of its own -- Sharingan
# Genjutsu has its own separate chakra_cost like any other jutsu, not
# folded into this upkeep). Tomoe 6 is the lowest COMBAT rate in the
# whole progression, matching the table's own "lowest upkeep"
# capstone description -- but never below 1, per a later follow-up
# request ("make sharingan cost upkeep at all times and increases
# during combat vs its not combat settings") that added a separate,
# always-on idle rate (SHARINGAN_IDLE_CHAKRA_UPKEEP below): a combat
# rate of 0 would have been cheaper than simply having the ability on
# while idle, backwards from "increases during combat". Falls back to
# tomoe 1's rate for any tomoe count beyond what's been designed here
# (there's no tomoe 0, the ability can't be toggled on without at
# least 1). Stamina upkeep stays flat at 1 regardless of tomoe count
# -- already at the practical floor, so discounting it further would
# make the ability free of that resource entirely rather than merely
# cheaper.
SHARINGAN_CHAKRA_UPKEEP_BY_TOMOE = {1: 6, 2: 3, 3: 6, 4: 3, 5: 3, 6: 3}
SHARINGAN_STAMINA_UPKEEP = 3


def sharingan_chakra_upkeep(tomoe_count: int) -> int:
    """The per-round COMBAT chakra upkeep for a given tomoe count --
    see SHARINGAN_CHAKRA_UPKEEP_BY_TOMOE above. Falls back to tomoe
    1's rate for any tomoe count beyond what's been designed (1-6 now
    cover the full progression), rather than guessing at a value."""
    return SHARINGAN_CHAKRA_UPKEEP_BY_TOMOE.get(tomoe_count, SHARINGAN_CHAKRA_UPKEEP_BY_TOMOE[1])


# Idle (non-combat) chakra upkeep, per direct follow-up request ("make
# sharingan cost upkeep at all times and increases during combat vs
# its not combat settings"). Deliberately flat regardless of tomoe
# count, unlike the combat table above -- the point of this is a
# simple "having it active costs something, always" baseline, not
# another tomoe-scaled curve. Genuinely lower than combat both in its
# own per-tick amount AND because it only ticks once per regen.
# tick_player call (every config.REGEN_INTERVAL_SECONDS, currently
# 10s) rather than every combat round (COMBAT_ROUND_SECONDS, 2.5s) --
# 4x less often on top of a smaller number, so "increases during
# combat" is true on both axes at once.
SHARINGAN_IDLE_CHAKRA_UPKEEP = 3


def _sharingan_eye_description(tomoe_count: int) -> str:
    """A short, accurate description of the Sharingan's current state
    for the given tomoe count (1-6, see data_kekkei_genkai.
    SHARINGAN_MAX_TOMOE) -- 1-3 tomoe are a single eye still
    developing, 4-6 mean both eyes now carry tomoe (2 eyes x 3 tomoe
    each is the full progression), matching the numbers the mastery
    system actually tracks rather than a generic, unchanging line
    regardless of how far the player has actually progressed."""
    if tomoe_count <= 3:
        return f"{tomoe_count} tomoe spin into focus"
    tomoe_per_eye = tomoe_count - 3
    return f"both eyes ignite -- {tomoe_per_eye} tomoe now spin in each"


def cmd_sharingan(session, args: List[str]) -> None:
    """Toggles the Sharingan's active perks on/off: reading an
    opponent's attacks well enough to dodge them (see derived_stats.py
    for the dodge bonus itself), plus whatever additional perks the
    player's current tomoe count has unlocked (combat.py's own
    resolve_pulse/resolve_pvp_pulse apply all of them each combat
    round -- this command only flips the toggle). Costs a small
    chakra+stamina upkeep every combat round it stays on, nothing
    while not fighting. Refuses with the exact same generic "haven't
    learned that skill" wording used everywhere else in the game for
    an unknown ability -- deliberately reveals nothing about whether
    this player has a hidden, un-awakened bloodline roll at all, same
    security stance the rest of this framework was built around (see
    data_kekkei_genkai.py's own docstring). The activation/
    deactivation message reflects the player's actual current tomoe
    count (see _sharingan_eye_description above), per direct follow-up
    request -- it no longer says "one tomoe" regardless of how far the
    player has actually progressed."""
    player = session.player
    if player.bloodline_id != "sharingan" or player.bloodline_tomoe < 1:
        session.send("You haven't learned that skill or jutsu.")
        return

    player.sharingan_active = not player.sharingan_active
    if player.sharingan_active:
        eye_description = _sharingan_eye_description(player.bloodline_tomoe)
        session.send(
            f"&RYour eyes bleed to red -- {eye_description}. You can read your "
            "opponent's every movement.&x"
        )
    else:
        session.send(f"&RYour {player.bloodline_tomoe}-tomoe Sharingan fades back to black.&x")


def _tsukuyomi_torture_action(session, command_name: str) -> None:
    """Shared real logic for all 5 Tsukuyomi torture commands (Section
    140, per direct confirmation) -- validates the caster genuinely
    has an active Tsukuyomi running, applies that command's own real
    effect (data_mangekyo.TSUKUYOMI_COMMANDS) to the target, advances
    the real hidden countdown by that command's own cost, and ends
    the technique (mangekyo.end_tsukuyomi) once it hits 0 or an
    early-end roll succeeds (crush only)."""
    import random
    import data_mangekyo
    import mangekyo
    import world as world_module

    player = session.player
    target_name = player.tsukuyomi_active_target_name
    if not target_name:
        session.send("You're not currently inside Tsukuyomi.")
        return
    target_session = next(
        (s for s in session.active_sessions() if s.player and s.player.name == target_name),
        None,
    )
    if target_session is None:
        session.send("Your target is no longer there!")
        return

    spec = data_mangekyo.TSUKUYOMI_COMMANDS[command_name]
    target = target_session.player
    lo, hi = spec["hp_damage"]
    if hi > 0:
        dmg = random.randint(lo, hi)
        target.health -= dmg
    else:
        dmg = 0
    stamina_lo, stamina_hi = spec.get("stamina_drain", (0, 0))
    if stamina_hi > 0:
        target.stamina = max(0, target.stamina - random.randint(stamina_lo, stamina_hi))
    chakra_lo, chakra_hi = spec.get("chakra_drain", (0, 0))
    if chakra_hi > 0:
        target.chakra = max(0, target.chakra - random.randint(chakra_lo, chakra_hi))

    session.send(f"&RYou use {command_name} on {target.name} -- {damage_messages.describe_damage(dmg)} damage.&x" if dmg else f"&RYou use {command_name} on {target.name}.&x")
    target_session.send(f"&R{player.name} uses {command_name} on you -- {damage_messages.describe_damage(dmg)} damage!&x" if dmg else f"&R{player.name} uses {command_name} on you!&x")

    player.tsukuyomi_actions_remaining -= spec["countdown_cost"]
    early_end_chance = spec.get("early_end_chance_pct", 0)
    genuinely_ended_early = early_end_chance and random.randint(1, 100) <= early_end_chance

    if player.tsukuyomi_actions_remaining <= 0 or genuinely_ended_early:
        target.stamina = 0
        target.health = max(1, min(target.health, int(target.maximum_health * 0.05)))
        session.send("&RThe technique runs its course -- reality snaps back into place.&x")
        target_session.send("&RThe torment finally ends -- you're released, exhausted and broken.&x")
        mangekyo.end_tsukuyomi(session, target_session, world_module)


def cmd_stab(session, args: List[str]) -> None:
    """'stab' -- one of the 5 real Tsukuyomi torture commands (Section
    140), a moderate, consistent damage source."""
    _tsukuyomi_torture_action(session, "stab")


def cmd_impale(session, args: List[str]) -> None:
    """'impale' -- one of the 5 real Tsukuyomi torture commands
    (Section 140), heavier damage than stab, but costs 2 of the real
    hidden countdown instead of 1."""
    _tsukuyomi_torture_action(session, "impale")


def cmd_burn(session, args: List[str]) -> None:
    """'burn' -- one of the 5 real Tsukuyomi torture commands (Section
    140), moderate damage plus a real stamina drain."""
    _tsukuyomi_torture_action(session, "burn")


def cmd_crush(session, args: List[str]) -> None:
    """'crush' -- one of the 5 real Tsukuyomi torture commands
    (Section 140), the single highest per-hit damage option, with a
    real chance to end the whole technique one action early."""
    _tsukuyomi_torture_action(session, "crush")


def cmd_unmake(session, args: List[str]) -> None:
    """'unmake' -- one of the 5 real Tsukuyomi torture commands
    (Section 140), no direct HP damage at all, but a heavy real
    stamina and chakra drain together."""
    _tsukuyomi_torture_action(session, "unmake")


def cmd_guess(session, args: List[str]) -> None:
    """'guess <number>' -- per direct confirmation (Section 140), the
    real command a target trapped in Izanami uses to try escaping.
    One real guess per round: a correct guess ends the loop
    immediately; a wrong one does nothing but let the loop continue.
    Genuinely a no-op (falls through to a plain refusal) for anyone
    not currently trapped, matching the game's own established
    convention for context-specific commands (e.g. 'yes' outside a
    real defeat prompt)."""
    player = session.player
    if not player.izanami_trapped:
        session.send("Guess what?")
        return
    if not args or not args[0].lstrip("-").isdigit():
        session.send("Guess a number.")
        return
    guess = int(args[0])
    if guess == player.izanami_target_number:
        player.izanami_trapped = False
        player.izanami_target_number = None
        session.send("&RThe loop shatters -- you guessed correctly, and reality snaps back into place!&x")
    else:
        session.send("&RWrong. The moment resets, and you're trapped again...&x")


def cmd_izanagi(session, args: List[str]) -> None:
    """Toggles Izanagi on/off -- per direct confirmation (Section 140):
    a real, deliberate stance the player must proactively activate,
    NOT automatic. Mirrors cmd_sharingan/cmd_tailed_beast_mode's own
    established toggle pattern. Only usable if the player genuinely
    rolled Izanagi as one of their 2 real Mangekyo eye techniques.
    Blocked while on its own real, once-per-real-day cooldown after a
    genuine trigger (see combat.py's own defeat-check, which fires
    the actual save and sets izanagi_cooldown_until)."""
    player = session.player
    if player.mangekyo_eye_1 != "izanagi" and player.mangekyo_eye_2 != "izanagi":
        session.send("You haven't learned that skill or jutsu.")
        return
    now = time.time()
    if now < player.izanagi_cooldown_until:
        remaining = player.izanagi_cooldown_until - now
        session.send(f"Izanagi is still recovering ({remaining / 3600:.1f} hours).")
        return

    player.izanagi_active = not player.izanagi_active
    if player.izanagi_active:
        session.send("&RReality bends around you -- fate itself now answers to your will.&x")
    else:
        session.send("&RYou release your grip on fate. Izanagi fades.&x")


def cmd_tailed_beast_mode(session, args: List[str]) -> None:
    """Toggles Tailed Beast Mode on/off -- per direct confirmation
    (Section 127 continued): "Tailed beast mode is much like
    sharingan on/off." Mirrors cmd_sharingan's own exact established
    pattern. Only ever togglable ON at genuinely full (100%)
    jinchuriki_mastery -- confirmed directly this represents having
    achieved real, free control over the beast's own power. The real
    combat/stat bonus itself (tailed_beasts.mode_bonus_percent,
    scaled by the specific beast's own tail count) is applied
    automatically by combat.py's own resolution wherever the
    personality-trait/rampage bonuses already are -- this command
    only flips the toggle. Blocked while rampaging (a defensive
    safeguard per direct confirmation, since these 2 states can't
    naturally co-occur given the real mastery gates on each)."""
    player = session.player
    if not player.jinchuriki_beast_key:
        session.send("You haven't learned that skill or jutsu.")
        return
    if player.jinchuriki_mastery < 100:
        session.send("You haven't mastered your beast's power well enough to control it yet.")
        return
    if player.rampage_until:
        session.send("You're consumed by the beast's rage -- you have no control over your own body!")
        return

    player.tailed_beast_mode_active = not player.tailed_beast_mode_active
    import data_tailed_beasts
    beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY[player.jinchuriki_beast_key]
    if player.tailed_beast_mode_active:
        session.send(f"&R{beast['display_name']}'s chakra cloaks you -- you feel its full power flow through you, under your own control.&x")
    else:
        session.send(f"&RThe cloak of {beast['display_name']}'s chakra fades.&x")


def cmd_aff(session, args: List[str]) -> None:
    """Shows every status effect (stunned, bleeding, confused, etc. --
    see status_effects.EFFECT_DEFS) currently active on the player,
    with remaining duration, same formatting score's own sheet already
    uses (see _format_active_effects above, extracted so the two can't
    drift apart). Also shows the Sharingan toggle when it's on -- the
    player already knows they activated it themselves, so this is
    ordinary visible ability state, not a Kekkei Genkai security
    concern the way raw mastery/tomoe numbers would be."""
    player = session.player
    lines = ["&WActive effects:&x " + _format_active_effects(player.active_status_effects)]
    if player.sharingan_active:
        lines.append("&RYour Sharingan is active.&x")
    session.send("\n".join(lines))


def cmd_afk(session, args: List[str]) -> None:
    player = session.player
    player.afk = not player.afk
    session.send("You are now AFK." if player.afk else "You are no longer AFK.")


def cmd_goto(session, args: List[str]) -> None:
    """Teleports the user directly to a room (by vnum) or to wherever
    another online player currently is (by name) -- an immortal/staff
    convenience for getting places instantly. Distinct from 'rset
    goto', which only changes which room subsequent OLC commands
    (rset/oset/mset) are editing, without moving the character at all.
    Bypasses any "locked"/"private" room restrictions the same way
    staff already can when walking normally -- this sets room_vnum
    directly rather than going through a directional move command."""
    if not olc._require_builder(session):
        return
    if not args:
        session.send("Usage: goto <vnum>  OR  goto <player name>")
        return

    query = " ".join(args)
    if query.isdigit():
        vnum = int(query)
        if vnum not in WORLD.rooms:
            WORLD.add_room(world.Room(vnum, "An Unfinished Room", "You see nothing special."))
            olc._log(session.player.name, "room", vnum, "auto-created via goto")
            session.send(f"Room {vnum} didn't exist yet -- created it.")
        destination = vnum
    else:
        target_session = next(
            (
                s for s in session.active_sessions()
                if s is not session and s.player and query.lower() in s.player.name.lower()
            ),
            None,
        )
        if not target_session:
            session.send(f"No player named '{query}' is online.")
            return
        destination = target_session.player.room_vnum

    session.player.room_vnum = destination
    session.send("You vanish in a puff of smoke.")
    cmd_look(session, [])
    _fire_enter_triggers(session)


def cmd_transfer(session, args: List[str]) -> None:
    """Teleports another (real, online) player directly to the
    caller's own current room -- per direct request/confirmation
    (Section 126): "add a transfer command and return so an imm can
    trasnfer a player to their location and it remembers where they
    where to transfer back." Saves that player's own real room first
    (pre_transfer_room_vnum), so 'return' can send them back later --
    a genuine, single saved value per player: transferring them again
    while already away just overwrites it with wherever they were at
    THAT moment, confirmed directly, not a stack of past locations."""
    if not olc._require_builder(session):
        return
    if not args:
        session.send("Usage: transfer <player name>")
        return

    query = " ".join(args)
    target_session = next(
        (
            s for s in session.active_sessions()
            if s is not session and s.player and query.lower() in s.player.name.lower()
        ),
        None,
    )
    if not target_session:
        session.send(f"No player named '{query}' is online.")
        return

    target_session.player.pre_transfer_room_vnum = target_session.player.room_vnum
    target_session.player.room_vnum = session.player.room_vnum
    session.last_transferred_player_name = target_session.player.name

    session.send(f"You transfer {target_session.player.name} to your location.")
    target_session.send(f"{session.player.name} transfers you elsewhere in a puff of smoke!")
    _fire_enter_triggers(target_session)


def cmd_return(session, args: List[str]) -> None:
    """Sends whoever the caller most recently transferred back to
    their own real, original room -- per direct request/confirmation
    (Section 126). Confirmed directly: takes no argument, always
    targeting the caller's own last transfer (session.
    last_transferred_player_name), not a name the caller specifies
    fresh each time. Refuses cleanly if that player isn't online
    anymore, or has already been returned (or never had a saved room
    at all)."""
    if not olc._require_builder(session):
        return
    if not session.last_transferred_player_name:
        session.send("You haven't transferred anyone yet.")
        return

    target_session = next(
        (
            s for s in session.active_sessions()
            if s.player and s.player.name == session.last_transferred_player_name
        ),
        None,
    )
    if not target_session:
        session.send(f"{session.last_transferred_player_name} isn't online anymore.")
        return
    if target_session.player.pre_transfer_room_vnum is None:
        session.send(f"{target_session.player.name} doesn't have anywhere saved to return to.")
        return

    target_session.player.room_vnum = target_session.player.pre_transfer_room_vnum
    target_session.player.pre_transfer_room_vnum = None
    session.last_transferred_player_name = None

    session.send(f"You send {target_session.player.name} back to where they were.")
    target_session.send(f"{session.player.name} sends you back to where you were in a puff of smoke!")
    _fire_enter_triggers(target_session)


def cmd_reload(session, args: List[str]) -> None:
    """Spawns back any registered spawn point (mob or item) in the
    room the player is currently standing in that's genuinely
    missing right now -- per direct request/confirmation ("add a
    command reload that reloads all items and mobs set to spawn in
    that room"). Confirmed: only spawns what's genuinely absent, no
    duplicates for anything already present, matching the exact same
    "missing-only" guarantee already established for mob spawn points
    via area resets, now extended to cover items too. See
    spawn_points.reload_room for the actual logic."""
    import spawn_points

    if not olc._require_builder(session):
        return

    player = session.player
    result = spawn_points.reload_room(player.room_vnum)
    if result["mobs"] == 0 and result["items"] == 0:
        session.send("Nothing to reload -- every spawn point registered in this room is already present.")
        return
    parts = []
    if result["mobs"]:
        parts.append(f"{result['mobs']} mob(s)")
    if result["items"]:
        parts.append(f"{result['items']} item(s)")
    session.send(f"Reloaded {' and '.join(parts)} into this room.")


def cmd_spawnpoint(session, args: List[str]) -> None:
    """'spawnpoint add mob|item <vnum>' -- registers a persistent
    spawn point in the room you're standing in right now (always the
    room you're in, matching how 'rset' works -- no separate targeting
    needed) and immediately spawns one instance too. It'll keep
    existing there across server restarts; for mobs, dying and
    respawning after that was already automatic (see spawn_points.py).
    'spawnpoint remove mob|item <vnum>' unregisters one (in the room
    you're standing in). 'spawnpoint remove all' unregisters every
    spawn point in the room at once, per direct request. 'spawnpoint
    list' shows every registered spawn point in the room you're
    standing in, with its own cap info alongside it.

    'spawnpoint cap mob|item <vnum> <total> <per_period>' -- per
    direct request/confirmation (Section 152: "why do we have
    setspawn AND spawnpoint...they move need to be merged into one
    command"), this folds the real, formerly-separate 'setspawn'
    command's own cap-setting ability in here as a subcommand instead
    of a whole second top-level command. Sets a real population cap
    on a spawn point (registering one at the caller's current room
    first if it doesn't already exist, same convenience 'spawnpoint
    add' already has). <total> is the max number of that vnum allowed
    to exist across the WHOLE containing area at once; <per_period>
    is the max NEW ones the area's own 15-minute reset sweep (see
    'help area') is allowed to add in a single pass, never exceeding
    the total. Use 'off' for either number to remove that cap
    (uncapped). 'spawnpoint cap mob|item <vnum>' with no numbers
    shows the current caps instead of changing them. Caps only ever
    affect mob spawn points in practice -- the area-reset sweep that
    actually enforces them is mob-only (see spawn_points.
    respawn_missing_mobs_in_area), matching that same design scope,
    though the caps themselves are stored the same way for either
    kind in case a future sweep extends to items."""
    import spawn_points

    if not olc._require_builder(session):
        return
    if not args:
        session.send(
            "Usage: spawnpoint add mob|item <vnum>\n"
            "       spawnpoint remove mob|item <vnum>\n"
            "       spawnpoint remove all\n"
            "       spawnpoint list\n"
            "       spawnpoint cap mob|item <vnum> <total> <per_period>\n"
            "       spawnpoint cap mob|item <vnum>   (shows current caps)"
        )
        return

    sub = args[0].lower()
    player = session.player

    if sub == "list":
        points = spawn_points.list_spawn_points(player.room_vnum)
        if not points:
            session.send("No spawn points registered in this room.")
            return
        lines = ["&WSpawn points in this room:&x"]
        for point in points:
            if point["kind"] == "mob":
                proto = combat.MOB_TEMPLATES.get(point["vnum"])
            else:
                proto = olc.OBJECT_TEMPLATES.get(point["vnum"])
            display = proto["short_desc"] if proto else f"(missing {point['kind']} {point['vnum']})"
            total_cap, per_period_cap = spawn_points.get_spawn_caps(point["kind"], point["vnum"], player.room_vnum)
            total_text = str(total_cap) if total_cap is not None else "uncapped"
            per_period_text = str(per_period_cap) if per_period_cap is not None else "uncapped"
            lines.append(
                f"  [{point['kind']}] vnum {point['vnum']} -- {display} "
                f"(total cap {total_text}, per-period cap {per_period_text})"
            )
        session.send("\n".join(lines))
        return

    if sub == "remove" and len(args) == 2 and args[1].lower() == "all":
        removed = spawn_points.remove_all_spawn_points(player.room_vnum)
        if not removed:
            session.send("No spawn points registered in this room.")
            return
        session.send(f"Removed all {removed} spawn point(s) registered in this room.")
        return

    if sub == "cap":
        if len(args) not in (3, 5) or args[1].lower() not in ("mob", "item") or not args[2].isdigit():
            session.send(
                "Usage: spawnpoint cap mob|item <vnum> <total> <per_period>\n"
                "       spawnpoint cap mob|item <vnum>   (shows current caps)"
            )
            return

        kind, vnum = args[1].lower(), int(args[2])

        if len(args) == 3:
            total_cap, per_period_cap = spawn_points.get_spawn_caps(kind, vnum, player.room_vnum)
            total_text = str(total_cap) if total_cap is not None else "uncapped"
            per_period_text = str(per_period_cap) if per_period_cap is not None else "uncapped"
            session.send(f"{kind.capitalize()} vnum {vnum} in this room: total cap {total_text}, per-period cap {per_period_text}.")
            return

        total_text, per_period_text = args[3], args[4]
        total_cap = None if total_text.lower() == "off" else (int(total_text) if total_text.isdigit() else None)
        per_period_cap = None if per_period_text.lower() == "off" else (int(per_period_text) if per_period_text.isdigit() else None)
        if (total_text.lower() != "off" and not total_text.isdigit()) or (per_period_text.lower() != "off" and not per_period_text.isdigit()):
            session.send("Both <total> and <per_period> must be a number or 'off'.")
            return
        if total_cap is not None and per_period_cap is not None and per_period_cap > total_cap:
            session.send(f"Per-period cap ({per_period_cap}) can't be higher than the total cap ({total_cap}).")
            return

        # Register the spawn point first if it doesn't exist yet --
        # same convenience 'spawnpoint add' already offers, so staff
        # don't need a separate add first just to set caps.
        existing = [p for p in spawn_points.list_spawn_points(player.room_vnum) if p["kind"] == kind and p["vnum"] == vnum]
        if not existing:
            error = spawn_points.add_spawn_point(kind, vnum, player.room_vnum)
            if error:
                session.send(error)
                return

        error = spawn_points.set_spawn_caps(kind, vnum, player.room_vnum, total_cap, per_period_cap)
        if error:
            session.send(error)
            return

        total_display = str(total_cap) if total_cap is not None else "uncapped"
        per_period_display = str(per_period_cap) if per_period_cap is not None else "uncapped"
        session.send(f"{kind.capitalize()} vnum {vnum} in this room: total cap set to {total_display}, per-period cap set to {per_period_display}.")
        cmd_look(session, [])
        return

    if sub not in ("add", "remove") or len(args) != 3 or args[1].lower() not in ("mob", "item") or not args[2].isdigit():
        session.send(
            "Usage: spawnpoint add mob|item <vnum>\n"
            "       spawnpoint remove mob|item <vnum>\n"
            "       spawnpoint remove all\n"
            "       spawnpoint list\n"
            "       spawnpoint cap mob|item <vnum> <total> <per_period>\n"
            "       spawnpoint cap mob|item <vnum>   (shows current caps)"
        )
        return

    kind, vnum = args[1].lower(), int(args[2])

    if sub == "add":
        error = spawn_points.add_spawn_point(kind, vnum, player.room_vnum)
        if error:
            session.send(error)
            return
        session.send(f"Spawn point registered: a {kind} (vnum {vnum}) will now always exist in this room.")
        return

    removed = spawn_points.remove_spawn_point(kind, vnum, player.room_vnum)
    if not removed:
        session.send("No matching spawn point registered in this room.")
        return
    session.send(f"Spawn point removed: a {kind} (vnum {vnum}) will no longer be re-placed here on server start.")


def cmd_recall(session, args: List[str]) -> None:
    player = session.player
    if session.combat_target is not None:
        session.send("You can't recall while you're fighting!")
        return
    if player.apartment_room_vnum is None:
        session.send("You don't own an apartment yet -- try 'buy apartment'.")
        return
    room = WORLD.get(player.apartment_room_vnum)
    if not room or not room.apartment or room.owner != player.name:
        session.send("Something's wrong with your apartment's deed -- contact a builder.")
        return
    player.room_vnum = room.vnum
    session.send(f"&CYou recall home to {room.name}.&x")
    cmd_look(session, [])
    _fire_enter_triggers(session)


ANKI_COOLDOWN_SECONDS = 5 * 60.0  # confirmed directly: "5 minute cooldown between use"


def cmd_anki(session, args: List[str]) -> None:
    """'anki' -- per direct request/confirmation (Section 136): "like
    recall but it will teleport the player to their village Kage room
    with a 5 minute cooldown between use." Confirmed directly: the
    same "can't use while fighting" restriction as recall, no level
    requirement at all, and auto-known by every character from
    creation (see data_jutsu.UNIVERSAL_STARTING_SKILLS).

    Fixed a real, genuine bug caught by direct user correction
    ("anki was supposed to be the kage room not village square"):
    VILLAGES[village]["starting_room_vnum"] is actually the Village
    Square, not the Kage room -- the real Kage room lives in a
    completely separate, real place, content._VILLAGE_ROOMS[village]
    ["kage"] (e.g. vnum 1010 for Leaf, distinct from the square's
    1000), the same real room used elsewhere for the Hokage's own
    chamber."""
    player = session.player
    if session.combat_target is not None:
        session.send("You can't use Anki while you're fighting!")
        return
    now = time.time()
    cooldown_ready_at = player.cooldowns.get("anki", 0)
    if now < cooldown_ready_at:
        session.send(f"Anki is still recovering ({cooldown_ready_at - now:.1f}s).")
        return
    import content
    village_rooms = content._VILLAGE_ROOMS.get(player.village)
    if not village_rooms:
        session.send("Something's wrong with your village registration -- contact a builder.")
        return
    room = WORLD.get(village_rooms["kage"])
    if not room:
        session.send("Something's wrong with your village's Kage room -- contact a builder.")
        return
    player.cooldowns["anki"] = now + ANKI_COOLDOWN_SECONDS
    player.room_vnum = room.vnum
    session.send(f"&CYou focus your chakra and recall the way home -- you arrive in {room.name}.&x")
    cmd_look(session, [])
    _fire_enter_triggers(session)


def cmd_apartment(session, args: List[str]) -> None:
    """Customize your OWNED apartment's name and description -- nothing
    else. Must be standing inside it (matching the 'buy apartment'
    restriction, so a player can't redecorate a home they aren't in)."""
    player = session.player
    if not args or args[0].lower() not in ("name", "desc", "description"):
        session.send("Usage: apartment name <text>  OR  apartment desc <text>")
        return
    if player.apartment_room_vnum is None:
        session.send("You don't own an apartment.")
        return
    room = WORLD.get(player.room_vnum)
    if not room or not room.apartment or room.owner != player.name:
        session.send("You have to be standing inside your own apartment to customize it.")
        return
    sub, rest = args[0].lower(), args[1:]
    if not rest:
        session.send(f"Usage: apartment {sub} <text>")
        return
    text = " ".join(rest)
    if sub == "name":
        room.name = text
        player.apartment_name = text
        storage.save_player(player)
        session.send(f"Your apartment is now called '{text}'.")
    else:
        room.description = text
        player.apartment_description = text
        storage.save_player(player)
        session.send("Your apartment's description has been updated.")


def _find_any_player(name: str):
    """Case-insensitive exact-name lookup for viewing purposes -- open
    to any player, not just staff (unlike olc._find_target_player,
    which is admin-only and used for editing). Checks online sessions
    first (so a just-written edit shows immediately), falling back to
    the save file for an offline character."""
    from session import ACTIVE_SESSIONS
    name_lower = name.lower()
    for s in ACTIVE_SESSIONS:
        if s.player and s.player.name.lower() == name_lower:
            return s.player
    return storage.load_player(name)


def cmd_description(session, args: List[str]) -> None:
    """Opens the guided line editor (same one used for help-topic
    authoring) to write a short roleplay description of your own
    character -- shown to others via 'look <you>'."""
    if args:
        session.send("Usage: 'description' with no arguments opens the editor to write your own.")
        return
    player = session.player

    def save(text: str) -> None:
        player.description = text
        storage.save_player(player)
        session.send("Description saved.")

    session.enter_editor(
        save, initial_text=player.description,
        header="Write a short description others will see when they 'look' at you.",
    )


def cmd_biography(session, args: List[str]) -> None:
    """With no arguments, opens the guided line editor to write your
    own character's longer roleplay backstory. With a name, shows that
    player's biography (online or offline, open to any player)."""
    if not args:
        player = session.player

        def save(text: str) -> None:
            player.biography = text
            storage.save_player(player)
            session.send("Biography saved.")

        session.enter_editor(
            save, initial_text=player.biography,
            header="Write your character's biography/backstory.",
        )
        return

    target = _find_any_player(" ".join(args))
    if not target:
        session.send(f"No player named '{' '.join(args)}' was found.")
        return
    if not target.biography:
        session.send(f"{target.name} hasn't written a biography yet.")
        return
    session.send(f"&Y{target.name}'s Biography:&x\n\n{target.biography}")


# --- Equipment -----------------------------------------------------------

def cmd_inventory(session, args: List[str]) -> None:
    player = session.player
    if not player.inventory:
        session.send("You aren't carrying anything.")
        return
    counts = inventory.slot_counts(player.inventory)
    lines = []
    for name, count in counts.items():
        colored = rarity_colored_name(tool_durability.display_name(name))
        shown = f"{colored} (x{count})" if count > 1 else colored
        lines.append(f"{shown}{_staff_vnum_suffix(session, item_name=name)}")
    session.send(
        "You are carrying:\n  " + "\n  ".join(lines)
        + f"\n&D({len(counts)}/{inventory.MAX_INVENTORY_SLOTS} slots used)&x"
    )


def cmd_equipment(session, args: List[str]) -> None:
    player = session.player
    lines = ["You are using:"]
    preferred_order = ("head", "neck", "piercing", "body", "back", "hands",
                       "finger", "waist", "legs", "feet", "chakra aura",
                       "wielded", "tool")
    slots = [slot for slot in preferred_order if slot in olc.WEAR_LOCATIONS]
    slots.extend(sorted((olc.WEAR_LOCATIONS | player.equipment.keys()) - set(slots)))
    for slot in slots:
        item = player.equipment.get(slot)
        lines.append(f"  <{slot}> {rarity_colored_name(tool_durability.display_name(item)) if item else '&D(nothing)&x'}")
    session.send("\n".join(lines))


def cmd_wear(session, args: List[str]) -> None:
    if args and " ".join(args).lower() == "all":
        _wear_all(session)
        return
    _equip_item(session, args, accepted_locs=olc.ARMOR_WEAR_LOCATIONS | {"wielded"}, verb="wear")


def cmd_wield(session, args: List[str]) -> None:
    _equip_item(session, args, accepted_locs={"wielded"}, verb="wield")


def cmd_hold(session, args: List[str]) -> None:
    """Equips a tool (a crafted fishing rod, etc.) in its own 'tool'
    slot -- separate from wielded weapons and worn armor, so a player
    can hold a rod and still fight with their weapon equipped."""
    _equip_item(session, args, accepted_locs={"tool"}, verb="hold")


def _item_wear_loc(item_name: str):
    """The wear_loc an item's own prototype declares, or None if it
    has none set (not equippable at all) or no prototype exists."""
    proto = _find_object_prototype_by_name(item_name)
    return proto.get("wear_loc") or None if proto else None


def _learn_weapon_skill_if_new(player, weapon_type: str):
    """Grants the weapon skill for weapon_type (data_weapons.WEAPON_TYPES)
    the first time a player wields a weapon of that type, if they
    don't already have it -- fixes a previously-flagged gap where no
    weapon skill (Kunai, Sword, etc.) was ever actually granted to any
    player anywhere in the codebase, despite being defined in the
    catalog and shown under General Skills in 'prac'. Returns a
    one-time announcement message, or None if the player already had
    it."""
    weapon_info = data_weapons.WEAPON_TYPES.get(weapon_type)
    if not weapon_info:
        return None
    skill_name = weapon_info["skill"]
    if skill_name in player.learned_skills:
        return None
    player.learned_skills.append(skill_name)
    player.skill_proficiencies[skill_name] = 0
    return f"&GYou've learned the basics of {skill_name}!&x"


_EQUIPMENT_STAT_BONUS_PLAYER_FIELDS = {
    "max_health": "maximum_health",
    "max_chakra": "maximum_chakra",
    "max_stamina": "maximum_stamina",
    "strength": "strength",
    "dexterity": "dexterity",
    "intelligence": "intelligence",
    "wisdom": "wisdom",
    "luck": "luck",
    "constitution": "constitution",
}


def _apply_equipment_stat_bonuses(player, item_name: str, sign: int) -> None:
    """Applies (sign=+1, on equip) or reverses (sign=-1, on unequip) an
    item's stat_bonuses for the 9 categories beyond hitroll/damroll/
    armor_class -- those 3 are already summed dynamically each time
    they're needed (see equipped_weapon_hitroll_bonus and friends),
    but max_health/max_chakra/max_stamina and the 6 attributes are
    read directly all over the codebase (regen caps, the score sheet,
    damage formulas), so baking the bonus permanently into the
    player's own field here, exactly once at the moment of equipping,
    keeps every one of those existing reads correct automatically
    rather than needing each individually rewritten to account for
    equipment. Deliberately no cap check here -- an equipment bonus
    can push an attribute past config.MAX_ATTRIBUTE_VALUE, same
    established precedent as a completed armor set's bonus in
    derived_stats.py (that cap only applies to raw training). For the
    3 resource pools, the current value moves by the same delta as the
    max (so equipping doesn't look like a sudden % drop, nor unequip a
    sudden overflow), then clamped to a sane [0, max] range as a
    safety net."""
    proto = _find_object_prototype_by_name(item_name)
    if not proto:
        return
    for stat_key, player_field in _EQUIPMENT_STAT_BONUS_PLAYER_FIELDS.items():
        bonus = proto.get("stat_bonuses", {}).get(stat_key, 0)
        if not bonus:
            continue
        setattr(player, player_field, getattr(player, player_field) + sign * bonus)
        if stat_key == "max_health":
            player.health = max(0, min(player.maximum_health, player.health + sign * bonus))
        elif stat_key == "max_chakra":
            player.chakra = max(0, min(player.maximum_chakra, player.chakra + sign * bonus))
        elif stat_key == "max_stamina":
            player.stamina = max(0, min(player.maximum_stamina, player.stamina + sign * bonus))


def _equip_item(session, args: List[str], accepted_locs, verb: str) -> None:
    """Equips an item into ITS OWN wear_loc (an item's own prototype
    field, not a slot forced by which command the player typed) --
    provided that wear_loc is one this command actually accepts.
    'wear' accepts both armor and weapons; 'wield' accepts weapons."""
    player = session.player
    if not args:
        session.send(f"{verb.capitalize()} what?")
        return
    query = " ".join(args).lower()

    already_equipped = next((item for item in player.equipment.values() if _item_matches(query, item)), None)
    if already_equipped:
        session.send(f"You are already using {already_equipped}.")
        return

    match = find_indexed_item(query, player.inventory)
    if not match:
        session.send(f"You aren't carrying anything like '{query}'.")
        return

    wear_loc = _item_wear_loc(match)
    if wear_loc not in accepted_locs:
        session.send(f"You can't {verb} {match}.")
        return

    player.inventory.remove(match)
    previous = player.equipment.get(wear_loc)
    if previous and previous != match:
        ok, reason = inventory.add_item(player.inventory, previous)
        if ok:
            session.send(f"You stop using {rarity_colored_name(previous)}.")
            _apply_equipment_stat_bonuses(player, previous, sign=-1)
        else:
            # Only reachable if the player somehow already has 64 of
            # this exact item sitting loose in inventory -- no
            # drop-to-room mechanic exists in this game, so be
            # honest that it's lost rather than claiming it's
            # retrievable somewhere.
            session.send(inventory.full_message(reason, previous))
            session.send(f"With nowhere to put it, {rarity_colored_name(previous)} is lost.")
            _apply_equipment_stat_bonuses(player, previous, sign=-1)
    player.equipment[wear_loc] = match
    _apply_equipment_stat_bonuses(player, match, sign=1)
    if wear_loc == "wielded":
        weapon_type = data_weapons.weapon_type_for_item(match)
        if weapon_type:
            session.send(f"You wield {rarity_colored_name(match)} ({data_weapons.display_name(weapon_type)}-style weapon).")
            learn_msg = _learn_weapon_skill_if_new(player, weapon_type)
            if learn_msg:
                session.send(learn_msg)
        else:
            session.send(f"You wield {rarity_colored_name(match)}.")
    elif wear_loc == "tool":
        session.send(f"You hold {rarity_colored_name(tool_durability.display_name(match))}.")
    else:
        session.send(f"You wear {rarity_colored_name(match)}.")
    _fire_item_trigger(session, match, "wear")



def _wear_all(session) -> None:
    """'wear all' -- per explicit request. Equips every equippable
    item in inventory (any wear_loc: armor, weapon, or tool) into its
    OWN slot, not all into one. Skips a slot that's already occupied
    rather than silently swapping out whatever's there -- an explicit
    single-item wear/wield/hold is how you replace something on
    purpose. Replaces the old 'wear all', which forced everything into
    a single hardcoded slot and silently dropped all but the first
    match due to a dict.setdefault bug."""
    player = session.player
    equipped_count = 0
    for item in list(player.inventory):
        wear_loc = _item_wear_loc(item)
        if wear_loc not in olc.WEAR_LOCATIONS:
            continue
        if wear_loc in player.equipment:
            continue
        player.inventory.remove(item)
        player.equipment[wear_loc] = item
        _apply_equipment_stat_bonuses(player, item, sign=1)
        if wear_loc == "wielded":
            weapon_type = data_weapons.weapon_type_for_item(item)
            if weapon_type:
                learn_msg = _learn_weapon_skill_if_new(player, weapon_type)
                if learn_msg:
                    session.send(learn_msg)
        _fire_item_trigger(session, item, "wear")
        equipped_count += 1
    if equipped_count:
        session.send(f"You put on {equipped_count} item(s).")
    else:
        session.send("You have nothing new to wear.")


def cmd_remove(session, args: List[str]) -> None:
    player = session.player
    if not args:
        session.send("Remove what?")
        return
    query = " ".join(args).lower()

    if query == "all":
        _remove_all(session)
        return

    match_slot = next(
        (slot for slot, item in player.equipment.items() if _item_matches(query, item)), None
    )
    if not match_slot:
        session.send(f"You aren't wearing or wielding anything like '{query}'.")
        return

    item = player.equipment[match_slot]
    ok, reason = inventory.add_item(player.inventory, item)
    if not ok:
        session.send(inventory.full_message(reason, item))
        return
    del player.equipment[match_slot]
    _apply_equipment_stat_bonuses(player, item, sign=-1)
    session.send(f"You remove {item}.")


def _remove_all(session) -> None:
    """'remove all' -- per explicit request. Removes everything
    currently equipped, one slot at a time, adding each back to
    inventory. If inventory is full partway through, whatever's left
    stays equipped rather than being lost -- same "don't destroy items
    on a full inventory" principle used everywhere else in the game."""
    player = session.player
    removed_count = 0
    for slot in list(player.equipment.keys()):
        item = player.equipment[slot]
        ok, reason = inventory.add_item(player.inventory, item)
        if not ok:
            session.send(inventory.full_message(reason, item))
            session.send(f"With nowhere to put it, {rarity_colored_name(item)} stays equipped.")
            continue
        del player.equipment[slot]
        _apply_equipment_stat_bonuses(player, item, sign=-1)
        removed_count += 1
    if removed_count:
        session.send(f"You remove {removed_count} item(s).")
    else:
        session.send("You aren't wearing or wielding anything.")


CONSIDER_THRESHOLDS = [
    (-10, "&GYou can kill it with a single blow.&x"),
    (-5, "&GIt looks like an easy kill.&x"),
    (-1, "&GThe odds are in your favor.&x"),
    (0, "&YThe perfect match for your skills!&x"),
    (4, "&YYou should be cautious.&x"),
    (9, "&RYou would need some luck!&x"),
    (float("inf"), "&RDeath will thank you for your gift.&x"),
]


def _consider_verdict(level_diff: int) -> str:
    for threshold, verdict in CONSIDER_THRESHOLDS:
        if level_diff <= threshold:
            return verdict
    return CONSIDER_THRESHOLDS[-1][1]


def cmd_weather(session, args: List[str]) -> None:
    """Reports the current world-wide weather and time of day
    (weather.py) -- both change periodically via the main pulse loop,
    not per-room. Purely informational; the actual mechanical effects
    (gathering fail chance, combat accuracy, night dodge bonus) apply
    automatically without needing to check this first."""
    session.send(weather.status_line())


def cmd_consider(session, args: List[str]) -> None:
    """Gauges how dangerous a mob would be to fight, based on the level
    gap between it and the player -- a quick, cheap way to check before
    committing to 'attack', not a full combat simulation. Mobs only,
    matching the classic convention (a player's level/rank is already
    visible via 'who' or 'look' for a PvP read)."""
    player = session.player
    if not args:
        session.send("Consider fighting whom?")
        return
    mob = combat.find_mob(player.room_vnum, " ".join(args))
    if not mob:
        session.send("You don't see that here.")
        return
    verdict = _consider_verdict(mob.level - player.level)
    session.send(f"You consider {mob.name}.\n{verdict}")


def cmd_attack(session, args: List[str]) -> None:
    player = session.player

    if not args:
        session.send("Attack what?")
        return
    mob = combat.find_mob(player.room_vnum, " ".join(args))
    if mob:
        if combat.is_shopkeeper(mob) or combat.is_gambler(mob) or combat.is_teacher(mob) or combat.is_immortal_mob(mob):
            session.send(f"{mob.name.capitalize()} is protected and cannot be attacked.")
            return
        _wake_and_stand(session)
        combat.start_attack(session, mob)
        session.send(f"You attack {mob.name}!")
        return

    query = " ".join(args).lower()
    target_session = next(
        (
            s for s in session.active_sessions()
            if s is not session and s.player and s.player.room_vnum == player.room_vnum
            and query in s.player.name.lower()
        ),
        None,
    )
    if not target_session:
        session.send("There is nothing here for you to attack.")
        return
    if player.illusion_walk_caster is not None:
        session.send("There is nothing here for you to attack.")
        return

    room = world.WORLD.get(player.room_vnum)
    if room and room.safe:
        session.send("This is a PvP-safe zone. You cannot attack other players here.")
        return
    if target_session.player.izanami_trapped:
        session.send(f"{target_session.player.name} is lost in a loop, untouched by reality -- you cannot reach them.")
        return
    if target_session.player.health <= 0:
        session.send(f"{target_session.player.name} is already down.")
        return

    _wake_and_stand(session)
    combat.start_pvp_attack(session, target_session)
    session.send(f"You attack {target_session.player.name}!")
    target_session.send(f"&R{player.name} attacks you!&x")


def cmd_use_jutsu(session, jutsu_key: str, target_words: List[str]) -> None:
    player = session.player
    jutsu_data = data_jutsu.JUTSU.get(jutsu_key, {})
    if jutsu_data.get("jutsu_type") == "summon":
        if jutsu_key == "shadow clone jutsu":
            combat.use_shadow_clone_jutsu(session)
        return
    if jutsu_data.get("jutsu_type") == "track":
        import tracking
        import areas
        import session as session_module

        if not target_words:
            session.send("Track who or what?")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("track", 0)
        if now < cooldown_ready_at:
            session.send(f"&WTrack&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return

        query = " ".join(target_words)
        target_mob = tracking.find_mob_anywhere_in_world(combat, query)
        target_player_session = None
        if target_mob is None:
            target_player_session = tracking.find_online_player_anywhere(session_module, query)
        if target_mob is None and target_player_session is None:
            session.send(f"You can't find any trace of '{query}' anywhere.")
            return

        target_room_vnum = target_mob.room_vnum if target_mob else target_player_session.player.room_vnum
        area = areas.find_area_for_vnum(target_room_vnum)
        if area is None:
            session.send("You can't get a fix on their location.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["track"] = now + jutsu_data["cooldown"]
        tracking.start_tracking(
            player,
            target_mob=target_mob,
            target_player_name=target_player_session.player.name if target_player_session else None,
            area_name=area.name,
        )
        target_name = target_mob.name if target_mob else target_player_session.player.name
        session.send(f"&YYou focus your senses and pick up {target_name}'s trail...&x")
        return
    if jutsu_data.get("jutsu_type") == "sealing":
        if not target_words:
            session.send("Seal what?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        query = " ".join(target_words)
        mob = combat.find_mob(player.room_vnum, query)
        if mob is None or not getattr(mob, "tailed_beast_key", None):
            session.send("There's no Tailed Beast here by that name.")
            return
        if mob.tailed_beast_downed_until == 0.0:
            session.send(f"{mob.name} is still fighting back -- you can't seal it yet.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        beast_key = mob.tailed_beast_key
        import data_tailed_beasts
        beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY[beast_key]
        combat.remove_mob(mob)
        player.jinchuriki_beast_key = beast_key
        player.jinchuriki_mastery = 0
        session.send(f"&RYou complete the seal -- {beast['display_name']} is bound within you now!&x")
        _broadcast_globally(f"&R{player.name} has sealed {beast['display_name']} within themselves!&x")
        return
    if jutsu_data.get("jutsu_type") == "beast_release":
        if not target_words:
            session.send("Release the beast from who?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        query = " ".join(target_words).lower()
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player and query in s.player.name.lower()),
            None,
        )
        if not target_session or not target_session.player.jinchuriki_beast_key:
            session.send("That player isn't a jinchuriki.")
            return
        if target_session.player.health > 0:
            session.send(f"You must defeat {target_session.player.name} in combat first.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        beast_key = target_session.player.jinchuriki_beast_key
        import data_tailed_beasts
        import tailed_beasts as tailed_beasts_module
        import world as world_module
        beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY[beast_key]
        target_session.player.jinchuriki_beast_key = None
        target_session.player.jinchuriki_mastery = 0
        mob = tailed_beasts_module.release_beast(beast, world_module, combat)
        session.send(f"&RYou tear {beast['display_name']} free from {target_session.player.name}!&x")
        target_session.send(f"&R{player.name} rips {beast['display_name']} out of you!&x")
        _broadcast_globally(f"&R{beast['display_name']} has been torn free and released back into the world!&x")
        return
    if jutsu_data.get("jutsu_type") == "beast_bomb":
        if not player.tailed_beast_mode_active:
            session.send("You can only unleash this while Tailed Beast Mode is active.")
            return
        if not target_words:
            session.send("Unleash the Tailed Beast Bomb on who?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("tailed beast bomb", 0)
        if now < cooldown_ready_at:
            session.send(f"&WTailed Beast Bomb&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return

        query = " ".join(target_words)
        mob = combat.find_mob(player.room_vnum, query)
        target_session = None
        if mob is None:
            target_session = next(
                (s for s in session.active_sessions() if s is not session and s.player and query.lower() in s.player.name.lower()),
                None,
            )
        if mob is None and target_session is None:
            session.send("There's nothing here by that name.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["tailed beast bomb"] = now + jutsu_data["cooldown"]
        import tailed_beasts as tailed_beasts_module
        dmg = tailed_beasts_module.bomb_damage(player)
        import data_tailed_beasts
        beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY[player.jinchuriki_beast_key]
        if mob is not None:
            mob.health -= dmg
            session.send(f"&RYou unleash a {beast['display_name']} Bomb on {mob.name} for {damage_messages.describe_damage(dmg)} damage!&x")
            if mob.health <= 0:
                combat.handle_mob_defeat(session, mob)
        else:
            target_session.player.health -= dmg
            session.send(f"&RYou unleash a {beast['display_name']} Bomb on {target_session.player.name} for {damage_messages.describe_damage(dmg)} damage!&x")
            target_session.send(f"&R{player.name} unleashes a {beast['display_name']} Bomb on you for {damage_messages.describe_damage(dmg)} damage!&x")
            if target_session.player.health <= 0:
                if combat.is_immortal_immune_to_defeat(target_session):
                    combat.clamp_immortal_health(target_session)
                else:
                    combat.handle_pvp_defeat(winner_session=session, loser_session=target_session)
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_tsukuyomi":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if not target_words:
            session.send("Trap who in Tsukuyomi?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("tsukuyomi", 0)
        if now < cooldown_ready_at:
            session.send(f"&WTsukuyomi&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return

        query = " ".join(target_words)
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player and query.lower() in s.player.name.lower()),
            None,
        )
        if target_session is None:
            session.send("There's nobody here by that name.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["tsukuyomi"] = now + jutsu_data["cooldown"]
        if has_silent_genjutsu(player):
            combat.resolve_tsukuyomi_cast(session, target_session)
        else:
            combat.begin_pending_cast(session, "tsukuyomi", target_session, is_pvp=True, start_combat_on_resolve=False)
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_amaterasu":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if not target_words:
            session.send("Unleash Amaterasu on who?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("amaterasu", 0)
        if now < cooldown_ready_at:
            session.send(f"&WAmaterasu&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return

        query = " ".join(target_words)
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player and query.lower() in s.player.name.lower()),
            None,
        )
        if target_session is None:
            session.send("There's nobody here by that name.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["amaterasu"] = now + jutsu_data["cooldown"]
        if has_silent_genjutsu(player):
            combat.resolve_amaterasu_cast(session, target_session)
        else:
            combat.begin_pending_cast(session, "amaterasu", target_session, is_pvp=True, start_combat_on_resolve=False)
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_kamui_pocket_dimension":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if not target_words:
            session.send("Open the pocket dimension on who?")
            return
        query = " ".join(target_words).lower()

        # Step 2: targeting oneself joins a dimension already opened.
        if query in player.name.lower():
            import mangekyo
            if mangekyo.enter_own_pocket_dimension(session):
                session.send("&RYou step through the rift and into the pocket dimension you opened.&x")
            else:
                session.send("You haven't opened a pocket dimension yet.")
            return

        # Step 1: targeting another player opens it and sends them alone.
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player and query in s.player.name.lower()),
            None,
        )
        if target_session is None:
            session.send("There's nobody here by that name.")
            return

        import mangekyo
        import world as world_module
        mangekyo.open_pocket_dimension(session, target_session, world_module)
        session.send(f"&RYou tear open a rift and cast {target_session.player.name} into a pocket dimension.&x")
        target_session.send(f"&R{player.name}'s eyes flash -- reality tears open and swallows you whole!&x")
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_kamui_intangibility":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("kamui intangibility", 0)
        if now < cooldown_ready_at:
            session.send(f"&WKamui: Intangibility&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return
        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["kamui intangibility"] = now + jutsu_data["cooldown"]
        import data_mangekyo
        player.kamui_intangibility_rounds_left = data_mangekyo.KAMUI_INTANGIBILITY_ROUNDS
        session.send("&RYour body turns to mist -- nothing can touch you for a moment.&x")
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_kamui_limb_removal":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if not target_words:
            session.send("Unleash Kamui: Limb Removal on who?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("kamui limb removal", 0)
        if now < cooldown_ready_at:
            session.send(f"&WKamui: Limb Removal&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return

        query = " ".join(target_words)
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player and query.lower() in s.player.name.lower()),
            None,
        )
        if target_session is None:
            session.send("There's nobody here by that name.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["kamui limb removal"] = now + jutsu_data["cooldown"]
        import random
        import data_mangekyo
        delay = random.uniform(*data_mangekyo.KAMUI_LIMB_REMOVAL_CAST_SECONDS)
        session.pending_cast = combat.PendingCast("kamui limb removal", target_session, is_pvp=True, remaining_seconds=delay, start_combat_on_resolve=False)
        session.send(f"&WYou begin tearing a rift through space, blade poised to strike {target_session.player.name}...&x")
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_izanami":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if not target_words:
            session.send("Trap who in Izanami?")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("izanami", 0)
        if now < cooldown_ready_at:
            session.send(f"&WIzanami&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return

        query = " ".join(target_words)
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player and query.lower() in s.player.name.lower()),
            None,
        )
        if target_session is None:
            session.send("There's nobody here by that name.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["izanami"] = now + jutsu_data["cooldown"]
        if has_silent_genjutsu(player):
            combat.resolve_izanami_cast(session, target_session)
        else:
            combat.begin_pending_cast(session, "izanami", target_session, is_pvp=True, start_combat_on_resolve=False)
        return
    if jutsu_data.get("jutsu_type") == "mangekyo_kekkei_no_me":
        if not combat._can_use_jutsu(player, jutsu_data, jutsu_key):
            session.send("You haven't learned that skill or jutsu.")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("kekkei no me", 0)
        if now < cooldown_ready_at:
            session.send(f"&WKekkei no Me&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return
        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["kekkei no me"] = now + jutsu_data["cooldown"]
        if has_silent_genjutsu(player):
            combat.resolve_kekkei_no_me_cast(session)
        else:
            combat.begin_pending_cast(session, "kekkei no me", session, is_pvp=False, start_combat_on_resolve=False)
        return
    if jutsu_data.get("jutsu_type") == "illusion_walk":
        if not target_words:
            session.send("Cast Illusion Walk on who?")
            return
        now = time.time()
        cooldown_ready_at = player.cooldowns.get("illusion walk", 0)
        if now < cooldown_ready_at:
            session.send(f"&WIllusion Walk&x is still recovering ({cooldown_ready_at - now:.1f}s).")
            return
        if player.chakra < jutsu_data["chakra_cost"]:
            session.send("You don't have enough chakra.")
            return
        if session.pending_cast is not None:
            session.send("You're already in the middle of forming hand signs for another jutsu!")
            return

        query = " ".join(target_words).lower()
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player
             and s.player.room_vnum == player.room_vnum and query in s.player.name.lower()),
            None,
        )
        if not target_session:
            session.send("There's nobody here by that name.")
            return

        player.chakra -= jutsu_data["chakra_cost"]
        player.cooldowns["illusion walk"] = now + jutsu_data["cooldown"]
        if has_silent_genjutsu(player):
            combat.resolve_illusion_walk_cast(session, target_session)
        else:
            combat.begin_pending_cast(session, "illusion walk", target_session, is_pvp=True, start_combat_on_resolve=False)
        return
    if jutsu_data.get("jutsu_type") in ("counter", "silent_genjutsu_passive"):
        session.send(f"{jutsu_data['display_name']} is a passive ability -- it triggers automatically, you don't use it directly.")
        return
    if target_words:
        mob = combat.find_mob(player.room_vnum, " ".join(target_words))
    else:
        mob = session.combat_target
    if mob:
        if combat.is_shopkeeper(mob) or combat.is_gambler(mob) or combat.is_teacher(mob) or combat.is_immortal_mob(mob):
            session.send(f"{mob.name.capitalize()} is protected and cannot be attacked.")
            return
        if session.pending_cast is not None:
            session.send("You're already in the middle of forming hand signs for another jutsu!")
            return
        import data_handsigns
        starting_fresh = session.combat_target is None
        if data_handsigns.has_handsigns(jutsu_data) and combat._can_use_jutsu(player, jutsu_data, jutsu_key) and not has_silent_genjutsu(player):
            if starting_fresh:
                _wake_and_stand(session)
            combat.begin_pending_cast(session, jutsu_key, mob, is_pvp=False, start_combat_on_resolve=starting_fresh)
        else:
            if starting_fresh:
                _wake_and_stand(session)
                combat.start_attack(session, mob)
            combat.use_jutsu(session, jutsu_key, mob)
        return

    # No mob matched -- per direct request ("make jutsu pvp enabled"),
    # fall back to another player in the room, same targeting
    # convention cmd_attack already uses.
    target_session = None
    if target_words:
        query = " ".join(target_words).lower()
        target_session = next(
            (
                s for s in session.active_sessions()
                if s is not session and s.player and s.player.room_vnum == player.room_vnum
                and query in s.player.name.lower()
            ),
            None,
        )
    elif session.pvp_target is not None:
        target_session = session.pvp_target

    if not target_session:
        session.send("There is nothing here to use that on.")
        return
    if player.illusion_walk_caster is not None:
        session.send("There is nothing here to use that on.")
        return

    room = world.WORLD.get(player.room_vnum)
    if room and room.safe:
        session.send("This is a PvP-safe zone. You cannot attack other players here.")
        return
    if target_session.player.health <= 0:
        session.send(f"{target_session.player.name} is already down.")
        return
    if session.pending_cast is not None:
        session.send("You're already in the middle of forming hand signs for another jutsu!")
        return

    import data_handsigns
    starting_fresh = session.pvp_target is None
    if data_handsigns.has_handsigns(jutsu_data) and combat._can_use_jutsu(player, jutsu_data, jutsu_key) and not has_silent_genjutsu(player):
        if starting_fresh:
            _wake_and_stand(session)
        combat.begin_pending_cast(session, jutsu_key, target_session, is_pvp=True, start_combat_on_resolve=starting_fresh)
    else:
        if starting_fresh:
            _wake_and_stand(session)
            combat.start_pvp_attack(session, target_session)
        combat.use_jutsu_on_player(session, jutsu_key, target_session)


def cmd_perform(session, args: List[str]) -> None:
    """Ninjutsu and Genjutsu require this deliberate 'perform <jutsu>'
    entry point instead of a bare jutsu name (unlike Taijutsu/Bukijutsu,
    which can be used directly -- see dispatch_line)."""
    if not args:
        session.send("Perform what?")
        return
    lower_words = [w.lower() for w in args]
    jutsu_key, consumed = data_jutsu.match_prefix(lower_words)
    if not jutsu_key:
        session.send("You don't know a jutsu by that name.")
        return
    jutsu = data_jutsu.JUTSU[jutsu_key]
    if jutsu["class_requirement"] in BARE_NAME_JUTSU_CATEGORIES:
        session.send(f"{jutsu['display_name']} is a {jutsu['class_requirement'].capitalize()} technique -- just use its name directly, no 'perform' needed.")
        return
    cmd_use_jutsu(session, jutsu_key, args[consumed:])


WEEDS_DELAY_SECONDS = 6.0


def _find_villager(room_vnum: int):
    for mob in combat.mobs_in_room(room_vnum):
        if "villager" in mob.name.lower():
            return mob
    return None


def cmd_pullweeds(session, args: List[str]) -> None:
    """Pulls one bundle of weeds from a villager's garden -- feeds the
    'Weed the Garden' gather-type mission (missions.py), but isn't
    itself gated on having that mission active, matching how mining/
    lumberjacking are also an open economy rather than mission-locked.
    Always yields exactly 1 bundle (no rarity table -- this is a plain
    menial chore, not a skill-based catch). Takes WEEDS_DELAY_SECONDS,
    same delayed-action treatment as every other gather/craft/gamble
    action (session.start_timed_action)."""
    player = session.player
    if not _find_villager(player.room_vnum):
        session.send("There's no garden to pull weeds from here.")
        return
    if session.is_busy():
        session.send("You're already busy with something.")
        return

    def resolve() -> None:
        ok, reason = inventory.add_item(player.inventory, "A Bundle of Weeds")
        if not ok:
            session.send(f"You pull a bundle of weeds, but had nowhere to put it!")
            session.send(inventory.full_message(reason, "A Bundle of Weeds"))
            return
        session.send("You pull a bundle of weeds from the garden.")

    session.send("You crouch down and start pulling weeds...")
    session.start_timed_action("pullweeds", WEEDS_DELAY_SECONDS, resolve)


def cmd_deliver(session, args: List[str]) -> None:
    """Hands over every 'A Bundle of Weeds' the player is carrying (up
    to however many the active gather-type mission still needs) to a
    villager mob in the current room, advancing that mission's
    progress (missions.on_weeds_delivered) -- partial delivery across
    multiple trips works fine, since progress accumulates rather than
    requiring the full target_count in one go."""
    player = session.player
    villager = _find_villager(player.room_vnum)
    if not villager:
        session.send("There's no one here to deliver anything to.")
        return

    carried = sum(1 for item in player.inventory if item.lower() == "a bundle of weeds")
    if carried == 0:
        session.send("You aren't carrying any bundles of weeds to deliver.")
        return

    for _ in range(carried):
        player.inventory.remove(next(item for item in player.inventory if item.lower() == "a bundle of weeds"))

    session.send(f"You hand {villager.name} {carried} bundle(s) of weeds.")
    for message in missions.on_weeds_delivered(player, villager.template_vnum, carried):
        session.send(message)


def cmd_group(session, args: List[str]) -> None:
    """Player grouping (groups.py) -- 'group' alone shows the roster;
    'group invite <player>' (same room required) + 'group accept'
    forms one; 'group leave'/'kick <player>'/'disband' break it back
    apart. The main mechanical effect (shared XP on a kill) lives in
    combat.handle_mob_defeat, not here -- this command only manages
    who's in the group."""
    player = session.player

    if not args:
        if not session.group:
            session.send("You aren't in a group. Try 'group invite <player>'.")
            return
        lines = ["&WYour group:&x"]
        for member in session.group.members:
            if not member.player:
                continue
            leader_tag = " &Y(Leader)&x" if member is session.group.leader else ""
            elsewhere = "" if member.player.room_vnum == player.room_vnum else " &D(elsewhere)&x"
            lines.append(
                f"  {member.player.name}{leader_tag} - "
                f"HP: {member.player.health}/{member.player.maximum_health}{elsewhere}"
            )
        session.send("\n".join(lines))
        return

    sub = args[0].lower()

    if sub == "invite":
        if len(args) < 2:
            session.send("Usage: group invite <player>")
            return
        if session.group and session.group.leader is not session:
            session.send("Only the group leader can invite new members.")
            return
        if session.group and session.group.is_full():
            session.send(f"Your group is already full ({groups.MAX_GROUP_SIZE} members max).")
            return

        target_query = args[1].lower()
        target_session = next(
            (
                s for s in session.active_sessions()
                if s is not session and s.player and s.player.room_vnum == player.room_vnum
                and target_query in s.player.name.lower()
            ),
            None,
        )
        if not target_session:
            session.send("There's no one here by that name.")
            return
        if target_session.group:
            session.send(f"{target_session.player.name} is already in a group.")
            return

        if not session.group:
            session.group = groups.Group(session)
        target_session.pending_group_invite = session.group
        session.send(f"You invite {target_session.player.name} to your group.")
        target_session.send(f"{player.name} invites you to join their group. Type 'group accept' to join.")
        return

    if sub == "accept":
        if not session.pending_group_invite:
            session.send("You have no pending group invite.")
            return
        group = session.pending_group_invite
        session.pending_group_invite = None
        if group.is_full():
            session.send("That group is now full.")
            return
        group.members.append(session)
        session.group = group
        for member in group.members:
            member.send(f"&G{player.name} has joined the group.&x")
        return

    if sub == "leave":
        if not session.group:
            session.send("You aren't in a group.")
            return
        group = session.group
        groups.remove_member(group, session)
        session.group = None
        session.send("You leave the group.")
        for member in group.members:
            member.send(f"&D{player.name} has left the group.&x")
        return

    if sub == "kick":
        if len(args) < 2:
            session.send("Usage: group kick <player>")
            return
        if not session.group or session.group.leader is not session:
            session.send("Only the group leader can kick members.")
            return
        query = args[1].lower()
        target = next(
            (m for m in session.group.members if m is not session and query in m.player.name.lower()),
            None,
        )
        if not target:
            session.send("No one in your group matches that name.")
            return
        group = session.group
        groups.remove_member(group, target)
        target.group = None
        target.send(f"&D{player.name} has removed you from the group.&x")
        for member in group.members:
            member.send(f"&D{target.player.name} has been removed from the group.&x")
        return

    if sub == "disband":
        if not session.group or session.group.leader is not session:
            session.send("Only the group leader can disband the group.")
            return
        group = session.group
        for member in group.members:
            member.send("&DThe group has been disbanded.&x")
        groups.disband(group)
        return

    session.send("Usage: group [invite <player>|accept|leave|kick <player>|disband]")


def cmd_team(session, args: List[str]) -> None:
    """The new, persistent Teams system (teams.py) -- genuinely
    separate from 'group' above (see teams.py's own module docstring
    for the full distinction). 'team' alone shows the roster; 'team
    create <name>' (Chunin+ only, not on disband cooldown) forms a
    new team with the creator as leader; 'team invite <player>'
    (leader only, target can be offline) + 'team accept' joins;
    'team leave'/'team disband' (leader only) break it apart, always
    starting the 24-hour rejoin cooldown for whoever's membership
    just ended, per confirmed design."""
    player = session.player

    if not args:
        team = teams.get_team(player.team_name)
        if not team:
            session.send("You aren't on a team. Try 'team create <name>' or wait for an invite.")
            return
        lines = [f"&WTeam {team['name']}:&x"]
        for member_name in team["members"]:
            leader_tag = " &Y(Leader)&x" if member_name == team["leader"] else ""
            online_session = next((s for s in session.active_sessions() if s.player and s.player.name == member_name), None)
            status = "&Gonline&x" if online_session else "&Doffline&x"
            lines.append(f"  {member_name}{leader_tag} - {status}")
        session.send("\n".join(lines))
        return

    sub = args[0].lower()

    if sub == "create":
        if len(args) < 2:
            session.send("Usage: team create <name>")
            return
        if player.team_name:
            session.send("You're already on a team -- leave it first.")
            return
        if teams.on_disband_cooldown(player):
            remaining = teams.disband_cooldown_remaining_seconds(player)
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            session.send(f"You must wait {hours}h {minutes}m after leaving a team before joining or creating another.")
            return
        if not teams.can_lead_team(player):
            session.send(f"Only {teams.MIN_LEADER_RANK.title()} rank or higher can lead a team.")
            return
        team_name = " ".join(args[1:])
        error = teams.create_team(player, team_name)
        if error:
            session.send(error)
            return
        session.send(f"You form Team {team_name}, with yourself as leader.")
        return

    if sub == "invite":
        if len(args) < 2:
            session.send("Usage: team invite <player>")
            return
        team = teams.get_team(player.team_name)
        if not team:
            session.send("You aren't on a team.")
            return
        if team["leader"] != player.name:
            session.send("Only the team leader can invite new members.")
            return
        if len(team["members"]) >= teams.MAX_TEAM_SIZE:
            session.send(f"Your team is already full ({teams.MAX_TEAM_SIZE} members max).")
            return

        target_query = args[1].lower()
        target_session = next(
            (s for s in session.active_sessions() if s.player and target_query in s.player.name.lower()),
            None,
        )
        if target_session:
            target_player = target_session.player
        else:
            target_player = storage.load_player(args[1].capitalize())
        if not target_player:
            session.send("There's no player by that name.")
            return
        if target_player.team_name:
            session.send(f"{target_player.name} is already on a team.")
            return

        target_player.pending_team_invite = team["name"]
        storage.save_player(target_player)
        if target_session:
            target_session.send(f"{player.name} invites you to join Team {team['name']}. Type 'team accept' to join.")
        session.send(f"You invite {target_player.name} to join Team {team['name']}.")
        return

    if sub == "accept":
        if not player.pending_team_invite:
            session.send("You don't have a pending team invite.")
            return
        team = teams.get_team(player.pending_team_invite)
        player.pending_team_invite = None
        if not team:
            session.send("That team no longer exists.")
            return
        if player.team_name:
            session.send("You're already on a team -- leave it first.")
            return
        if teams.on_disband_cooldown(player):
            remaining = teams.disband_cooldown_remaining_seconds(player)
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            session.send(f"You must wait {hours}h {minutes}m after leaving a team before joining another.")
            return
        error = teams.join_team(player, team["name"])
        if error:
            session.send(error)
            return
        session.send(f"You join Team {team['name']}.")
        for other_name in team["members"]:
            if other_name == player.name:
                continue
            other_session = next((s for s in session.active_sessions() if s.player and s.player.name == other_name), None)
            if other_session:
                other_session.send(f"{player.name} has joined Team {team['name']}.")
        return

    if sub == "leave":
        if not player.team_name:
            session.send("You aren't on a team.")
            return
        team_name = player.team_name
        teams.leave_team(player)
        session.send(f"You leave Team {team_name}. You must wait 24 hours before joining or creating another team.")
        return

    if sub == "disband":
        team = teams.get_team(player.team_name)
        if not team:
            session.send("You aren't on a team.")
            return
        if team["leader"] != player.name:
            session.send("Only the team leader can disband the team.")
            return
        team_name = team["name"]
        member_names = list(team["members"])
        for member_name in member_names:
            member_session = next((s for s in session.active_sessions() if s.player and s.player.name == member_name), None)
            if member_session and member_session is not session:
                member_session.player.team_name = None
                member_session.player.team_disband_cooldown_until = time.time() + teams.DISBAND_COOLDOWN_SECONDS
                member_session.send(f"&DTeam {team_name} has been disbanded.&x")
            elif not member_session:
                offline_player = storage.load_player(member_name)
                if offline_player:
                    offline_player.team_name = None
                    offline_player.team_disband_cooldown_until = time.time() + teams.DISBAND_COOLDOWN_SECONDS
                    storage.save_player(offline_player)
        player.team_name = None
        player.team_disband_cooldown_until = time.time() + teams.DISBAND_COOLDOWN_SECONDS
        del teams.TEAMS[team_name.lower()]
        teams._save()
        session.send(f"You disband Team {team_name}. Every member must wait 24 hours before joining or creating another team.")
        return

    session.send("Usage: team [create <name>|invite <player>|accept|leave|disband]")


def cmd_trade(session, args: List[str]) -> None:
    """Player-to-player trading (trade.py) -- per direct request
    ("Trade commands"). Confirmed design: an invite/accept flow to
    start (matching 'group invite'/'group accept'), same room
    required for the ENTIRE negotiation (leaving cancels it entirely,
    enforced in cmd_move), full negotiation where each side stages
    their OWN offer (items + an optional ryo amount, never touching
    the other side's offer), and a genuine safety property -- ANY
    change to either side's offer after either side has confirmed
    resets BOTH confirmations, so a trade can never complete on terms
    neither side actually agreed to at the same moment."""
    player = session.player

    if not args:
        active_trade = session.trade
        if not active_trade:
            session.send("You aren't trading with anyone. Try 'trade <player>' to propose one.")
            return
        other = active_trade.other(session)
        my_offer = active_trade.my_offer(session)
        their_offer = active_trade.their_offer(session)
        lines = [f"&WTrading with {other.player.name}:&x"]
        lines.append(f"  Your offer: {', '.join(my_offer['items']) or '(nothing)'}" + (f" + {my_offer['ryo']} ryo" if my_offer["ryo"] else ""))
        lines.append(f"  Their offer: {', '.join(their_offer['items']) or '(nothing)'}" + (f" + {their_offer['ryo']} ryo" if their_offer["ryo"] else ""))
        lines.append(f"  You: {'confirmed' if active_trade.is_confirmed(session) else 'not confirmed'}")
        lines.append(f"  {other.player.name}: {'confirmed' if active_trade.is_confirmed(other) else 'not confirmed'}")
        session.send("\n".join(lines))
        return

    sub = args[0].lower()

    if sub not in ("add", "remove", "ryo", "confirm", "cancel"):
        # 'trade <player>' -- propose or accept, matching group's own invite/accept shape.
        if session.trade and session.trade.accepted:
            session.send("You're already trading with someone. 'trade cancel' first if you want to switch.")
            return
        query = " ".join(args).lower()
        target_session = next(
            (s for s in session.active_sessions() if s is not session and s.player
             and s.player.room_vnum == player.room_vnum and query in s.player.name.lower()),
            None,
        )
        if not target_session:
            session.send("There's nobody here by that name.")
            return
        if session.trade and session.trade.other(session) is target_session and not session.trade.accepted:
            # WE were the one invited -- this is the accept.
            session.trade.accepted = True
            session.send(f"You accept {target_session.player.name}'s trade offer.")
            target_session.send(f"{player.name} accepts your trade offer.")
            return
        if target_session.trade and target_session.trade.accepted:
            session.send(f"{target_session.player.name} is already trading with someone else.")
            return
        import trade as trade_module
        trade_module.start_trade(session, target_session)
        session.send(f"You propose a trade to {target_session.player.name}. They must 'trade {player.name.lower()}' to accept.")
        target_session.send(f"{player.name} wants to trade with you. Type 'trade {player.name.lower()}' to accept, or ignore to decline.")
        return

    active_trade = session.trade
    if not active_trade:
        session.send("You aren't trading with anyone.")
        return
    other = active_trade.other(session)

    if sub != "cancel" and not active_trade.accepted:
        session.send(f"{other.player.name} hasn't accepted your trade proposal yet.")
        return

    if sub == "cancel":
        import trade as trade_module
        trade_module.cancel_trade(active_trade)
        session.send("You cancel the trade.")
        other.send(f"{player.name} cancels the trade.")
        return

    if sub == "add":
        if len(args) < 2:
            session.send("Usage: trade add <item>")
            return
        item_query = " ".join(args[1:]).lower()
        match = next((item for item in player.inventory if item_query in item.lower()), None)
        if not match:
            session.send(f"You aren't carrying anything like '{item_query}'.")
            return
        my_offer = active_trade.my_offer(session)
        if match in my_offer["items"]:
            session.send(f"{match} is already in your offer.")
            return
        my_offer["items"].append(match)
        active_trade.reset_confirmations()
        session.send(f"You add {match} to your offer.")
        other.send(f"{player.name} adds {match} to their offer. Any previous confirmations were reset.")
        return

    if sub == "remove":
        if len(args) < 2:
            session.send("Usage: trade remove <item>")
            return
        item_query = " ".join(args[1:]).lower()
        my_offer = active_trade.my_offer(session)
        match = next((item for item in my_offer["items"] if item_query in item.lower()), None)
        if not match:
            session.send(f"'{item_query}' isn't in your offer.")
            return
        my_offer["items"].remove(match)
        active_trade.reset_confirmations()
        session.send(f"You remove {match} from your offer.")
        other.send(f"{player.name} removes {match} from their offer. Any previous confirmations were reset.")
        return

    if sub == "ryo":
        if len(args) < 2 or not args[1].isdigit():
            session.send("Usage: trade ryo <amount>")
            return
        amount = int(args[1])
        if amount > player.ryo:
            session.send(f"You don't have {amount} ryo.")
            return
        my_offer = active_trade.my_offer(session)
        my_offer["ryo"] = amount
        active_trade.reset_confirmations()
        session.send(f"You set your ryo offer to {amount}.")
        other.send(f"{player.name} sets their ryo offer to {amount}. Any previous confirmations were reset.")
        return

    if sub == "confirm":
        active_trade.set_confirmed(session, True)
        session.send("You confirm the trade.")
        other.send(f"{player.name} confirms the trade.")
        if active_trade.both_confirmed():
            import trade as trade_module
            trade_module.complete_trade(active_trade)
            session.send("&GThe trade is complete!&x")
            other.send("&GThe trade is complete!&x")
        return


def cmd_duel(session, args: List[str]) -> None:
    """Formal 1v1 duels (duel.py + duel_arena.py) -- per direct
    request/design ("What you described but it transfers combatants
    to an 10 room arena with several biomes. When combat ends they
    are returned to the room they came from."). Confirmed design: an
    invite/accept flow (matching group/team/trade's own pattern,
    including the same accepted-flag fix already proven necessary for
    trade -- a pending, not-yet-accepted proposal must be told apart
    from an active one, since both sessions' .duel is set the instant
    a proposal is made). The instant BOTH sides have accepted, both
    combatants are teleported straight into the Arena's two starting
    rooms -- no separate "ready" step. Actually ending the duel
    happens entirely in combat.handle_player_defeat's own new duel
    branch (checked there, not here), since the confirmed design is
    that only a genuine defeat ends a duel."""
    player = session.player

    if not args:
        if session.duel and session.duel.accepted:
            other = session.duel.other(session)
            session.send(f"You are dueling {other.player.name} in the arena.")
        elif session.duel:
            session.send("You have a pending duel proposal.")
        else:
            session.send("You aren't in a duel. Try 'duel <player>' to propose one.")
        return

    if args[0].lower() == "cancel":
        if not session.duel:
            session.send("You aren't in a duel.")
            return
        other = session.duel.other(session)
        if session.duel.accepted:
            import duel as duel_module
            duel_module.end_duel(session.duel, session)
        else:
            import duel as duel_module
            duel_module.cancel_duel(session.duel)
            session.send("You cancel the duel proposal.")
            other.send(f"{player.name} cancels the duel proposal.")
        return

    if session.duel and session.duel.accepted:
        session.send("You're already dueling someone.")
        return
    query = " ".join(args).lower()
    target_session = next(
        (s for s in session.active_sessions() if s is not session and s.player
         and s.player.room_vnum == player.room_vnum and query in s.player.name.lower()),
        None,
    )
    if not target_session:
        session.send("There's nobody here by that name.")
        return

    if session.duel and session.duel.other(session) is target_session and not session.duel.accepted:
        # WE were the one invited -- this is the accept.
        import duel as duel_module
        session.duel.accepted = True
        duel_module.begin_duel(session.duel)
        session.send(f"You accept {target_session.player.name}'s duel! You're pulled into the arena.")
        target_session.send(f"{player.name} accepts your duel! You're both pulled into the arena.")
        return

    if target_session.duel and target_session.duel.accepted:
        session.send(f"{target_session.player.name} is already dueling someone else.")
        return
    import duel as duel_module
    duel_module.start_duel(session, target_session)
    session.send(f"You challenge {target_session.player.name} to a duel. They must 'duel {player.name.lower()}' to accept.")
    target_session.send(f"{player.name} challenges you to a duel! Type 'duel {player.name.lower()}' to accept, or ignore to decline.")


def cmd_chunin_exam(session, args: List[str]) -> None:
    """Enters (or re-enters) the Chunin Exam -- see chunin_exam.py's
    own docstring for the full design. Grants one random scroll type
    on first entry only; re-entering after leaving (e.g. via a
    hospital respawn from a PvP loss) does NOT re-roll or top up a
    scroll already lost, since that would undermine the entire point
    of the theft mechanic -- the exam is meant to be survived, not
    retried for free."""
    player = session.player
    if player.village_rank != "genin":
        session.send("The Chunin Exam is only open to Genin.")
        return
    if not chunin_exam.qualifies_for_exam(player):
        session.send(
            f"You aren't ready yet. The Chunin Exam requires at least level "
            f"{chunin_exam.MIN_LEVEL} and {chunin_exam.MIN_COMPLETED_MISSIONS} completed mission(s)."
        )
        return

    if player.in_chunin_exam:
        session.send("You're already in the middle of the exam -- head deeper into the forest.")
        player.room_vnum = chunin_exam.ENTRANCE_VNUM
        return

    player.in_chunin_exam = True
    starting_scroll = random.choice(chunin_exam.SCROLLS)
    player.inventory.append(starting_scroll)
    player.room_vnum = chunin_exam.ENTRANCE_VNUM
    session.send(
        f"&YYou pass through the gate into the Forest of Death.&x\n"
        f"You've been given {rarity_colored_name(starting_scroll)} -- you'll need to find "
        f"{'an Earth Scroll' if starting_scroll == chunin_exam.HEAVEN_SCROLL else 'a Heaven Scroll'} "
        f"to pass. Defeat one of the scroll guardians deeper in the forest, or another exam "
        f"candidate carrying one, then reach the tower."
    )


def cmd_leave_exam(session, args: List[str]) -> None:
    """Voluntarily exits the Forest of Death back to the player's
    village, without finishing or forfeiting the exam -- per polish
    pass, since previously the only ways out were completing it or
    dying (and 'recall' only works for apartment owners, which most
    players taking this exam won't have yet). Keeps scrolls and
    in_chunin_exam intact, so 'exam' picks back up exactly where they
    left off rather than re-rolling anything -- this is a breather,
    not a forfeit."""
    player = session.player
    if not player.in_chunin_exam:
        session.send("You aren't currently taking the Chunin Exam.")
        return
    player.room_vnum = VILLAGES[player.village]["starting_room_vnum"]
    session.send(
        "&YYou slip out of the Forest of Death and head back to the village. "
        "Your exam progress is safe -- 'exam' will take you right back in when you're ready.&x"
    )


def cmd_submit_scrolls(session, args: List[str]) -> None:
    """Completes the Chunin Exam, if the player is standing in the
    tower with both scrolls. Consumes both scrolls and promotes
    directly -- reuses the same headband-swap helper a Kage promotion
    uses, so this is a real promotion in every respect, not a
    separate, parallel one."""
    player = session.player
    if player.room_vnum != chunin_exam.TOWER_VNUM:
        session.send("You need to be at the tower to submit your scrolls.")
        return
    if not player.in_chunin_exam:
        session.send("You aren't currently taking the Chunin Exam.")
        return
    if not chunin_exam.has_both_scrolls(player):
        missing = chunin_exam.missing_scroll(player)
        session.send(f"You still need {rarity_colored_name(missing)} to pass.")
        return

    for scroll in chunin_exam.SCROLLS:
        match = next(item for item in player.inventory if item.lower() == scroll.lower())
        player.inventory.remove(match)

    player.village_rank = "chunin"
    player.in_chunin_exam = False
    data_headbands.apply_rank_headband(player, "chunin")
    player.room_vnum = VILLAGES[player.village]["starting_room_vnum"]
    kage.announce_rank_up(player.name, "chunin")
    session.send(
        "&GYou present both scrolls to the proctor. Well done -- you are promoted to Chunin!&x"
    )


def cmd_missions(session, args: List[str]) -> None:
    player = session.player
    village_rooms = content._VILLAGE_ROOMS.get(player.village)
    if village_rooms and player.room_vnum == village_rooms["board"]:
        all_missions = missions.missions_for_village(player.village)
        first_words = [m["title"].split()[0].lower() for m in all_missions]
        lines = ["&WMissions posted here:&x"]
        for m in all_missions:
            already_active = any(am["mission_id"] == m["mission_id"] for am in player.active_missions)
            remaining = missions.cooldown_remaining(player, m["mission_id"])
            if already_active:
                status = "already accepted -- check 'missions' for journal progress"
            elif remaining > 0:
                status = f"on cooldown, ready in {missions._format_duration(remaining)}"
            else:
                first_word = m["title"].split()[0].lower()
                if first_words.count(first_word) > 1:
                    # Ambiguous with another mission here (e.g. several
                    # "Hunt the X" missions) -- suggest the rank instead,
                    # which is always unique per village.
                    status = f"type 'accept {m['rank'].lower()}' to take it"
                else:
                    status = f"type 'accept {first_word}' to take it"
            lines.append(f"  &Y{m['title']}&x ({m['rank']}): {m['description']}\n    ({status})")
        lines.append("\n&D(Looking for something tougher? C-Rank and up aren't posted here -- see 'help request'.)&x")
        session.send("\n".join(lines))
        return

    session.send(missions.journal_text(player))


def cmd_accept(session, args: List[str]) -> None:
    player = session.player
    village_rooms = content._VILLAGE_ROOMS.get(player.village)
    if not village_rooms or player.room_vnum != village_rooms["board"]:
        session.send("There is nothing to accept here.")
        return
    available = missions.missions_for_village(player.village)
    if not args:
        if len(available) == 1:
            session.send(missions.accept_mission(player, player.village, available[0]["mission_id"]))
            return
        session.send(
            "Accept which mission? " + ", ".join(m["title"] for m in available)
        )
        return
    query = " ".join(args).lower()
    matched = next(
        (m for m in available if query in m["title"].lower() or query in m["rank"].lower()),
        None,
    )
    if not matched:
        session.send(f"No mission here matches '{' '.join(args)}'.")
        return
    session.send(missions.accept_mission(player, player.village, matched["mission_id"]))


def cmd_request(session, args: List[str]) -> None:
    """'request <rank>' -- requests a dynamic C/B/A/S mission, per
    direct request ("instead of a static board you request what
    mission difficulty you want and it will select from a pool of
    mobs within your level range dependent on what you picked").
    Deliberately works from anywhere, not gated to standing at a
    village mission board -- unlike D-Rank (still 'accept' at the
    board, unchanged), the whole point of this system is moving away
    from that board-bound model. See missions.request_mission for the
    actual selection/gating logic."""
    if not args:
        session.send("Request which rank? Usage: request <c-rank|b-rank|a-rank|s-rank>")
        return
    rank = " ".join(args)
    session.send(missions.request_mission(session.player, rank))



# --- Training / practice --------------------------------------------

def cmd_train(session, args: List[str]) -> None:
    player = session.player
    typed = args[0].lower() if len(args) == 1 else ""
    attr = TRAIN_ATTRIBUTE_NAMES.get(typed, typed)
    if attr not in TRAINABLE_ATTRIBUTES:
        session.send("Usage: train <attribute> (str, wis, con, int, dex, luk, per, wil, cc)")
        return
    if player.training_points <= 0:
        session.send("You have no training points left.")
        return
    current = getattr(player, attr)
    if current >= config.MAX_ATTRIBUTE_VALUE:
        session.send(f"Your {attr.replace('_', ' ')} is already at its maximum ({config.MAX_ATTRIBUTE_VALUE}).")
        return
    setattr(player, attr, current + 1)
    player.training_points -= 1
    session.send(f"You train your {attr.replace('_', ' ')}. It is now {getattr(player, attr)}.")
    if attr == "chakra_control":
        # Per direct request/confirmation (Section 131): a real, immediate
        # +10 max Chakra the instant Chakra Control is trained -- NOT tied
        # to leveling up at all, genuinely distinct from the per-level
        # Int/Wis Chakra formula (Section 130). Fires once per point
        # trained above the baseline of 10 (checked via `current` here,
        # since that's the value BEFORE this train just added +1).
        player.maximum_chakra += 10
        session.send(f"&CYour finer control over your own chakra permanently expands your reserves by 10 -- max Chakra is now {player.maximum_chakra}.&x")


PRACTICE_POINTS_PER_TRAINING_POINT = 5  # confirmed directly: "turn in 5 practice points for 1 training point"


def cmd_convert_practice(session, args: List[str]) -> None:
    """'convert practice' -- per direct request/confirmation (Section
    132): turns 5 unused practice points into 1 training point,
    letting a player accelerate stat training with practice points
    they aren't otherwise using. Confirmed directly: only usable
    while standing near a real teacher mob (any teacher counts, since
    this isn't tied to a specific skill's own class category, matching
    how a General Skills entry already works for anyone), and
    repeatable as many times as the player has spare practice points."""
    player = session.player
    if not any(combat.is_teacher(mob) for mob in combat.mobs_in_room(player.room_vnum)):
        session.send("You need to find a teacher to convert practice points into training.")
        return
    if player.practice_points < PRACTICE_POINTS_PER_TRAINING_POINT:
        session.send(f"You need at least {PRACTICE_POINTS_PER_TRAINING_POINT} practice points to convert (you have {player.practice_points}).")
        return
    player.practice_points -= PRACTICE_POINTS_PER_TRAINING_POINT
    player.training_points += 1
    session.send(
        f"&WThe teacher exchanges {PRACTICE_POINTS_PER_TRAINING_POINT} of your practice points for 1 training point. "
        f"You now have {player.practice_points} practice point(s) and {player.training_points} training point(s).&x"
    )


def _practice_gain(player) -> int:
    """Percentage points gained per practice attempt, scaled by
    Intelligence -- higher Int means faster proficiency growth.
    Floor of 1 so practicing is never a no-op even at very low Int."""
    return max(1, player.intelligence // 2)


def proficiency_level_name(pct: int) -> str:
    """Maps a raw percentage back to the familiar tier name for flavor
    text (score sheet, skills list) without that name being the actual
    stored value anymore."""
    if pct >= 100:
        return "mastered"
    if pct >= 80:
        return "expert"
    if pct >= 60:
        return "skilled"
    if pct >= 40:
        return "familiar"
    if pct >= 20:
        return "novice"
    return "untrained"


def proficiency_color(pct: int) -> str:
    """A genuine continuous 256-color gradient for a skill proficiency
    percentage, per direct request ("create a better prac list with
    color based on skill% used the 256 color scale not just basics").
    Smoothly interpolates through the real xterm 256-color RGB cube
    (index = 16 + 36r + 6g + b, r/g/b in 0-5) from red at 0% through
    orange and yellow to green at 100%, rather than a small, fixed set
    of threshold buckets like resource_color/proficiency_level_name
    use -- every distinct percentage from 0 to 100 gets its own
    genuinely distinct shade along the ramp, not just 6 flat blocks.

    The ramp itself: red (5,0,0) -> orange (5,2,0) -> yellow (5,5,0)
    -> green (0,5,0), moving through 3 linear segments so the color
    genuinely reads as "red early, yellow in the middle, green late"
    rather than a flat rainbow smear."""
    pct = max(0, min(100, pct))
    if pct <= 33:
        # Red -> orange: green channel ramps 0 -> 2
        r, g, b = 5, round(pct / 33 * 2), 0
    elif pct <= 66:
        # Orange -> yellow: green channel ramps 2 -> 5
        r, g, b = 5, 2 + round((pct - 33) / 33 * 3), 0
    else:
        # Yellow -> green: red channel ramps 5 -> 0
        r, g, b = 5 - round((pct - 66) / 34 * 5), 5, 0
    xterm = 16 + 36 * r + 6 * g + b
    return f"&[{xterm}]"


def _is_weapon_skill_name(skill_name: str) -> bool:
    """Whether skill_name is one of the weapon proficiencies
    (data_weapons.WEAPON_TYPES' own "skill" display names -- Kunai,
    Sword, Shuriken, Blunt Weapon, Polearm, Exotic Weapon), as
    opposed to a jutsu. Needed because "usage" means something
    genuinely different for each once past the practice cap --
    confirmed design: any attack made while a weapon type is
    equipped counts for its own skill, while a jutsu specifically
    needs to land a real hit."""
    return skill_name in {info["skill"] for info in data_weapons.WEAPON_TYPES.values()}


def cmd_practice(session, args: List[str]) -> None:
    player = session.player
    if not args:
        session.send("Practice what?")
        return
    query = " ".join(args).lower()
    match = next((s for s in player.learned_skills if query in s.lower()), None)
    if not match:
        session.send("You haven't learned that skill or jutsu.")
        return
    if data_passives.is_passive(match):
        session.send(f"{match} is a passive skill -- it improves automatically through combat experience, not practice.")
        return
    teacher = _find_matching_teacher(player.room_vnum, match)
    if not teacher:
        category = _category_for_skill(match)
        if category == "General Skills":
            session.send(f"You need to find a teacher to practice {match}.")
        else:
            session.send(f"You need to find a {category} teacher to practice {match}.")
        return
    if player.practice_points <= 0:
        session.send("You have no practice points left.")
        return
    current = player.skill_proficiencies.get(match, 0)
    practice_cap = data_jutsu.PRACTICE_CAP_PERCENT.get(match, data_jutsu.DEFAULT_PRACTICE_CAP_PERCENT)
    if current >= practice_cap:
        if practice_cap < 100:
            if match == "Handsigns":
                usage_hint = "actually performing hand signs to cast a jutsu"
            elif _is_weapon_skill_name(match):
                usage_hint = "actually attacking with it equipped, in combat"
            else:
                usage_hint = "actually landing a hit with it in combat"
            session.send(f"{match} can only be practiced up to {practice_cap}% -- {usage_hint} is the only way to raise it further.")
        else:
            session.send(f"{match} is already mastered.")
        return
    gain = _practice_gain(player)
    new_pct = min(practice_cap, current + gain)
    player.skill_proficiencies[match] = new_pct
    player.practice_points -= 1
    player.practice_sessions_used += 1
    session.send(
        f"You practice {match} (+{new_pct - current}% from your Intelligence). "
        f"Proficiency is now {new_pct}% ({proficiency_level_name(new_pct)})."
    )


def _skill_unlock_level(skill_name: str) -> Optional[int]:
    """The level a given entry in player.learned_skills was actually
    obtained at, per direct request ("make skills list the level that
    that jutsu is obtained before the name"). Checked across every
    real source of a level-gated skill, in order: an actual jutsu
    (data_jutsu.JUTSU, keyed by the lowercased display name), a
    weapon multi-attack skill (data_jutsu.MULTI_ATTACK_SKILLS, e.g.
    "Third Attack"), Handsigns and Examine (their own dedicated
    level constants), a weapon skill (data_weapons.WEAPON_TYPES, e.g.
    "Kunai", "Sword" -- genuinely obtainable at ANY character level
    by wielding a matching weapon, not level-gated at all, so shown
    as level 1 as a consistent, honest standard rather than left
    blank), and finally a universal starting skill
    (data_jutsu.UNIVERSAL_STARTING_SKILLS) -- granted at character
    creation with no real level gate beyond that, so shown as level 1
    for a consistent, honest display rather than left blank. Returns
    None only for something with no real "unlock level" concept at
    all (there currently isn't one, but this stays defensive)."""
    jutsu = data_jutsu.JUTSU.get(skill_name.lower().replace(":", ""))
    if jutsu:
        return jutsu["level_requirement"]
    for name, level_req, _required_class in data_jutsu.MULTI_ATTACK_SKILLS:
        if name == skill_name:
            return level_req
    import data_handsigns
    if skill_name == "Handsigns":
        return data_handsigns.HANDSIGNS_MIN_LEVEL
    if skill_name == "Examine":
        return data_jutsu.APPRAISAL_LEVEL_REQUIREMENT
    import data_weapons
    if skill_name in {info["skill"] for info in data_weapons.WEAPON_TYPES.values()}:
        return 1
    if skill_name in data_jutsu.UNIVERSAL_STARTING_SKILLS:
        return 1
    return None


def cmd_skills(session, args: List[str]) -> None:
    player = session.player
    lines = ["Skills and jutsu:"]
    ordered_skills = sorted(
        player.learned_skills,
        key=lambda name: (_skill_unlock_level(name) is None, _skill_unlock_level(name) or 0),
    )
    for skill in ordered_skills:
        if skill.lower() == "sharingan genjutsu":
            continue  # old saved characters may still contain the retired skill
        level = _skill_unlock_level(skill)
        prefix = f"[Level {level}] " if level is not None else ""
        color = PRAC_CATEGORY_COLOR[_category_for_skill(skill)]
        lines.append(f"  {prefix}{color}{skill}&x")
    session.send("\n".join(lines))


def cmd_examine(session, args: List[str]) -> None:
    """Examines an item (in inventory or equipped) and reveals its
    stats -- gated first by character LEVEL (Examine isn't granted at
    creation; it unlocks automatically at data_jutsu.APPRAISAL_LEVEL_REQUIREMENT,
    see leveling.py), then by proficiency in that skill once unlocked
    (trainable via 'practice examine' like any other skill),
    revealing progressively more detail at higher proficiency rather
    than dumping everything at once. Untrained/novice: just the name
    and rarity. Familiar/skilled: adds item type, weapon type, cost,
    and weight. Expert/mastered: adds full armor-set requirements and
    bonus, and a clear breakdown of any crafted stat bonus (which is
    also visible in the item's own name text, but spelled out
    explicitly here)."""
    player = session.player
    if not args:
        session.send("Examine what?")
        return

    query = " ".join(args).lower()
    candidates = list(player.inventory) + list(player.equipment.values())
    match = find_indexed_item(query, candidates)
    if not match:
        session.send(f"You aren't carrying or wearing anything like '{query}'.")
        return

    if "Examine" not in player.learned_skills:
        session.send(
            f"You don't know how to examine items that closely yet -- "
            f"Examine unlocks at level {data_jutsu.APPRAISAL_LEVEL_REQUIREMENT}."
        )
        return

    appraisal_pct = player.skill_proficiencies.get("Examine", 0)
    proto = _find_object_prototype_by_name(match)
    rarity = proto.get("rarity", "common") if proto else "common"

    lines = [f"You examine {_examine_rarity_colored_name(match)}."]
    lines.append(f"&WRarity:&x {data_rarity.display_name(rarity)}")

    if appraisal_pct < 40:
        lines.append("&D(Train Examine further to learn more about this item.)&x")
        session.send("\n".join(lines))
        return

    if proto:
        lines.append(f"&WItem Type:&x {proto.get('item_type', 'misc').capitalize()}")
        wear_loc = proto.get("wear_loc")
        if wear_loc:
            lines.append(f"&WWear Location:&x {wear_loc.replace('_', ' ').title()}")

    stat_lines = []
    if proto and proto.get("stat_bonuses"):
        for key, value in proto["stat_bonuses"].items():
            stat_lines.append(f"  {key.replace('_', ' ').title()}: {value:+d}")
    crafted_bonus = parse_crafted_hitroll_bonus(match)
    if crafted_bonus and not (proto and proto.get("stat_bonuses", {}).get("hitroll")):
        stat_lines.append(f"  Hitroll: +{crafted_bonus}")
    if stat_lines:
        lines.append("&WStat Bonuses:&x")
        lines.extend(stat_lines)

    if proto:
        if proto.get("weapon_type"):
            lines.append(f"&WWeapon Type:&x {data_weapons.display_name(proto['weapon_type'])}")
        if proto.get("gem_bonuses"):
            bonuses = proto["gem_bonuses"]
            lines.append(f"&WFuture Weapon Gem Bonus:&x Hitroll +{bonuses.get('hitroll', 0)}, Damageroll +{bonuses.get('damroll', 0)}")
        lines.append(f"&WCost:&x {proto.get('cost', 0):,} ryo   &WWeight:&x {proto.get('weight', 1)}")

    if appraisal_pct < 80:
        lines.append("&D(Train Examine further to see full set details.)&x")
        session.send("\n".join(lines))
        return

    if proto and proto.get("set_vnums"):
        required = ", ".join(str(v) for v in proto["set_vnums"])
        lines.append(
            f"&WSet Bonus:&x requires vnums {required} also worn -- "
            f"+{proto.get('set_bonus_percent', 25)}% to combat stats when complete"
        )
    elif proto:
        lines.append("&WSet Bonus:&x not part of a set")

    session.send("\n".join(lines))


# --- prac: categorized skill list (Sections 8-9, 12) --------------------

PRAC_CATEGORY_ORDER = ["Ninjutsu", "Taijutsu", "Genjutsu", "Bukijutsu", "General Skills"]


def _categorize_skill(skill_name: str) -> str:
    lname = skill_name.lower()
    for jutsu in data_jutsu.JUTSU.values():
        if jutsu["display_name"].lower() == lname:
            return jutsu["class_requirement"].capitalize()
    if lname == "punch":
        return "Taijutsu"
    return "General Skills"


def _skill_catalog_for_category(category: str) -> list:
    """Every skill that belongs to `category`, regardless of whether
    the player has learned it yet -- (name, level_requirement) pairs.
    The single source of truth cmd_prac uses to show the FULL catalog,
    not just what a player already knows."""
    entries = []
    if category in ("Ninjutsu", "Taijutsu", "Genjutsu", "Bukijutsu"):
        class_key = category.lower()
        for jutsu in data_jutsu.JUTSU.values():
            if jutsu["class_requirement"] == class_key:
                entries.append((jutsu["display_name"], jutsu["level_requirement"]))
    elif category == "General Skills":
        # Weapon skills folded in here per explicit request (previously
        # their own "Weapon Skills" category). Not level-gated --
        # learned by wielding a matching weapon type, so there's no
        # meaningful "unlocks at level N" for these.
        for weapon_info in data_weapons.WEAPON_TYPES.values():
            entries.append((weapon_info["skill"], None))
        entries.append(("Strong Fist Style", 1))
        entries.append(("Examine", data_jutsu.APPRAISAL_LEVEL_REQUIREMENT))
        import data_handsigns
        entries.append(("Handsigns", data_handsigns.HANDSIGNS_MIN_LEVEL))
        entries.append(("Anki", 1))  # confirmed directly: no real level requirement at all, shown as level 1 like every other level-1-effectively skill (matches how UNIVERSAL_STARTING_SKILLS is handled elsewhere)
        # Second/Third/Fourth/Fifth Attack (data_jutsu.MULTI_ATTACK_SKILLS)
        # -- genuinely granted and practicable, but previously missing
        # from this catalog entirely, so a player who'd learned one
        # would never see it in 'prac' despite it being real. This
        # function has no access to the viewing player (by design --
        # it's the full, static catalog), so all 4 are always listed
        # here; class-correctness is already handled the same way it
        # is for the 4 jutsu categories above -- cmd_prac only ever
        # displays an entry that's also in the viewer's own
        # learned_skills, and leveling.py already only ever grants
        # Fourth/Fifth Attack to Bukijutsu characters.
        for skill_name, level_req, required_class in data_jutsu.MULTI_ATTACK_SKILLS:
            entries.append((skill_name, level_req))
        # Every real class-agnostic jutsu (class_requirement="general",
        # e.g. Track, Sealing Jutsu, Release Jutsu, Tailed Beast Bomb --
        # any class can learn these) genuinely belongs here too. Caught
        # by direct user report: "many jutsu dont show on prac list
        # every single jutsu learned by a player should be there" --
        # these 4 were never added when they were originally built,
        # so a player who'd learned any of them never saw it on 'prac'
        # at all, despite it being real.
        for jutsu in data_jutsu.JUTSU.values():
            if jutsu["class_requirement"] == "general":
                entries.append((jutsu["display_name"], jutsu["level_requirement"]))
    return entries


def _category_for_skill(skill_name: str) -> str:
    """The PRAC_CATEGORY_ORDER category a given skill belongs to, per
    direct request ("make the skills command colored based on
    class... so genjutsu skills will be a color and so on"). Built
    directly on _skill_catalog_for_category, the existing single
    source of truth cmd_prac already uses for this exact
    classification, rather than duplicating its logic. Defaults to
    "General Skills" for anything not found in any of the 4 class
    catalogs (matches how General Skills already behaves as the
    catch-all category in cmd_prac)."""
    for category in PRAC_CATEGORY_ORDER:
        for name, _level_req in _skill_catalog_for_category(category):
            if name == skill_name:
                return category
    return "General Skills"


PRAC_CATEGORY_COLOR = {
    "Ninjutsu": "&B",
    "Taijutsu": "&R",
    "Genjutsu": "&M",
    "Bukijutsu": "&Y",
    "General Skills": "&C",  # confirmed: a distinct color from the 4 class colors, changed from gray per direct request
}


def _prac_header(category: str, width: int = 74) -> str:
    label = f"[ {category} ]"
    pad = max(0, width - len(label))
    left = pad // 2
    right = pad - left
    color = PRAC_CATEGORY_COLOR.get(category, "&W")
    return f"&D{'-' * left}&x{color}{label}&x&D{'-' * right}&x"


def _prac_entry(name: str, pct: int, width: int = 45) -> str:
    """A single colored skill entry, name and percentage colored by
    proficiency_color's own 256-color gradient. Padded to `width`
    against the VISIBLE text (computed before color codes are added)
    so the existing 2-column layout still lines up -- color codes are
    invisible characters that would otherwise throw off a plain
    len()-based right-justify."""
    visible = f"{name}  {pct}%"
    pad = max(0, width - len(visible))
    color = proficiency_color(pct)
    return " " * pad + f"{color}{name}  {pct}%&x"


def cmd_prac(session, args: List[str]) -> None:
    if args:
        cmd_practice(session, args)
        return

    player = session.player
    lines = []
    for category in PRAC_CATEGORY_ORDER:
        lines.append(_prac_header(category))
        catalog = _skill_catalog_for_category(category)
        entries = []
        for name, level_req in catalog:
            if name in player.learned_skills:
                pct = player.skill_proficiencies.get(name, 0)
                entries.append(_prac_entry(name, pct))
        for i in range(0, len(entries), 2):
            pair = entries[i:i + 2]
            row = pair[0] + "  "
            if len(pair) == 2:
                row += pair[1]
            lines.append(row)

    lines.append(f"You have {player.practice_points} practice session(s) remaining.")
    session.send("\n".join(lines))


def cmd_clan(session, args: List[str]) -> None:
    player = session.player
    if not args:
        current = data_clans.display_name(player.clan)
        session.send(
            f"Your clan: {current}\n"
            "Usage: clan join <name>  (cosmetic only for now -- no bonuses attached)\n"
            f"Clans of your village:\n" + data_clans.clan_names_display(player.village)
        )
        return
    if args[0].lower() != "join" or len(args) < 2:
        session.send("Usage: clan join <name>")
        return
    key = " ".join(args[1:]).lower()
    village_clans = data_clans.clans_for_village(player.village)
    if key not in village_clans:
        session.send(
            f"'{' '.join(args[1:])}' is not a clan of your village. Available:\n"
            + data_clans.clan_names_display(player.village)
        )
        return
    player.clan = key
    session.send(f"You are now affiliated with the {data_clans.display_name(key)} clan.")


# --- Shops ----------------------------------------------------------------

def _own_kage_chamber(player) -> bool:
    village_rooms = content._VILLAGE_ROOMS.get(player.village)
    return bool(village_rooms) and player.room_vnum == village_rooms["kage"]


def _find_shopkeeper(room_vnum: int):
    for mob in combat.mobs_in_room(room_vnum):
        if combat.is_shopkeeper(mob):
            return mob
    return None


def _find_gambler(room_vnum: int):
    for mob in combat.mobs_in_room(room_vnum):
        if combat.is_gambler(mob):
            return mob
    return None


def _find_matching_teacher(room_vnum: int, skill_name: str):
    """The first teacher-flagged mob in the room genuinely able to
    teach `skill_name`, or None if no such teacher is present. Per
    direct confirmation: a teacher can only teach skills matching
    their own class (Ninjutsu/Taijutsu/Genjutsu/Bukijutsu); any
    teacher works for a "General Skills" entry, since those aren't
    tied to a class at all."""
    category = _category_for_skill(skill_name)
    for mob in combat.mobs_in_room(room_vnum):
        if not combat.is_teacher(mob):
            continue
        if category == "General Skills" or combat.teacher_class(mob) == category.lower():
            return mob
    return None


def cmd_list(session, args: List[str]) -> None:
    player = session.player
    if _own_kage_chamber(player):
        lines = [f"&W{kage.kage_title(player.village)} offers these village-wide perks:&x"]
        for key, info in village_perks.PERK_TYPES.items():
            lines.append(f"  {info['display_name']} ({key}) - {info['cost']} mission point(s)")
        lines.append("&D(Perks are global -- they apply to every player of your village, not just you.)&x")
        active = village_perks.active_perks_display(player.village)
        if active:
            lines.append("&GCurrently active:&x " + "; ".join(active))
        lines.append("")
        lines.append(f"&W{kage.kage_title(player.village)} also offers these legendary items:&x")
        owned_names = {item.lower() for item in list(player.inventory) + [slot for slot in player.equipment.values() if slot]}
        for key, data in legendary_items.LEGENDARY_ITEMS.items():
            proto = olc.OBJECT_TEMPLATES.get(data["vnum"])
            item_name = proto["short_desc"] if proto else data["short_desc"]
            already_owned = item_name.lower() in owned_names
            status = "&D(already owned)&x" if already_owned else f"{data['cost_mission_points']:,} mission point(s)"
            level_text = f" (level {proto['level']})" if proto and proto.get("level", 0) > 0 else ""
            lines.append(f"  {rarity_colored_name(item_name)} - {status}{level_text}")
        lines.append("&D('examine' one to see its full stats.)&x")
        session.send("\n".join(lines))
        return

    shopkeeper = _find_shopkeeper(player.room_vnum)
    if shopkeeper and shopkeeper.player_shop_owner:
        lines = [f"&W{shopkeeper.name.capitalize()} offers for sale:&x"]
        stock = playershops.stock_for_display(shopkeeper)
        priced_any = False
        for entry in stock:
            if entry["price"] is None:
                continue
            priced_any = True
            proto = playershops.stock_prototype(entry)
            level_text = f" (level {proto['level']})" if proto and proto.get("level", 0) > 0 else ""
            lines.append(f"  {rarity_colored_name(entry['item_name'])} - {entry['price']:,} ryo{level_text}")
        if not priced_any:
            lines.append("  (nothing in stock right now)")
        session.send("\n".join(lines))
        return

    if shopkeeper:
        shop_items = combat.mob_shop_items(shopkeeper)
        buys_categories = combat.mob_shop_buys_categories(shopkeeper)
        lines = [f"&W{shopkeeper.name.capitalize()} offers for sale:&x"]
        for obj_vnum in shop_items:
            obj = olc.OBJECT_TEMPLATES.get(obj_vnum)
            if obj:
                level_text = f" (level {obj['level']})" if obj.get("level", 0) > 0 else ""
                lines.append(f"  {rarity_colored_name(obj['short_desc'])} - {obj['cost']} ryo{level_text}")
        if not shop_items:
            lines.append("  (nothing in stock right now)")
        if buys_categories:
            lines.append(f"&D(Only buys {', '.join(buys_categories)} items.)&x")
        else:
            lines.append("&D(Buys any item, but at a lower price than a specialty shop.)&x")
        session.send("\n".join(lines))
        return

    shop = content.SHOPS.get(player.room_vnum)
    if not shop:
        session.send("There is nothing to list here.")
        return
    shop_info = data_shops.SHOP_TYPES[shop["type"]]
    lines = [f"&W{shop_info['display_name']} -- for sale:&x"]
    for item in shop["items"]:
        proto = _find_object_prototype_by_name(item["name"])
        level_text = f" (level {proto['level']})" if proto and proto.get("level", 0) > 0 else ""
        lines.append(f"  {rarity_colored_name(item['name'])} - {item['price']} ryo{level_text}")
    if shop["type"] == "general":
        lines.append("&D(Buys any item, but at a lower price than a specialty shop.)&x")
    else:
        categories = ", ".join(sorted(data_shops.SHOP_TYPES[shop["type"]]["allowed_sell_categories"]))
        lines.append(f"&D(Only buys {categories} items.)&x")
    session.send("\n".join(lines))


def cmd_buy(session, args: List[str]) -> None:
    player = session.player

    if args and "apartment" in " ".join(args).lower():
        current_room = WORLD.get(player.room_vnum)
        if not current_room or not current_room.apartment:
            session.send("You can only buy an apartment while standing inside one that's available.")
            return
        if current_room.owner is not None:
            session.send("This apartment is already owned. Look for a vacant one.")
            return
        if player.apartment_room_vnum is not None:
            session.send("You already own an apartment. Only one per player.")
            return
        if player.ryo < config.APARTMENT_COST_RYO:
            session.send(f"An apartment costs {config.APARTMENT_COST_RYO:,} ryo -- you have {player.ryo:,}.")
            return
        player.ryo -= config.APARTMENT_COST_RYO
        current_room.owner = player.name
        player.apartment_room_vnum = current_room.vnum
        session.send(
            f"You pay {config.APARTMENT_COST_RYO:,} ryo and receive the deed to {current_room.name}. "
            f"It's yours -- type 'recall' anytime to return home."
        )
        return

    if args and args[0].lower() == "room":
        if player.apartment_room_vnum is None:
            session.send("You need to own an apartment first -- try 'buy apartment'.")
            return
        if not apartments.owns_room_at(player, player.room_vnum):
            session.send("You have to be standing inside your own apartment (or one of its rooms) to buy a new room.")
            return
        current_room = WORLD.get(player.room_vnum)
        if not current_room or current_room.owner != player.name:
            session.send("Something's wrong with your apartment's deed -- contact a builder.")
            return
        if len(args) != 3:
            session.send(
                f"Usage: buy room <type> <direction>\n"
                f"Types: {', '.join(apartments.APARTMENT_ROOM_TYPES)}"
            )
            return
        room_type = args[1].lower()
        direction = world.normalize_direction(args[2])
        if room_type not in apartments.APARTMENT_ROOM_TYPES:
            session.send(f"'{args[1]}' isn't a room type. Choose one of: {', '.join(apartments.APARTMENT_ROOM_TYPES)}")
            return
        if not direction:
            session.send(f"'{args[2]}' isn't a direction.")
            return
        if room_type in player.apartment_expansions:
            session.send(f"You already have a {room_type} -- only one of each type.")
            return
        if direction in current_room.exits:
            session.send(f"There's already an exit to the {direction} from here.")
            return
        cost = apartments.expansion_cost(len(player.apartment_expansions))
        if player.ryo < cost:
            session.send(f"A {room_type} costs {cost:,} ryo -- you have {player.ryo:,}.")
            return

        player.ryo -= cost
        new_vnum = apartments.expansion_room_vnum(player.apartment_room_vnum, room_type)
        new_room = world.Room(
            new_vnum, f"{player.name}'s {room_type.capitalize()}",
            apartments.ROOM_TYPE_DESCRIPTIONS[room_type],
        )
        new_room.apartment = True
        new_room.owner = player.name
        new_room.safe = True
        WORLD.add_room(new_room)
        apartments.setup_expansion_room(new_room, room_type)
        WORLD.link(current_room.vnum, direction, new_vnum)
        if room_type == "storage":
            new_room.ground_items = player.storage_room_items
        player.apartment_expansions[room_type] = {
            "direction": direction, "cost": cost, "parent_vnum": current_room.vnum,
        }
        session.send(
            f"You pay {cost:,} ryo and build a {room_type} to the {direction}. "
            f"{apartments.ROOM_TYPE_DESCRIPTIONS[room_type]}"
        )
        return

    if args and args[0].lower() == "shop":
        current_room = WORLD.get(player.room_vnum)
        if not current_room or not current_room.player_shop:
            session.send("You can only buy a shop while standing inside a vacant one along Main Street.")
            return
        if current_room.owner is not None:
            session.send("This shop is already claimed. Look for a vacant one.")
            return
        if player.shop_room_vnum is not None:
            session.send("You already own a shop. Only one per player.")
            return
        if player.ryo < config.PLAYER_SHOP_COST_RYO:
            session.send(f"A shop costs {config.PLAYER_SHOP_COST_RYO:,} ryo -- you have {player.ryo:,}.")
            return

        player.ryo -= config.PLAYER_SHOP_COST_RYO
        current_room.owner = player.name
        player.shop_room_vnum = current_room.vnum
        shopkeeper = combat.spawn_mob(playershops.SHOPKEEPER_TEMPLATE_VNUM, current_room.vnum)
        shopkeeper.player_shop_owner = player.name
        shopkeeper.name = f"{player.name}'s shopkeeper"
        session.send(
            f"You pay {config.PLAYER_SHOP_COST_RYO:,} ryo and claim {current_room.name}. "
            f"Give items to your shopkeeper (see 'help give') and use 'price' to set what they sell for."
        )
        return

    if _own_kage_chamber(player):
        if not args:
            session.send("Buy what? Try 'list' to see available perks and legendary items.")
            return
        query = " ".join(args).lower()

        legendary_key, legendary_data = legendary_items.find_by_query(query)
        if not legendary_key:
            legendary_key = next(
                (key for key, data in legendary_items.LEGENDARY_ITEMS.items()
                 if (proto := olc.OBJECT_TEMPLATES.get(data["vnum"]))
                 and query in proto["short_desc"].lower()), None)
            if legendary_key:
                legendary_data = legendary_items.LEGENDARY_ITEMS[legendary_key]
        if legendary_key:
            vnum = legendary_data["vnum"]
            cost = legendary_data["cost_mission_points"]
            proto = olc.OBJECT_TEMPLATES.get(vnum)
            item_name = proto["short_desc"] if proto else legendary_data["short_desc"]
            level_error = playershops.purchase_level_error(
                player, proto, item_name)
            if level_error:
                session.send(level_error)
                return
            already_owned = any(
                item.lower() == item_name.lower()
                for item in list(player.inventory) + [slot for slot in player.equipment.values() if slot]
            )
            if already_owned:
                session.send(f"You already own {rarity_colored_name(item_name)} -- there's only one to a customer.")
                return
            if player.mission_points < cost:
                session.send(f"You need {cost:,} mission point(s) for that -- you have {player.mission_points:,}.")
                return
            ok, reason = inventory.add_item(player.inventory, item_name)
            if not ok:
                session.send(inventory.full_message(reason, item_name))
                return
            player.mission_points -= cost
            session.send(
                f"You spend {cost:,} mission point(s). {kage.kage_title(player.village)} presents you with "
                f"{rarity_colored_name(item_name)}!"
            )
            return

        perk_key = next((key for key in village_perks.PERK_TYPES if query in key), None)
        if not perk_key:
            session.send("That isn't a perk or legendary item your Kage offers. Try 'list'.")
            return
        info = village_perks.PERK_TYPES[perk_key]
        if player.mission_points < info["cost"]:
            session.send(f"You need {info['cost']} mission point(s) for that -- you have {player.mission_points}.")
            return
        player.mission_points -= info["cost"]
        village_perks.purchase(player.village, perk_key)
        minutes = village_perks.duration_seconds(perk_key) // 60
        session.send(
            f"You spend {info['cost']} mission point(s). {kage.kage_title(player.village)} grants the village "
            f"&Y{info['display_name']}&x perk for {minutes} minutes!"
        )
        session.broadcast_village(
            player.village,
            f"&Y[{info['display_name']} is now active for the village for {minutes} minutes, "
            f"purchased by {player.name}!]&x",
            exclude_self=True,
        )
        return

    shopkeeper = _find_shopkeeper(player.room_vnum)
    if shopkeeper and shopkeeper.player_shop_owner:
        if not args:
            session.send("Buy what?")
            return
        ok, result, price = playershops.buy_from_shop(shopkeeper, player, " ".join(args).lower())
        if not ok:
            session.send(result)
            return
        session.send(f"You buy {rarity_colored_name(result)} for {price:,} ryo.")
        _fire_item_trigger(session, result, "get")
        return

    if shopkeeper:
        if not args:
            session.send("Buy what?")
            return
        query = " ".join(args).lower()
        obj_vnum = next(
            (v for v in combat.mob_shop_items(shopkeeper)
             if v in olc.OBJECT_TEMPLATES and query in olc.OBJECT_TEMPLATES[v]["short_desc"].lower()),
            None,
        )
        if obj_vnum is None:
            session.send(f"{shopkeeper.name.capitalize()} doesn't sell that.")
            return
        obj = olc.OBJECT_TEMPLATES[obj_vnum]
        level_error = playershops.purchase_level_error(player, obj, obj["short_desc"])
        if level_error:
            session.send(level_error)
            return
        if player.ryo < obj["cost"]:
            session.send("You can't afford that.")
            return
        ok, reason = inventory.add_item(player.inventory, obj["short_desc"])
        if not ok:
            session.send(inventory.full_message(reason, obj["short_desc"]))
            return
        player.ryo -= obj["cost"]
        session.send(f"You buy {rarity_colored_name(obj['short_desc'])} for {obj['cost']} ryo.")
        _fire_item_trigger(session, obj["short_desc"], "get")
        return

    shop = content.SHOPS.get(player.room_vnum)
    if not shop:
        session.send("There is nothing to buy here.")
        return
    if not args:
        session.send("Buy what?")
        return
    query = " ".join(args).lower()
    match = next((item for item in shop["items"] if query in item["name"].lower()), None)
    if not match:
        session.send("They don't sell that here.")
        return
    level_error = playershops.purchase_level_error(
        player, _find_object_prototype_by_name(match["name"]), match["name"])
    if level_error:
        session.send(level_error)
        return
    if player.ryo < match["price"]:
        session.send("You can't afford that.")
        return
    ok, reason = inventory.add_item(player.inventory, match["name"])
    if not ok:
        session.send(inventory.full_message(reason, match["name"]))
        return
    player.ryo -= match["price"]
    session.send(f"You buy {rarity_colored_name(match['name'])} for {match['price']} ryo.")
    _fire_item_trigger(session, match["name"], "get")


def cmd_sell(session, args: List[str]) -> None:
    player = session.player

    if args and args[0].lower() == "shop":
        if player.shop_room_vnum is None:
            session.send("You don't own a shop to close.")
            return
        results = playershops.close_shop(player)
        if not results:
            session.send("You close your shop. It stood empty, so there was nothing to return.")
        else:
            floor_items = [name for name, dest in results if dest == "floor"]
            inv_items = [name for name, dest in results if dest == "inventory"]
            lines = ["You close your shop."]
            if inv_items:
                lines.append(f"Returned to your inventory: {', '.join(inv_items)}.")
            if floor_items:
                lines.append(f"No room left for these, so they're on the floor: {', '.join(floor_items)}.")
            session.send("\n".join(lines))
        return

    if args and args[0].lower() == "room":
        if player.apartment_room_vnum is None:
            session.send("You don't own an apartment.")
            return
        if len(args) != 2:
            session.send(f"Usage: sell room <type>\nTypes you own: {', '.join(player.apartment_expansions) or 'none'}")
            return
        room_type = args[1].lower()
        if room_type not in player.apartment_expansions:
            session.send(f"You don't have a {room_type} to sell.")
            return

        entry = player.apartment_expansions.pop(room_type)
        refund = apartments.refund_for_cost(entry["cost"])
        player.ryo += refund
        room_vnum = apartments.expansion_room_vnum(player.apartment_room_vnum, room_type)
        room = WORLD.get(room_vnum)
        if room:
            apartments.reset_room_to_empty(
                room, clear_owner=False,
                parent_vnum=entry.get("parent_vnum", player.apartment_room_vnum),
                direction=entry["direction"],
            )
        if room_type == "storage":
            player.storage_room_items = []
        session.send(
            f"You tear out the {room_type} and receive {refund:,} ryo "
            f"(50% of the {entry['cost']:,} ryo it cost)."
        )
        return

    if args and "apartment" in " ".join(args).lower():
        if player.apartment_room_vnum is None:
            session.send("You don't own an apartment to sell.")
            return
        room = WORLD.get(player.apartment_room_vnum)
        total_refund = apartments.refund_for_cost(config.APARTMENT_COST_RYO)
        for room_type, entry in player.apartment_expansions.items():
            total_refund += apartments.refund_for_cost(entry["cost"])
            expansion_vnum = apartments.expansion_room_vnum(player.apartment_room_vnum, room_type)
            expansion_room = WORLD.get(expansion_vnum)
            if expansion_room:
                apartments.reset_room_to_empty(
                    expansion_room, clear_owner=True,
                    parent_vnum=entry.get("parent_vnum", player.apartment_room_vnum),
                    direction=entry["direction"],
                )
        if room:
            apartments.reset_room_to_empty(room, clear_owner=True)
        player.apartment_room_vnum = None
        player.apartment_name = None
        player.apartment_description = None
        player.apartment_expansions = {}
        player.storage_room_items = []
        player.ryo += total_refund
        session.send(
            f"You sign over the deed (and every room you built) and receive {total_refund:,} ryo "
            f"(50% of what each room cost)."
        )
        return

    shopkeeper = _find_shopkeeper(player.room_vnum)
    if shopkeeper:
        if not args:
            session.send("Sell what?")
            return
        query = " ".join(args).lower()
        match = find_indexed_item(query, player.inventory)
        if not match:
            session.send(f"You aren't carrying anything like '{query}'.")
            return
        category = item_types.classify_item(match)
        buys_categories = combat.mob_shop_buys_categories(shopkeeper)
        if buys_categories and category not in buys_categories:
            session.send(f"{shopkeeper.name.capitalize()} doesn't buy {category} items.")
            return
        multiplier = 1.0 if buys_categories else 0.5
        dish_price = cooking.price_for_dish(match)
        base_price = dish_price if dish_price is not None else item_types.base_sell_price(match)
        price = max(1, int(base_price * multiplier))
        player.inventory.remove(match)
        player.ryo += price
        session.send(f"You sell {match} for {price} ryo.")
        return

    shop = content.SHOPS.get(player.room_vnum)
    if not shop:
        session.send("There is nowhere to sell that here.")
        return
    if not args:
        session.send("Sell what?")
        return
    query = " ".join(args).lower()
    match = find_indexed_item(query, player.inventory)
    if not match:
        session.send(f"You aren't carrying anything like '{query}'.")
        return

    category = item_types.classify_item(match)
    shop_type = shop["type"]
    if not data_shops.can_sell_here(shop_type, category):
        shop_info = data_shops.SHOP_TYPES[shop_type]
        session.send(f"{shop_info['display_name']} doesn't buy {category} items.")
        return

    dish_price = cooking.price_for_dish(match)
    base_price = dish_price if dish_price is not None else item_types.base_sell_price(match)
    price = max(1, int(base_price * data_shops.sell_multiplier(shop_type)))
    player.inventory.remove(match)
    player.ryo += price
    session.send(f"You sell {match} for {price} ryo.")


CHOU_HAN_CHOICES = {"chou": "chou", "even": "chou", "han": "han", "odd": "han"}
CHOU_HAN_PAYOUT_MULTIPLIER = 3  # a win pays back 3x the wager (net gain = 2x)


GAMBLE_DELAY_SECONDS = 60.0


def cmd_gamble(session, args: List[str]) -> None:
    """Chou-han (even/odd): the dealer rolls two dice; bet on whether
    the sum is even (chou) or odd (han). Requires sitting down at the
    table (position == 'resting' -- our existing 'rest' position is
    also how the game narrates it: 'You sit down and rest'). Takes
    GAMBLE_DELAY_SECONDS (~1 minute) to resolve, with flavor messages
    along the way, rather than resolving instantly -- the wager is
    deducted up front (so it can't be spent elsewhere mid-roll), and
    the actual result only lands once the delay is up."""
    player = session.player
    dealer = _find_gambler(player.room_vnum)
    if not dealer:
        session.send("There is no dealer here to gamble with.")
        return
    if session.is_busy():
        session.send("You're already busy with something.")
        return
    if player.position != "resting":
        session.send(f"You need to sit down at the table first (try 'rest') before {dealer.name} will deal you in.")
        return
    if len(args) != 2:
        session.send("Usage: gamble <chou|han|even|odd> <wager>")
        return
    choice_word, wager_text = args[0].lower(), args[1]
    if choice_word not in CHOU_HAN_CHOICES:
        session.send("Call 'chou' (even) or 'han' (odd).")
        return
    if not wager_text.isdigit() or int(wager_text) <= 0:
        session.send("Wager must be a positive number of ryo.")
        return
    wager = int(wager_text)
    if wager > player.ryo:
        session.send("You can't wager more ryo than you have.")
        return

    choice = CHOU_HAN_CHOICES[choice_word]
    player.ryo -= wager

    def resolve() -> None:
        die1, die2 = random.randint(1, 6), random.randint(1, 6)
        total = die1 + die2
        outcome = "chou" if total % 2 == 0 else "han"

        session.send(
            f"{dealer.name.capitalize()} lifts the cup -- {die1} and {die2} -- {total} ({outcome})."
        )
        if choice == outcome:
            winnings = wager * CHOU_HAN_PAYOUT_MULTIPLIER
            player.ryo += winnings
            session.send(f"&GYou called {choice_word} correctly! {dealer.name.capitalize()} pays you {winnings} ryo.&x")
        else:
            session.send(f"&R{dealer.name.capitalize()} sweeps your {wager} ryo off the table.&x")

    session.send(f"You place your wager. {dealer.name.capitalize()} begins rattling the dice cup...")
    flavor = [
        (20.0, f"{dealer.name.capitalize()} shakes the cup with a steady, rhythmic clatter..."),
        (40.0, "The dice tumble and knock against the sides of the cup..."),
    ]
    session.start_timed_action("gambling", GAMBLE_DELAY_SECONDS, resolve, flavor_schedule=flavor)


SLOTS_DELAY_SECONDS = 15.0


def cmd_slots(session, args: List[str]) -> None:
    """Slot machine gambling (slots.py) -- four wager tiers (1/25/100/
    1,000 ryo), each with its own progressive jackpot that grows from
    every pull. Same location requirement as chou-han: needs a
    gambler-flagged mob in the room, but no sitting required (a
    standing machine, not a table game). Takes SLOTS_DELAY_SECONDS to
    resolve rather than being instant, same treatment as every other
    gambling/job action -- the wager is deducted up front (so it can't
    be spent elsewhere mid-pull), and the reels/payout only land once
    the delay is up (session.start_timed_action)."""
    player = session.player
    dealer = _find_gambler(player.room_vnum)
    if not dealer:
        session.send("There is no gambling machine attendant here.")
        return

    if not args:
        lines = [f"&W{dealer.name.capitalize()}'s slot machines:&x"]
        for tier in slots.TIERS:
            jackpot = slots.get_jackpot(tier)
            lines.append(f"  &Y{tier:,} ryo&x pull -- current jackpot: &O{jackpot:,} ryo&x")
        lines.append("Usage: slots <tier>")
        session.send("\n".join(lines))
        return

    if session.is_busy():
        session.send("You're already busy with something.")
        return
    if not args[0].isdigit() or int(args[0]) not in slots.TIERS:
        session.send(f"That's not a valid tier. Choose one of: {', '.join(str(t) for t in slots.TIERS)}.")
        return
    tier = int(args[0])
    if player.ryo < tier:
        session.send(f"You need {tier:,} ryo to pull this machine -- you have {player.ryo:,}.")
        return

    player.ryo -= tier

    def resolve() -> None:
        result = slots.pull(tier, tier)
        session.send(f"&D[ {slots.display_reels(result['reels'])} &D]&x")

        if result["outcome"] == "jackpot":
            player.ryo += result["payout"]
            session.send(f"&r*** JACKPOT! *** {dealer.name.capitalize()} pays out {result['payout']:,} ryo!&x")
        elif result["outcome"] == "three":
            player.ryo += result["payout"]
            session.send(f"&GThree {slots.SYMBOL_DISPLAY[result['symbol']]}&G! You win {result['payout']:,} ryo.&x")
        elif result["outcome"] == "two":
            player.ryo += result["payout"]
            session.send(f"&YTwo of a kind. You win {result['payout']:,} ryo.&x")
        else:
            session.send(f"&DNo match. {dealer.name.capitalize()} keeps your {tier:,} ryo.&x")

    session.send(f"You pull the lever on {dealer.name}'s machine. The reels start spinning...")
    session.start_timed_action("slots", SLOTS_DELAY_SECONDS, resolve)


ROULETTE_DELAY_SECONDS = 30.0


def cmd_roulette(session, args: List[str]) -> None:
    """Roulette (roulette.py) -- wagered in MISSION POINTS, not ryo,
    since it's meant to feel like the higher-stakes table game of the
    three gambling mechanics. Same gambler-mob location requirement as
    slots/chou-han, no sitting required. 'roulette number <0-36>
    <wager>' for a 36x straight-up bet, or 'roulette
    <red|black|odd|even|low|high> <wager>' for a 2x even-money bet.
    Takes ROULETTE_DELAY_SECONDS to resolve rather than being instant,
    same treatment as slots/chou-han -- the wager is deducted up
    front, and the wheel's result only lands once the delay is up."""
    player = session.player
    dealer = _find_gambler(player.room_vnum)
    if not dealer:
        session.send("There is no roulette dealer here.")
        return

    if not args:
        session.send(
            "Usage: roulette number <0-36> <wager>\n"
            "       roulette <red|black|odd|even|low|high> <wager>\n"
            "Wagers are in MISSION POINTS, not ryo. Straight numbers pay 36x; "
            "red/black/odd/even/low/high pay 2x."
        )
        return

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    bet_type = args[0].lower()
    if bet_type == "number":
        if len(args) != 3 or not args[1].isdigit() or not (0 <= int(args[1]) <= 36) or not args[2].isdigit():
            session.send("Usage: roulette number <0-36> <wager>")
            return
        bet_value = int(args[1])
        wager_text = args[2]
    elif bet_type in roulette.OUTSIDE_BET_TYPES:
        if len(args) != 2 or not args[1].isdigit():
            session.send(f"Usage: roulette {bet_type} <wager>")
            return
        bet_value = None
        wager_text = args[1]
    else:
        session.send(
            f"'{bet_type}' isn't a valid bet. Choose 'number' or one of: "
            + ", ".join(sorted(roulette.OUTSIDE_BET_TYPES))
        )
        return

    wager = int(wager_text)
    if wager <= 0:
        session.send("Wager must be a positive number of mission points.")
        return
    if wager > player.mission_points:
        session.send(f"You only have {player.mission_points} mission points -- you can't wager {wager}.")
        return

    player.mission_points -= wager

    def resolve() -> None:
        result = roulette.spin()
        session.send(f"{dealer.name.capitalize()} spins the wheel... it lands on {roulette.colored_number(result)}.")

        payout = roulette.resolve_bet(bet_type, bet_value, wager, result)
        if payout > 0:
            player.mission_points += payout
            session.send(f"&GYou win {payout:,} mission points!&x")
        else:
            session.send(f"&DThe house takes your {wager:,} mission points.&x")

    session.send(f"You place your bet. {dealer.name.capitalize()} spins up the wheel...")
    session.start_timed_action("roulette", ROULETTE_DELAY_SECONDS, resolve)


FISHING_DELAY_SECONDS = 6.0


def _use_held_job_tool(session, held_tool: str) -> bool:
    """Spend one use when a delayed job attempt actually resolves.

    A switched or removed tool cancels the attempt. The tool breaks on
    its final use, after which the current attempt still finishes.
    """
    player = session.player
    if player.equipment.get("tool") != held_tool:
        session.send("You stopped holding the tool before finishing the job.")
        return False
    remaining, _total = tool_durability.uses_left(held_tool)
    if remaining <= 0:
        session.send("That tool is broken.")
        return False
    updated = tool_durability.spend_use(held_tool)
    if updated is None:
        _apply_equipment_stat_bonuses(player, held_tool, sign=-1)
        del player.equipment["tool"]
        session.send(f"&R{tool_durability.base_name(held_tool)} breaks after its final use!&x")
    else:
        player.equipment["tool"] = updated
        if remaining <= 11 or remaining in {101, 51, 26}:
            session.send(f"&YYour tool has {remaining - 1} uses left.&x")
    return True


def cmd_fish(session, args: List[str]) -> None:
    """Fishing (fishing.py) -- the first job on jobs.py's generic
    leveling framework, entirely separate from ninja level/experience.
    Needs a fishing rod actually HELD (via 'hold <rod>', in the 'tool'
    equipment slot -- merely carrying one in inventory isn't enough,
    per explicit request) and a water biome (rset biome
    ocean/river/lake/swamp); the rod's tier gates both what's reachable
    at all and shifts the odds toward rarer fish, alongside the
    player's own Fishing job level. Takes FISHING_DELAY_SECONDS to
    resolve rather than being instant -- preconditions (rod held,
    right biome, rod usable at the player's level) are still checked
    immediately, but the actual catch only resolves once the delay is
    up (session.start_timed_action, resolved from the pulse loop)."""
    player = session.player

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    held_tool = player.equipment.get("tool", "")
    rod_name = strip_crafted_suffix(held_tool)
    if rod_name.lower() not in fishing.RODS:
        session.send("You need to hold a fishing rod to do that (see 'help hold').")
        return

    room = world.WORLD.get(player.room_vnum)
    if not room or not fishing.can_fish_here(room.biome):
        session.send("There's nowhere to fish here -- you need to be near water.")
        return

    job_level = jobs.get_job_level(player, "fishing")

    required = fishing.rod_required_level(rod_name.lower())
    if required > job_level:
        session.send(
            f"{held_tool} requires Fishing level {required} to use -- you're only level {job_level}."
        )
        return

    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if not _use_held_job_tool(session, held_tool):
            return
        catch = fishing.attempt_catch(job_level, rod_name.lower())
        if catch["failed"]:
            session.send("You feel a tug, but come up with nothing. The fish got away.")
            return
        proto = _find_object_prototype_by_name(catch["name"])
        display_name = proto["short_desc"] if proto else catch["name"]

        ok, reason = inventory.add_item(player.inventory, display_name)
        if not ok:
            session.send(f"You caught {rarity_colored_name(display_name)}, but had nowhere to put it!")
            session.send(inventory.full_message(reason, display_name))
            session.send("You release it back into the water.")
            for message in jobs.add_job_xp(player, "fishing", catch["xp"]):
                session.send(message)
            return

        session.send(f"You caught {rarity_colored_name(display_name)}!")
        for message in jobs.add_job_xp(player, "fishing", catch["xp"]):
            session.send(message)

    session.send("You cast your line and wait...")
    session.start_timed_action("fishing", FISHING_DELAY_SECONDS, resolve)


def cmd_mine(session, args: List[str]) -> None:
    """Mining (mining.py) -- the second job on jobs.py's framework,
    structured identically to cmd_fish, including the same delay
    treatment: preconditions check immediately, but the actual find
    only resolves after FISHING_DELAY_SECONDS via the timed-action
    mechanism, not instantly. Needs a pickaxe actually HELD (via 'hold
    <pickaxe>', in the 'tool' equipment slot -- merely carrying one in
    inventory isn't enough, matching the same fix applied to fishing
    rods) and a mountain biome; the pickaxe's tier gates both what's
    reachable and shifts the odds toward rarer finds, alongside the
    player's own Mining job level."""
    player = session.player

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    held_tool = player.equipment.get("tool", "")
    tool_name = strip_crafted_suffix(held_tool)
    if tool_name.lower() not in mining.PICKAXES:
        session.send("You need to hold a pickaxe to do that (see 'help hold').")
        return

    room = world.WORLD.get(player.room_vnum)
    if not room or not mining.can_mine_here(room.biome):
        session.send("There's nowhere to mine here -- you need to be somewhere rocky.")
        return

    job_level = jobs.get_job_level(player, "mining")

    required = mining.tool_required_level(tool_name.lower())
    if required > job_level:
        session.send(
            f"{held_tool} requires Mining level {required} to use -- you're only level {job_level}."
        )
        return

    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if not _use_held_job_tool(session, held_tool):
            return
        find = mining.attempt_mine(job_level, tool_name.lower())
        if find["failed"]:
            session.send("Your pickaxe glances off the rock. Nothing comes loose.")
            return
        proto = _find_object_prototype_by_name(find["name"])
        display_name = proto["short_desc"] if proto else find["name"]

        ok, reason = inventory.add_item(player.inventory, display_name)
        if not ok:
            session.send(f"You dig up {rarity_colored_name(display_name)}, but had nowhere to put it!")
            session.send(inventory.full_message(reason, display_name))
            session.send("You leave it in the rock.")
            return

        session.send(f"You mine {rarity_colored_name(display_name)}!")
        for message in jobs.add_job_xp(player, "mining", find["xp"]):
            session.send(message)

        bonus = gems.roll_bonus_gem()
        if bonus:
            gem_name, gem_rarity = bonus
            gem_proto = _find_object_prototype_by_name(gem_name)
            gem_display = gem_proto["short_desc"] if gem_proto else gem_name
            ok2, reason2 = inventory.add_item(player.inventory, gem_display)
            if ok2:
                session.send(
                    f"&YSomething catches your eye in the rubble -- you find "
                    f"{rarity_colored_name(gem_display)}!&x"
                )
            else:
                session.send(
                    f"&YSomething catches your eye in the rubble -- "
                    f"{rarity_colored_name(gem_display)}, but you have nowhere to put it!&x"
                )
                session.send(inventory.full_message(reason2, gem_display))

    session.send("You swing your pickaxe at the rock face...")
    session.start_timed_action("mining", FISHING_DELAY_SECONDS, resolve)


def cmd_smelt(session, args: List[str]) -> None:
    """Smelting (mining.py) -- converts a raw ore (an iron ore/a steel
    ore/a chakra steel ore) into the ingot every downstream crafting
    recipe in the game already depends on by exact name. Gated by
    Mining level (matching the ore's own implicit tier), costs 1-2
    stamina like every other job action, and takes a real delay to
    resolve -- but always succeeds once level and material checks
    pass, since the randomness already happened at the mining step
    that produced the ore in the first place. No location or tool
    requirement, unlike the gathering jobs -- smelting works
    anywhere."""
    player = session.player

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    if not args:
        session.send("Usage: smelt <ore>")
        return

    query = " ".join(args).lower()
    ore_name = next(
        (item for item in player.inventory
         if _item_matches(query, item) and item.lower() in mining.SMELTING_RECIPES),
        None,
    )
    if not ore_name:
        session.send("You don't have that ore to smelt.")
        return

    job_level = jobs.get_job_level(player, "mining")
    required = mining.smelt_required_level(ore_name.lower())
    if required > job_level:
        session.send(
            f"Smelting {ore_name} requires Mining level {required} -- you're only level {job_level}."
        )
        return

    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if ore_name not in player.inventory:
            session.send(f"You no longer have {ore_name} to smelt.")
            return
        player.inventory.remove(ore_name)

        ingot_name = mining.smelt_ore(ore_name.lower())
        proto = _find_object_prototype_by_name(ingot_name)
        display_name = proto["short_desc"] if proto else ingot_name

        ok, reason = inventory.add_item(player.inventory, display_name)
        if not ok:
            session.send(f"You smelt {rarity_colored_name(display_name)}, but had nowhere to put it!")
            session.send(inventory.full_message(reason, display_name))
            session.send("It cools into a useless slag heap and crumbles away.")
            return

        session.send(f"You smelt {ore_name} into {rarity_colored_name(display_name)}!")

    session.send(f"You stoke the forge and begin smelting {ore_name}...")
    session.start_timed_action("mining", FISHING_DELAY_SECONDS, resolve)


def cmd_chop(session, args: List[str]) -> None:
    """Lumberjacking (lumberjack.py) -- the third job on jobs.py's
    framework, structured identically to cmd_fish/cmd_mine, including
    the same delay treatment (FISHING_DELAY_SECONDS via the timed-
    action mechanism, not instant). Needs an axe actually HELD (via
    'hold <axe>', in the 'tool' equipment slot -- merely carrying one
    in inventory isn't enough, matching the same fix applied to
    fishing rods and pickaxes) and a forest biome; the axe's tier
    gates both what's reachable and shifts the odds toward rarer
    finds, alongside the player's own Lumberjack job level."""
    player = session.player

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    held_tool = player.equipment.get("tool", "")
    tool_name = strip_crafted_suffix(held_tool)
    if tool_name.lower() not in lumberjack.AXES:
        session.send("You need to hold an axe to do that (see 'help hold').")
        return

    room = world.WORLD.get(player.room_vnum)
    if not room or not lumberjack.can_chop_here(room.biome):
        session.send("There's nothing to chop here -- you need to be somewhere wooded.")
        return

    job_level = jobs.get_job_level(player, "lumberjack")

    required = lumberjack.tool_required_level(tool_name.lower())
    if required > job_level:
        session.send(
            f"{held_tool} requires Lumberjack level {required} to use -- you're only level {job_level}."
        )
        return

    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if not _use_held_job_tool(session, held_tool):
            return
        find = lumberjack.attempt_chop(job_level, tool_name.lower())
        if find["failed"]:
            session.send("Your axe bites into bark, but nothing worth taking comes free.")
            return
        proto = _find_object_prototype_by_name(find["name"])
        display_name = proto["short_desc"] if proto else find["name"]

        ok, reason = inventory.add_item(player.inventory, display_name)
        if not ok:
            session.send(f"You cut free {rarity_colored_name(display_name)}, but had nowhere to put it!")
            session.send(inventory.full_message(reason, display_name))
            session.send("You leave it where it fell.")
            return

        session.send(f"You chop free {rarity_colored_name(display_name)}!")
        for message in jobs.add_job_xp(player, "lumberjack", find["xp"]):
            session.send(message)

    session.send("You swing your axe at the trunk...")
    session.start_timed_action("lumberjack", FISHING_DELAY_SECONDS, resolve)


COOK_DELAY_SECONDS = 6.0


def cmd_farm(session, args: List[str]) -> None:
    """Farming (farming.py) -- a new gathering job on jobs.py's
    framework, structured identically to cmd_fish/cmd_mine/cmd_chop.
    Needs a hoe actually HELD and a "plains" biome. Farming level
    unlocks crops; gathering can still fail."""
    player = session.player

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    held_tool = player.equipment.get("tool", "")
    tool_name = strip_crafted_suffix(held_tool)
    if tool_name.lower() not in farming.HOES:
        session.send("You need to hold a hoe to do that (see 'help hold').")
        return

    room = world.WORLD.get(player.room_vnum)
    if not room or not farming.can_farm_here(room.biome):
        session.send("There's nowhere to farm here -- you need open farmland.")
        return

    job_level = jobs.get_job_level(player, "farming")

    required = farming.tool_required_level(tool_name.lower())
    if required > job_level:
        session.send(
            f"{held_tool} requires Farming level {required} to use -- you're only level {job_level}."
        )
        return

    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if not _use_held_job_tool(session, held_tool):
            return
        find = farming.attempt_farm(job_level, tool_name.lower())
        if find["failed"]:
            session.send("You till the soil, but come up with nothing usable.")
            return
        proto = _find_object_prototype_by_name(find["name"])
        display_name = proto["short_desc"] if proto else find["name"]

        ok, reason = inventory.add_item(player.inventory, display_name)
        if not ok:
            session.send(f"You harvest {rarity_colored_name(display_name)}, but had nowhere to put it!")
            session.send(inventory.full_message(reason, display_name))
            session.send("You leave it in the field.")
            return

        session.send(f"You harvest {rarity_colored_name(display_name)}!")
        for message in jobs.add_job_xp(player, "farming", find["xp"]):
            session.send(message)

    session.send("You till the soil and tend the crops...")
    session.start_timed_action("farming", FISHING_DELAY_SECONDS, resolve)


def cmd_cook(session, args: List[str]) -> None:
    """Cooking (cooking.py) -- reworked per the same explicit request
    as fishing/mining/lumberjack/farming's own reworks: needs one of 6
    tiered cooking pots actually HELD (same requirement as fishing
    rods/pickaxes/axes/hoes), or standing in your own apartment
    kitchen (which needs no pot at all -- treated as the lowest,
    Copper tier for quality odds, since there's no specific pot item
    to gate there). A raw fish (from Fishing) is named as the argument
    -- no biome/location requirement otherwise, unlike the gathering
    jobs, since cooking works anywhere. Takes COOK_DELAY_SECONDS to
    resolve, with a real chance to burn the dish entirely; on success,
    the resulting dish's quality tier is shown as a suffix (e.g.
    "(Rare)"), same pattern crafting.py uses for a crafted item's stat
    bonus suffix -- and, per the rework, the pot's own tier shifts the
    odds toward better quality the same tier-distance way a rod/
    pickaxe/axe/hoe shifts catch rarity, so only the top pot gives a
    real shot at a Legendary dish. The ingredient is consumed either
    way (burned or not) -- re-checked at resolution time in case it
    was spent elsewhere during the delay, same pattern crafting.py
    uses for its own materials."""
    player = session.player

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    room = world.WORLD.get(player.room_vnum)
    in_own_kitchen = room and room.apartment_room_type == "kitchen" and room.owner == player.name
    held_tool = player.equipment.get("tool", "")
    stripped_tool = strip_crafted_suffix(held_tool)
    pot_name = stripped_tool if stripped_tool.lower() in cooking.POTS else None
    if pot_name is None and not in_own_kitchen:
        session.send("You need to hold a cooking pot to do that (see 'help hold').")
        return

    if not args:
        session.send("Usage: cook <fish>")
        return

    query = " ".join(args).lower()
    ingredient_name = next(
        (item for item in player.inventory
         if _item_matches(query, item) and item.lower() in cooking.INGREDIENTS),
        None,
    )
    if not ingredient_name:
        session.send("You don't have that ingredient to cook.")
        return

    job_level = jobs.get_job_level(player, "cooking")

    if pot_name is not None:
        required = cooking.pot_required_level(pot_name)
        if required > job_level:
            session.send(
                f"{held_tool} requires Cooking level {required} to use -- you're only level {job_level}."
            )
            return
    effective_pot = pot_name if pot_name is not None else "a copper cooking pot"

    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if ingredient_name not in player.inventory:
            session.send(f"You no longer have {ingredient_name} to cook.")
            return
        if pot_name is not None and not _use_held_job_tool(session, held_tool):
            return
        player.inventory.remove(ingredient_name)

        result = cooking.attempt_cook(job_level, ingredient_name.lower(), effective_pot)
        if result["burned"]:
            session.send(f"You burn {ingredient_name} to a crisp! It's ruined.")
            return

        display_name = result["name"]

        ok, reason = inventory.add_item(player.inventory, display_name)
        if not ok:
            session.send(f"You cook {rarity_colored_name(display_name)}, but had nowhere to put it!")
            session.send(inventory.full_message(reason, display_name))
            session.send("You eat it yourself on the spot rather than waste it.")
            return

        session.send(f"You cook {rarity_colored_name(display_name)}!")
        for message in jobs.add_job_xp(player, "cooking", result["xp"]):
            session.send(message)

    session.send(f"You start cooking {ingredient_name}...")
    session.start_timed_action("cooking", COOK_DELAY_SECONDS, resolve)


def cmd_gemcut(session, args: List[str]) -> None:
    """Cut one raw mining gem using a held chisel and its durability."""
    player = session.player
    if session.is_busy():
        session.send("You're already busy with something.")
        return
    held_tool = player.equipment.get("tool", "")
    if strip_crafted_suffix(held_tool).lower() not in gemcutter.CHISELS:
        session.send("You need to hold a copper chisel to cut gems.")
        return
    if not args:
        session.send("Usage: gemcut <raw gem>  (rough quartz, raw sapphire, raw ruby, raw diamond)")
        return
    raw_gems = [item for item in player.inventory if item.lower() in gemcutter.RECIPES]
    raw_gem = find_indexed_item(" ".join(args).lower(), raw_gems)
    if not raw_gem:
        session.send("You aren't carrying that raw gem.")
        return
    result_name, required_level, xp = gemcutter.RECIPES[raw_gem.lower()]
    job_level = jobs.get_job_level(player, "gemcutter")
    if job_level < required_level:
        session.send(f"Cutting {raw_gem} requires Gemcutter level {required_level} (yours: {job_level}).")
        return
    if not jobs.try_deduct_action_stamina(player):
        session.send("You don't have enough stamina.")
        return

    def resolve() -> None:
        if raw_gem not in player.inventory:
            session.send(f"You no longer have {raw_gem} to cut.")
            return
        if not _use_held_job_tool(session, held_tool):
            return
        player.inventory.remove(raw_gem)
        ok, reason = inventory.add_item(player.inventory, result_name)
        if not ok:
            player.inventory.append(raw_gem)
            session.send(inventory.full_message(reason, result_name))
            session.send(f"You keep {raw_gem} for another attempt.")
            return
        gem_proto = _find_object_prototype_by_name(result_name)
        bonuses = gem_proto.get("gem_bonuses", {}) if gem_proto else {}
        session.send(
            f"You cut {raw_gem} into {result_name}! "
            f"Its {gem_proto.get('rarity', 'common') if gem_proto else 'common'} quality stores "
            f"Hitroll +{bonuses.get('hitroll', 0)} and Damageroll +{bonuses.get('damroll', 0)} "
            "for future weapon upgrades."
        )
        for message in jobs.add_job_xp(player, "gemcutter", xp):
            session.send(message)

    session.send(f"You carefully start cutting {raw_gem}...")
    session.start_timed_action("gemcutting", COOK_DELAY_SECONDS, resolve)


CRAFT_DELAY_SECONDS = 20.0


_NEXT_CRAFTED_ITEM_VNUM = None  # lazily initialized on first real craft, see _allocate_crafted_item_vnum


def _allocate_crafted_item_vnum() -> int:
    """A genuinely unique, real, persistent vnum for a newly crafted
    item -- starting at 500000 (confirmed genuinely free via a direct
    scan of every real vnum already in use), incrementing by 1 each
    real craft. Lazily scans for the highest already-used vnum in this
    dedicated range on first use, so it correctly resumes past
    whatever's already registered rather than always restarting at
    500000 (e.g. after a server restart where earlier crafted items
    were already saved into OBJECT_TEMPLATES via world-save/reload)."""
    global _NEXT_CRAFTED_ITEM_VNUM
    if _NEXT_CRAFTED_ITEM_VNUM is None:
        existing = [v for v in olc.OBJECT_TEMPLATES if v >= 500000]
        _NEXT_CRAFTED_ITEM_VNUM = (max(existing) + 1) if existing else 500000
    vnum = _NEXT_CRAFTED_ITEM_VNUM
    _NEXT_CRAFTED_ITEM_VNUM += 1
    return vnum


def cmd_craft(session, args: List[str]) -> None:
    """'craft weapon <type> <name>' / 'craft armor <slot> <name>' --
    the real Bukijutsu crafting skill (Section 133), per direct
    request/confirmation, replacing the old crafting.py recipe
    framework entirely (it shipped with zero real recipes and was
    never refilled after an earlier revamp). Combines exactly 2 real
    materials (data_crafting.MATERIALS) into a brand-new, genuinely
    unique item the player names themselves -- their own combined
    stat_value applies as both +hitroll and +damroll for a weapon, or
    -armor_class for armor (confirmed directly, matching the game's
    own existing real equipment-bonus mechanism, commands.
    equipped_weapon_hitroll_bonus/damroll_bonus/armor_class_bonus).
    Unlocked at Bukijutsu level 25+ OR any class at level 70+
    (data_crafting.can_craft, confirmed as 2 separate real paths)."""
    import data_crafting

    player = session.player
    if not data_crafting.can_craft(player):
        session.send(
            f"You need to be a Bukijutsu user of level {data_crafting.CRAFTING_BUKIJUTSU_MIN_LEVEL}+, "
            f"or any class at level {data_crafting.CRAFTING_GENERAL_MIN_LEVEL}+, to craft."
        )
        return

    if len(args) < 3 or args[0].lower() not in ("weapon", "armor"):
        session.send("Usage: craft weapon <type> <name>  |  craft armor <slot> <name>")
        return

    kind = args[0].lower()
    if kind == "weapon":
        if args[1].lower() not in data_weapons.WEAPON_TYPES:
            session.send(f"That's not a real weapon type. Choose from: {', '.join(sorted(data_weapons.WEAPON_TYPES))}.")
            return
        sub_type = args[1].lower()
    else:
        if args[1].lower() not in olc.ARMOR_WEAR_LOCATIONS:
            session.send(f"That's not a real armor slot. Choose from: {', '.join(sorted(olc.ARMOR_WEAR_LOCATIONS))}.")
            return
        sub_type = args[1].lower()

    item_name = " ".join(args[2:])
    if not item_name:
        session.send("You need to give your crafted item a name.")
        return

    if session.is_busy():
        session.send("You're already busy with something.")
        return

    def on_materials(response: str) -> None:
        if response.strip().lower() == "cancel":
            session.send("You set your tools aside.")
            return
        parts = [p.strip() for p in response.split(",")]
        if len(parts) != 2:
            session.send("You need to name exactly 2 materials, separated by a comma (e.g. 'iron ingot, yew log').")
            return
        material_a = data_crafting.find_material(parts[0])
        material_b = data_crafting.find_material(parts[1])
        if not material_a or not material_b:
            unknown = parts[0] if not material_a else parts[1]
            session.send(f"'{unknown}' isn't a real crafting material.")
            return

        count_a = sum(1 for item in player.inventory if material_a in item.lower())
        count_b = sum(1 for item in player.inventory if material_b in item.lower())
        required_a = 2 if material_a == material_b else 1
        required_b = 1
        if count_a < required_a or (material_a != material_b and count_b < required_b):
            session.send(f"You don't have both {material_a} and {material_b} in your inventory.")
            return

        if not jobs.try_deduct_action_stamina(player):
            session.send("You don't have enough stamina.")
            return

        def resolve() -> None:
            # Re-check materials are still owned -- could have been
            # given away or otherwise spent during the crafting delay.
            count_a = sum(1 for item in player.inventory if material_a in item.lower())
            count_b = sum(1 for item in player.inventory if material_b in item.lower())
            required_a = 2 if material_a == material_b else 1
            required_b = 1
            if count_a < required_a or (material_a != material_b and count_b < required_b):
                session.send(f"You no longer have both materials. The crafting attempt fails.")
                return

            stat_value = data_crafting.combined_stat_value(material_a, material_b)
            vnum = _allocate_crafted_item_vnum()
            proto = dict(olc.DEFAULT_OBJECT_FIELDS)
            proto["keywords"] = item_name.lower().split()
            proto["short_desc"] = item_name
            proto["long_desc"] = f"{item_name} lies here."
            proto["description"] = f"A crafted {kind} named {item_name}, forged from {material_a} and {material_b}."
            if kind == "weapon":
                proto["item_type"] = "weapon"
                proto["weapon_type"] = sub_type
                proto["wear_loc"] = "wielded"
                proto["stat_bonuses"] = {"hitroll": stat_value, "damroll": stat_value}
            else:
                proto["item_type"] = "armor"
                proto["wear_loc"] = sub_type
                proto["stat_bonuses"] = {"armor_class": -stat_value}
            olc.OBJECT_TEMPLATES[vnum] = proto

            if material_a == material_b:
                removed = 0
                for item in list(player.inventory):
                    if removed >= 2:
                        break
                    if material_a in item.lower():
                        player.inventory.remove(item)
                        removed += 1
            else:
                for material in (material_a, material_b):
                    for item in list(player.inventory):
                        if material in item.lower():
                            player.inventory.remove(item)
                            break

            ok, reason = inventory.add_item(player.inventory, item_name)
            if not ok:
                session.send(inventory.full_message(reason, item_name))
                return
            session.send(f"&WYou craft {rarity_colored_name(item_name)}!&x")

        session.send(f"You set to work crafting {item_name}...")
        session.start_timed_action("crafting", CRAFT_DELAY_SECONDS, resolve)

    session.enter_single_line("What 2 materials do you want to combine? (or 'cancel')", on_materials)


def cmd_give(session, args: List[str]) -> None:
    """Gives an item from inventory to another player in the same
    room, OR to the player's own shopkeeper mob (Section 75 player
    shops) if no matching player is found -- adding it to that shop's
    stock, unpriced until 'price' sets what it sells for. The main
    other use case: trading crafting materials (fishing.CRAFTING_RECIPES)
    that have no gathering job to produce them yet -- a player who has
    one can hand it to someone crafting a rod."""
    player = session.player
    if len(args) < 2:
        session.send("Usage: give <item> <player name>")
        return

    target_query = args[-1].lower()
    target_session = next(
        (
            s for s in session.active_sessions()
            if s is not session and s.player and s.player.room_vnum == player.room_vnum
            and target_query in s.player.name.lower()
        ),
        None,
    )

    item_query = " ".join(args[:-1]).lower()

    if not target_session:
        shopkeeper = next(
            (m for m in combat.mobs_in_room(player.room_vnum)
             if m.player_shop_owner == player.name and target_query in m.name.lower()),
            None,
        )
        if shopkeeper:
            if len(player.shop_stock) >= config.PLAYER_SHOP_MAX_ITEMS:
                session.send(f"Your shop is full -- it can only hold {config.PLAYER_SHOP_MAX_ITEMS} items at once.")
                return
            match = find_indexed_item(item_query, player.inventory)
            if not match:
                session.send("You aren't carrying that.")
                return
            player.inventory.remove(match)
            player.shop_stock.append({"item_name": match, "price": None,
                                      "item_vnum": playershops.item_vnum_for_stock(match)})
            session.send(
                f"You give {rarity_colored_name(match)} to your shopkeeper. "
                f"Use 'price {match.split()[-1]} <amount>' to set what it sells for."
            )
            return
        session.send("There's no one here by that name.")
        return

    match = find_indexed_item(item_query, player.inventory)
    if not match:
        session.send("You aren't carrying that.")
        return

    ok, reason = inventory.add_item(target_session.player.inventory, match)
    if not ok:
        session.send(f"{target_session.player.name} has no room for that.")
        return
    player.inventory.remove(match)
    session.send(f"You give {rarity_colored_name(match)} to {target_session.player.name}.")
    target_session.send(f"{player.name} gives you {rarity_colored_name(match)}.")


def cmd_price(session, args: List[str]) -> None:
    """Sets the sell price for an item already given to the player's
    own shopkeeper (Section 75 player shops). Applies to every
    matching, currently-unpriced entry in shop_stock at once -- if
    several of the same item were given before any of them had a
    price, one 'price' call sets them all rather than requiring one
    call per instance."""
    player = session.player
    if player.shop_room_vnum is None:
        session.send("You don't own a shop.")
        return
    if len(args) < 2 or not args[-1].isdigit():
        session.send("Usage: price <item> <amount>")
        return

    amount = int(args[-1])
    if amount <= 0:
        session.send("Price must be a positive amount.")
        return
    item_query = " ".join(args[:-1]).lower()

    matches = [entry for entry in player.shop_stock
               if entry["price"] is None and _item_matches(item_query, playershops.stock_item_name(entry))]
    if not matches:
        matches = [entry for entry in player.shop_stock if _item_matches(item_query, playershops.stock_item_name(entry))]
    if not matches:
        session.send("You don't have that in your shop's stock.")
        return

    for entry in matches:
        entry["price"] = amount
    session.send(f"You set the price of {playershops.stock_item_name(matches[0])} to {amount:,} ryo.")


def cmd_shop(session, args: List[str]) -> None:
    """Renames/redescribes the player's own shop (only while standing
    inside it, matching 'apartment name'/'apartment desc'), or with no
    arguments shows its current stock and prices."""
    player = session.player
    if player.shop_room_vnum is None:
        session.send("You don't own a shop.")
        return

    if not args:
        if not player.shop_stock:
            session.send("Your shop's stock is empty.")
            return
        lines = ["&WYour shop's stock:&x"]
        for entry in player.shop_stock:
            price_str = f"{entry['price']:,} ryo" if entry["price"] is not None else "no price set"
            lines.append(f"  {rarity_colored_name(playershops.stock_item_name(entry))} - {price_str}")
        session.send("\n".join(lines))
        return

    if player.room_vnum != player.shop_room_vnum:
        session.send("You have to be standing inside your own shop to rename or redescribe it.")
        return

    subcommand = args[0].lower()
    room = WORLD.get(player.shop_room_vnum)
    if subcommand == "name" and len(args) > 1:
        new_name = " ".join(args[1:])
        player.shop_name = new_name
        if room:
            room.name = new_name
        session.send(f"Your shop is now named '{new_name}'.")
        return
    if subcommand in ("desc", "description") and len(args) > 1:
        new_desc = " ".join(args[1:])
        player.shop_description = new_desc
        if room:
            room.description = new_desc
        session.send("Your shop's description has been updated.")
        return

    session.send("Usage: shop name <text> | shop desc <text> | shop (with no arguments to see stock)")


def cmd_drop(session, args: List[str]) -> None:
    """Drops one item, or everything, onto the ground in the current
    room -- 'drop <item>' for one, 'drop all' (or the literal command
    'drop.all', registered as its own alias) for everything at once.
    Dropped items land in Room.ground_items and can be picked back up
    with 'get', not just discarded -- a drop mechanic with no way to
    retrieve what you dropped would be a dead end, not a feature."""
    player = session.player
    room = WORLD.get(player.room_vnum)

    if not args or args[0].lower() == "all":
        if not player.inventory:
            session.send("You aren't carrying anything.")
            return
        dropped = list(player.inventory)
        player.inventory.clear()
        room.ground_items.extend(dropped)
        counts = inventory.slot_counts(dropped)
        summary = ", ".join(
            f"{name} (x{count})" if count > 1 else name for name, count in counts.items()
        )
        session.send(f"You drop everything you were carrying: {summary}.")
        return

    query = " ".join(args).lower()
    match = find_indexed_item(query, player.inventory)
    if not match:
        session.send("You aren't carrying that.")
        return

    player.inventory.remove(match)
    room.ground_items.append(match)
    session.send(f"You drop {rarity_colored_name(match)}.")


def cmd_get(session, args: List[str]) -> None:
    """Picks up one item lying on the ground in the current room
    (dropped via 'drop'), subject to the same inventory stacking caps
    as everything else (inventory.py). Per direct confirmation
    (Section 158): 'get <item> from <backpack>' instead takes an item
    OUT of a real backpack container and into ordinary inventory --
    detected by a literal ' from ' in the args, matching the
    confirmed real command syntax exactly."""
    player = session.player
    if not args:
        session.send("Get what?")
        return

    full_query = " ".join(args).lower()
    if " from " in full_query:
        item_query, _, backpack_query = full_query.partition(" from ")
        _get_from_backpack(session, item_query.strip(), backpack_query.strip())
        return

    room = WORLD.get(player.room_vnum)

    query = full_query
    match = find_indexed_item(query, room.ground_items)
    if not match:
        session.send("You don't see that here.")
        return
    if _has_no_take_flag(match):
        session.send(f"{rarity_colored_name(match)} won't budge -- it's fixed in place.")
        return

    ok, reason = inventory.add_item(player.inventory, match)
    if not ok:
        session.send(inventory.full_message(reason, match))
        return
    room.ground_items.remove(match)
    session.send(f"You pick up {rarity_colored_name(match)}.")


def _find_backpack_position(player, backpack_query: str):
    """Per direct confirmation (Section 158): resolves which real,
    specific backpack a query refers to -- by its own real, current
    position in player.inventory (raw position tracking, a confirmed,
    accepted design). Returns (position, item_name) or (None, None) if
    no real container item matches. A "container" here means any real
    item whose own oset prototype has a genuine container_capacity > 0
    -- confirmed directly this should work for ANY item set up this
    way, not just a fixed, hardcoded "backpack" item."""
    index, keyword = inventory.parse_indexed_query(backpack_query)
    candidates_with_positions = []
    for position, item_name in enumerate(player.inventory):
        if not _item_matches(keyword, item_name):
            continue
        proto = _find_object_prototype_by_name(item_name)
        if proto and proto.get("container_capacity", 0) > 0:
            candidates_with_positions.append((position, item_name))
    if index > len(candidates_with_positions) or index < 1:
        return None, None
    return candidates_with_positions[index - 1]


def cmd_put(session, args: List[str]) -> None:
    """'put <item> in <backpack>' -- per direct confirmation (Section
    158): moves an item from ordinary inventory INTO a real container
    item's own separate contents, which don't count against the
    normal 20-slot inventory cap at all. The backpack itself is
    resolved by its own real, current inventory position (see
    _find_backpack_position) -- raw position tracking, a confirmed,
    accepted design."""
    player = session.player
    full_query = " ".join(args).lower()
    if " in " not in full_query:
        session.send("Usage: put <item> in <backpack>")
        return

    item_query, _, backpack_query = full_query.partition(" in ")
    item_query, backpack_query = item_query.strip(), backpack_query.strip()

    position, backpack_name = _find_backpack_position(player, backpack_query)
    if position is None:
        session.send("You aren't carrying a container by that name.")
        return

    item_index, item_keyword = inventory.parse_indexed_query(item_query)
    item_matches = [i for i, name in enumerate(player.inventory) if _item_matches(item_keyword, name)]
    if item_index > len(item_matches) or item_index < 1:
        session.send("You aren't carrying that.")
        return
    item_position = item_matches[item_index - 1]
    match = player.inventory[item_position]
    if item_position == position:
        session.send("You can't put a container inside itself.")
        return

    proto = _find_object_prototype_by_name(backpack_name)
    capacity = proto.get("container_capacity", 0) if proto else 0
    contents = player.backpack_contents.setdefault(str(position), [])
    if len(contents) >= capacity:
        session.send(f"{rarity_colored_name(backpack_name)} is full.")
        return

    del player.inventory[item_position]
    # If the item removed came BEFORE the backpack in the list, every
    # later real position (including the backpack's own) just shifted
    # down by one -- re-key backpack_contents to the correct, new
    # position, or this backpack's own contents would silently point
    # at the wrong real slot from here on.
    if item_position < position:
        new_position = position - 1
        if str(position) in player.backpack_contents:
            player.backpack_contents[str(new_position)] = player.backpack_contents.pop(str(position))
        position = new_position
    contents = player.backpack_contents.setdefault(str(position), [])
    contents.append(match)
    session.send(f"You put {rarity_colored_name(match)} in {rarity_colored_name(backpack_name)}.")


def _get_from_backpack(session, item_query: str, backpack_query: str) -> None:
    """The real 'get <item> from <backpack>' branch of cmd_get -- see
    cmd_get's own docstring above."""
    player = session.player
    position, backpack_name = _find_backpack_position(player, backpack_query)
    if position is None:
        session.send("You aren't carrying a container by that name.")
        return

    contents = player.backpack_contents.get(str(position), [])
    item_index, item_keyword = inventory.parse_indexed_query(item_query)
    item_matches = [i for i, name in enumerate(contents) if _item_matches(item_keyword, name)]
    if item_index > len(item_matches) or item_index < 1:
        session.send(f"{rarity_colored_name(backpack_name)} doesn't have that.")
        return
    contents_position = item_matches[item_index - 1]
    match = contents[contents_position]

    ok, reason = inventory.add_item(player.inventory, match)
    if not ok:
        session.send(inventory.full_message(reason, match))
        return
    del contents[contents_position]
    session.send(f"You get {rarity_colored_name(match)} from {rarity_colored_name(backpack_name)}.")


def _item_matches(query: str, item_name: str) -> bool:
    """Word-level match: every word in `query` must appear somewhere in
    `item_name`, not necessarily contiguously. Fixes a real bug found
    while adding crafted item names with a stat-bonus suffix: a plain
    `query in item_name` substring check fails for a query that skips a
    middle word -- 'iron rod' is not a contiguous substring of 'an iron
    fishing rod', even though it's an obviously intended match. Used
    everywhere an item is looked up by a player-typed partial name."""
    item_lower = item_name.lower()
    return all(word in item_lower for word in query.lower().split())


def find_indexed_item(query: str, items):
    """Per direct confirmation (Section 158): "a real general
    N.keyword targeting convention...usable anywhere a name is
    currently typed to target an item." Replaces the extremely
    common real pattern "next((item for item in <list> if
    _item_matches(query, item)), None)" -- a real "N." prefix (e.g.
    "2.kunai") returns the Nth match (1-indexed) in `items`, in the
    order given; a bare query with no real "N." prefix still means
    "the first match", exactly matching every existing caller's
    prior behavior. Returns None if there's no match at that index."""
    index, keyword = inventory.parse_indexed_query(query)
    matches = [item for item in items if _item_matches(keyword, item)]
    if index > len(matches) or index < 1:
        return None
    return matches[index - 1]


def _find_object_prototype_by_name(item_name: str):
    """Reverse lookup: player inventory is plain name strings, not
    linked to a vnum, so to find which oset prototype a carried item
    corresponds to (for scroll_jutsu, etc.) we match on short_desc --
    same substring-match convention used everywhere else in this file."""
    query = item_name.lower()
    for proto in olc.OBJECT_TEMPLATES.values():
        if query == proto["short_desc"].lower():
            return proto
    for proto in olc.OBJECT_TEMPLATES.values():
        if query in proto["short_desc"].lower() or proto["short_desc"].lower() in query:
            return proto
    return None


def _find_object_vnum_by_name(item_name: str):
    """Same reverse lookup as _find_object_prototype_by_name, but
    returns the vnum itself (needed to check set_vnums membership)."""
    query = item_name.lower()
    for vnum, proto in olc.OBJECT_TEMPLATES.items():
        if query in proto["short_desc"].lower() or proto["short_desc"].lower() in query:
            return vnum
    return None


def _staff_vnum_suffix(session, item_name: str = None, mob=None) -> str:
    """Per direct user feedback ("imms need to see object vnums and
    mobs not just rooms") -- staff_show_vnums previously only affected
    the room header (see cmd_look). Returns " [vnum N]" for a staff
    member with that config on, or "" otherwise (non-staff, staff with
    it off, or -- for an item -- no matching prototype found at all).
    Exactly one of item_name/mob should be passed."""
    player = session.player
    is_staff = session.account is not None and session.account.staff_level != "player"
    if not is_staff or not player.staff_show_vnums:
        return ""
    if mob is not None:
        return f" &D[vnum {mob.template_vnum}]&x"
    vnum = _find_object_vnum_by_name(item_name)
    return f" &D[vnum {vnum}]&x" if vnum is not None else ""

def equipped_set_bonus_percent(player) -> int:  # player: Player or combat.Mob -- both share the same real .equipment shape
    """Sum of set_bonus_percent, once per DISTINCT completed set, not
    once per piece -- a 3-piece set worth 25% gives +25% total when all
    three are worn, not +75%. Multiple pieces of the same set all
    resolve to the same set (identified by the full group of vnums:
    each piece's own vnum plus its declared set_vnums), so they're only
    counted once; wearing a second, unrelated completed set would add
    its own bonus on top. An item with no set_vnums (the vast majority)
    contributes nothing. Applied to derived combat stats -- see
    derived_stats.py."""
    equipped_vnums = set()
    resolved = []
    for item_name in player.equipment.values():
        vnum = _find_object_vnum_by_name(item_name)
        if vnum is not None:
            equipped_vnums.add(vnum)
            resolved.append(vnum)

    completed_sets = {}  # frozenset of the set's full vnum group -> bonus_percent
    for vnum in resolved:
        proto = olc.OBJECT_TEMPLATES.get(vnum)
        if not proto or not proto.get("set_vnums"):
            continue
        required = {int(v) for v in proto["set_vnums"]}
        full_group = frozenset(required | {vnum})
        if required.issubset(equipped_vnums):
            completed_sets[full_group] = proto.get("set_bonus_percent", 25)
    return sum(completed_sets.values())


def _fire_item_trigger(session, item_name: str, trigger: str) -> None:
    """Fires an item's programs matching `trigger` (wear or get). Looks
    up the item's prototype via the same reverse short_desc match used
    for rarity/scrolls/set bonuses."""
    proto = _find_object_prototype_by_name(item_name)
    if proto and proto.get("item_programs"):
        programs.fire_programs(session, proto["item_programs"], trigger, speaker_name=proto["short_desc"])


CRAFT_BONUS_PATTERN = re.compile(r"\(\+(\d+) ([\w ]+)\)$")


def strip_crafted_suffix(item_name: str) -> str:
    """The base item name with any craft_stat_bonus_suffix stripped
    off (e.g. 'An Iron Fishing Rod (+3 Hitroll)' -> 'An Iron Fishing
    Rod'). Needed anywhere a crafted item's name is looked up against
    a plain, unsuffixed name-keyed dict (fishing.RODS, mining.PICKAXES,
    lumberjack.AXES, farming.HOES, cooking.POTS) -- those dicts only
    know the plain recipe output name and have no reason to know
    about every possible bonus suffix a crafted instance might carry,
    so a suffixed name would otherwise never match at all."""
    return re.sub(r" \(\+\d+ [A-Za-z ]+\)$", "", tool_durability.base_name(item_name))


def craft_stat_bonus_suffix(bonus: int, stat: str = "hitroll") -> str:
    """Bakes a crafted item's stat bonus into its own name text, since
    inventory items are plain strings in this project rather than
    per-instance objects with their own stat fields -- e.g. 'An Iron
    Fishing Rod (+3 Hitroll)'. `stat` names WHICH stat (a recipe's own
    "stat" field -- crafting.py -- so a future crafting job can use a
    different one, e.g. "armor_class" for smithed gear, rendered as
    "Armor Class"). Empty string for a zero bonus, so a plain
    (unenchanted) craft doesn't grow an empty '(+0 Hitroll)' tag."""
    return f" (+{bonus} {stat.replace('_', ' ').title()})" if bonus > 0 else ""


def parse_crafted_bonus(item_name: str, stat_key: str) -> int:
    """The other direction of craft_stat_bonus_suffix -- extracts a
    crafted item's own stat bonus back out of its display name (e.g.
    'An Iron Fishing Rod (+3 Hitroll)' -> 3 for stat_key='hitroll').
    Returns 0 if no matching suffix is present. This is what makes a
    crafted weapon/armor's bonus actually DO something in combat,
    rather than being purely cosmetic text on the item name -- see
    equipped_weapon_hitroll_bonus/equipped_armor_class_bonus below,
    which use this to feed real combat calculations."""
    stat_display = re.escape(stat_key.replace("_", " ").title())
    match = re.search(rf"\(\+(\d+) {stat_display}\)", item_name)
    return int(match.group(1)) if match else 0


def equipped_weapon_hitroll_bonus(player) -> int:  # player: Player or combat.Mob
    """The wielded weapon's Hit Roll bonus, combining two sources: the
    item prototype's own stat_bonuses (set once by a builder via 'oset
    <vnum> statbonus hitroll <n>', shared by every instance of that
    item) plus any legacy '+N Hitroll' text still baked into the
    item's own display name (parse_crafted_bonus) -- kept only for
    backward compatibility with an item a player already owns from
    before crafting stopped generating that suffix, or with rank
    headbands, which still use it for their own progression bonus.
    Added directly to the player's Hit Roll in combat, on top of
    Dexterity's own contribution."""
    wielded = player.equipment.get("wielded", "")
    if not wielded:
        return 0
    proto = _find_object_prototype_by_name(wielded)
    prototype_bonus = proto.get("stat_bonuses", {}).get("hitroll", 0) if proto else 0
    return prototype_bonus + parse_crafted_bonus(wielded, "hitroll")


def equipped_weapon_damroll_bonus(player) -> int:  # player: Player or combat.Mob
    """The wielded weapon's Damage Roll bonus from its item prototype's
    stat_bonuses (set via 'oset <vnum> statbonus damroll <n>') --
    damroll never had an equipment bonus hook of any kind before this,
    unlike hitroll/armor_class. No legacy name-suffix fallback needed
    here since damroll was never one of the stats the old crafting
    suffix supported in the first place."""
    wielded = player.equipment.get("wielded", "")
    if not wielded:
        return 0
    proto = _find_object_prototype_by_name(wielded)
    return proto.get("stat_bonuses", {}).get("damroll", 0) if proto else 0


def equipped_armor_class_bonus(player) -> int:  # player: Player or combat.Mob
    """The sum of every worn armor piece's Armor Class bonus, combining
    two sources per item: the item prototype's own stat_bonuses (set
    via 'oset <vnum> statbonus armor_class <n>') plus any legacy '+N
    Armor Class' text still baked into that item's own display name
    (parse_crafted_bonus) -- kept only for backward compatibility with
    an item a player already owns from before crafting stopped
    generating that suffix, or with rank headbands, which still use it
    for their own progression bonus. Subtracted from the player's
    Armor Class in combat (lower/more negative is better, ROM
    convention), on top of Dexterity's own contribution."""
    total = 0
    for slot, item_name in player.equipment.items():
        if slot == "wielded" or not item_name:
            continue
        proto = _find_object_prototype_by_name(item_name)
        prototype_bonus = proto.get("stat_bonuses", {}).get("armor_class", 0) if proto else 0
        total += prototype_bonus + parse_crafted_bonus(item_name, "armor_class")
    return total


def reduce_weapon_damage(defender, weapon_type: str, damage: int) -> int:
    """Apply each worn armor piece's resistance to the incoming weapon type.

    Multiplying the remaining fractions lets armor stack without simple
    addition exceeding 100%. AC still handles the chance to be hit.
    """
    if not weapon_type or weapon_type not in data_weapons.WEAPON_TYPES or damage <= 0:
        return damage
    remaining, divisor = damage, 1
    for slot, item_name in defender.equipment.items():
        if slot not in olc.ARMOR_WEAR_LOCATIONS or not item_name:
            continue
        proto = _find_object_prototype_by_name(item_name)
        percent = proto.get("weapon_resistances", {}).get(weapon_type, 0) if proto else 0
        if percent:
            remaining *= 100 - max(0, min(100, percent))
            divisor *= 100
    return remaining // divisor


def equipped_weapon_type_damage_bonus(player) -> int:  # player: Player or combat.Mob
    """The wielded item's set base damage, or the weapon type default."""
    wielded = player.equipment.get("wielded", "")
    if not wielded:
        return 0
    proto = _find_object_prototype_by_name(wielded)
    if proto:
        return data_weapons.item_base_damage(proto)
    weapon_type = data_weapons.weapon_type_for_item(wielded)
    return data_weapons.weapon_damage_bonus(weapon_type) if weapon_type else 0


def parse_crafted_stat_bonus(item_name: str, stat: str = "hitroll") -> int:
    """The inverse of craft_stat_bonus_suffix() -- reads the bonus for
    `stat` back out of an item's name text. 0 if the item has no such
    suffix, or its suffix names a different stat."""
    match = CRAFT_BONUS_PATTERN.search(item_name)
    if not match:
        return 0
    amount, matched_stat = match.groups()
    expected_stat_text = stat.replace("_", " ").title()
    if matched_stat != expected_stat_text:
        return 0
    return int(amount)


def parse_crafted_hitroll_bonus(item_name: str) -> int:
    """Thin alias of parse_crafted_stat_bonus for the hitroll case --
    kept since it's the only stat actually wired to matter anywhere
    today (the score sheet's Hit Roll)."""
    return parse_crafted_stat_bonus(item_name, "hitroll")


def rarity_colored_name(item_name: str) -> str:
    """The single shared function for showing an item's name, used
    wherever an item name is shown to a player: inventory, equipment,
    shop listings, buy/wield confirmations, ground items, and so on.
    Per direct confirmation (Section 149): "remove all tags of items
    from common all the way to legendary..just hide them for now or
    they only show when you examine the item" -- this now returns
    the plain, uncolored name everywhere. The real, tagged/colored
    display (a bracketed rarity tag cycling through that tier's own
    colors, e.g. "[Legendary] a legendary blade") still exists, but
    only in cmd_examine's own dedicated view -- see
    _examine_rarity_colored_name below."""
    return item_name


def _examine_rarity_colored_name(item_name: str) -> str:
    """The real, tagged/colored rarity display (Borderlands-style,
    Common -> Legendary) -- confirmed directly (Section 149) to be
    hidden from every OTHER real item display in the game, surfacing
    only here, in cmd_examine's own dedicated view. Shows as a
    bracketed tag at the front -- e.g. '[Legendary] a legendary
    blade' -- with the tier name inside the brackets cycling through
    that tier's own colors, followed by the item name in the tier's
    plain color. Falls back to plain/common (white) if the item has
    no matching oset prototype."""
    proto = _find_object_prototype_by_name(item_name)
    rarity = proto.get("rarity", "common") if proto else "common"
    return f"{data_rarity.colored_tag(rarity)} {data_rarity.color(rarity)}{item_name}&x"


_CHAKRA_PAPER_REACTIONS = {
    "fire": "curls up and bursts into ash in your hand",
    "water": "goes damp and limp, water beading across its surface",
    "wind": "splits cleanly down the middle",
    "earth": "crumbles into fine dust",
    "lightning": "wrinkles and puckers all over",
}


CHAKRA_NATURE_MIN_LEVEL = 50
CHAKRA_NATURE_SECONDARY_MIN_LEVEL = 100


def cmd_channel(session, args: List[str]) -> None:
    """Reveals a player's own hidden chakra nature/natures by
    consuming a Chakra Paper. Confirmed design: a genuinely new,
    dedicated verb (not the existing 'hold', which equips a tool
    persistently rather than consuming it in one action) -- matching
    how 'read' consumes a scroll in a single step. Chakra nature
    itself is purely a personal identity/flavor trait for now (no
    jutsu in the game currently carries an element to interact with
    it) -- revealing it doesn't change anything mechanically, it's
    information the player didn't have before.

    PRIMARY nature (rolled once, secretly, at character creation --
    see session.py's _create_player, and biomes.roll_chakra_nature's
    own docstring): gated to CHAKRA_NATURE_MIN_LEVEL (50), per a
    direct follow-up request -- confirmed the paper is REFUSED, not
    consumed, below that level, so a player who bought one early can
    simply hold onto it and try again once they've actually reached
    the requirement, rather than wasting the purchase on a request
    made too soon.

    SECONDARY nature (Section 84, per direct follow-up request): a
    second, independent Chakra Paper channel, gated to
    CHAKRA_NATURE_SECONDARY_MIN_LEVEL (100) instead -- but ALSO
    requires the primary to already be revealed first, confirmed
    directly rather than assumed, even for a character already well
    past level 100. Rolled fresh at the moment of THIS reveal (see
    biomes.roll_secondary_chakra_nature), guaranteed to differ from
    the primary element with no thematic restriction on which one --
    confirmed design explicitly allows a directly opposing element.
    A character who already has both revealed is told plainly there's
    nothing left to discover, rather than the paper doing anything
    confusing."""
    player = session.player
    if not args:
        session.send("Channel what?")
        return
    query = " ".join(args).lower()
    match = find_indexed_item(query, player.inventory)
    if not match:
        session.send(f"You aren't carrying anything like '{query}'.")
        return

    proto = _find_object_prototype_by_name(match)
    if not proto or "chakra paper" not in match.lower():
        session.send(f"You can't channel chakra into {match}.")
        return

    if player.chakra_nature_revealed and player.chakra_nature_secondary_revealed:
        session.send(
            f"You channel a thread of your own chakra into {match}, but nothing happens -- "
            f"you've already learned everything about your own chakra nature that there is to know."
        )
        return

    revealing_secondary = player.chakra_nature_revealed  # primary already known -> this reveal is the secondary
    min_level = CHAKRA_NATURE_SECONDARY_MIN_LEVEL if revealing_secondary else CHAKRA_NATURE_MIN_LEVEL

    if player.level < min_level:
        session.send(
            f"You channel a thread of your own chakra into {match}, but nothing happens -- "
            f"your own chakra is still too raw and unrefined to reveal anything yet. "
            f"(Requires level {min_level}; you are level {player.level}.)"
        )
        return

    player.inventory.remove(match)

    if revealing_secondary:
        if player.chakra_nature is None:
            # Genuinely shouldn't be reachable (revealing_secondary
            # implies chakra_nature_revealed, which implies a real
            # nature exists) -- defensive fallback only.
            player.chakra_nature = biomes.roll_chakra_nature()
        player.chakra_nature_secondary = biomes.roll_secondary_chakra_nature(player.chakra_nature)
        nature = player.chakra_nature_secondary
        player.chakra_nature_secondary_revealed = True
        reaction = _CHAKRA_PAPER_REACTIONS.get(nature, "reacts, but nothing seems to happen")
        session.send(
            f"You channel a thread of your own chakra into {match}...\n"
            f"The paper {reaction}!\n"
            f"&WYou also carry a second chakra nature: {nature.capitalize()}.&x"
        )
        return

    if player.chakra_nature is None:
        # A character created before chakra nature existed at all --
        # confirmed design: roll one right now, on the spot, using the
        # exact same mechanism chargen itself uses, rather than
        # crashing (nature.capitalize() on a None) or defaulting to a
        # fixed element for everyone in this situation.
        player.chakra_nature = biomes.roll_chakra_nature()
    nature = player.chakra_nature
    reaction = _CHAKRA_PAPER_REACTIONS.get(nature, "reacts, but nothing seems to happen")
    player.chakra_nature_revealed = True
    session.send(
        f"You channel a thread of your own chakra into {match}...\n"
        f"The paper {reaction}!\n"
        f"&WYour chakra nature is {nature.capitalize()}.&x"
    )


def cmd_read(session, args: List[str]) -> None:
    """Learn a jutsu from a scroll (item_type 'scroll' with a
    scroll_jutsu set via oset) -- an alternate way to obtain a jutsu
    beyond the universal starting kit. The scroll is consumed on a
    successful read; a blank (not yet inscribed) scroll or one teaching
    something already known is not consumed."""
    player = session.player
    if not args:
        session.send("Read what?")
        return
    query = " ".join(args).lower()
    match = find_indexed_item(query, player.inventory)
    if not match:
        session.send(f"You aren't carrying anything like '{query}'.")
        return

    proto = _find_object_prototype_by_name(match)
    if not proto or proto.get("item_type") != "scroll":
        session.send(f"You can't read {match}.")
        return

    jutsu_key = proto.get("scroll_jutsu", "")
    if not jutsu_key or jutsu_key not in data_jutsu.JUTSU:
        session.send(f"{match} hasn't been inscribed with a technique yet.")
        return


    jutsu = data_jutsu.JUTSU[jutsu_key]
    display = jutsu["display_name"]
    if display in player.learned_skills:
        session.send(f"You already know {display}.")
        return

    player.learned_skills.append(display)
    player.skill_proficiencies[display] = 0
    player.inventory.remove(match)
    session.send(f"You study {match} carefully... you have learned &Y{display}&x!")


def cmd_eat(session, args: List[str]) -> None:
    consumables.consume(session, "eat", " ".join(args))


def cmd_drink(session, args: List[str]) -> None:
    consumables.consume(session, "drink", " ".join(args))


def cmd_use(session, args: List[str]) -> None:
    consumables.consume(session, "use", " ".join(args))


# --- Corpses / looting ---------------------------------------------------

def cmd_loot(session, args: List[str]) -> None:
    player = session.player
    query = " ".join(args) if args else None
    corpse = corpses.find_corpse(player.room_vnum, query)
    if not corpse:
        session.send("There is nothing here to loot.")
        return
    if corpse.is_empty():
        session.send(f"{corpse.name.capitalize()} has already been picked clean.")
        return

    ryo_taken = corpses.loot_ryo(player, corpse)
    if ryo_taken:
        session.send(f"You loot {ryo_taken} ryo from {corpse.name}.")
    items_taken = corpses.loot_gear(player, corpse)
    for item in items_taken:
        session.send(f"You loot {item} from {corpse.name}.")
    if corpse.items:
        session.send(f"&D(Your inventory is full -- some items are still on {corpse.name}.)&x")


def _has_no_sac_flag(item_name: str) -> bool:
    """True if item_name's own prototype carries the no_sac extra_flag
    -- checked by cmd_sacrifice for both a single named item and 'sac
    all', so a staff member can protect a special/quest item from
    being destroyed this way (oset <vnum> extra_flags no_sac)."""
    proto = _find_object_prototype_by_name(item_name)
    return proto is not None and "no_sac" in proto.get("extra_flags", [])


def _has_no_take_flag(item_name: str) -> bool:
    """True if item_name's own prototype carries the no_take
    extra_flag -- checked by cmd_get, per direct request ("make an
    item flag that doesnt allow players to pick the item up...this
    would be used for cosmetic stuff like furniture or signs and
    plants in the room"). Meant for room decoration placed via 'oset
    load <vnum>' or a registered item spawn point (spawnpoint.py) --
    both already write straight into room.ground_items, so a no_take
    item behaves exactly like any other ground item in every other
    way (visible on 'look', listed among the room's items) except
    that 'get' specifically refuses it."""
    proto = _find_object_prototype_by_name(item_name)
    return proto is not None and "no_take" in proto.get("extra_flags", [])


def cmd_sacrifice(session, args: List[str]) -> None:
    """Destroys a corpse (unchanged, see corpses.py) OR an item lying
    on the ground in the current room, in exchange for a small ryo
    reward -- meant as a way to dispose of anything you can't
    otherwise sell (no shop around, or no shop buys that category),
    not as a substitute for 'sell': an item's own reward is
    deliberately half of what selling it would give
    (item_types.base_sell_price), floored at 1 ryo so a real item
    never sacrifices for literally nothing, same reasoning as the
    existing sell-price floor. Corpses are checked first, matching the
    original behavior exactly; ground items are checked as a fallback
    when no corpse matches. Confirmed design: an item still in your
    OWN inventory is never sacrificeable through this command at all
    -- drop it first (or it must already be on the ground).

    'sacrifice all' (per explicit request) sacrifices everything
    currently in the ROOM instead -- every corpse and every ground
    item, all at once, for their combined ryo reward. This was already
    ground-items-only before this change, so it's completely
    unaffected.

    Per explicit request, items can carry a no_sac extra_flag (set via
    'oset <vnum> extra_flags no_sac') to protect specific special
    items from being sacrificed at all -- checked here for both a
    single named item and 'sacrifice all'. Corpses are unaffected by
    no_sac -- it's an item-prototype flag, and a corpse isn't a
    prototype-backed item."""
    player = session.player

    if args and args[0].lower() == "all":
        room = world.WORLD.get(player.room_vnum)
        sacrificed_count = 0
        skipped_count = 0
        before_ryo = player.ryo

        for corpse in list(corpses.corpses_in_room(player.room_vnum)):
            corpses.sacrifice(player, corpse)
            sacrificed_count += 1

        if room:
            remaining_ground = []
            for item in list(room.ground_items):
                if _has_no_sac_flag(item):
                    remaining_ground.append(item)
                    skipped_count += 1
                    continue
                reward = max(1, item_types.base_sell_price(item) // 2)
                player.ryo += reward
                sacrificed_count += 1
            room.ground_items = remaining_ground

        if sacrificed_count == 0:
            if skipped_count:
                session.send("Everything here is protected from sacrifice.")
            else:
                session.send("There is nothing here to sacrifice.")
            return

        ryo_gained = player.ryo - before_ryo
        msg = f"You sacrifice {sacrificed_count} thing(s) here and receive {ryo_gained} ryo."
        if skipped_count:
            msg += f" ({skipped_count} protected item(s) left untouched.)"
        session.send(msg)
        return

    query = " ".join(args) if args else None
    corpse = corpses.find_corpse(player.room_vnum, query)
    if corpse:
        corpse_name = corpse.name
        forfeited_ryo, forfeited_items = corpses.sacrifice(player, corpse)
        msg = f"You sacrifice {corpse_name} and receive {corpses.SACRIFICE_RYO_REWARD} ryo."
        if forfeited_ryo or forfeited_items:
            parts = []
            if forfeited_ryo:
                parts.append(f"{forfeited_ryo} ryo")
            if forfeited_items:
                parts.append(f"{len(forfeited_items)} item(s)")
            msg += f" ({' and '.join(parts)} still on it were forfeited.)"
        session.send(msg)
        return

    if not args:
        session.send("There is nothing here to sacrifice.")
        return

    room = world.WORLD.get(player.room_vnum)
    item_query = " ".join(args).lower()
    match = find_indexed_item(item_query, room.ground_items) if room else None
    if not match:
        session.send("There is nothing here to sacrifice.")
        return
    if _has_no_sac_flag(match):
        session.send(f"{rarity_colored_name(match)} is too special to sacrifice.")
        return

    reward = max(1, item_types.base_sell_price(match) // 2)
    room.ground_items.remove(match)
    player.ryo += reward
    session.send(f"You sacrifice {rarity_colored_name(match)} and receive {reward} ryo.")


def cmd_purge(session, args: List[str]) -> None:
    """Immortal utility (classic ROM/DIKU command, per explicit
    request): deletes every mob, ground item, and corpse in the
    current room at once -- a cleanup tool for staff, not a
    player-facing command. Mobs removed this way still respawn
    normally later if they're a respawning template
    (combat.remove_mob's own behavior, unchanged) -- purge clears the
    room right now, it doesn't permanently depopulate it. Takes no
    argument -- always targets the room the immortal is currently
    standing in, matching 'rset'/'oset'/'mset's own "current room"
    convention rather than requiring a vnum."""
    if not olc._require_builder(session):
        return

    player = session.player
    room = world.WORLD.get(player.room_vnum)

    mob_count = 0
    for mob in list(combat.mobs_in_room(player.room_vnum)):
        combat.remove_mob(mob)
        mob_count += 1

    corpse_count = 0
    for corpse in list(corpses.corpses_in_room(player.room_vnum)):
        corpses.remove_corpse(corpse)
        corpse_count += 1

    item_count = 0
    if room:
        item_count = len(room.ground_items)
        room.ground_items = []

    session.send(
        f"You purge the room: {mob_count} mob(s), {item_count} item(s), "
        f"and {corpse_count} corpse(s) destroyed in a flash of light."
    )


# --- Player preference config ----------------------------------------------

CONFIG_OPTIONS = {
    "auto_loot_ryo": "Automatically loot ryo from corpses you defeat",
    "auto_loot_gear": "Automatically loot items from corpses you defeat",
    "auto_sac_corpse": "Automatically sacrifice each corpse for 1 ryo (forfeiting anything left un-looted on it)",
    "tips": "Show a periodic tip-of-the-day (every 30 minutes)",
}


def cmd_config(session, args: List[str]) -> None:
    player = session.player
    if not args:
        lines = ["&WYour settings:&x"]
        for key, description in CONFIG_OPTIONS.items():
            state = "&Gon&x" if getattr(player, key) else "&Doff&x"
            lines.append(f"  {key:16s} [{state}]  {description}")
        lines.append("Usage: config <name> on|off")
        session.send("\n".join(lines))
        return

    if len(args) != 2 or args[0].lower() not in CONFIG_OPTIONS or args[1].lower() not in ("on", "off"):
        session.send("Usage: config <" + "|".join(CONFIG_OPTIONS.keys()) + "> on|off")
        return

    key = args[0].lower()
    value = args[1].lower() == "on"
    setattr(player, key, value)
    session.send(f"{key} is now {'on' if value else 'off'}.")


STAFF_CONFIG_OPTIONS = {
    "staff_show_vnums": "Show room vnum/flags in the room header (off gives you a player's-eye view)",
    "staff_notify_reports": "Get a live ping when a player submits a bug report ('report')",
    "staff_notify_ideas": "Get a live ping when a player submits an idea ('idea')",
}


def force_all_player_configs_on() -> int:
    """Called once from main.py at every server start, per direct user
    request ("yes every player config should be on at start"). Forces
    every regular player CONFIG_OPTIONS field on for every saved
    character (not just online ones -- this reads every save file, an
    acceptable one-time startup cost, same as world.
    reconcile_apartment_ownership already does). A player can still
    turn any of them back off during their session with 'config
    <name> off' -- this only resets the starting state each time the
    server (re)starts, it doesn't lock them on. Deliberately leaves
    STAFF_CONFIG_OPTIONS untouched -- that's a separate set staff
    manage themselves, not part of what was asked to be forced.
    Returns how many player files were actually changed (0 if
    everyone was already fully on)."""
    changed = 0
    for player in storage.all_players():
        needs_save = False
        for key in CONFIG_OPTIONS:
            if not getattr(player, key):
                setattr(player, key, True)
                needs_save = True
        if needs_save:
            storage.save_player(player)
            changed += 1
    return changed


def cmd_staffconfig(session, args: List[str]) -> None:
    """Staff's own, separate config set (STAFF_CONFIG_OPTIONS) --
    distinct from the regular player config command above, per direct
    user request ("staff should have there own configs")."""
    if not olc._require_builder(session):
        return
    player = session.player
    if not args:
        lines = ["&WYour staff settings:&x"]
        for key, description in STAFF_CONFIG_OPTIONS.items():
            state = "&Gon&x" if getattr(player, key) else "&Doff&x"
            lines.append(f"  {key:20s} [{state}]  {description}")
        lines.append("Usage: staffconfig <name> on|off")
        session.send("\n".join(lines))
        return

    if len(args) != 2 or args[0].lower() not in STAFF_CONFIG_OPTIONS or args[1].lower() not in ("on", "off"):
        session.send("Usage: staffconfig <" + "|".join(STAFF_CONFIG_OPTIONS.keys()) + "> on|off")
        return

    key = args[0].lower()
    value = args[1].lower() == "on"
    setattr(player, key, value)
    session.send(f"{key} is now {'on' if value else 'off'}.")


def _resource_row(label1, color1, cur1, max1, label2="", color2="", cur2=0, max2=0, width=40):
    left_plain = f" {label1}: {cur1} / {max1}"
    pad = " " * max(1, width - len(left_plain))
    left = f" {color1}{label1}: {cur1} / {max1}&x{pad}"
    if not label2:
        return left
    return left + f"{color2}{label2}: {cur2} / {max2}&x"


def _row(label1, val1, label2="", val2="", width=40):
    """Two-column row helper: pads on the PLAIN text length (before color
    codes are added) so columns still line up once colors.render() swaps
    &-codes for invisible ANSI escapes."""
    left_plain = f" {label1}: {val1}"
    pad = " " * max(1, width - len(left_plain))
    left = f" &W{label1}:&x &C{val1}&x{pad}"
    if not label2:
        return left
    return left + f"&W{label2}:&x &C{val2}&x"


def _section(title: str, width: int = 78) -> str:
    return f"&W{'-' * width}&x\n&C{title.center(width)}&x\n&W{'-' * width}&x"


def _format_playtime(total_seconds: float) -> str:
    total_minutes = int(total_seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} hour(s) {minutes} minute(s)"
    if hours:
        return f"{hours} hour(s)"
    return f"{minutes} minute(s)"


def _format_active_effects(effects: dict) -> str:
    """One-line, comma-joined display of every active status effect
    with its remaining duration, same format score's own sheet
    already used before this was extracted -- shared so 'score' and
    the new 'aff' command (see cmd_aff below) can't drift apart."""
    if not effects:
        return "&Gnone&x"
    effect_strs = []
    for name, data in effects.items():
        display = status_effects.EFFECT_DEFS.get(name, {}).get("display_name", name.title())
        effect_strs.append(f"&R{display}&x (&C{data['duration']}&x pulse(s) left)")
    return ", ".join(effect_strs)


def build_score_lines(p, fighting_name: str, target_staff_level: Optional[str] = None) -> List[str]:
    """The full character-score display, built from an arbitrary Player
    object rather than tied to a live session -- lets both `score`
    (the player's own session) and `mstat <player name>` (an immortal
    inspecting anyone, online or offline) share the exact same sheet."""
    width = 78
    hp_color = colors.resource_color(p.health, p.maximum_health)
    ch_color = colors.resource_color(p.chakra, p.maximum_chakra)
    st_color = colors.resource_color(p.stamina, p.maximum_stamina)
    next_xp = leveling.xp_for_next_level(p.level)
    set_bonus = equipped_set_bonus_percent(p)
    stats = derived_stats.compute_all(p, set_bonus)
    tool_item = p.equipment.get("tool")
    if tool_item:
        stats["hit_roll"] += parse_crafted_hitroll_bonus(tool_item)
    stats["hit_roll"] += equipped_weapon_hitroll_bonus(p)
    stats["damage_roll"] += equipped_weapon_damroll_bonus(p)
    stats["armor_class"] -= equipped_armor_class_bonus(p)
    village_full_name = VILLAGES[p.village]["village_name"]

    lines = [
        "&W" + "=" * width + "&x",
        f"&C{f'{config.MUD_NAME.upper()} CHARACTER SCORE'.center(width)}&x",
        "&W" + "=" * width + "&x",
        "",
        _row("Name", p.name, "Village", village_full_name),
        _row("Rank", p.village_rank.title(), "Clan", data_clans.display_name(p.clan)),
        _row("Level", p.level, "Class", p.primary_class.capitalize()),
        _row("Experience", p.experience, "Next Level", next_xp),
        _row("Ryo", p.ryo, "Age", p.age),
        _row("Sex", data_appearance.sex_display(p.sex), "Skin Tone", data_appearance.skin_tone_display(p.skin_tone)),
        _row("Hair Color", data_appearance.hair_color_display(p.hair_color), "Eye Color", data_appearance.eye_color_display(p.eye_color)),
        _row("Build", data_appearance.build_display(p.build), "Personality", data_appearance.personality_trait_display(p.personality_trait)),
        _row("Total Play Time", _format_playtime(p.total_play_seconds)),
    ]
    if p.chakra_nature_revealed:
        if p.chakra_nature_secondary_revealed:
            lines.append(_row("Chakra Nature", p.chakra_nature.capitalize(), "Secondary Nature", p.chakra_nature_secondary.capitalize()))
        else:
            lines.append(_row("Chakra Nature", p.chakra_nature.capitalize()))
    lines += [
        "",
        _section("COMBAT INFORMATION"),
        "",
        _resource_row("Health", hp_color, p.health, p.maximum_health, "Chakra", ch_color, p.chakra, p.maximum_chakra),
        f" {st_color}Stamina: {p.stamina} / {p.maximum_stamina}&x",
        "",
        _row("Armor Class", stats["armor_class"], "Hit Roll", f"+{stats['hit_roll']}" if stats["hit_roll"] >= 0 else stats["hit_roll"]),
        _row("Damage Roll", f"+{stats['damage_roll']}" if stats["damage_roll"] >= 0 else stats["damage_roll"], "Initiative", f"+{stats['initiative']}" if stats["initiative"] >= 0 else stats["initiative"]),
        _row("Dodge Chance", f"{stats['dodge_chance']}%", "Critical Chance", f"{stats['critical_chance']}%"),
        "",
        _row("Position", p.position.title(), "Fighting", fighting_name),
        _row("Player Kills", p.player_kills, "Player Deaths", p.player_deaths),
    ]
    if set_bonus:
        lines.append(f" &Y(Armor set bonus active: +{set_bonus}% to the stats above)&x")
    lines += [
        "",
        _section("ATTRIBUTES"),
        "",
        _row("Strength", p.strength, "Wisdom", p.wisdom),
        _row("Constitution", p.constitution, "Intelligence", p.intelligence),
        _row("Dexterity", p.dexterity, "Luck", p.luck),
        _row("Perception", p.perception, "Willpower", p.willpower),
        _row("Chakra Control", p.chakra_control),
        _row("Practice Points", p.practice_points, "Training Points", p.training_points),
        "",
        _section("MISSION INFO"),
        "",
    ]

    if target_staff_level and target_staff_level != "player":
        lines.insert(3, f" &M[{target_staff_level.title()}]&x")

    if p.active_status_effects:
        lines.append(" &WActive effects:&x " + _format_active_effects(p.active_status_effects))
    else:
        lines.append(" &WActive effects:&x &Gnone&x")

    if p.active_missions:
        mission_strs = []
        for entry in p.active_missions:
            m = missions._find_mission(entry["mission_id"])
            if m:
                mission_strs.append(f"&Y{m['title']}&x (&C{entry['progress']}/{m['target_count']}&x)")
        lines.append(" &WActive missions:&x " + "; ".join(mission_strs))
    else:
        lines.append(" &WActive missions:&x &Dnone&x")

    rank_counts = missions.completed_counts_by_rank(p)
    total_completed = sum(rank_counts.values())
    if total_completed:
        rank_str = "  ".join(f"&W{rank}:&x &C{count}&x" for rank, count in rank_counts.items() if count > 0)
        lines.append(f" &WMissions completed:&x &C{total_completed}&x total -- {rank_str}")
    else:
        lines.append(" &WMissions completed:&x &C0&x")

    rep = p.village_reputation.get(p.village, 0)
    rep_color = "&G" if rep > 0 else ("&R" if rep < 0 else "&W")
    lines.append(f" &WReputation with {village_full_name}:&x {rep_color}{rep}&x")
    lines.append("")
    lines.append("&W" + "=" * width + "&x")
    return lines


def cmd_score(session, args: List[str]) -> None:
    p = session.player
    fighting = session.combat_target.name if session.combat_target else "Nobody"
    target_staff_level = session.account.staff_level if session.account else None
    lines = build_score_lines(p, fighting, target_staff_level)
    session.send("\n".join(lines))


def build_jobs_lines(p, width: int = 78) -> List[str]:
    """Every registered job (jobs.JOB_NAMES), shown even at level 1/0
    xp -- a player who has never fished still sees Fishing listed, not
    an empty page, matching the request to show every job "even if
    they have zero levels." Reuses the score sheet's own _section/_row
    helpers so this reads as a companion sheet, not a different style
    bolted on next to it."""
    lines = [
        "&W" + "=" * width + "&x",
        f"&C{'JOB LEVELS'.center(width)}&x",
        "&W" + "=" * width + "&x",
        "",
        _section("JOBS"),
        "",
    ]
    for job in jobs.JOB_NAMES:
        if job in jobs.HIDDEN_JOBS:
            continue
        level = jobs.get_job_level(p, job)
        xp = jobs.get_job_xp(p, job)
        next_xp = jobs.job_xp_for_level(level + 1) if level < jobs.MAX_JOB_LEVEL else xp
        lines.append(_row(f"{job.capitalize()} Level", level, f"{job.capitalize()} XP", f"{xp}/{next_xp}"))
    lines += ["", "&W" + "=" * width + "&x"]
    return lines


def cmd_jobs(session, args: List[str]) -> None:
    session.send("\n".join(build_jobs_lines(session.player)))


def cmd_prompt(session, args: List[str]) -> None:
    player = session.player
    if not args:
        session.send(f"Current prompt format: {player.prompt_string or PRESETS['default']}")
        return
    arg = args[0].lower()
    if arg == "help":
        session.send(
            "Usage: prompt <preset|off|default|custom format>\n"
            "Presets: " + ", ".join(PRESETS.keys()) + "\n"
            "Tokens: %h %H %c %C %s %S %x %X %q %r %m %l %v %k %p %e"
        )
        return
    if arg == "off":
        player.prompt_string = "off"
        session.send("Prompt disabled.")
        return
    if arg in PRESETS:
        player.prompt_string = PRESETS[arg]
        session.send(f"Prompt set to the '{arg}' preset.")
        return
    player.prompt_string = " ".join(args)
    session.send("Prompt format updated.")


def cmd_password(session, args: List[str]) -> None:
    if len(args) != 2:
        session.send("Usage: password <old password> <new password>")
        return
    old_pw, new_pw = args
    account = session.account
    if not security.verify_password(old_pw, account.salt_hex, account.hash_hex):
        session.send("Your old password was incorrect.")
        return
    ok, reason = security.validate_new_password(
        new_pw, session.player.name,
        previous_hash=tuple(account.previous_hash) if account.previous_hash else None,
    )
    if not ok:
        session.send(reason)
        return
    account.previous_hash = [account.salt_hex, account.hash_hex]
    account.salt_hex, account.hash_hex = security.hash_password(new_pw)
    account.forced_reset = False
    storage.save_account(account)
    session.send("Password changed.")


def cmd_quit(session, args: List[str]) -> None:
    storage.save_player(session.player)
    session.send("Saving and disconnecting. Farewell, ninja.")
    session.request_close()


def cmd_save(session, args: List[str]) -> None:
    if args and args[0].lower() == "world":
        cmd_save_world(session, args[1:])
        return
    storage.save_player(session.player)
    session.send("Saved.")


def cmd_save_world(session, args: List[str]) -> None:
    """'save world' -- Implementor-only, per direct request ("how do
    we make it so when you package up the newest version it does not
    effect area files ever again so i can start 'building' the mud").
    Writes a full snapshot of every room/mob/item CURRENTLY live in
    memory to disk (world_persistence.save_world -- see that module's
    own docstring for the 3 confirmed design decisions this rests on:
    a full snapshot rather than additions-only, saved data always
    winning on restart, and this being a deliberate manual command
    rather than an autosave). From this point on, EVERY future server
    restart -- whether from a crash, a reboot, or deploying a newly
    packaged version of the code -- loads this exact saved state back
    in, on top of whatever content.py itself would otherwise build,
    rather than losing anything built or edited since the code was
    last written. Gated to implementor, matching 'reboot's own
    precedent -- this is a genuinely high-impact command, not an
    ordinary builder-level edit, since it permanently determines what
    every future restart loads from here on. Dispatched from cmd_save
    itself ("save world") rather than a separate top-level command,
    since "save" was already a registered single-word verb that would
    otherwise silently swallow the "world" argument and just re-save
    the player's own character instead."""
    if not session.account or session.account.staff_level != "implementor":
        session.send("You don't have access to that.")
        return

    import world_persistence
    counts = world_persistence.save_world()
    session.send(
        f"World saved: {counts['rooms']} room(s), {counts['mobs']} mob(s), {counts['items']} item(s). "
        f"This exact state will be restored on every future restart from here on."
    )


def _reboot_process() -> None:
    """The actual process replacement -- split out from cmd_reboot so
    a test can monkeypatch just this piece and verify the save/warn
    logic ran correctly beforehand, without actually terminating the
    test process. Re-execs the exact same command line in place
    (os.execv), which restarts the server whether or not it's running
    under an external supervisor like systemd -- unlike just exiting,
    which only comes back on its own if something like systemd's
    Restart=on-failure is watching for it."""
    import os
    import sys
    os.execv(sys.executable, [sys.executable] + sys.argv)


def cmd_reboot(session, args: List[str]) -> None:
    """Implementor-only: saves every connected player, warns everyone,
    then restarts the whole server process in place. Restricted to the
    single highest staff tier given the severity -- this affects every
    connected player, not just the one running the command."""
    if not session.account or session.account.staff_level != "implementor":
        session.send("You don't have access to that.")
        return

    from session import ACTIVE_SESSIONS
    for other in list(ACTIVE_SESSIONS):
        other.send("&R*** The MUD is rebooting now -- please reconnect in a few seconds. ***&x")
        if other.player:
            storage.save_player(other.player)

    _reboot_process()


def cmd_changes(session, args: List[str]) -> None:
    import changelog
    lines = ["&WChangelog (newest first):&x"]
    for version, summary in reversed(changelog.CHANGELOG):
        lines.append(f"  &C{version}&x - {summary}")
    session.send_paginated("\n".join(lines))


def _format_leaderboard_value(category: str, value: int) -> str:
    if category == "playtime":
        hours, minutes = divmod(int(value) // 60, 60)
        return f"{hours}h {minutes}m"
    return f"{value:,}"


def cmd_leaderboard(session, args: List[str]) -> None:
    import leaderboards

    if not args:
        lines = ["&WLeaderboard categories:&x"]
        for key, (display_name, _) in leaderboards.CATEGORIES.items():
            lines.append(f"  &C{key}&x - {display_name}")
        lines.append("Usage: leaderboard <category>")
        session.send("\n".join(lines))
        return

    category = args[0].lower()
    if category not in leaderboards.CATEGORIES:
        session.send(
            f"'{category}' isn't a leaderboard category. Valid: "
            + ", ".join(sorted(leaderboards.CATEGORIES.keys()))
        )
        return

    display_name, _ = leaderboards.CATEGORIES[category]
    entries = leaderboards.top(category)
    lines = [f"&W=== {display_name} ===&x"]
    if not entries:
        lines.append("  Nobody has any record here yet.")
    else:
        for rank, (name, value) in enumerate(entries, start=1):
            lines.append(f"  &Y{rank:>2}.&x {name.ljust(16)} {_format_leaderboard_value(category, value)}")
    session.send("\n".join(lines))


def cmd_bingobook(session, args: List[str]) -> None:
    """The Bingo Book -- lists every posted bounty, grouped by village,
    showing whether the viewing player has already claimed each one.
    Open to any player; posting/removing entries is a staff-only
    'bounty' command below."""
    import bounties

    player = session.player
    all_entries = bounties.all_bounties()
    if not all_entries:
        session.send("&DThe Bingo Book is empty. No bounties have been posted.&x")
        return

    lines = ["&r=== THE BINGO BOOK ===&x"]
    for village in sorted(bounties.VILLAGE_ID_RANGES.keys()):
        village_entries = {
            bid: e for bid, e in all_entries.items() if e["village"] == village
        }
        if not village_entries:
            continue
        village_full_name = VILLAGES.get(village, {}).get("village_name", village.title())
        lines.append(f"&W-- {village_full_name} --&x")
        for bid in sorted(village_entries.keys(), key=int):
            entry = village_entries[bid]
            if bounties.target_type_of(entry) == "player":
                target_name = f"{entry['target_player']} &D(player)&x"
                if entry.get("posted_by"):
                    target_name += f" &D-- posted by {entry['posted_by']}&x"
            else:
                mob_proto = combat.MOB_TEMPLATES.get(entry["mob_vnum"])
                target_name = mob_proto["short_desc"] if mob_proto else f"(vnum {entry['mob_vnum']}, missing)"
            claimed_tag = " &G[CLAIMED]&x" if player.name in entry["claimed_by"] else ""
            reward_bits = []
            if entry["reward_ryo"]:
                reward_bits.append(f"{entry['reward_ryo']:,} ryo")
            if entry["reward_mission_points"]:
                reward_bits.append(f"{entry['reward_mission_points']} mission point(s)")
            reward_text = " + ".join(reward_bits) if reward_bits else "no reward set"
            lines.append(f"  &Y#{bid}&x {target_name} -- {entry['description']} ({reward_text}){claimed_tag}")
    session.send("\n".join(lines))


def cmd_bounty(session, args: List[str]) -> None:
    """Staff-only: post or remove a Bingo Book bounty on a mob
    prototype or a player. IDs are auto-assigned within the target
    village's fixed block (bounties.VILLAGE_ID_RANGES) -- the mob's
    own village theme, or the target player's own village. Unlike the
    player-facing 'place bounty' command, this requires no payment and
    isn't subject to the same-village restriction."""
    if not olc._require_builder(session):
        return
    import bounties

    usage = (
        "Usage: bounty create mob <mob vnum> <village> <reward_ryo> <reward_mission_points> <description...>\n"
        "       bounty create player <name> <reward_ryo> <reward_mission_points> <description...>\n"
        "       bounty remove <id>\n"
        f"Villages: {', '.join(sorted(bounties.VILLAGE_ID_RANGES.keys()))}"
    )
    if not args or args[0].lower() not in ("create", "remove"):
        session.send(usage)
        return

    sub = args[0].lower()
    if sub == "remove":
        if len(args) != 2 or not args[1].isdigit():
            session.send("Usage: bounty remove <id>")
            return
        if bounties.remove_bounty(int(args[1])):
            session.send(f"Bounty #{args[1]} removed from the Bingo Book.")
        else:
            session.send(f"No bounty #{args[1]} exists.")
        return

    # create
    if len(args) < 2 or args[1].lower() not in ("mob", "player"):
        session.send(usage)
        return
    target_kind = args[1].lower()

    if target_kind == "mob":
        if len(args) < 7 or not args[2].isdigit() or not args[4].isdigit() or not args[5].isdigit():
            session.send(usage)
            return
        mob_vnum, village, reward_ryo, reward_mp = int(args[2]), args[3].lower(), int(args[4]), int(args[5])
        description = " ".join(args[6:])

        if mob_vnum not in combat.MOB_TEMPLATES:
            session.send(f"No mobile prototype {mob_vnum} exists.")
            return
        if village not in bounties.VILLAGE_ID_RANGES:
            session.send(f"'{village}' isn't a valid village. Choose one of: {', '.join(sorted(bounties.VILLAGE_ID_RANGES.keys()))}")
            return

        bounty_id = bounties.create_bounty("mob", mob_vnum, village, reward_ryo, reward_mp, description)
        if bounty_id is None:
            session.send(f"'{village}'s Bingo Book block is completely full -- no ID available.")
            return
        session.send(f"Bounty #{bounty_id} posted on {combat.MOB_TEMPLATES[mob_vnum]['short_desc']}.")
        return

    # create player
    if len(args) < 6 or not args[3].isdigit() or not args[4].isdigit():
        session.send(usage)
        return
    target_name, reward_ryo, reward_mp = args[2].capitalize(), int(args[3]), int(args[4])
    description = " ".join(args[5:])

    if not storage.player_exists(target_name):
        session.send(f"No character named '{target_name}' exists.")
        return
    target_player = storage.load_player(target_name)
    village = target_player.village

    bounty_id = bounties.create_bounty("player", target_name, village, reward_ryo, reward_mp, description)
    if bounty_id is None:
        session.send(f"'{village}'s Bingo Book block is completely full -- no ID available.")
        return
    session.send(f"Bounty #{bounty_id} posted on {target_name}.")


def cmd_territory(session, args: List[str]) -> None:
    """Shows every capture point (any room flagged CapturePoint --
    see 'rset flags CapturePoint'), its owner and garrison, the
    current war window status, and your own village's treasury."""
    import territory
    import world

    player = session.player
    points = territory.all_capture_point_vnums()

    window = territory.war_window_status()
    if window["active"]:
        remaining = int(window["ends_at"] - time.time())
        window_text = f"&r*** WAR WINDOW ACTIVE *** &x({remaining // 60}m {remaining % 60}s remaining)"
    elif window["starts_at"]:
        until = int(window["starts_at"] - time.time())
        hours, minutes = until // 3600, (until % 3600) // 60
        window_text = f"&YNext war window in ~{hours}h {minutes}m.&x"
    else:
        window_text = "&DNo war window scheduled yet.&x"

    lines = [window_text, f"&WYour village treasury:&x {territory.treasury_balance(player.village):,} ryo", ""]

    if not points:
        lines.append("No capture points exist yet.")
    else:
        lines.append("&WCapture points:&x")
        for vnum in points:
            room = world.WORLD.get(vnum)
            room_name = room.name if room else f"room {vnum}"
            point = territory.point_state(vnum)
            owner_text = point["owner"].capitalize() if point["owner"] else "&Dunclaimed&x"
            income = territory.point_income(vnum)
            garrison_text = f"{len(point['garrison'])}/{territory.MAX_GARRISON_PER_POINT} garrisoned"
            contest_text = ""
            if point["contested_by"]:
                remaining = int(territory.HOLD_DURATION_SECONDS - (time.time() - point["hold_started_at"]))
                contest_text = f" &r-- being captured by {point['contested_by'].capitalize()} ({remaining}s left)&x"
            lines.append(
                f"  {room_name} (vnum {vnum}) -- owner: {owner_text}, {garrison_text}, "
                f"{income} ryo/tick{contest_text}"
            )
    session.send("\n".join(lines))


def cmd_garrison(session, args: List[str]) -> None:
    """'garrison buy <tier>' -- stations a new defense mob at the
    capture point you're standing in, funded by your village's shared
    treasury. Requires being that village's Kage (the official
    village leader, since this spends communal funds, not your own --
    see 'help setkage') and standing at a point your own village
    currently owns."""
    import territory

    player = session.player
    if player.village_rank != "kage":
        session.send("Only your village's Kage can spend the village treasury on defenses.")
        return
    if not args or args[0].lower() != "buy" or len(args) != 2:
        session.send(f"Usage: garrison buy <tier>\nTiers: {', '.join(territory.GARRISON_TIER_ORDER)}")
        return

    tier = args[1].lower()
    error = territory.buy_garrison(player.village, player.room_vnum, tier)
    if error:
        session.send(error)
        return

    tier_info = territory.GARRISON_TIERS[tier]
    session.send(
        f"You pay {tier_info['cost']:,} ryo from the village treasury. "
        f"A {tier_info['display_name']} takes up position to defend this point."
    )
    session.broadcast_room(f"{player.name} summons a {tier_info['display_name']} to defend this point!", exclude_self=True)


def cmd_trap(session, args: List[str]) -> None:
    """'trap buy <type>' -- places a trap in the room you're standing
    in, funded by your village's shared treasury. Requires being that
    village's Kage (same reasoning as 'garrison buy') and standing
    within 1-2 rooms of a capture point your own village currently
    owns -- traps guard the approach, not the point itself."""
    import territory

    player = session.player
    if player.village_rank != "kage":
        session.send("Only your village's Kage can spend the village treasury on defenses.")
        return
    if not args or args[0].lower() != "buy" or len(args) != 2:
        session.send(f"Usage: trap buy <type>\nTypes: {', '.join(territory.TRAP_TYPES.keys())}")
        return

    trap_type = args[1].lower()
    error = territory.buy_trap(player.village, player.room_vnum, trap_type)
    if error:
        session.send(error)
        return

    trap_info = territory.TRAP_TYPES[trap_type]
    session.send(f"You pay {trap_info['cost']:,} ryo from the village treasury. A {trap_info['display_name']} is set here.")


def cmd_report(session, args: List[str]) -> None:
    """'report <message>' -- logs a bug report to a running text file
    (data/bug_reports/reports.txt) that staff can read directly,
    outside the game. Open to any player, anywhere, anytime -- no
    location or rank gating, since a bug report should be as
    frictionless to file as possible."""
    message = " ".join(args).strip()
    if not message:
        session.send("Usage: report <what went wrong>")
        return

    player = session.player
    storage.append_bug_report(player.name, player.village, player.room_vnum, message)
    session.send("Thanks -- your report has been logged for staff to review.")

    for s in session.active_sessions():
        if (s is not session and s.player and s.account and s.account.staff_level != "player"
                and s.player.staff_notify_reports):
            s.send(f"&Y*** Bug report from {player.name}: {message}&x")
            s.send_prompt()


def cmd_idea(session, args: List[str]) -> None:
    """'idea <suggestion>' -- logs a player suggestion to a running
    text file (data/ideas/ideas.txt) that staff can read directly,
    outside the game. Genuinely a copy of cmd_report's own structure,
    per direct request ("like the buigs command create a copy of it
    just make it ideas command so players can submit ideas") -- open
    to any player, anywhere, anytime, no location or rank gating,
    same reasoning as bug reports: as frictionless to file as
    possible. Uses its own, genuinely SEPARATE live-notify toggle
    (player.staff_notify_ideas) from bug reports, per direct
    confirmation, so staff can turn one off without the other."""
    message = " ".join(args).strip()
    if not message:
        session.send("Usage: idea <your suggestion>")
        return

    player = session.player
    storage.append_idea(player.name, player.village, player.room_vnum, message)
    session.send("Thanks -- your idea has been logged for staff to review.")

    for s in session.active_sessions():
        if (s is not session and s.player and s.account and s.account.staff_level != "player"
                and s.player.staff_notify_ideas):
            s.send(f"&Y*** Idea from {player.name}: {message}&x")
            s.send_prompt()


def cmd_bank(session, args: List[str]) -> None:
    """'bank' shows your balance from anywhere. 'bank deposit <n>' /
    'bank withdraw <n>' require standing at a mob flagged "Banker" --
    a small amount of interest (see bank.py) is applied lazily
    whenever you interact with your balance in any way, including just
    checking it."""
    import bank

    player = session.player

    if not args:
        bank.apply_interest(player)
        session.send(
            f"&WOn hand:&x {player.ryo:,} ryo\n"
            f"&WBanked:&x {player.bank_balance:,} ryo"
        )
        return

    sub = args[0].lower()
    if sub not in ("deposit", "withdraw") or len(args) != 2 or not args[1].isdigit():
        session.send("Usage: bank\n       bank deposit <amount>\n       bank withdraw <amount>")
        return

    room_mobs = combat.mobs_in_room(player.room_vnum)
    has_banker = any(
        "Banker" in combat.MOB_TEMPLATES.get(mob.template_vnum, {}).get("act_flags", [])
        for mob in room_mobs
    )
    if not has_banker:
        session.send("There's no banker here to do that.")
        return

    amount = int(args[1])
    if sub == "deposit":
        error = bank.deposit(player, amount)
        if error:
            session.send(error)
            return
        session.send(f"You deposit {amount:,} ryo. Banked: {player.bank_balance:,} ryo.")
    else:
        error = bank.withdraw(player, amount)
        if error:
            session.send(error)
            return
        session.send(f"You withdraw {amount:,} ryo. Banked: {player.bank_balance:,} ryo.")


def cmd_place(session, args: List[str]) -> None:
    """'place bounty <player> <reward_ryo> <reward_mission_points>
    <description...>' -- posts a player bounty to the Bingo Book, in
    person at a mob flagged "BountyOffice" (see act_flags). Unlike the
    staff-only 'bounty create', this requires the poster to pay the
    full reward up front (deducted immediately, refused if they can't
    afford it -- otherwise this would be a free way to spam bounties),
    and enforces a hard failsafe, per explicit request: a bounty can
    never be placed on a fellow villager -- bounties are for rival-
    village ninja, not internal betrayal."""
    player = session.player
    usage = "Usage: place bounty <player name> <reward_ryo> <reward_mission_points> <description...>"
    if len(args) < 2 or args[0].lower() != "bounty":
        session.send(usage)
        return

    room = world.WORLD.get(player.room_vnum)
    room_mobs = combat.MOBS_BY_ROOM.get(player.room_vnum, [])
    has_bounty_office = any(
        "BountyOffice" in combat.MOB_TEMPLATES.get(mob.template_vnum, {}).get("act_flags", [])
        for mob in room_mobs
    )
    if not has_bounty_office:
        session.send("There's no Bingo Book office here to place a bounty at.")
        return

    if len(args) < 5 or not args[2].isdigit() or not args[3].isdigit():
        session.send(usage)
        return
    target_name = args[1].capitalize()
    reward_ryo, reward_mp = int(args[2]), int(args[3])
    description = " ".join(args[4:])

    if reward_ryo <= 0 and reward_mp <= 0:
        session.send("The reward has to be at least 1 ryo or 1 mission point.")
        return
    if target_name == player.name:
        session.send("You can't place a bounty on yourself.")
        return
    if not storage.player_exists(target_name):
        session.send(f"No character named '{target_name}' exists.")
        return

    import bounties
    target_player = storage.load_player(target_name)
    if target_player.village == player.village:
        session.send(
            f"You can't place a bounty on a fellow {VILLAGES[player.village]['village_name']} ninja."
        )
        return

    if player.ryo < reward_ryo:
        session.send(f"You need {reward_ryo:,} ryo to fund that reward -- you have {player.ryo:,}.")
        return
    if player.mission_points < reward_mp:
        session.send(f"You need {reward_mp} mission point(s) to fund that reward -- you have {player.mission_points}.")
        return

    player.ryo -= reward_ryo
    player.mission_points -= reward_mp

    bounty_id = bounties.create_bounty(
        "player", target_name, target_player.village, reward_ryo, reward_mp, description, posted_by=player.name
    )
    if bounty_id is None:
        # Refund -- the block being completely full is a genuine, if
        # unlikely, failure after payment was already taken.
        player.ryo += reward_ryo
        player.mission_points += reward_mp
        session.send(f"'{target_player.village}'s Bingo Book block is completely full -- no ID available.")
        return

    session.send(
        f"&r*** BOUNTY POSTED (#{bounty_id}) ***&x\n"
        f"You place a bounty on {target_name} for {description}. "
        f"Reward: {reward_ryo:,} ryo and {reward_mp} mission point(s)."
    )


def cmd_commands(session, args: List[str]) -> None:
    """Lists every registered command verb -- player and staff/immortal
    alike, in one combined list -- three columns wide. Movement
    (north/south/etc. and their n/s/e/w/u/d shorthand) is handled
    outside the COMMANDS dict, so it's called out separately."""
    names = sorted(set(COMMANDS.keys()))
    col_width = max(len(name) for name in names) + 2
    per_column = (len(names) + 2) // 3  # split into 3 roughly-even columns
    columns = [names[i:i + per_column] for i in range(0, len(names), per_column)]

    lines = ["&WMovement:&x north/south/east/west/up/down/northeast/northwest/southeast/southwest "
             "(n/s/e/w/u/d/ne/nw/se/sw)", "", "&WCommands:&x"]
    for row in range(max(len(col) for col in columns)):
        parts = []
        for col in columns:
            if row < len(col):
                parts.append(col[row].ljust(col_width))
        lines.append("  " + "".join(parts).rstrip())
    session.send("\n".join(lines))


COMMANDS = {
    "restore": cmd_restore, "respawn": cmd_respawn,
    "emotes": cmd_emotes, "emojis": cmd_emotes,
    "look": cmd_look, "l": cmd_look,
    "say": cmd_say,
    "ooc": cmd_ooc,
    "chatlog": cmd_chatlog,
    "village": cmd_village_chat, "vchat": cmd_village_chat, "vc": cmd_village_chat,
    "ask": cmd_ask,
    "who": cmd_who,
    "whois": cmd_whois,
    "sharingan": cmd_sharingan, "shar": cmd_sharingan,
    "beastmode": cmd_tailed_beast_mode,
    "izanagi": cmd_izanagi,
    "guess": cmd_guess,
    "stab": cmd_stab,
    "impale": cmd_impale,
    "burn": cmd_burn,
    "crush": cmd_crush,
    "unmake": cmd_unmake,
    "aff": cmd_aff,
    "afk": cmd_afk,
    "recall": cmd_recall,
    "anki": cmd_anki,
    "goto": cmd_goto,
    "transfer": cmd_transfer,
    "return": cmd_return,
    "apartment": cmd_apartment,
    "description": cmd_description,
    "biography": cmd_biography, "bio": cmd_biography,
    "inventory": cmd_inventory, "i": cmd_inventory,
    "equipment": cmd_equipment, "eq": cmd_equipment,
    "wear": cmd_wear,
    "wield": cmd_wield,
    "hold": cmd_hold,
    "remove": cmd_remove,
    "attack": cmd_attack, "kill": cmd_attack,
    "consider": cmd_consider,
    "weather": cmd_weather,
    "flee": cmd_flee,
    "yes": cmd_finish_downed_yes,
    "release": cmd_release,
    "unleash": cmd_unleash,
    "no": cmd_finish_downed_no,
    "auction": cmd_auction,
    "price": cmd_price,
    "shop": cmd_shop,
    "wimpy": cmd_wimpy,
    "perform": cmd_perform,
    "per": cmd_perform,
    "missions": cmd_missions,
    "exam": cmd_chunin_exam,
    "submit": cmd_submit_scrolls,
    "leave": cmd_leave_exam,
    "accept": cmd_accept,
    "request": cmd_request,
    "train": cmd_train,
    "convert": cmd_convert_practice,
    "practice": cmd_practice,
    "prac": cmd_prac,
    "rest": cmd_rest,
    "sleep": cmd_sleep,
    "stand": cmd_stand, "wake": cmd_stand,
    "skills": cmd_skills,
    "examine": cmd_examine,
    "clan": cmd_clan,
    "list": cmd_list,
    "sell": cmd_sell,
    "gamble": cmd_gamble, "chouhan": cmd_gamble,
    "slots": cmd_slots,
    "roulette": cmd_roulette,
    "fish": cmd_fish,
    "mine": cmd_mine,
    "smelt": cmd_smelt,
    "pullweeds": cmd_pullweeds,
    "deliver": cmd_deliver,
    "chop": cmd_chop,
    "cook": cmd_cook,
    "farm": cmd_farm,
    "gemcut": cmd_gemcut,
    "craft": cmd_craft,
    "give": cmd_give,
    "drop": cmd_drop,
    "open": cmd_open,
    "close": cmd_close,
    "lock": cmd_lock,
    "unlock": cmd_unlock,
    "drop.all": lambda session, args: cmd_drop(session, ["all"]),
    "get": cmd_get,
    "put": cmd_put,
    "read": cmd_read, "study": cmd_read,
    "channel": cmd_channel,
    "buy": cmd_buy,
    "eat": cmd_eat,
    "drink": cmd_drink,
    "use": cmd_use,
    "loot": cmd_loot,
    "sacrifice": cmd_sacrifice, "sac": cmd_sacrifice,
    "purge": cmd_purge,
    "config": cmd_config,
    "score": cmd_score, "sc": cmd_score,
    "jobs": cmd_jobs,
    "group": cmd_group,
    "team": cmd_team,
    "trade": cmd_trade,
    "duel": cmd_duel,
    "prompt": cmd_prompt,
    "password": cmd_password,
    "help": help_system.cmd_help,
    "hedit": help_system.cmd_hedit,
    "quit": cmd_quit,
    "save": cmd_save,
    "reboot": cmd_reboot,
    "commands": cmd_commands,
    "changes": cmd_changes,
    "leaderboard": cmd_leaderboard, "leaderboards": cmd_leaderboard, "top": cmd_leaderboard,
    "bingobook": cmd_bingobook, "bounty": cmd_bounty, "place": cmd_place,
    "territory": cmd_territory, "war": cmd_territory, "garrison": cmd_garrison,
    "bank": cmd_bank,
    "trap": cmd_trap,
    "reload": cmd_reload,
    "spawnpoint": cmd_spawnpoint,
    "staffconfig": cmd_staffconfig,
    "report": cmd_report,
    "idea": cmd_idea,
    "rset": olc.cmd_rset,
    "redit": olc.cmd_rset,  # classic ROM naming alias for the same room editor, per direct request
    "rcreate": olc.cmd_rcreate,
    "rfind": olc.cmd_rfind,
    "rlist": olc.cmd_rlist,
    "area": olc.cmd_area,
    "aset": olc.cmd_aset,
    "astat": olc.cmd_astat,
    "mset": olc.cmd_mset,
    "mcreate": olc.cmd_mcreate,
    "mcopy": olc.cmd_mcopy,
    "minvoke": olc.cmd_minvoke,
    "mfind": olc.cmd_mfind,
    "mlist": olc.cmd_mlist,
    "silence": olc.cmd_silence,
    "unsilence": olc.cmd_unsilence,
    "jail": olc.cmd_jail,
    "unjail": olc.cmd_unjail,
    "levelup": olc.cmd_levelup,
    "oset": olc.cmd_oset,
    "ocreate": olc.cmd_ocreate,
    "ocopy": olc.cmd_ocopy,
    "oinvoke": olc.cmd_oinvoke,
    "ofind": olc.cmd_ofind,
    "olist": olc.cmd_olist,
    "mstat": olc.cmd_mstat,
    "bloodstat": olc.cmd_bloodstat,
    "bloodset": olc.cmd_bloodset,
    "awaken": olc.cmd_awaken,
    "setkage": olc.cmd_setkage,
    "award": olc.cmd_award,
    "addtip": olc.cmd_addtip,
    "remtip": olc.cmd_remtip,
    "vnum": olc.cmd_vnum,
    "ostat": olc.cmd_ostat,
    "rstat": olc.cmd_rstat,
}
