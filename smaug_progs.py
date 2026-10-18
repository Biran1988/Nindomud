"""Sandboxed SmaugFUSS-inspired multiline programs for Nindo_mud builders.

Scripts are data, never Python. No eval/exec, filesystem, shell, network, or
privileged staff commands. Limits apply during validation AND at runtime.
Legacy one-action programs continue to run in programs.py unchanged.
"""
import random
import re
import time

MAX_SCRIPT_CHARS = 12000
MAX_LINES = 160
MAX_DEPTH = 8
MAX_ACTIONS = 60
MAX_CALL_DEPTH = 4
MAX_PROGRAMS = 60
MAX_PENDING = 256  # global queued delayed continuations
MAX_PENDING_PER_PLAYER = 8
MAX_WAIT_SECONDS = 120
MAX_TOTAL_WAIT_SECONDS = 300
_PENDING = []  # ephemeral per-server runtime, never world/player save data
TRIGGERS = {
    "mob": {"greet", "speech", "death", "fight", "random", "move", "give", "bribe", "entry"},
    "room": {"enter", "random"},
    "item": {"get", "wear"},
}
COMMANDS = {
    "say", "emote", "mpecho", "mpechoat", "mpechoaround",
    "mptransfer", "mpmload", "mpoload", "mpforce", "mpgive",
    "mpheal", "mpgoto", "mphealmana", "mphealmove", "mpdamage",
    "mphealchakra", "mphealstamina",
    "mpasound", "mpjunk", "mpremember", "mpforget", "wait",
}
COMPARISONS = {"==", "!=", "<", "<=", ">", ">="}
_CONDITION = re.compile(r"^([a-z_]+)\s*\(([^()]*)\)\s*(==|!=|<=|>=|<|>)?\s*(.*?)\s*$", re.I)
_VARIABLE = re.compile(r"\$\$|\$[nirvdob]", re.I)


def validate_script(script):
    """Return clear editing errors, never an executable Python object."""
    try:
        compile_script(script)
    except ValueError as exc:
        return [str(exc)]
    return []


def _condition_parts(expression):
    match = _CONDITION.fullmatch(expression.strip())
    if not match:
        raise ValueError("Condition syntax: if level($n) < 10, if hasitem($n, 100), or if random(30).")
    func, arguments, operator, expected = match.groups()
    func = func.lower()
    if func not in {"level", "room", "ryo", "rank", "clan", "name", "direction", "object", "bribe", "hasitem", "random", "ispc",
                    "hitprcnt", "moblevel", "health", "chakra", "stamina", "roomflag",
                    "remembered"}:
        raise ValueError(f"Unsupported condition '{func}()'.")
    if func in {"random", "hasitem", "ispc", "roomflag", "remembered"}:
        if operator or expected:
            raise ValueError(f"{func}() is a boolean test (no comparison).")
        if func == "random" and (not arguments.isdigit() or not 1 <= int(arguments) <= 100):
            raise ValueError("random() requires a percent from 1 to 100.")
        if func == "hasitem" and not re.fullmatch(r"\$n\s*,\s*[0-9]{1,6}", arguments, re.I):
            raise ValueError("hasitem($n, OBJECT_VNUM) requires a numeric object VNUM.")
        if func == "ispc" and arguments.lower() != "$n":
            raise ValueError("Use ispc($n).")
        if func == "roomflag" and not re.fullmatch(r"\$r\s*,\s*[A-Za-z_]{1,40}", arguments, re.I):
            raise ValueError("Use roomflag($r, no_wander).")
        if func == "remembered" and not re.fullmatch(r"\$n\s*,\s*[A-Za-z0-9_-]{1,60}", arguments, re.I):
            raise ValueError("Use remembered($n, quest_marker).")
    else:
        if arguments.lower() != {"direction": "$d", "object": "$o", "bribe": "$b",
                                  "hitprcnt": "$i", "moblevel": "$i"}.get(func, "$n") or operator not in COMPARISONS or not expected:
            raise ValueError(f"Use {func}($n) == value (or <, <=, >, >=, !=).")
        if func in {"level", "room", "ryo", "object", "bribe", "hitprcnt", "moblevel",
                    "health", "chakra", "stamina"} and not re.fullmatch(r"-?\d{1,9}", expected):
            raise ValueError(f"{func}() needs an integer comparison value.")
        if func in {"rank", "clan", "name", "direction"} and (operator not in {"==", "!="} or len(expected) > 60):
            raise ValueError(f"{func}() accepts only == or != and bounded text.")
    return func, arguments, operator, expected


