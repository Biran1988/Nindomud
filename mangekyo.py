"""
Mangekyo technique mechanics (Section 140).

Real, mechanical logic for the Mangekyo roster confirmed in
data_mangekyo.py -- kept in its own module (matching tailed_beasts.py's
own established convention) since several techniques need real,
periodic world-tick logic (a burning room, a pocket-dimension's own
chakra upkeep, a shared-room guessing loop) beyond what a single jutsu
cast can resolve in one turn.
"""

import time

import data_mangekyo
import damage_messages
import status_effects

_NEXT_POCKET_DIMENSION_VNUM = None  # lazily initialized on first real use, see _allocate_pocket_dimension_vnum


def _allocate_pocket_dimension_vnum(world_module) -> int:
    """A genuinely unique, real, per-caster room vnum for Kamui's own
    pocket dimension -- starting at 700000 (confirmed genuinely free
    via a direct scan, a real, separate range from crafted items'
    own 500000+), incrementing by 1 each real use. Deliberately NEVER
    shared between different Mangekyo users -- each caster gets their
    own real, distinct room, so 2 unrelated Kamui casts happening at
    the same time never collide or let players see into each other's
    own private pocket dimension."""
    global _NEXT_POCKET_DIMENSION_VNUM
    if _NEXT_POCKET_DIMENSION_VNUM is None:
        existing = [v for v in world_module.WORLD.rooms if v >= 700000]
        _NEXT_POCKET_DIMENSION_VNUM = (max(existing) + 1) if existing else 700000
    vnum = _NEXT_POCKET_DIMENSION_VNUM
    _NEXT_POCKET_DIMENSION_VNUM += 1
    return vnum


def _create_pocket_room(world_module) -> int:
    """Allocate a temporary room for either a target or a solo entry."""
    from world import Room
    vnum = _allocate_pocket_dimension_vnum(world_module)
    world_module.WORLD.add_room(Room(
        vnum=vnum,
        name="A Pocket Dimension",
        description=(
            "A vast, featureless void stretches in every direction, silent "
            "and still. There is no way out except by the will of whoever "
            "brought you here."
        ),
        biome="none",
    ))
    return vnum


def open_pocket_dimension(caster_session, target_session, world_module) -> int:
    """Send a same-room target into a new pocket without moving the caster."""
    if caster_session.player.room_vnum != target_session.player.room_vnum:
        raise ValueError("There's nobody here by that name.")
    if caster_session.player.kamui_pocket_dimension_vnum in world_module.WORLD.rooms:
        raise ValueError("You already have a pocket dimension open. Enter it or let it close first.")
    target_room = world_module.WORLD.get(target_session.player.room_vnum)
    if target_room and target_room.name == "A Pocket Dimension":
        raise ValueError("That target is already inside a pocket dimension.")
    vnum = _create_pocket_room(world_module)
    caster_session.player.kamui_return_room_vnum = caster_session.player.room_vnum
    target_session.player.kamui_return_room_vnum = target_session.player.room_vnum
    caster_session.player.kamui_pocket_dimension_vnum = vnum
    target_session.player.room_vnum = vnum
    return vnum


def open_mob_pocket_dimension(caster_session, mob, world_module) -> int:
    """Transfer a mob to the caster's temporary dimension."""
    import combat
    player = caster_session.player
    if player.room_vnum != mob.room_vnum or mob not in combat.mobs_in_room(player.room_vnum):
        raise ValueError("That target is no longer here.")
    if player.kamui_pocket_dimension_vnum in world_module.WORLD.rooms:
        raise ValueError("You already have a pocket dimension open. Enter it or let it close first.")
    if world_module.WORLD.get(player.room_vnum).name == "A Pocket Dimension":
        raise ValueError("You cannot open Kamui from inside a pocket dimension.")
    vnum = _create_pocket_room(world_module)
    player.kamui_return_room_vnum = player.room_vnum
    player.kamui_pocket_dimension_vnum = vnum
    mob.kamui_return_room_vnum = mob.room_vnum
    combat.MOBS_BY_ROOM[mob.room_vnum].remove(mob)
    mob.room_vnum = vnum
    combat.MOBS_BY_ROOM.setdefault(vnum, []).append(mob)
    return vnum


