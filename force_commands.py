"""Bounded player-command forcing for staff and scripted SMAUG mob programs.

Only actual in-game player verbs from SAFE_FORCE_VERBS can be dispatched.
Never dispatch arbitrary admin, account, economy, editor or file commands
under a target's potentially-privileged session. This module also blocks
nested force loops and commands entered while editing/account prompts.
"""
import re

MAX_FORCED_COMMAND_LENGTH = 320
MAX_FORCED_DEPTH = 1

# Explicit allowlist, not a denylist: newly added commands remain
# unforceable until reviewed. 'perform' and attack are ordinary combat
# commands and will still be subject to the game's combat checks.
SAFE_FORCE_VERBS = frozenset({
    "look", "l", "scan", "say", "ask", "emotes", "emojis",
    "rest", "sleep", "stand", "wake", "examine", "consider",
    "inventory", "i", "equipment", "eq", "score", "sc",
    "who", "help", "skills", "weather", "emote", "aff",
    "attack", "kill", "flee", "perform", "per", "recall",
})
# $n selects the triggering player inside a mob program, but is not
# expanded here. Caller resolves that target from the triggering session.
TARGET_SELECTOR = "$n"
_INVALID_TEXT = re.compile(r"[\x00-\x1f\x7f]")


def validate_forced_command(command):
    """Validate a single allowed in-world player action.

    Return an error message or None, and do not invoke the dispatcher
    during validation. Keep a script and staff command on the same
    whitelist to prevent a privilege escalation through nested calls.
    """
    if not isinstance(command, str) or not command.strip():
        return "Force requires a player command."
    if len(command) > MAX_FORCED_COMMAND_LENGTH or _INVALID_TEXT.search(command):
        return "Forced commands must be one line and at most 320 characters."
    word = command.split(None, 1)[0].lower()
    import emotes
    if word.startswith("@") or word == "emote":
        args = command.split()
        name = word[1:] if word.startswith("@") else (args[1].lower() if len(args) == 2 else "")
        if len(args) != (1 if word.startswith("@") else 2) or name not in emotes.EMOTES:
            return "Use a real social, such as @yawn or emote smile."
        return None
    import world
    if word not in SAFE_FORCE_VERBS and not world.normalize_direction(word):
        return f"'{word}' cannot be forced. Only approved movement, social and combat commands are allowed."
    # All legitimate forced actions go through the regular player command
    # dispatcher; account/staff/economy actions never appear in this set.
    return None


def parse_mpforce_args(raw):
    """Accept SMAUG 'mpforce $n <command>' and old 'mpforce <command>'.

    The old format has always addressed the triggering player implicitly,
    so retain it. All other target selectors (including 'all') are
    prohibited for mob programs.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, "Usage: mpforce $n <allowed player command>"
    parts = raw.strip().split(None, 1)
    if parts[0].lower() == TARGET_SELECTOR:
        if len(parts) != 2:
            return None, "Usage: mpforce $n <allowed player command>"
        command = parts[1]
    else:
        command = raw.strip()
        # Retain the pre-SMAUG Nindo_mud shorthand: "mpforce emote
        # <freeform text>" was a harmless room narration action, not
        # a player command. Genuine socials still use @yawn/emote yawn.
        if command.lower().startswith("emote ") and len(command) <= MAX_FORCED_COMMAND_LENGTH:
            return command, None
    error = validate_forced_command(command)
    return (None, error) if error else (command, None)


def run_forced_player_command(target_session, command, actor):
    """Run a command AS the target, never AS the immortal or NPC.

    All game checks still run normally, including combat restrictions,
    inability to move, locked exits, resource requirements, etc.
    """
    error = validate_forced_command(command)
    if error:
        return False, error
    target = getattr(target_session, "player", None)
    account = getattr(target_session, "account", None)
    if not target or not account:
        return False, "The target is not a connected character."
    if getattr(target_session, "controlled_clone", None) is not None:
        return False, "That character is remotely controlling an elemental clone."
    if account.staff_level != "player":
        return False, "Staff characters cannot be forced."
    state = getattr(target_session, "state", None)
    if getattr(state, "name", None) != "PLAYING":
        return False, "The target is not currently playing."
    if getattr(target_session, "_force_command_depth", 0) >= MAX_FORCED_DEPTH:
        return False, "The target is already executing a forced command."
    # It is important that the notification is outside the forced-command
    # call: the player can tell which actions were forced.
    target_session.send(f"&Y{actor} forces you to: {command}&x")
    target_session._force_command_depth = getattr(target_session, "_force_command_depth", 0) + 1
    try:
        import commands
        if command.split(None, 1)[0].lower() == "emote":
            # Nindo_mud socials are native '@name' commands rather than
            # an 'emote' command in the regular dispatcher.
            commands.dispatch_line(target_session, "@" + command.split()[1])
        else:
            commands.dispatch_line(target_session, command)
        prompt = getattr(target_session, "send_prompt", None)
        if callable(prompt):
            prompt()
        return True, ""
    finally:
        target_session._force_command_depth -= 1
