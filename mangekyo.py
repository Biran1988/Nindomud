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


def open_pocket_dimension(caster_session, target_session, world_module) -> int:
    """Step 1 of Kamui's real, confirmed 2-step entry: sends ONLY the
    target to a real, brand-new, exit-less room (matching jail.py's
    own established convention for a dedicated, non-standard room).
    The caster is NOT moved here at all -- confirmed directly they
    must separately cast Kamui again on THEMSELVES to actually join.
    Returns the real, new room's own vnum, stashed on the caster's
    own player (kamui_pocket_dimension_vnum) so their own follow-up
    cast knows where to send them."""
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
    caster_session.player.kamui_pocket_dimension_vnum = vnum
    target_session.player.room_vnum = vnum
    return vnum


def enter_own_pocket_dimension(caster_session) -> bool:
    """Step 2 of Kamui's real, confirmed 2-step entry: the caster
    joins the pocket dimension they themselves already opened (see
    open_pocket_dimension). No chakra cost to enter (confirmed
    directly) -- real upkeep only starts ticking once they're
    actually inside (see process_kamui_pocket_dimensions below).
    Returns False if the caster has no real pocket dimension open at
    all right now."""
    vnum = caster_session.player.kamui_pocket_dimension_vnum
    if not vnum:
        return False
    caster_session.player.room_vnum = vnum
    caster_session.player.kamui_pocket_dimension_active = True
    return True


def leave_pocket_dimension(caster_session, world_module) -> None:
    """Ends the caster's own real Kamui pocket dimension -- clears
    their own real state, and genuinely deletes the dedicated room
    itself (it was only ever created for this one real use, per
    direct confirmation there's no reason to keep it around once
    nobody's using it)."""
    vnum = caster_session.player.kamui_pocket_dimension_vnum
    caster_session.player.kamui_pocket_dimension_active = False
    caster_session.player.kamui_pocket_dimension_vnum = None
    if vnum and vnum in world_module.WORLD.rooms:
        del world_module.WORLD.rooms[vnum]


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
    unlike Kamui's own 2-step entry). A real random number from 5-10
    is rolled right here, hidden from both players, setting how many
    of the caster's own actions the technique lasts."""
    import random
    from world import Room

    target_session.player.tsukuyomi_return_room_vnum = target_session.player.room_vnum
    caster_return_vnum = caster_session.player.room_vnum

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


def process_kamui_pocket_dimensions(combat_module, world_module, session_module) -> None:
    """Called once per real pulse -- ticks the real, confirmed chakra
    upkeep for every active Kamui pocket dimension: 15/tick with just
    the caster present, 35/tick once the target has also been sent in
    (still occupying the same dimension room). Ends the dimension
    entirely (see leave_pocket_dimension) the moment the caster's own
    chakra can't sustain it anymore."""
    for s in session_module.ACTIVE_SESSIONS:
        if not s.player or not s.player.kamui_pocket_dimension_active:
            continue
        vnum = s.player.kamui_pocket_dimension_vnum
        target_present = any(
            other.player and other is not s and other.player.room_vnum == vnum
            for other in session_module.ACTIVE_SESSIONS
        )
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
        s.send(f"&CYour Kamui pocket dimension uses {cost} chakra to remain active.&x")


def process_amaterasu_room_fires(combat_module, world_module) -> None:
    """Called once per real pulse (server.py's own pulse loop),
    alongside process_tailed_beasts -- sweeps every real room
    currently on fire from Amaterasu (Room.amaterasu_fire_caster is
    set), and:
    1. Expires the fire once Room.amaterasu_fire_expires_at has
       passed (confirmed directly: a real 30 minutes from the cast,
       unless sealed early by a scroll-taught sealing jutsu -- not
       yet built).
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
            if not s.player or s.player.room_vnum != room.vnum:
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


def process_amaterasu_player_burns(combat_module, session_module) -> None:
    """Called once per real pulse -- ticks every player's own,
    genuinely PERMANENT direct Amaterasu burn (player.
    mangekyo_amaterasu_burn_until, confirmed directly to have no real
    duration of its own at all: it burns forever until sealed, so
    this never actually clears it on a timer -- only a future sealing
    jutsu will). Separate from the room-fire tick above, since this
    travels with the player wherever they go."""
    import random

    for s in session_module.ACTIVE_SESSIONS:
        if not s.player or not s.player.mangekyo_amaterasu_burning:
            continue
        dmg = random.randint(*data_mangekyo.AMATERASU_PLAYER_BURN_PER_TICK)
        dmg = status_effects.reduce_incoming_damage(s.player.active_status_effects, dmg)
        s.player.health -= dmg
        s.send(f"&RAmaterasu's black flame burns you for {damage_messages.describe_damage(dmg)} damage -- it will not go out.&x")
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
            if not s.player or s.player.room_vnum != room.vnum:
                continue
            if s.player.name == room.kekkei_no_me_caster:
                continue
            chakra_loss = random.randint(*data_mangekyo.KEKKEI_NO_ME_CHAKRA_DRAIN_PER_TICK)
            stamina_loss = random.randint(*data_mangekyo.KEKKEI_NO_ME_STAMINA_DRAIN_PER_TICK)
            s.player.chakra = max(0, s.player.chakra - chakra_loss)
            s.player.stamina = max(0, s.player.stamina - stamina_loss)
            s.send(f"&RThe {room.kekkei_no_me_element} chakra saturating this domain saps your strength ({chakra_loss} chakra, {stamina_loss} stamina).&x")