def enter_own_pocket_dimension(caster_session) -> bool:
    """Join an existing pocket or create a solo one on a self cast.

    Upkeep begins once the caster is inside. Returns False when they
    are already there, without opening a duplicate room.
    """
    import world
    player = caster_session.player
    vnum = player.kamui_pocket_dimension_vnum
    current_room = world.WORLD.get(player.room_vnum)
    if current_room and current_room.name == "A Pocket Dimension" and player.room_vnum != vnum:
        raise ValueError("You cannot open Kamui from inside another pocket dimension.")
    if player.room_vnum == vnum and player.kamui_pocket_dimension_active:
        return False
    if not vnum or world.WORLD.get(vnum) is None:
        vnum = _create_pocket_room(world)
        player.kamui_return_room_vnum = player.room_vnum
        player.kamui_pocket_dimension_vnum = vnum
    player.room_vnum = vnum
    player.kamui_pocket_dimension_active = True
    return True


def leave_pocket_dimension(caster_session, world_module) -> None:
    """Ends the caster's own real Kamui pocket dimension -- clears
    their own real state, and genuinely deletes the dedicated room
    itself (it was only ever created for this one real use, per
    direct confirmation there's no reason to keep it around once
    nobody's using it)."""
    import upkeep_reports
    for message in upkeep_reports.flush(caster_session.player, "Kamui Pocket Dimension"):
        caster_session.send(message)
    upkeep_reports.stop_maintaining(caster_session.player, "Kamui: Pocket Dimension")
    import session as session_module
    vnum = caster_session.player.kamui_pocket_dimension_vnum
    import combat
    for mob in list(combat.MOBS_BY_ROOM.get(vnum, [])):
        combat.MOBS_BY_ROOM[vnum].remove(mob)
        destination = mob.kamui_return_room_vnum
        if destination not in world_module.WORLD.rooms:
            destination = caster_session.player.kamui_return_room_vnum
        if destination not in world_module.WORLD.rooms:
            destination = next(iter(world_module.WORLD.rooms))
        mob.room_vnum = destination
        mob.kamui_return_room_vnum = None
        combat.MOBS_BY_ROOM.setdefault(destination, []).append(mob)
    for participant in session_module.ACTIVE_SESSIONS:
        if participant.player and participant.player.room_vnum == vnum and vnum is not None:
            destination = participant.player.kamui_return_room_vnum
            if destination not in world_module.WORLD.rooms:
                destination = caster_session.player.kamui_return_room_vnum
            if destination not in world_module.WORLD.rooms:
                destination = next(iter(world_module.WORLD.rooms))
            participant.player.room_vnum = destination
            participant.player.kamui_return_room_vnum = None
            if participant is not caster_session:
                participant.send("&YThe Kamui dimension collapses; you return to reality.&x")
                participant.send_prompt()
    caster_session.player.kamui_return_room_vnum = None
    caster_session.player.kamui_pocket_dimension_active = False
    caster_session.player.kamui_pocket_dimension_vnum = None
    if vnum and vnum in world_module.WORLD.rooms:
        del world_module.WORLD.rooms[vnum]


def end_kamui_on_departure(leaving_session, world_module) -> None:
    """Close a temporary dimension when its caster or captive leaves."""
    import session as session_module
    import storage
    player = leaving_session.player
    if player is None:
        return
    owner = next((s for s in session_module.ACTIVE_SESSIONS if s.player
                  and s.player.kamui_pocket_dimension_vnum
                  and (s is leaving_session or s.player.kamui_pocket_dimension_vnum == player.room_vnum)), None)
    if owner is None:
        return
    vnum = owner.player.kamui_pocket_dimension_vnum
    participants = [s for s in session_module.ACTIVE_SESSIONS
                    if s.player and s.player.room_vnum == vnum]
    leave_pocket_dimension(owner, world_module)
    for s in participants + [owner]:
        storage.save_player(s.player)


_NEXT_TSUKUYOMI_ROOM_VNUM = None  # lazily initialized on first real use, see _allocate_tsukuyomi_room_vnum


def _allocate_tsukuyomi_room_vnum(world_module) -> int:
    """A genuinely unique, real, per-cast room vnum for Tsukuyomi's
    own shared torture room -- starting at 750000 (confirmed
    genuinely free via a direct scan, a real, separate range from
    Kamui's own 700000+), incrementing by 1 each real cast. Never
    reused across different casts, matching Kamui's own established
    real precedent for a dedicated, single-use room."""
    global _NEXT_TSUKUYOMI_ROOM_VNUM
    if _NEXT_TSUKUYOMI_ROOM_VNUM is None:
        existing = [v for v in world_module.WORLD.rooms if v >= 750000]
        _NEXT_TSUKUYOMI_ROOM_VNUM = (max(existing) + 1) if existing else 750000
    vnum = _NEXT_TSUKUYOMI_ROOM_VNUM
    _NEXT_TSUKUYOMI_ROOM_VNUM += 1
    return vnum