def compile_script(script):
    if not isinstance(script, str) or len(script) > MAX_SCRIPT_CHARS:
        raise ValueError(f"Script must contain at most {MAX_SCRIPT_CHARS} characters.")
    if not script.strip():
        raise ValueError("Script must have at least one command.")
    lines = script.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError(f"Script exceeds {MAX_LINES} lines.")
    root = []
    stack = []
    for number, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith("//"):
            continue
        word, _, args = stripped.partition(" ")
        word = word.lower()
        current = (stack[-1]["otherwise"] if stack[-1]["branch"] == "otherwise"
                   else stack[-1]["then"]) if stack else root
        if word == "if":
            _condition_parts(args)
            if len(stack) >= MAX_DEPTH:
                raise ValueError(f"Line {number}: maximum nested if depth is {MAX_DEPTH}.")
            node = {"kind": "if", "conditions": [args], "then": [], "otherwise": [], "branch": "then"}
            current.append(node)
            stack.append(node)
        elif word == "or":
            if not stack or stack[-1]["branch"] != "then" or stack[-1]["then"]:
                raise ValueError(f"Line {number}: or must immediately follow if/or, before its commands.")
            _condition_parts(args)
            stack[-1]["conditions"].append(args)
        elif word == "else":
            if not stack or stack[-1]["branch"] != "then":
                raise ValueError(f"Line {number}: else without an unmatched if.")
            stack[-1]["branch"] = "otherwise"
        elif word == "endif":
            if not stack:
                raise ValueError(f"Line {number}: endif without if.")
            stack.pop()
        else:
            if word not in COMMANDS:
                raise ValueError(f"Line {number}: unknown MUD program command '{word}'.")
            if not args.strip():
                raise ValueError(f"Line {number}: {word} requires arguments.")
            if word in {"mptransfer", "mpmload", "mpoload", "mpgive", "mpheal", "mpgoto",
                        "mphealmana", "mphealmove", "mphealchakra", "mphealstamina",
                        "mpdamage", "wait", "mpjunk"}:
                if word == "mpjunk" and args.strip().lower() == "all":
                    pass
                elif not re.fullmatch(r"\d{1,7}", args.strip()):
                    raise ValueError(f"Line {number}: {word} expects a numeric VNUM/amount.")
                if word != "mpjunk" or args.strip().lower() != "all":
                    value = int(args.strip())
                    cap = (MAX_WAIT_SECONDS if word == "wait" else
                           10000 if word in {"mpheal", "mphealmana", "mphealmove", "mphealchakra", "mphealstamina"} else
                           500 if word == "mpdamage" else 999999)
                    if value <= 0 or value > cap:
                        raise ValueError(f"Line {number}: {word} value is out of range.")
            if word in {"mpremember", "mpforget"} and not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", args.strip()):
                raise ValueError(f"Line {number}: {word} requires a short quest marker identifier.")
            if word == "mpforce":
                import force_commands
                _, problem = force_commands.parse_mpforce_args(args)
                if problem:
                    raise ValueError(f"Line {number}: mpforce: {problem}")
            current.append({"kind": "cmd", "command": word, "args": args})
    if stack:
        raise ValueError("Missing endif for one or more if blocks.")
    if not root:
        raise ValueError("Script contains no commands.")
    return root


