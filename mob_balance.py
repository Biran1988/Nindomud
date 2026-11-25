"""Adjustable, level-based PvE difficulty for ordinary mobs.

All normal spawned mobs share one baseline at each assigned level. The
multipliers are persisted outside the repository's tracked source, so staff
can balance fights without rewriting any world or player data.

Bosses / unusual scripted mobs can opt out with mset <vnum> autobalance off.
Only newly spawned mobs receive changes; live fights are never silently reset.
"""
from copy import deepcopy
import json
import os
import tempfile

DEFAULT_SETTINGS = {"hp_percent": 100, "damage_percent": 100, "hitroll_percent": 100}
# Fivefold base health gives players time to use jutsu instead of one-shotting mobs.
# The adjustable mobscale HP percentage remains relative to this tougher baseline.
BASE_HP_MULTIPLIER = 5
_MIN_PERCENT = 25
_MAX_PERCENT = 400
_cached_path = None
_cached_settings = None


def _settings_path():
    import storage
    return os.path.join(storage.DATA_DIR, "mob_balance.json")


def rank_brackets():
    """Mob level bands, inclusive and non-overlapping, using earned rank caps."""
    import kage
    start = 1
    result = []
    for rank in kage.RANK_ORDER:
        end = kage.RANK_LEVEL_CAPS[rank]
        result.append((rank, start, end))
        start = end + 1
    return result


def rank_for_level(level):
    brackets = rank_brackets()
    level = max(1, min(brackets[-1][2], int(level)))
    return next(rank for rank, low, high in brackets if low <= level <= high)


def resolve_bracket(value):
    key = value.strip().lower().replace("_", " ").replace("jounin", "jonin").replace("chuunin", "chunin")
    aliases = {"academy": "student", "special": "special jonin", "special-jonin": "special jonin"}
    key = aliases.get(key, key)
    return next((rank for rank, low, high in rank_brackets()
                 if key in (rank, f"{low}-{high}")), None)


def _valid_percent(value):
    return type(value) is int and _MIN_PERCENT <= value <= _MAX_PERCENT


def _load_settings():
    global _cached_path, _cached_settings
    path = _settings_path()
    if _cached_path != path or _cached_settings is None:
        values = dict(DEFAULT_SETTINGS)
        stored = {}
        try:
            with open(path, encoding="utf-8") as handle:
                candidate = json.load(handle)
            if isinstance(candidate, dict):
                stored = candidate
        except (OSError, ValueError, TypeError):
            pass
        for field in DEFAULT_SETTINGS:
            if _valid_percent(stored.get(field)):
                values[field] = stored[field]
        # Migrate legacy global percentages to independent copies. Missing
        # or invalid fields inherit the legacy value only on load.
        overrides = stored.get("brackets", {})
        if not isinstance(overrides, dict):
            overrides = {}
        bands = {}
        for rank, _, _ in rank_brackets():
            values_for_rank = dict(values)
            record = overrides.get(rank, {})
            if isinstance(record, dict):
                for field in DEFAULT_SETTINGS:
                    if _valid_percent(record.get(field)):
                        values_for_rank[field] = record[field]
            bands[rank] = values_for_rank
        values["brackets"] = bands
        _cached_path, _cached_settings = path, values
    return deepcopy(_cached_settings)


def settings(level=None, *, rank=None):
    """Return a copy of the selected band; no-argument legacy global view."""
    current = _load_settings()
    if level is not None:
        rank = rank_for_level(level)
    if rank is not None:
        return current["brackets"][rank]
    return {field: current[field] for field in DEFAULT_SETTINGS}