def open_tsukuyomi(caster_session, target_session, world_module) -> None:
    """Casting Tsukuyomi immediately moves BOTH caster and target into
    a shared, real torture room in one action (confirmed directly,
    unlike Kamui's target-first 2-step entry). A real random number from 5-10
    is rolled right here, hidden from both players, setting how many
    of the caster's own actions the technique lasts."""
    import random
    from world import Room

    target_session.player.tsukuyomi_return_room_vnum = target_session.player.room_vnum
    caster_return_vnum = caster_session.player.room_vnum

    # Entering the mindscape ends ordinary fights for both participants.
    # A cast or timed action already queued by the victim must not fire
    # after the freeze takes hold, regardless of staff rank.
    for participant in (caster_session, target_session):
        participant.combat_target = None
        participant.pvp_target = None
    target_session.pending_cast = None
    target_session.pending_action = None
    target_session.chakra_charge = None

    vnum = _allocate_tsukuyomi_room_vnum(world_module)
    world_module.WORLD.add_room(Room(
        vnum=vnum,
        name="A Shattered Mindscape",
        description=(
            "Crimson sky bleeds into a horizon that never quite settles. "
            "Time itself feels wrong here -- every second stretches, "
            "every heartbeat echoes. There is no escape but the will of "
            "whoever brought you here."
        ),
        biome="none",
    ))
    caster_session.player.room_vnum = vnum
    target_session.player.room_vnum = vnum
    caster_session.player.tsukuyomi_active_target_name = target_session.player.name
    target_session.player.tsukuyomi_frozen = True
    caster_session.player.tsukuyomi_actions_remaining = random.randint(5, 10)
    caster_session.player.tsukuyomi_room_vnum = vnum
    caster_session.player.tsukuyomi_caster_return_vnum = caster_return_vnum


def end_tsukuyomi(caster_session, target_session, world_module) -> None:
    """Ends a real, active Tsukuyomi -- returns both players to their
    own real, original rooms, clears every real piece of state on
    both sides, and deletes the dedicated shared room (single-use,
    matching Kamui's own established real precedent)."""
    vnum = caster_session.player.tsukuyomi_room_vnum
    caster_return_vnum = caster_session.player.tsukuyomi_caster_return_vnum
    if caster_return_vnum:
        caster_session.player.room_vnum = caster_return_vnum
    if target_session.player.tsukuyomi_return_room_vnum:
        target_session.player.room_vnum = target_session.player.tsukuyomi_return_room_vnum
    caster_session.player.tsukuyomi_active_target_name = None
    caster_session.player.tsukuyomi_actions_remaining = 0
    caster_session.player.tsukuyomi_room_vnum = None
    caster_session.player.tsukuyomi_caster_return_vnum = None
    target_session.player.tsukuyomi_frozen = False
    target_session.player.tsukuyomi_return_room_vnum = None
    if vnum and vnum in world_module.WORLD.rooms:
        del world_module.WORLD.rooms[vnum]


def end_tsukuyomi_on_departure(leaving_session, world_module) -> None:
    """Release both minds if either participant logs out or disconnects."""
    import storage

    player = leaving_session.player
    if player is None:
        return
    if player.tsukuyomi_active_target_name:
        other = next((s for s in leaving_session.active_sessions()
                      if s is not leaving_session and s.player
                      and s.player.name == player.tsukuyomi_active_target_name), None)
        if other:
            end_tsukuyomi(leaving_session, other, world_module)
            other.send("&YTsukuyomi ends as its caster leaves.&x")
            other.send_prompt()
            storage.save_player(other.player)
        else:
            player.room_vnum = player.tsukuyomi_caster_return_vnum or player.room_vnum
            if player.tsukuyomi_room_vnum:
                world_module.WORLD.rooms.pop(player.tsukuyomi_room_vnum, None)
            player.tsukuyomi_active_target_name = None
            player.tsukuyomi_actions_remaining = 0
            player.tsukuyomi_room_vnum = None
            player.tsukuyomi_caster_return_vnum = None
        storage.save_player(player)
    elif player.tsukuyomi_frozen:
        other = next((s for s in leaving_session.active_sessions()
                      if s is not leaving_session and s.player
                      and s.player.tsukuyomi_active_target_name == player.name), None)
        if other:
            end_tsukuyomi(other, leaving_session, world_module)
            other.send("&YTsukuyomi ends as its target leaves.&x")
            other.send_prompt()
            storage.save_player(other.player)
        else:
            player.room_vnum = player.tsukuyomi_return_room_vnum or player.room_vnum
            player.tsukuyomi_frozen = False
            player.tsukuyomi_return_room_vnum = None
        storage.save_player(player)


