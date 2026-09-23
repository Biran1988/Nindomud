"""
Declarative, safe trigger/program system for mobs, items, and rooms.

Deliberately NOT arbitrary code execution. A "program" is a small dict
-- {"trigger": str, "action": str, "args": str} (plus "keyword" for
speech programs only) -- built entirely from fixed, validated sets
(see MOB_TRIGGERS/ITEM_TRIGGERS/ROOM_TRIGGERS and ACTIONS below).
Builders configure WHEN something fires and WHICH of a handful of safe
actions runs; the actual execution logic is written and controlled
here, in Python, not supplied by the builder as code.

This matters because STAFF_CAN_BUILD (olc.py) includes builder and area
leader, not just administrator/implementor -- handing that group raw
exec() would be a real privilege-escalation risk (reading other
players' data, crashing the server, etc.), even on a single-admin MUD.
A fixed action set has no such risk: every action is a few lines of
plain game logic, reviewed once here, that any valid `args` can only
parameterize, never redirect.

Trigger types differ by what they're attached to:
  - Mob:  greet (a player enters the mob's room), death (the mob is
          defeated), random (a per-pulse chance while a player shares
          its room), speech (a player 'say's a matching keyword while
          sharing its room -- see SPEECH_KEYWORD below; the only
          trigger that carries an extra "keyword" field, letting a
          single mob hold a small keyword-driven conversation for
          quest-style interactions)
  - Item: wear (worn/wielded), get (added to inventory via buy)
  - Room: enter (a player enters the room), random (per-pulse chance
          while a player is present)

Not yet covered (a reasonable follow-up, not built now): item drop
trigger, and firing 'get' from looting a corpse (currently only firing
from a shop purchase).

Actions (identical fixed set across all three trigger sources):
  - say <text>                  - speaks the text
  - emote <text>                - shows the text as an emote
  - give <vnum>                 - gives the player the object prototype at <vnum>
  - heal <n>                    - heals the player n HP (capped at their max)
  - teleport <vnum>              - moves the player to room <vnum>
  - drop_chance <pct> <vnum>     - pct% chance (checked once, at fire time)
                                   to give the player the object at <vnum>;
                                   most naturally used on a mob's 'death'
                                   trigger for random loot, but valid anywhere
  - give_mission_points <n>      - grants n mission points, counted toward
                                   both the spendable balance AND the
                                   lifetime-earned leaderboard total,
                                   same as a real mission reward would
  - give_ryo <n>                 - grants n ryo

A 'speech' program's reward for a quest turn-in is often more than one
thing (a line of dialogue, an item, some ryo/mission points) -- so
fire_speech_programs fires EVERY program sharing the matched keyword,
not just the first one found, letting a builder stack several programs
under the same keyword (e.g. three programs all keyword='turn in
quest': one 'say', one 'give', one 'give_ryo') to build a complete
reward. Only the first DIFFERENT keyword found in a given utterance is
used, though -- a sentence that happens to contain two configured
keywords only triggers the one found first, not both.
"""

MOB_TRIGGERS = {"greet", "death", "random", "speech", "move"}
ITEM_TRIGGERS = {"wear", "get"}
ROOM_TRIGGERS = {"enter", "random"}

ACTIONS = {
    "say", "emote", "give", "heal", "teleport", "drop_chance", "give_mission_points", "give_ryo", "set_rank",
    "take", "give_xp", "learn_skill", "require_item", "remember_keyword", "min_level", "max_level",
    "wear_message", "iruka_graduation_check",
}

RANDOM_TRIGGER_CHANCE_PCT = 15  # per pulse, for any 'random' program