def validate_entry(entry, allowed):
    if not isinstance(entry, dict) or set(entry) - {"trigger", "script", "keyword", "chance"}:
        return ["Script entry has invalid keys."]
    trigger = entry.get("trigger")
    if trigger not in allowed:
        return [f"Unsupported script trigger: {trigger!r}."]
    keyword = entry.get("keyword", "")
    if trigger == "speech" and (not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 120):
        return ["Speech scripts require a keyword of 1–120 characters."]
    if trigger != "speech" and keyword:
        return ["Only speech scripts may have a keyword."]
    chance = entry.get("chance", 100)
    if type(chance) is not int or not 1 <= chance <= 100:
        return ["Script chance must be an integer percentage from 1 to 100."]
    return validate_script(entry.get("script"))


def _evaluate(expression, session, mob=None):
    func, arguments, comparison, expected = _condition_parts(expression)
    player = session.player
    if func == "random":
        return random.randint(1, 100) <= int(arguments)
    if func == "ispc":
        return bool(player)
    if func == "remembered":
        import combat
        template = combat.MOB_TEMPLATES.get(mob.template_vnum) if mob else None
        key = arguments.split(",", 1)[1].strip().casefold()
        return bool(template and player.name in template.get("script_memory", {}).get(key, []))
    if func == "roomflag":
        import world
        vnum = player.room_vnum
        flag = arguments.split(",", 1)[1].strip()
        room = world.WORLD.get(vnum)
        return bool(room and flag in room.flags)
    if func == "hasitem":
        import olc
        vnum = int(arguments.split(",", 1)[1].strip())
        template = olc.OBJECT_TEMPLATES.get(vnum)
        return bool(template and any(x.lower() == template["short_desc"].lower()
                                     for x in player.inventory))
    actual = {
        "level": player.level, "room": player.room_vnum,
        "ryo": player.ryo, "rank": player.village_rank,
        "clan": player.clan, "name": player.name,
        "direction": getattr(session, "_mudprog_direction", ""),
        "object": getattr(session, "_mudprog_object_vnum", 0),
        "bribe": getattr(session, "_mudprog_bribe", 0),
        "hitprcnt": max(0, 100 * mob.health // max(1, mob.max_health)) if mob else -1,
        "moblevel": mob.level if mob else -1,
        "health": player.health,
        "chakra": player.chakra,
        "stamina": player.stamina,
    }[func]
    if func in {"level", "room", "ryo", "object", "bribe", "hitprcnt", "moblevel",
                "health", "chakra", "stamina"}:
        expected = int(expected)
    else:
        actual = str(actual).casefold()
        expected = expected.casefold()
    return {
        "==": lambda: actual == expected, "!=": lambda: actual != expected,
        "<": lambda: actual < expected, "<=": lambda: actual <= expected,
        ">": lambda: actual > expected, ">=": lambda: actual >= expected,
    }[comparison]()


def _substitute(text, session, speaker_name, mob=None):
    room = session.player.room_vnum
    values = {"$n": session.player.name,
              "$i": mob.name if mob else speaker_name,
              "$r": str(room), "$v": str(mob.template_vnum) if mob else "0",
              "$d": getattr(session, "_mudprog_direction", ""),
              "$o": getattr(session, "_mudprog_object_name", ""),
              "$b": str(getattr(session, "_mudprog_bribe", 0))}
    return _VARIABLE.sub(lambda match: "$" if match.group(0) == "$$"
                         else values.get(match.group(0).lower(), ""), text)[:2000]


def _broadcast(session, text, *, include_self=True):
    for other in session.active_sessions():
        if other.player and other.player.room_vnum == session.player.room_vnum:
            if include_self or other is not session:
                other.send(text)


def _command(session, command, args, speaker_name, mob, budget):
    import combat
    import olc
    import world
    player = session.player
    source_args = args  # retain literal $n in mpforce target syntax
    args = _substitute(args, session, speaker_name, mob)
    room_vnum = mob.room_vnum if mob else player.room_vnum
    room = world.WORLD.get(room_vnum)
    if command == "say":
        _broadcast(session, f'{speaker_name} says, "{args}"')
    elif command == "emote":
        _broadcast(session, f"{speaker_name} {args}")
    elif command == "mpecho":
        _broadcast(session, args)
    elif command == "mpechoat":
        session.send(args)
    elif command == "mpechoaround":
        _broadcast(session, args, include_self=False)
    elif command == "mpheal":
        amount = int(args)
        player.health = min(player.maximum_health, player.health + amount)
        session.send(f"{speaker_name} restores {amount} health.")
    elif command in {"mphealmana", "mphealchakra"}:
        amount = int(args)
        player.chakra = min(player.maximum_chakra, player.chakra + amount)
    elif command in {"mphealmove", "mphealstamina"}:
        amount = int(args)
        player.stamina = min(player.maximum_stamina, player.stamina + amount)
    elif command == "mpdamage":
        # Scripted attacks cannot bypass the game\'s death/combat pipeline.
        player.health = max(1, player.health - int(args))
        session.send(f"{speaker_name} strikes you with a scripted attack!")
    elif command == "mpasound":
        # Echo once to players in immediately adjacent enabled rooms.
        if room:
            import session as session_module
            dests = {v for v in room.exits.values() if world.WORLD.get(v) and world.WORLD.get(v).enabled}
            for other in session_module.ACTIVE_SESSIONS:
                if other.player and other.player.room_vnum in dests:
                    other.send(args)
    elif command == "mpjunk" and room:
        if args.lower() == "all":
            del room.ground_items[:20]
        else:
            template = olc.OBJECT_TEMPLATES.get(int(args))
            if template and template["short_desc"] in room.ground_items:
                room.ground_items.remove(template["short_desc"])
    elif command == "mpremember" and mob:
        # Saved per prototype like legacy remember_keyword, not an arbitrary variable.
        template = combat.MOB_TEMPLATES.get(mob.template_vnum)
        if template is not None:
            memory = template.setdefault("script_memory", {})
            key = args.casefold()[:60]
            if key in memory or len(memory) < 100:
                names = memory.setdefault(key, [])
                if player.name not in names and len(names) < 300:
                    names.append(player.name)
    elif command == "mpforget" and mob:
        template = combat.MOB_TEMPLATES.get(mob.template_vnum)
        if template is not None:
            memory = template.get("script_memory", {})
            key = args.casefold()[:60]
            if player.name in memory.get(key, []):
                memory[key].remove(player.name)
    elif command == "mpgive":
        import inventory
        item = olc.OBJECT_TEMPLATES.get(int(args))
        if item:
            inventory.add_item(player.inventory, item["short_desc"])
    elif command == "mptransfer":
        dest = world.WORLD.get(int(args))
        if dest and dest.enabled and not dest.apartment and not dest.player_shop:
            player.room_vnum = dest.vnum
            session.send(f"{speaker_name} sends you to {dest.name}.")
    elif command == "mpgoto" and mob:
        dest = world.WORLD.get(int(args))
        if dest and dest.enabled and not dest.apartment and not dest.player_shop:
            origin = mob.room_vnum
            if mob in combat.MOBS_BY_ROOM.get(origin, ()):
                combat.MOBS_BY_ROOM[origin].remove(mob)
                mob.room_vnum = dest.vnum
                combat.MOBS_BY_ROOM.setdefault(dest.vnum, []).append(mob)
                import programs
                programs.fire_mob_entry(mob)
    elif command == "mpoload" and room and budget["loads"] < 2:
        item = olc.OBJECT_TEMPLATES.get(int(args))
        if item and item.get("enabled", True) and len(room.ground_items) < 30:
            room.ground_items.append(item["short_desc"])
            budget["loads"] += 1
    elif command == "mpmload" and room and budget["loads"] < 2:
        vnum = int(args)
        t = combat.MOB_TEMPLATES.get(vnum)
        if t and t.get("enabled", True) and not (set(t.get("act_flags", [])) & {"Immortal", "SummonElder"}):
            if sum(m.template_vnum == vnum for m in combat.mobs_in_room(room.vnum)) < 8:
                combat.spawn_mob(vnum, room.vnum)
                budget["loads"] += 1
    elif command == "mpforce":
        # Smaug syntax: mpforce $n <player command>. The original
        # Nindo_mud shorthand "mpforce <command>" still works.
        # Never dispatch arbitrary admin/account verbs, and never
        # force immortal characters, including via a scripted trigger.
        import force_commands
        if source_args.lower().startswith("emote "):
            # Historical "mpforce emote <narration>" produced a custom
            # player emote; preserve it for already-built NPC programs.
            import emotes
            text = _substitute(source_args[6:].strip(), session, speaker_name, mob)
            if text.lower() not in emotes.EMOTES:
                _broadcast(session, f"{player.name} {text}")
                return
        forced_command, error = force_commands.parse_mpforce_args(source_args)
        if error:
            return
        forced_command = _substitute(forced_command, session, speaker_name, mob)
        force_commands.run_forced_player_command(
            session, forced_command, f"{speaker_name}")


def execute(script, session, speaker_name="Something", mob=None):
    """Execute a bounded script, suspending after a validated wait N line.

    Continuations are in-memory only, released on disconnect or restart.
    Script conditions are evaluated when their branch is reached, while
    each wait pauses only its own invocation and never the event loop.
    """
    if not getattr(session, "player", None):
        return False
    if getattr(session, "_mudprog_depth", 0) >= MAX_CALL_DEPTH:
        return False
    try:
        statements = compile_script(script)
    except ValueError:
        return False
    def instructions(nodes):
        for node in nodes:
            if node["kind"] == "if":
                chosen = (node["then"] if any(_evaluate(cond, session, mob)
                                            for cond in node["conditions"])
                          else node["otherwise"])
                yield from instructions(chosen)
            else:
                yield node["command"], node["args"]
    state = {"steps": instructions(statements), "session": session,
             "speaker_name": speaker_name, "mob": mob,
             "budget": {"actions": 0, "loads": 0, "waits": 0},
             "context": {key: getattr(session, key, None) for key in
                         ("_mudprog_direction", "_mudprog_object_vnum",
                          "_mudprog_object_name", "_mudprog_bribe")}}
    return _advance(state, time.time())


def _advance(state, now):
    session = state["session"]
    depth = getattr(session, "_mudprog_depth", 0)
    if depth >= MAX_CALL_DEPTH:
        return False
    old_context = {k: getattr(session, k, None) for k in state["context"]}
    session._mudprog_depth = depth + 1
    for key, value in state["context"].items():
        setattr(session, key, value)
    try:
        for command, args in state["steps"]:
            if command == "wait":
                amount = int(args)
                state["budget"]["waits"] += amount
                if (state["budget"]["waits"] > MAX_TOTAL_WAIT_SECONDS or
                    len(_PENDING) >= MAX_PENDING or
                    sum(item["session"] is session for _, item in _PENDING) >= MAX_PENDING_PER_PLAYER):
                    return False
                _PENDING.append((now + amount, state))
                return True
            if state["budget"]["actions"] >= MAX_ACTIONS:
                return True
            state["budget"]["actions"] += 1
            _command(session, command, args, state["speaker_name"],
                     state["mob"], state["budget"])
        return True
    except (ValueError, TypeError, AttributeError, KeyError, IndexError, RuntimeError):
        return False
    finally:
        for key, value in old_context.items():
            setattr(session, key, value)
        session._mudprog_depth = depth


def process_delayed(now=None):
    """Run due continuations on normal server pulses, not blocking sleeps."""
    if now is None:
        now = time.time()
    import session as session_module
    # Drain a snapshot: a resumed script may schedule its next wait safely.
    due = [(timestamp, state) for timestamp, state in _PENDING if timestamp <= now]
    _PENDING[:] = [(timestamp, state) for timestamp, state in _PENDING if timestamp > now]
    for _, state in due:
        s = state["session"]
        if s in session_module.ACTIVE_SESSIONS and getattr(s, "player", None):
            _advance(state, now)