def process_kamui_pocket_dimensions(combat_module, world_module, session_module) -> None:
    """Called once per real pulse -- ticks the real, confirmed chakra
    upkeep for every active Kamui pocket dimension: 15/tick with just
    the caster present, 35/tick once the target has also been sent in
    (still occupying the same dimension room). Ends the dimension
    entirely (see leave_pocket_dimension) the moment the caster's own
    chakra can't sustain it anymore."""
    for s in session_module.ACTIVE_SESSIONS:
        if (not s.player or s.state != session_module.State.PLAYING
                or not s.player.kamui_pocket_dimension_active):
            continue
        vnum = s.player.kamui_pocket_dimension_vnum
        target_present = any(
            other.player and other is not s and other.player.room_vnum == vnum
            for other in session_module.ACTIVE_SESSIONS
        )
        target_present = target_present or bool(combat_module.MOBS_BY_ROOM.get(vnum))
        cost = (
            data_mangekyo.KAMUI_UPKEEP_WITH_TARGET_PER_TICK
            if target_present
            else data_mangekyo.KAMUI_UPKEEP_ALONE_PER_TICK
        )
        if s.player.chakra < cost:
            s.send("&RYour chakra runs dry -- the pocket dimension collapses, pulling you back to reality.&x")
            leave_pocket_dimension(s, world_module)
            continue
        s.player.chakra -= cost
        import upkeep_reports
        for message in upkeep_reports.record(s.player, "Kamui Pocket Dimension", cost):
            s.send(message)
        if "Kamui: Pocket Dimension" not in s.player.learned_skills:
            s.player.learned_skills.append("Kamui: Pocket Dimension")
            s.player.skill_proficiencies["Kamui: Pocket Dimension"] = (100 if getattr(s.player, "_immortal_skill_mastery", False) else 0)
            import skill_training
            skill_training.grant_without_practice(s.player, "Kamui: Pocket Dimension")
        upkeep_reports.maintain_skill(s.player, "Kamui: Pocket Dimension")


def process_amaterasu_room_fires(combat_module, world_module) -> None:
    """Called once per real pulse (server.py's own pulse loop),
    alongside process_tailed_beasts -- sweeps every real room
    currently on fire from Amaterasu (Room.amaterasu_fire_caster is
    set), and:
    1. Expires the room fire five minutes after the cast.
    2. Deals real, per-tick damage (data_mangekyo.
       AMATERASU_ROOM_BURN_PER_TICK) to every player physically in
       that room right now, EXCEPT the original caster (confirmed
       directly they're exempt from their own room's fire).

    Deliberately does NOT touch a player's own separate, direct
    Amaterasu burn (player.mangekyo_amaterasu_burn_until) -- that's a
    genuinely separate, permanent effect that travels with the player
    wherever they go, handled by its own real tick elsewhere. This
    function only concerns the ROOM itself, which stays behind if the
    original target leaves, exactly as confirmed."""
    import random
    import session as session_module

    now = time.time()
    for room in list(world_module.WORLD.rooms.values()):
        if not room.amaterasu_fire_caster:
            continue
        if now >= room.amaterasu_fire_expires_at:
            room.amaterasu_fire_caster = None
            room.amaterasu_fire_expires_at = 0.0
            continue

        for s in session_module.ACTIVE_SESSIONS:
            if (not s.player or s.state != session_module.State.PLAYING
                    or s.player.room_vnum != room.vnum):
                continue
            if s.player.name == room.amaterasu_fire_caster:
                continue
            dmg = random.randint(*data_mangekyo.AMATERASU_ROOM_BURN_PER_TICK)
            dmg = status_effects.reduce_incoming_damage(s.player.active_status_effects, dmg)
            s.player.health -= dmg
            s.send(f"&RThe black flames engulfing this room sear you for {damage_messages.describe_damage(dmg)} damage!&x")
            if s.player.health <= 0:
                if combat_module.try_trigger_izanagi(s):
                    pass
                elif combat_module.is_immortal_immune_to_defeat(s):
                    combat_module.clamp_immortal_health(s)
                else:
                    combat_module.handle_player_defeat(s)
        for mob in list(combat_module.MOBS_BY_ROOM.get(room.vnum, [])):
            if mob.tailed_beast_key and mob.tailed_beast_downed_until:
                continue  # keep the beast sealable for its full capture window
            mob.health -= status_effects.reduce_incoming_damage(
                mob.active_status_effects, random.randint(*data_mangekyo.AMATERASU_ROOM_BURN_PER_TICK))
            if mob.health <= 0:
                owner = next((s for s in session_module.ACTIVE_SESSIONS
                              if s.player and s.player.name == room.amaterasu_fire_caster), None)
                if owner:
                    combat_module.handle_mob_defeat(owner, mob)
                else:
                    combat_module.remove_mob(mob)


