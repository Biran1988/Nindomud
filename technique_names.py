"""Compatibility for renamed techniques and their existing player saves."""
OLD_NAME = "100 Years of Death"
NEW_NAME = "1000 Years of Death"
OLD_KEY = OLD_NAME.lower()
NEW_KEY = NEW_NAME.lower()


def migrate_player(player):
    changed = False
    for field in ("learned_skills", "practiced_skills", "practice_exempt_skills"):
        values = getattr(player, field)
        if OLD_NAME in values:
            setattr(player, field, list(dict.fromkeys(NEW_NAME if x == OLD_NAME else x for x in values)))
            changed = True
    for field, old, new in (("skill_proficiencies", OLD_NAME, NEW_NAME),
                            ("cooldowns", OLD_KEY, NEW_KEY)):
        values = getattr(player, field)
        if old in values:
            values[new] = max(values.get(new, 0), values.pop(old))
            changed = True
    if player.signature_move == OLD_NAME:
        player.signature_move = NEW_NAME
        changed = True
    if player.copied_jutsu_key == OLD_KEY:
        player.copied_jutsu_key = NEW_KEY
        changed = True
    for field in ("inventory", "storage_room_items"):
        values = getattr(player, field)
        if any(OLD_NAME in x for x in values):
            setattr(player, field, [scroll_name(x) for x in values])
            changed = True
    for items in player.backpack_contents.values():
        for i, item in enumerate(items):
            if OLD_NAME in item:
                items[i] = scroll_name(item)
                changed = True
    # Old scroll instances remain usable even with builder-customized names.
    return changed


def migrate_templates():
    import olc
    for proto in olc.OBJECT_TEMPLATES.values():
        if proto.get("scroll_jutsu") == OLD_KEY:
            proto["scroll_jutsu"] = NEW_KEY
        for field in ("short_desc", "long_desc", "description"):
            if OLD_NAME in proto.get(field, ""):
                proto[field] = proto[field].replace(OLD_NAME, NEW_NAME)


def scroll_name(item):
    return item.replace(OLD_NAME, NEW_NAME)
