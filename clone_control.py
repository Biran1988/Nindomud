"""First-person reconnaissance through one *existing* mastered elemental clone.

The character never leaves their original physical room.  The connection is
transient per Session, not a saved Player field; no second player/avatar is
created.  The controlled Mob retains its real position and HP, so defeating
that mob, dismissing it or running out of Chakra ends the link.
"""
from contextlib import contextmanager
from copy import copy

ELEMENT_SKILLS = {
    "lightning": "Raiton Kage Bunshin",
    "water": "Mizu Bunshin",
    "earth": "Deido Bunshin",
    "sand": "Suna Bunshin",
}
SENSE_VERBS = {"look", "l", "scan", "examine", "help", "who", "score", "sc", "level", "uptime", "jinchuriki", "mastery", "skills", "jutsu"}
ALLOWED_DOORS = {"open", "close"}


def _live(clone):
    import combat
    return bool(clone and clone.health > 0 and
                any(existing is clone for existing in combat.MOBS_BY_ROOM.get(clone.room_vnum, ())))


def view_room(session):
    """Room for incoming messages and the player's *view*, not their body."""
    clone = getattr(session, "controlled_clone", None)
    if _live(clone):
        return clone.room_vnum
    return session.player.room_vnum if getattr(session, "player", None) else None


def _notice_end(session, reason):
    session.controlled_clone = None
    session.send(f"&YYour elemental clone {reason}. Your awareness returns to your original body.&x")
    import commands
    commands.cmd_look(session, [])


def notify_clone_removed(mob, reason="disperses"):
    """Called from all clone-removal paths, including combat defeats."""
    import session as session_module
    for session in list(session_module.ACTIVE_SESSIONS):
        if getattr(session, "combat_target", None) is mob:
            session.combat_target = None
            session.send(f"&D{mob.name} vanishes; your fight ends.&x")
        if getattr(session, "controlled_clone", None) is mob:
            _notice_end(session, reason)


def is_in_combat(session):
    """No entering clone control during PvE/PvP or while being attacked."""
    import session as session_module
    if (getattr(session, "combat_target", None) is not None or
            getattr(session, "pvp_target", None) is not None or
            getattr(session, "duel", None) is not None):
        return True
    for other in session_module.ACTIVE_SESSIONS:
        if other is not session and getattr(other, "pvp_target", None) is session:
            return True
    return False


def cmd_clone(session, args):
    import combat
    args = [str(value).lower() for value in args]
    if not args or args[0] not in ("control", "disperse", "status"):
        session.send("Usage: clone control | clone status | clone disperse")
        return
    player = session.player
    controlled = getattr(session, "controlled_clone", None)
    if args[0] == "status":
        if controlled and _live(controlled):
            session.send(f"&CControlling {controlled.name}: room {controlled.room_vnum}, "
                         f"HP {controlled.health}/{controlled.max_health}. "
                         "Only 'clone disperse' or the clone's defeat ends control.&x")
        else:
            clones = [m for m in combat.active_shadow_clones(player)
                      if m.clone_element in ELEMENT_SKILLS]
            session.send(f"You have {len(clones)} active elemental clone(s). "
                         "Master its individual jutsu to 100% to control it.")
        return
    if args[0] == "disperse":
        if controlled:
            _disperse(session, controlled)
            return
        session.send("You are not controlling an elemental clone.")
        return
    if controlled:
        session.send("You are already controlling a clone. Only dispersal or defeat ends the connection.")
        return
    if is_in_combat(session):
        session.send("&RYou cannot take control of an elemental clone during combat.&x")
        return
    if (getattr(session, "pending_cast", None) is not None or
            getattr(session, "pending_action", None) is not None or
            getattr(session, "chakra_charge", None) is not None):
        session.send("Finish your current action before controlling a clone.")
        return
    if getattr(player, "downed_by", None) or player.health <= 0:
        session.send("You must be conscious to project into an elemental clone.")
        return
    clones = [m for m in combat.active_shadow_clones(player)
              if m.clone_element in ELEMENT_SKILLS and _live(m)]
    eligible = [m for m in clones if player.skill_proficiencies.get(
        ELEMENT_SKILLS[m.clone_element], 0) >= 100]
    if len(eligible) != 1:
        session.send("You need exactly one active elemental clone whose own "
                     "jutsu is mastered to 100% (Raiton, Mizu, Deido or Suna Bunshin).")
        return
    clone = eligible[0]
    if combat._mob_is_being_fought(clone):
        session.send("That clone is already fighting; you cannot enter its body during combat.")
        return
    # Preserve the ordinary player's identity, including clones summoned
    # before the disguise was added. No observer should see an element tag.
    clone.name = player.name
    session.controlled_clone = clone
    session.send(f"&CYour consciousness enters {clone.name}. Your real body remains "
                 f"in room {player.room_vnum}; you now see through your clone.&x")
    session.send("&DMove with directions, look/scan/examine, speak or use socials. "
                 "Combat and ordinary body commands are unavailable. "
                 "Only 'clone disperse' or defeat ends control.&x")
    _look(session)


def _disperse(session, clone):
    import combat
    if _live(clone):
        combat.remove_mob(clone)  # removal hook ends the connection
    else:
        _notice_end(session, "disperses")