def validate_program(trigger: str, action: str, args: str, valid_triggers: set, keyword: str = None):
    """Returns a list of human-readable error strings; empty if valid.
    `keyword` is required (and only meaningful) for the 'speech' trigger."""
    errors = []
    if trigger not in valid_triggers:
        errors.append(f"'{trigger}' isn't a valid trigger here. Valid: {', '.join(sorted(valid_triggers))}")
    if trigger == "speech" and not (keyword or "").strip():
        errors.append("A 'speech' program needs a keyword to listen for.")
    if action not in ACTIONS:
        errors.append(f"'{action}' isn't a valid action. Valid: {', '.join(sorted(ACTIONS))}")
        return errors  # can't validate args against an unknown action
    if action == "give" and not args.strip().isdigit():
        errors.append("'give' needs an object vnum (a number) as its argument.")
    if action == "teleport" and not args.strip().isdigit():
        errors.append("'teleport' needs a room vnum (a number) as its argument.")
    if action == "heal" and not args.strip().lstrip("-").isdigit():
        errors.append("'heal' needs a number as its argument.")
    if action in ("say", "emote") and not args.strip():
        errors.append(f"'{action}' needs some text as its argument.")
    if action == "drop_chance":
        parts = args.split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit() or not (1 <= int(parts[0]) <= 100) or not parts[1].isdigit():
            errors.append("'drop_chance' needs '<percent 1-100> <object vnum>' as its argument.")
    if action == "give_mission_points" and not args.strip().isdigit():
        errors.append("'give_mission_points' needs a positive number as its argument.")
    if action == "give_ryo" and not args.strip().isdigit():
        errors.append("'give_ryo' needs a positive number as its argument.")
    if action == "set_rank":
        import kage
        rank_arg = args.strip().lower()
        if rank_arg == "kage":
            errors.append("'set_rank' can't grant the Kage rank -- appointing a Kage stays exclusive to the real staff command, which enforces one Kage per village.")
        elif rank_arg not in kage.RANK_ORDER:
            errors.append(f"'set_rank' needs a real rank as its argument. Valid: {', '.join(kage.RANK_ORDER[:-1])}")
    return errors