def process_amaterasu_player_burns(combat_module, session_module) -> None:
    """Called once per real pulse -- ticks every player's own,
    direct Amaterasu burn. It has no timer; a real defeat clears it.
    Separate from the room-fire tick above, since this travels with
    the player wherever they go."""
    import random

    for s in session_module.ACTIVE_SESSIONS:
        if (not s.player or s.state != session_module.State.PLAYING
                or not s.player.mangekyo_amaterasu_burning):
            continue
        dmg = random.randint(*data_mangekyo.AMATERASU_PLAYER_BURN_PER_TICK)
        dmg = status_effects.reduce_incoming_damage(s.player.active_status_effects, dmg)
        s.player.health -= dmg
        s.send(f"&RAmaterasu's black flame burns you for {damage_messages.describe_damage(dmg)} damage!&x")
        if s.player.health <= 0:
            if combat_module.try_trigger_izanagi(s):
                pass
            elif combat_module.is_immortal_immune_to_defeat(s):
                combat_module.clamp_immortal_health(s)
            else:
                combat_module.handle_player_defeat(s)


def process_kekkei_no_me(combat_module, world_module, session_module) -> None:
    """Called once per real pulse -- sweeps every real room currently
    transformed by Kekkei no Me (Room.kekkei_no_me_caster is set),
    expiring it after its own real 90-second duration (confirmed
    directly), and draining real chakra AND stamina per tick from
    every player physically in that room right now, EXCEPT the
    caster (confirmed directly they're exempt). Deliberately does NOT
    apply the caster's own real +50% matching-element damage bonus
    here -- that's checked live at the moment a jutsu actually lands
    (see combat.py's own damage-calculation sites), not something to
    precompute on a timer."""
    import random

    now = time.time()
    for room in list(world_module.WORLD.rooms.values()):
        if not room.kekkei_no_me_caster:
            continue
        if now >= room.kekkei_no_me_expires_at:
            room.kekkei_no_me_caster = None
            room.kekkei_no_me_element = None
            room.kekkei_no_me_expires_at = 0.0
            continue

        for s in session_module.ACTIVE_SESSIONS:
            if (not s.player or s.state != session_module.State.PLAYING
                    or s.player.room_vnum != room.vnum):
                continue
            if s.player.name == room.kekkei_no_me_caster:
                continue
            chakra_loss = random.randint(*data_mangekyo.KEKKEI_NO_ME_CHAKRA_DRAIN_PER_TICK)
            stamina_loss = random.randint(*data_mangekyo.KEKKEI_NO_ME_STAMINA_DRAIN_PER_TICK)
            s.player.chakra = max(0, s.player.chakra - chakra_loss)
            s.player.stamina = max(0, s.player.stamina - stamina_loss)
            s.send(f"&RThe {room.kekkei_no_me_element} chakra saturating this domain saps your strength ({chakra_loss} chakra, {stamina_loss} stamina).&x")
        for mob in combat_module.MOBS_BY_ROOM.get(room.vnum, []):
            mob.chakra = max(0, mob.chakra - random.randint(*data_mangekyo.KEKKEI_NO_ME_CHAKRA_DRAIN_PER_TICK))
            mob.stamina = max(0, mob.stamina - random.randint(*data_mangekyo.KEKKEI_NO_ME_STAMINA_DRAIN_PER_TICK))