@contextmanager
def _eyes(session):
    """Look through the scout WITHOUT relocating the real player object.

    A shallow, read-only viewpoint copy is exposed to look/scan/examine
    while the original character remains physically in its own room.
    The actual Player instance (and all player saves) never acquires
    the clone's room vnum, even momentarily. Existing room commands
    receive the same room data through the viewpoint copy.
    """
    body = session.player
    former_body = getattr(session, "_clone_original_player", None)
    viewpoint = copy(body)
    viewpoint.room_vnum = session.controlled_clone.room_vnum
    try:
        session._clone_original_player = body
        session.player = viewpoint
        yield
    finally:
        session.player = body
        session._clone_original_player = former_body


def _look(session, args=None):
    import commands
    with _eyes(session):
        commands.cmd_look(session, args or [])


def _sense(session, verb, args):
    import commands
    with _eyes(session):
        if verb in ("look", "l"):
            commands.cmd_look(session, args)
        elif verb == "scan":
            commands.cmd_scan(session, args)
        elif verb == "examine":
            commands.cmd_examine(session, args)
        elif verb in ALLOWED_DOORS:
            getattr(commands, "cmd_" + verb)(session, args)
        elif verb in ("score", "sc"):
            commands.cmd_score(session, args)
        elif verb == "level":
            commands.cmd_level(session, args)
        elif verb == "uptime":
            commands.cmd_uptime(session, args)
        elif verb in ("jinchuriki", "mastery"):
            commands.cmd_jinchuriki(session, args)
        elif verb == "skills":
            commands.cmd_skills(session, args)
        elif verb == "jutsu":
            commands.cmd_jutsu(session, args)
        elif verb == "help":
            commands.help_system.cmd_help(session, args)
        elif verb == "who":
            commands.cmd_who(session, args)


def _move(session, direction):
    import world
    import combat
    clone = session.controlled_clone
    room = world.WORLD.get(clone.room_vnum)
    if not room or direction not in room.exits:
        session.send("Your clone can't go that way.")
        return
    if "door" in room.exit_flags.get(direction, ()) and not room.exit_door_open.get(direction, False):
        session.send("The door is closed.")
        return
    if "hidden" in room.exit_flags.get(direction, ()):
        session.send("Your clone cannot find an exit that way.")
        return
    dest = world.WORLD.get(room.exits[direction])
    if (not dest or not dest.enabled or dest.apartment or dest.player_shop):
        session.send("Your clone cannot enter there.")
        return
    # 'no_wander' stops RANDOM movement only. A manually piloted clone
    # is a deliberate reconnaissance action rather than an ambient wander.
    origin = clone.room_vnum
    combat._broadcast_to_room(origin, f"{clone.name} leaves {direction}.",
                              exclude_session=session)
    current = combat.MOBS_BY_ROOM.get(origin, ())
    if clone not in current:
        _notice_end(session, "disperses")
        return
    current.remove(clone)
    clone.room_vnum = dest.vnum
    combat.MOBS_BY_ROOM.setdefault(dest.vnum, []).append(clone)
    # Just like ordinary walking, show the destination room once.
    # Both room broadcasts exclude the pilot to prevent echo spam.
    combat._broadcast_to_room(dest.vnum, f"{clone.name} arrives from the {world.OPPOSITE_DIRECTION.get(direction, direction)}.",
                              exclude_session=session)
    _look(session)


def _say(session, text):
    if not text.strip():
        session.send("Say what?")
        return
    import session as session_module
    import commands
    import chat_moderation
    if commands._is_silenced(session):
        return
    if chat_moderation.record_and_check_spam(session):
        session.send("&D(You're talking too fast! You have been silenced for 10 minutes.)&x")
        return
    text = chat_moderation.censor(text)
    clone = session.controlled_clone
    # Match ordinary say exactly. No "through your clone" reveal.
    session.send(f"&gYou say, '{text}'&x")
    for other in session_module.ACTIVE_SESSIONS:
        if (other is not session and other.player and
                view_room(other) == clone.room_vnum):
            other.send(f"&g{session.player.name} says, '{text}'&x")


def _social(session, name):
    import emotes
    import session as session_module
    action = emotes.EMOTES.get(name)
    if not action:
        session.send("Unknown social. Type 'emotes' after dispersing for a list.")
        return
    own, other_text = action
    import chat_moderation
    import commands
    if commands._is_silenced(session):
        return
    if chat_moderation.record_and_check_spam(session):
        session.send("&D(You're talking too fast! You have been silenced for 10 minutes.)&x")
        return
    clone = session.controlled_clone
    session.send(f"You {own}")
    for other in session_module.ACTIVE_SESSIONS:
        if (other is not session and other.player and
                view_room(other) == clone.room_vnum):
            other.send(f"{session.player.name} {other_text}")


def handle_playing_command(session, line):
    """Handle commands while controlling; never fall through to body play."""
    if not getattr(session, "controlled_clone", None):
        return False
    clone = session.controlled_clone
    if not _live(clone):
        _notice_end(session, "is defeated or has vanished")
        return True
    parts = line.split()
    if not parts:
        return True
    verb, args = parts[0].lower(), parts[1:]
    if verb == "clone":
        cmd_clone(session, args)
        return True
    import world
    direction = world.normalize_direction(verb)
    if direction:
        _move(session, direction)
    elif verb in SENSE_VERBS or verb in ALLOWED_DOORS:
        _sense(session, verb, args)
    elif verb == "say":
        _say(session, " ".join(args))
    elif verb.startswith("@"):
        _social(session, verb[1:])
    elif verb == "emote" and len(args) == 1 and args[0].startswith("@"):
        _social(session, args[0][1:].lower())
    else:
        session.send("&RWhile controlling your clone you cannot use that command. "
                     "You can only return by 'clone disperse' or if the clone is defeated.&x")
    return True