def run_action(session, action: str, args: str, speaker_name: str = "Something", mob_template: dict = None, keyword: str = None) -> bool:
    """Executes exactly one program action against the triggering
    player's session. speaker_name flavors say/emote/give/teleport
    messages (e.g. the mob's name, an item's name, or a room's name).
    Returns True if the CALLER should keep processing any further
    real actions in this same program, False to genuinely halt there
    -- only require_item (per direct confirmation, a genuinely new
    conditional gate) can ever return False; every other real action
    always returns True."""
    import random

    import inventory
    import olc
    import world

    player = session.player
    args = args.strip()
    # Per direct confirmation (Section 151): a real, literal "*" in
    # any program's own args text is replaced with the triggering
    # player's own real name -- e.g. "say Hello * welcome in" says
    # "Hello Naruto welcome in" the moment Naruto walks in. Applied
    # universally here (not just in say/emote/wear_message) since a
    # literal "*" would never appear in a normal numeric/vnum
    # argument, so this is safe for every action.
    args = args.replace("*", player.name)

    if action == "say":
        session.send(f'{speaker_name} says, "{args}"')
    elif action == "emote":
        session.send(f"{speaker_name} {args}")
    elif action == "give":
        obj = olc.OBJECT_TEMPLATES.get(int(args))
        if obj:
            ok, reason = inventory.add_item(player.inventory, obj["short_desc"])
            if ok:
                session.send(f"{speaker_name} gives you {obj['short_desc']}.")
            else:
                session.send(inventory.full_message(reason, obj["short_desc"]))
    elif action == "heal":
        amount = int(args)
        player.health = min(player.maximum_health, player.health + amount)
        session.send(f"&G{speaker_name} restores you. (+{amount} HP)&x")
    elif action == "teleport":
        vnum = int(args)
        if vnum in world.WORLD.rooms:
            player.room_vnum = vnum
            session.send(f"{speaker_name} sends you elsewhere in a flash of light.")
    elif action == "drop_chance":
        pct_text, vnum_text = args.split(None, 1)
        if random.randint(1, 100) <= int(pct_text):
            obj = olc.OBJECT_TEMPLATES.get(int(vnum_text))
            if obj:
                ok, reason = inventory.add_item(player.inventory, obj["short_desc"])
                if ok:
                    session.send(f"&Y{speaker_name} dropped {obj['short_desc']}!&x")
                else:
                    session.send(inventory.full_message(reason, obj["short_desc"]))
    elif action == "give_mission_points":
        amount = int(args)
        player.mission_points += amount
        player.mission_points_earned_total += amount
        session.send(f"&GYou receive {amount} mission point(s).&x")
    elif action == "give_ryo":
        amount = int(args)
        player.ryo += amount
        session.send(f"&Y{speaker_name} hands you {amount:,} ryo.&x")
    elif action == "set_rank":
        import data_headbands
        import kage
        new_rank = args.lower()
        player.village_rank = new_rank
        data_headbands.apply_rank_headband(player, new_rank)
        session.send(f"&Y{speaker_name} promotes you to {new_rank.title()}!&x")
        kage.announce_rank_up(player.name, new_rank)
        kage.award_genin_mission_points_if_applicable(session, player, new_rank)
    elif action == "take":
        # The reverse of 'give' -- a genuine cost, not just rewards.
        # args is a real vnum, resolved to its own real short_desc,
        # matched against the player's own real inventory the same
        # way 'give'/'drop_chance' already resolve items.
        obj = olc.OBJECT_TEMPLATES.get(int(args))
        if obj:
            for item in list(player.inventory):
                if item.lower() == obj["short_desc"].lower():
                    player.inventory.remove(item)
                    session.send(f"{speaker_name} takes {obj['short_desc']} from you.")
                    break
    elif action == "give_xp":
        # Mirrors give_mission_points/give_ryo, but for experience --
        # reuses the real, established leveling.grant_experience
        # function so a quest-reward XP grant genuinely handles a
        # level-up (stat gains, real messages) exactly like combat XP
        # already does, rather than a raw field write.
        import leveling
        amount = int(args)
        for line in leveling.grant_experience(player, amount):
            session.send(line)
    elif action == "learn_skill":
        # Grants a specific real skill directly (bypassing the normal
        # level/teacher requirement), matching the exact real,
        # established pattern already used for every other automatic
        # skill grant in leveling.py (learned_skills + a fresh 0%
        # skill_proficiencies entry).
        skill_name = args
        if skill_name not in player.learned_skills:
            player.learned_skills.append(skill_name)
            player.skill_proficiencies[skill_name] = 0
            session.send(f"&Y{speaker_name} teaches you {skill_name}!&x")
    elif action == "require_item":
        # A genuinely NEW, conditional gate (per direct confirmation)
        # -- the first real action that can halt the REST of a
        # program's own actions rather than just doing something
        # itself. args is a real vnum; the check passes only if the
        # player's own real inventory contains a matching item.
        # Fail-SAFE (denies access) if the vnum itself is invalid --
        # caught by direct live testing, an earlier version silently
        # passed the gate for a nonexistent vnum instead of failing.
        obj = olc.OBJECT_TEMPLATES.get(int(args))
        if obj is None:
            return False
        has_item = any(item.lower() == obj["short_desc"].lower() for item in player.inventory)
        if not has_item:
            return False
    elif action == "remember_keyword":
        # Per direct confirmation: once this fires for a player, that
        # same player triggering the same keyword again on this same
        # mob is silently ignored forever (checked in
        # fire_speech_programs, BEFORE any of that keyword's own
        # programs run at all). Memory lives on the mob's own real
        # TEMPLATE (confirmed directly, shared by every spawned copy
        # of this same mob), so it persists through 'save world'
        # automatically -- mob templates are already real, plain,
        # persisted dicts.
        if mob_template is not None and keyword:
            remembered = mob_template.setdefault("remembered_keywords", {})
            names = remembered.setdefault(keyword, [])
            if player.name not in names:
                names.append(player.name)
    elif action in ("min_level", "max_level"):
        # Genuinely a real no-op here (per direct confirmation,
        # Section 142) -- these are checked directly by cmd_move via
        # programs.check_level_gate, on the "move" trigger only,
        # never dispatched through this normal run_action path at
        # all. Explicit rather than silently falling through, so a
        # builder who mistakenly attaches one to a greet/random/
        # speech trigger sees nothing happen rather than a confusing
        # crash or silent wrong behavior.
        pass
    elif action == "wear_message":
        # Per direct request (Section 148): "an item program fro when
        # an item is worn/held/wielded it will display a string to
        # the player/room." Reuses the already-established, real
        # "wear" trigger (_fire_item_trigger in commands.py), which
        # already correctly fires for wear/wield/hold alike via the
        # shared _equip_item function -- no new trigger type needed
        # at all. Messages the wearer directly, then broadcasts the
        # same real line to everyone ELSE physically in the room.
        session.send(args)
        for other in session.active_sessions():
            if other is not session and other.player and other.player.room_vnum == player.room_vnum:
                other.send(args)
    elif action == "iruka_graduation_check":
        # A genuinely one-off, hardcoded action for a specific named
        # NPC (Iruka Sensei, vnum 11, room 30) -- per direct request/
        # confirmation: "just hardcode it to this mob he will not be
        # changed or moved." NOT a generic, reusable action. Gates
        # genin promotion at level 10, checking the player's CURRENT
        # rank first so someone already genin or above is never
        # re-promoted or demoted.
        import kage
        import data_headbands
        try:
            current_rank_index = kage.RANK_ORDER.index(player.village_rank)
        except ValueError:
            current_rank_index = 0
        genin_index = kage.RANK_ORDER.index("genin")
        if current_rank_index >= genin_index:
            session.send(f'{speaker_name} says, "You\'ve already graduated the academy."')
        elif player.level < 10:
            session.send(f'{speaker_name} says, "You need level 10 to graduate the academy."')
        else:
            player.village_rank = "genin"
            data_headbands.apply_rank_headband(player, "genin")
            session.send(f'{speaker_name} says, "Congratulations, you have graduated the academy!"')
            kage.announce_rank_up(player.name, "genin")
            kage.award_genin_mission_points_if_applicable(session, player, "genin")
    return True


