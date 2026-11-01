"""Undocumented dimensional escape through an existing summoning bond.

Intentionally NOT registered in data_jutsu or public skill/help/changelog
catalogs: discovery is an in-world secret. The fallback uses the same village
Kage room as Anki, with contract-specific VNUMs configurable in future.
"""

# When summoning realms are built, set e.g. 'toad': 123456 to send
# that contract's users there. Empty means the player's Anki destination.
DESTINATION_VNUM_BY_SUMMON_FAMILY = {}


def _destination(player, summon, world_module):
    import content
    family = str(getattr(summon, "summon_tier_key", "") or "").split("_", 1)[0]
    vnum = DESTINATION_VNUM_BY_SUMMON_FAMILY.get(family)
    if vnum is None:
        village_rooms = content._VILLAGE_ROOMS.get(player.village, {})
        vnum = village_rooms.get("kage")
    return world_module.WORLD.get(vnum) if vnum is not None else None


def cast(session):
    """Only an active, living summon permits reverse transit from Kamui.

    A summon may be outside the pocket when its summoner was pulled in;
    the established bond, not physical co-location, makes escape possible.
    Success consumes ALL currently held Chakra and Stamina, with no Anki
    cooldown, and saves the destination immediately before any reboot.
    """
    import combat
    import mangekyo
    import storage
    import world
    import whirlpool_fuinjutsu

    player = session.player
    if not mangekyo.is_inside_kamui_pocket(player, world):
        session.send("&YThe summoning bond cannot find a dimensional rift here.&x")
        return
    summon = combat.active_summon(player)
    if summon is None or getattr(summon, "health", 0) <= 0:
        session.send("&RNo living summoned ally answers your call.&x")
        return
    if player.chakra <= 0 or player.stamina <= 0:
        session.send("&RYou need remaining chakra and stamina to reverse the summoning bond.&x")
        return
    if whirlpool_fuinjutsu.blocks_teleport(player):
        session.send("&RA teleportation anchor prevents the reverse summoning.&x")
        return
    room = _destination(player, summon, world)
    if not room:
        session.send("&RYour summoning destination is unavailable. No energy is spent.&x")
        return

    previous_room = player.room_vnum
    # Break all live combat links before warping. Otherwise another combat
    # pulse could strike a combatant who is no longer present.
    for other in session.active_sessions():
        if other is not session and getattr(other, "pvp_target", None) is session:
            other.pvp_target = None
            if getattr(other, "player", None):
                combat.reset_summon_round_state(other.player)
    session.pvp_target = None
    session.combat_target = None
    session.pending_cast = None
    combat.reset_summon_round_state(player)

    # The bond is spent entirely, not a flat resource fee.
    player.chakra = 0
    player.stamina = 0
    session.broadcast_room(
        f"&M{player.name} vanishes into a spiral of summoning seals!&x",
        exclude_self=True,
    )
    player.room_vnum = room.vnum
    combat.follow_owner_summon(player, previous_room, room.vnum)

    # Owners who expend all chakra cannot sustain their own Kamui. Collapse
    # the now-unsustainable room immediately and return any other occupants.
    # Trapped non-owners leave the caster's pocket unchanged.
    if (getattr(player, "kamui_pocket_dimension_active", False)
            and getattr(player, "kamui_pocket_dimension_vnum", None) == previous_room):
        # Close *and save* everybody released, not just the caster.
        mangekyo.close_pocket_dimension(session, world)
    player.kamui_return_room_vnum = None

    # This must be durable NOW; no one can save in a deleted temp room.
    storage.save_player(player)
    session.send(f"&MYour summoned ally pulls you through space to {room.name}!&x")
    session.send("&RThe effort consumes ALL your Chakra and Stamina.&x")
    import commands
    commands.cmd_look(session, [])
    commands._fire_enter_triggers(session)
