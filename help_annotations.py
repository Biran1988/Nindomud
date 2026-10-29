"""Standardized unlock-level and damage metadata for technique helpfiles.

The technique catalog is authoritative. This keeps help accurate when
level gates or damage are rebalanced without rewriting author prose.
"""


def metadata(entry, jutsu_catalog):
    key = entry["primary_keyword"].lower()
    art = jutsu_catalog.get(key)
    if art is None:
        # An overview's alias is not necessarily a technique help page.
        for alias in entry.get("keywords", ()):
            candidate = jutsu_catalog.get(alias.lower())
            if candidate and candidate["display_name"].casefold() == entry["title"].casefold():
                art = candidate
                break
    if art:
        level = art.get("level_requirement", 1)
        element = art.get("element", "none")
        if art.get("damage") is None:
            damage_type = "None (utility / defense / non-damaging)"
            damage_range = "Base damage: None"
        else:
            damage_type = art.get("damage_type") or (
                "physical" if art.get("class_requirement") in ("taijutsu", "bukijutsu")
                else "mental" if art.get("class_requirement") == "genjutsu" else "chakra")
            damage_type = damage_type.capitalize()
            if element and element != "none":
                damage_type += f" ({element.capitalize()} element)"
            low, high = art["damage"]
            damage_range = f"Base damage: {low:,}-{high:,}"
        return f"Level gained: {level}\nDamage type: {damage_type}\n{damage_range}"
    import re
    match = re.search(r"\blevel (\d+)\b", entry.get("title", ""), re.I)
    if match:
        return f"Level gained: {match.group(1)}\nDamage type: None (non-damaging skill)"
    return ""


def enrich(entries, jutsu_catalog):
    topics = set()
    for entry in entries:
        extra = metadata(entry, jutsu_catalog)
        if extra:
            topics.add(entry["primary_keyword"])
            if "Level gained:" not in entry["body"]:
                entry["body"] = entry["body"].rstrip() + "\n\n" + extra
    return topics