def fire_programs(session, programs: list, trigger: str, speaker_name: str = "Something") -> None:
    """Runs every program in `programs` matching `trigger`, in order.
    Not used for 'speech' -- see fire_speech_programs, which also needs
    to match the spoken text against each program's keyword. A real
    require_item action returning False (per direct confirmation, a
    genuinely new conditional gate) halts the REST of this program's
    own actions entirely, not just that one action."""
    for prog in programs:
        if prog.get("trigger") == trigger:
            if not run_action(session, prog.get("action", ""), prog.get("args", ""), speaker_name):
                break


def check_level_gate(session, mob_programs: list, direction: str, speaker_name: str = "Something") -> bool:
    """Checked directly by cmd_move (not the normal run_action/
    fire_programs dispatch) -- per direct confirmation (Section 142):
    "a mob standing at/near an exit checks the player's level...like
    a guard physically stopping them." A mob's own real min_level/
    max_level programs targeting the SAME direction the player is
    trying to leave in can block that specific move. min_level blocks
    if the player's level is BELOW the given number; max_level blocks
    if it's AT OR ABOVE it (both confirmed directly, e.g. "min_level
    north 20 blocks going north below level 20"). A real, optional
    custom message can follow the level number (Section 144, per
    direct request: "how would i even have th elevelgate have the mob
    say you arnt ready for this area yet") -- e.g. "min_level north
    20 You're not ready for this yet, kid." -- falling back to a
    generic default line when none is given. Returns True if the move
    is genuinely blocked (caller should refuse the move and stop
    there), False if it's clear to proceed. Staff are deliberately
    NEVER checked here at all -- cmd_move's own real is_staff
    exemption is checked before this function is ever called,
    matching the same real exemption pattern doors/locked exits/
    apartment ownership already use."""
    player = session.player
    for prog in mob_programs:
        if prog.get("trigger") != "move":
            continue
        action = prog.get("action")
        args = (prog.get("args") or "").strip()
        if action not in ("min_level", "max_level"):
            continue
        try:
            prog_direction, rest = args.split(None, 1)
        except ValueError:
            continue
        # The level number is the first token of `rest`; anything
        # after it is a real, optional custom message (per direct
        # confirmation) -- the builder's own line for this specific
        # gate, replacing the generic default when given.
        level_parts = rest.split(None, 1)
        try:
            required_level = int(level_parts[0])
        except ValueError:
            continue
        custom_message = level_parts[1].strip() if len(level_parts) > 1 else None
        if prog_direction.lower() != direction:
            continue
        if action == "min_level" and player.level < required_level:
            message = custom_message or "You're not ready for this yet."
            session.send(f'{speaker_name} blocks your way. "{message}"')
            return True
        if action == "max_level" and player.level >= required_level:
            message = custom_message or "This isn't for someone of your level."
            session.send(f'{speaker_name} blocks your way. "{message}"')
            return True
    return False