def set_percent(field, percent, *, rank=None):
    if field not in DEFAULT_SETTINGS:
        raise ValueError("Unknown balance setting.")
    if not _valid_percent(percent):
        raise ValueError("Percent must be between 25 and 400.")
    import storage
    current = _load_settings()
    if rank is None:
        # Legacy global syntax intentionally updates this stat in ALL
        # bands. Other stats remain independent and unchanged.
        current[field] = percent
        for values in current["brackets"].values():
            values[field] = percent
    else:
        if rank not in current["brackets"]:
            raise ValueError("Unknown rank bracket.")
        current["brackets"][rank][field] = percent
    storage.ensure_dirs()
    path = _settings_path()
    fd, temp_path = tempfile.mkstemp(prefix=".mob_balance_", suffix=".json", dir=storage.DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(current, stream, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    global _cached_path, _cached_settings
    _cached_path, _cached_settings = path, current
    return settings(rank=rank)


def hp_for_level(level, setting=None):
    """Durable target with room for multiple spells and combat rounds."""
    level = max(1, min(250, int(level)))
    amount = 80 + 20 * level + 2 * level * level
    percent = (setting or settings(level))["hp_percent"]
    return max(1, amount * BASE_HP_MULTIPLIER * percent // 100)


def hit_roll_for_level(level, setting=None):
    """Level-scaled accuracy for auto-balanced NPCs.

    Mob combat uses Dexterity-10 as its *effective* hitroll. A flat zero
    leaves advanced NPCs almost unable to hit a trained Dexterity build.
    +0.6 per level keeps early mobs modest and grants +150 at level 250.
    Staff can tune this with MOB SCALE HITROLL without editing templates.
    """
    level = max(1, min(250, int(level)))
    baseline = round(level * 0.6)
    percent = (setting or settings(level))["hitroll_percent"]
    return max(1, round(baseline * percent / 100))


def target_damage_for_level(level, setting=None):
    """Expected total outgoing hit, including derived Strength damage_roll."""
    level = max(1, min(250, int(level)))
    amount = round(3 + 0.65 * level + 0.0075 * level * level)
    percent = (setting or settings(level))["damage_percent"]
    return max(2, amount * percent // 100)


def damage_dice_for_level(level, setting=None):
    """Create dice that produce the intended damage after Strength bonuses.

    The existing combat engine adds both rolled dice and a Strength modifier
    derived from their average, so we calibrate for BOTH, not just the roll.
    """
    target = target_damage_for_level(level, setting)
    sides = max(1, target // 3)
    average = (sides + 1) // 2
    bonus = max(0, round(target / 2) - average)
    return f"1d{sides}+{bonus}"


def cmd_mobscale(session, args):
    """Administrator controls for independently saved rank-level bands."""
    from kage import rank_label
    if (not getattr(session, "account", None)
            or session.account.staff_level not in {"administrator", "implementor"}):
        session.send("Only administrators may tune mob difficulty.")
        return
    usage = ("Usage: mobscale | mobscale preview <level> | "
             "mobscale <rank or level-range> <hp|damage|hitroll> <25-400>\n"
             "       mobscale all <hp|damage|hitroll> <25-400>")
    if not args:
        lines = ["Standard mob scaling (5x base HP; applies on next spawn):",
                 f"{'Rank':17} {'Levels':9} {'HP':>5} {'Damage':>7} {'Hitroll':>7}"]
        for rank, low, high in rank_brackets():
            values = settings(rank=rank)
            lines.append(f"{rank_label(rank):17} {f'{low}-{high}':9} "
                         f"{values['hp_percent']:4}% {values['damage_percent']:6}% "
                         f"{values['hitroll_percent']:6}%")
        session.send("\n".join(lines) + "\n" + usage)
        return
    if args[0].lower() == "preview":
        if len(args) != 2 or not args[1].isdigit() or not 1 <= int(args[1]) <= 250:
            session.send("Usage: mobscale preview <level 1-250>")
            return
        level = int(args[1])
        session.send(f"Level {level} standard mob ({rank_label(rank_for_level(level))} bracket): "
                     f"{hp_for_level(level):,} HP; "
                     f"about {target_damage_for_level(level):,} damage per hit; "
                     f"+{hit_roll_for_level(level)} hitroll "
                     f"({damage_dice_for_level(level)} before the derived Strength bonus).")
        return
    keys = {"hp": "hp_percent", "damage": "damage_percent", "hitroll": "hitroll_percent"}
    rank = None
    if len(args) == 2 and args[0].lower() in keys:
        # Keep the existing global command syntax compatible.
        field, number = args
    elif len(args) >= 3:
        scope = " ".join(args[:-2]).lower()
        field, number = args[-2:]
        if scope != "all":
            rank = resolve_bracket(scope)
            if rank is None:
                session.send(usage)
                return
    else:
        session.send(usage)
        return
    key = keys.get(field.lower())
    if key is None or not number.isdigit():
        session.send(usage)
        return
    try:
        values = set_percent(key, int(number), rank=rank)
    except (ValueError, OSError) as exc:
        session.send(f"Mob balance was not changed: {exc}")
        return
    scope = rank_label(rank) if rank is not None else "ALL rank brackets"
    session.send(f"Mob balance saved: {scope} - HP {values['hp_percent']}%, "
                 f"Damage {values['damage_percent']}%, Hitroll {values['hitroll_percent']}%. "
                 "Newly spawned mobs use the new standard; existing fights are unchanged.")
