"""Adjustable, level-based PvE difficulty for ordinary mobs.

All normal spawned mobs share one baseline at each assigned level. The
multipliers are persisted outside the repository's tracked source, so staff
can balance fights without rewriting any world or player data.

Bosses / unusual scripted mobs can opt out with mset <vnum> autobalance off.
Only newly spawned mobs receive changes; live fights are never silently reset.
"""
import json
import os
import tempfile

DEFAULT_SETTINGS = {"hp_percent": 100, "damage_percent": 100}
_MIN_PERCENT = 25
_MAX_PERCENT = 400
_cached_path = None
_cached_settings = None


def _settings_path():
    import storage
    return os.path.join(storage.DATA_DIR, "mob_balance.json")


def settings():
    global _cached_path, _cached_settings
    path = _settings_path()
    if _cached_path != path or _cached_settings is None:
        values = dict(DEFAULT_SETTINGS)
        try:
            with open(path, encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                for field in values:
                    value = stored.get(field)
                    if type(value) is int and _MIN_PERCENT <= value <= _MAX_PERCENT:
                        values[field] = value
        except (OSError, ValueError, TypeError):
            pass
        _cached_path, _cached_settings = path, values
    return dict(_cached_settings)


def set_percent(field, percent):
    if field not in DEFAULT_SETTINGS:
        raise ValueError("Unknown balance setting.")
    if type(percent) is not int or not _MIN_PERCENT <= percent <= _MAX_PERCENT:
        raise ValueError("Percent must be between 25 and 400.")
    import storage
    current = settings()
    current[field] = percent
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
    return dict(current)


def hp_for_level(level, setting=None):
    """Durable target with room for multiple spells and combat rounds."""
    level = max(1, min(250, int(level)))
    amount = 80 + 20 * level + 2 * level * level
    percent = (setting or settings())["hp_percent"]
    return max(1, amount * percent // 100)


def target_damage_for_level(level, setting=None):
    """Expected total outgoing hit, including derived Strength damage_roll."""
    level = max(1, min(250, int(level)))
    amount = round(3 + 0.65 * level + 0.0075 * level * level)
    percent = (setting or settings())["damage_percent"]
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
    """Administrator controls: mobscale, mobscale preview 50, hp 125, damage 85."""
    if (not getattr(session, "account", None)
            or session.account.staff_level not in {"administrator", "implementor"}):
        session.send("Only administrators may tune mob difficulty.")
        return
    if not args:
        values = settings()
        session.send(
            "Standard mob scaling (applies on next spawn): "
            f"HP {values['hp_percent']}%, Damage {values['damage_percent']}%.\n"
            "Usage: mobscale preview <level> | mobscale hp <25-400> | "
            "mobscale damage <25-400>\n"
            "A specific mob can use custom hit/damage dice with 'mset <vnum> autobalance off'."
        )
        return
    if args[0].lower() == "preview":
        if len(args) != 2 or not args[1].isdigit() or not 1 <= int(args[1]) <= 250:
            session.send("Usage: mobscale preview <level 1-250>")
            return
        level = int(args[1])
        session.send(f"Level {level} standard mob: {hp_for_level(level):,} HP; "
                     f"about {target_damage_for_level(level):,} damage per hit "
                     f"({damage_dice_for_level(level)} before the derived Strength bonus).")
        return
    key = {"hp": "hp_percent", "damage": "damage_percent"}.get(args[0].lower())
    if key is None or len(args) != 2 or not args[1].isdigit():
        session.send("Usage: mobscale hp <25-400> | mobscale damage <25-400>")
        return
    try:
        values = set_percent(key, int(args[1]))
    except (ValueError, OSError) as exc:
        session.send(f"Mob balance was not changed: {exc}")
        return
    session.send(f"Mob balance saved: HP {values['hp_percent']}%, "
                 f"Damage {values['damage_percent']}%. "
                 "Newly spawned mobs use the new standard; existing fights are unchanged.")