def fire_speech_programs(session, programs: list, spoken_text: str, speaker_name: str = "Something", mob_template: dict = None) -> bool:
    """Checks every 'speech' program's keyword against `spoken_text`
    (case-insensitive substring match). Finds the FIRST DIFFERENT
    keyword that matches, then fires EVERY program sharing that exact
    keyword -- a quest reward is often more than one thing (a line of
    dialogue, an item, some ryo/mission points), so a builder stacks
    several programs under the same keyword rather than being limited
    to one action per keyword. Only one keyword's worth of programs
    fires per utterance, even if a sentence happens to contain more
    than one DIFFERENT configured keyword. Returns True if anything
    fired, so callers can tell whether the 'say' was actually heard.

    mob_template (per direct confirmation, the new remember_keyword
    action) is the mob's own real, live template dict -- passed
    through so a matched keyword can be checked against
    remembered_keywords (a real dict of keyword -> set of player
    names who've already triggered it) BEFORE running any of that
    keyword's own real programs at all. A remembered player gets
    genuinely nothing for that keyword, forever, matching the
    confirmed design exactly. Memory lives on the TEMPLATE itself
    (confirmed directly), so every spawned copy of this same mob
    shares the same real memory, and it persists through 'save
    world' automatically (mob templates are already real, plain,
    persisted dicts)."""
    spoken_lower = spoken_text.lower()
    matched_keyword = None
    for prog in programs:
        if prog.get("trigger") != "speech":
            continue
        keyword = (prog.get("keyword") or "").lower()
        if keyword and keyword in spoken_lower:
            matched_keyword = keyword
            break

    if not matched_keyword:
        return False

    if mob_template is not None:
        remembered = mob_template.get("remembered_keywords", {})
        if session.player.name in remembered.get(matched_keyword, []):
            return False

    for prog in programs:
        if prog.get("trigger") == "speech" and (prog.get("keyword") or "").lower() == matched_keyword:
            if not run_action(session, prog.get("action", ""), prog.get("args", ""), speaker_name, mob_template=mob_template, keyword=matched_keyword):
                break
    return True


def process_random_triggers() -> None:
    """Called once per pulse (server.py's pulse loop). Rolls
    RANDOM_TRIGGER_CHANCE_PCT independently for every mob and room with
    a 'random' program, for every player session currently sharing that
    mob's/room's location -- so a busy room can fire its random program
    for more than one player on the same pulse, but each player rolls
    their own independent chance. (Area/room reset messages used to be
    rolled here too, but per direct follow-up request they're now a
    genuine fixed 15-minute timer instead -- see areas.
    perform_all_area_resets, called from server.py's own loop.)"""
    import random

    import combat
    import session as session_module
    import world

    for s in session_module.ACTIVE_SESSIONS:
        if not s.player:
            continue
        room = world.WORLD.get(s.player.room_vnum)
        if room and room.programs and random.randint(1, 100) <= RANDOM_TRIGGER_CHANCE_PCT:
            fire_programs(s, room.programs, "random", speaker_name=room.name)
        for mob in combat.mobs_in_room(s.player.room_vnum):
            t = combat.MOB_TEMPLATES.get(mob.template_vnum)
            if t and t.get("mob_programs") and random.randint(1, 100) <= RANDOM_TRIGGER_CHANCE_PCT:
                fire_programs(s, t["mob_programs"], "random", speaker_name=mob.name.capitalize())
