"""Sandboxed SmaugFUSS-inspired multiline programs for Nindo_mud builders.

Scripts are data, never Python. No eval/exec, filesystem, shell, network, or
privileged staff commands. Limits apply during validation AND at runtime.
Legacy one-action programs continue to run in programs.py unchanged.
"""
import random
import re

MAX_SCRIPT_CHARS = 12000
MAX_LINES = 160
MAX_DEPTH = 8
MAX_ACTIONS = 60
MAX_CALL_DEPTH = 4
MAX_PROGRAMS = 60
TRIGGERS = {
    "mob": {"greet", "speech", "death", "fight", "random", "move"},
    "room": {"enter", "random"},
    "item": {"get", "wear"},
}
COMMANDS = {
    "say", "emote", "mpecho", "mpechoat", "mpechoaround",
    "mptransfer", "mpmload", "mpoload", "mpforce", "mpgive",
    "mpheal", "mpgoto",
}
COMPARISONS = {"==", "!=", "<", "<=", ">", ">="}
_CONDITION = re.compile(r"^([a-z_]+)\s*\(([^()]*)\)\s*(==|!=|<=|>=|<|>)?\s*(.*?)\s*$", re.I)
_VARIABLE = re.compile(r"\$\$|\$[nirvd]", re.I)


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
    if func not in {"level", "room", "ryo", "rank", "clan", "name", "direction", "hasitem", "random", "ispc"}:
        raise ValueError(f"Unsupported condition '{func}()'.")
    if func in {"random", "hasitem", "ispc"}:
        if operator or expected:
            raise ValueError(f"{func}() is a boolean test (no comparison).")
        if func == "random" and (not arguments.isdigit() or not 1 <= int(arguments) <= 100):
            raise ValueError("random() requires a percent from 1 to 100.")
        if func == "hasitem" and not re.fullmatch(r"\$n\s*,\s*[0-9]{1,6}", arguments, re.I):
            raise ValueError("hasitem($n, OBJECT_VNUM) requires a numeric object VNUM.")
        if func == "ispc" and arguments.lower() != "$n":
            raise ValueError("Use ispc($n).")
    else:
        if arguments.lower() != ("$d" if func == "direction" else "$n") or operator not in COMPARISONS or not expected:
            raise ValueError(f"Use {func}($n) == value (or <, <=, >, >=, !=).")
        if func in {"level", "room", "ryo"} and not re.fullmatch(r"-?\d{1,9}", expected):
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
            if word in {"mptransfer", "mpmload", "mpoload", "mpgive", "mpheal", "mpgoto"}:
                if not re.fullmatch(r"\d{1,7}", args.strip()):
                    raise ValueError(f"Line {number}: {word} expects a numeric VNUM/amount.")
                value = int(args.strip())
                if value <= 0 or value > (10000 if word == "mpheal" else 999999):
                    raise ValueError(f"Line {number}: {word} value is out of range.")
            if word == "mpforce":
                forced = args.strip().split(None, 1)
                if not forced or forced[0].lower() not in {"look", "say", "emote"}:
                    raise ValueError("mpforce is restricted to look, say and emote; no staff/player commands.")
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


def _evaluate(expression, session):
    func, arguments, comparison, expected = _condition_parts(expression)
    player = session.player
    if func == "random":
        return random.randint(1, 100) <= int(arguments)
    if func == "ispc":
        return bool(player)
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
    }[func]
    if func in {"level", "room", "ryo"}:
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
              "$d": getattr(session, "_mudprog_direction", "")}
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
        # Deliberately never call the general command dispatcher: it
        # would let scripts invoke staff/admin commands as a player.
        forced, _, value = args.partition(" ")
        if forced.lower() == "look":
            import commands
            commands.cmd_look(session, [])
        elif forced.lower() == "say" and value.strip():
            _broadcast(session, f"{player.name} says, '{value}'")
        elif forced.lower() == "emote" and value.strip():
            _broadcast(session, f"{player.name} {value}")


def execute(script, session, speaker_name="Something", mob=None):
    """Run at most 60 approved actions, with recursion bounded per session.

    Errors in stale/corrupt saved scripts are contained and do not kill
    the whole server pulse or corrupt a player/world save.
    """
    if not getattr(session, "player", None):
        return False
    depth = getattr(session, "_mudprog_depth", 0)
    if depth >= MAX_CALL_DEPTH:
        return False
    try:
        statements = compile_script(script)
    except ValueError:
        return False
    budget = {"actions": 0, "loads": 0}
    session._mudprog_depth = depth + 1
    try:
        def walk(nodes):
            for node in nodes:
                if budget["actions"] >= MAX_ACTIONS:
                    return
                if node["kind"] == "if":
                    walk(node["then"] if any(_evaluate(expr, session)
                                             for expr in node["conditions"])
                         else node["otherwise"])
                else:
                    budget["actions"] += 1
                    _command(session, node["command"], node["args"], speaker_name, mob, budget)
        walk(statements)
        return True
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False
    finally:
        session._mudprog_depth = depth
