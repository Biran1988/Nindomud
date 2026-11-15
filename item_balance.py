"""Opt-in level-based object balancing, adjustable live by administrators.

New staff-built weapons, armor, tools, medical items and food automatically
receive the AutoBalance flag when categorized or copied in OLC. Existing
prototypes retain their saved flags. Healing and food recovery are computed at
use time so level and administrator global percentages take effect immediately.
Explicit builder damage, AC, cost, healing and tool overrides win.
"""
import json
import os
import tempfile

DEFAULT_SETTINGS = {"damage_percent": 100, "armor_percent": 100,
                    "value_percent": 100, "uses_percent": 100,
                    "healing_percent": 100, "food_percent": 100}
MIN_PERCENT, MAX_PERCENT = 25, 400
_cached_path = None
_cached_settings = None


def _path():
    import storage
    return os.path.join(storage.DATA_DIR, "item_balance.json")


def settings():
    global _cached_path, _cached_settings
    path = _path()
    if path != _cached_path or _cached_settings is None:
        values = dict(DEFAULT_SETTINGS)
        try:
            with open(path, encoding="utf-8") as stream:
                raw = json.load(stream)
            if isinstance(raw, dict):
                for key in values:
                    value = raw.get(key)
                    if type(value) is int and MIN_PERCENT <= value <= MAX_PERCENT:
                        values[key] = value
        except (OSError, ValueError, TypeError):
            pass
        _cached_path, _cached_settings = path, values
    return dict(_cached_settings)


def set_percent(key, percent):
    if key not in DEFAULT_SETTINGS or type(percent) is not int or not MIN_PERCENT <= percent <= MAX_PERCENT:
        raise ValueError("Choose damage, armor, value, uses, healing or food, between 25% and 400%.")
    import storage
    new = settings()
    new[key] = percent
    storage.ensure_dirs()
    fd, temp = tempfile.mkstemp(prefix=".item_balance_", suffix=".json", dir=storage.DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(new, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, _path())
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    global _cached_path, _cached_settings
    _cached_path, _cached_settings = _path(), new
    return dict(new)


def active(proto):
    if not proto or proto.get("crafted_vnum_identity"):
        return False
    try:
        valid_level = 1 <= int(proto.get("level") or 0) <= 250
    except (TypeError, ValueError):
        return False
    return bool(valid_level and "autobalance" in
                {str(f).casefold() for f in proto.get("extra_flags", ())})


def scaled(level, metric, current=None):
    level = max(1, min(250, int(level)))
    base = {
        "damage": 3 + level * 0.55,
        "armor": 2 + level * 0.12,
        "value": 50 + 20 * level + (level * level) // 3,
        "uses": 250 + 8 * level,
        "healing": 30 + 8 * level + (level * level) // 20,
        "food": 15 + 5 * level + (level * level) // 40,
    }[metric]
    pct = (current or settings())[metric + "_percent"]
    return max(1, round(base * pct / 100))


def effective_damage(proto, fallback):
    if active(proto) and proto.get("item_type") == "weapon" and proto.get("damage") is None:
        return scaled(proto["level"], "damage")
    return fallback


def effective_armor_bonus(proto):
    if (active(proto) and proto.get("item_type") == "armor"
            and "armor_class" not in proto.get("stat_bonuses", {})):
        return scaled(proto["level"], "armor")
    return 0


def effective_cost(proto):
    if active(proto) and int(proto.get("cost", 0)) <= 0:
        return scaled(proto["level"], "value")
    return int(proto.get("cost", 0))


def effective_uses(proto):
    if (active(proto) and proto.get("item_type") == "tool"
            and int(proto.get("max_uses", 250)) == 250):
        return scaled(proto["level"], "uses")
    return int(proto.get("max_uses", 250))


def effective_recovery(proto, metric):
    """Effective recovery per resource; 0 means use legacy data/fail closed.

    A positive HEAL is an explicit builder override on both food and medicine.
    AutoBalance affects only level-valid food/medical prototypes and never
    rewrites their saved amount, preserving existing standard/legendary items.
    """
    if not proto or metric not in {"healing", "food"}:
        return 0
    if proto.get("item_type") != ("medical" if metric == "healing" else "food"):
        return 0
    explicit = max(0, int(proto.get("heal_amount") or 0))
    if explicit:
        return explicit
    if active(proto):
        return scaled(proto["level"], metric)
    return 0


def cmd_itemscale(session, args):
    if (not getattr(session, "account", None)
            or session.account.staff_level not in {"administrator", "implementor"}):
        session.send("Only administrators can tune item scaling.")
        return
    values = settings()
    names = {"damage": "damage_percent", "armor": "armor_percent",
             "value": "value_percent", "uses": "uses_percent",
             "healing": "healing_percent", "food": "food_percent"}
    if not args:
        session.send("Opt-in item balance (AutoBalance item flag; affects live use, not saved templates): "
                     + ", ".join(f"{k} {values[v]}%" for k,v in names.items())
                     + ".\nUsage: itemscale preview <level 1-250> | itemscale <damage|armor|value|uses|healing|food> <25-400|+/-delta> | itemscale reset <field|all>.\n"
                     "Build: new weapon/armor/tool/medical/food ITEMTYPE automatically adds AutoBalance; set LEVEL 1-250. Explicit HEAL values override recovery scaling.")
        return
    verb = args[0].lower()
    if verb == "preview":
        if len(args) != 2 or not args[1].isdigit() or not 1 <= int(args[1]) <= 250:
            session.send("Usage: itemscale preview <level 1-250>")
            return
        level = int(args[1])
        session.send(f"Level {level} AutoBalance: weapon +{scaled(level, 'damage')} base damage, "
                     f"armor +{scaled(level, 'armor')} AC, item {scaled(level, 'value'):,} ryo value, "
                     f"tool {scaled(level, 'uses')} uses, medical {scaled(level, 'healing')} recovery, "
                     f"food {scaled(level, 'food')} recovery. Explicit object overrides win.")
        return
    if verb == "reset":
        if len(args) != 2 or args[1].lower() not in {*names, "all"}:
            session.send("Usage: itemscale reset <damage|armor|value|uses|healing|food|all>")
            return
        for key in names if args[1].lower() == "all" else (args[1].lower(),):
            values = set_percent(names[key], 100)
    else:
        if verb not in names or len(args) != 2:
            session.send("Usage: itemscale <damage|armor|value|uses|healing|food> <25-400|+/-delta>")
            return
        delta = args[1]
        try:
            # +10 and -10 shift percentage points; 125 sets the absolute value.
            new = values[names[verb]] + int(delta) if delta.startswith(('+', '-')) else int(delta)
            values = set_percent(names[verb], new)
        except (ValueError, OSError) as exc:
            session.send("Item balance unchanged: " + str(exc))
            return
    session.send("Item balance saved: " + ", ".join(f"{k} {values[v]}%" for k,v in names.items())
                 + ". Auto-balanced items use these values immediately; saved item fields are unchanged.")
