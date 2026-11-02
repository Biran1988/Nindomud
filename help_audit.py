"""Comprehensive, safe helpfile coverage from the actual game catalogs.

The index is built at startup from registered commands, jutsu, and public
gathering/crafting catalogs. Neither staff-authored data/help pages nor
hidden discoveries are overwritten or announced by this module.
"""
import inspect
import re

import data_jutsu

COVERED = set()

SECRET_KEYS = {
    # Do not disclose the bypass, its route, or other explicitly hidden
    # discoveries before players uncover them in game.
    "reverse summoning jutsu",
}
COMMAND_OVERRIDES = {
    "group": ("GROUP | GROUP INVITE <player> | GROUP ACCEPT | GROUP LEAVE | GROUP KICK <player> | GROUP DISBAND | GROUP FOLLOW",
              "Only groups within a 20-ninja-level spread can share combat XP. "
              "Players on the same verified connection IP cannot group: attempting "
              "to do so disconnects and bans that IP for 30 minutes. An invite and "
              "its acceptance are both checked. Grouped members must be alive and "
              "in the kill room to share experience; off-level members receive no "
              "shared XP. FOLLOW helps you travel with your leader, using normal stamina."),
    "examine": ("EXAMINE <carried or equipped item>",
                "Reveals the item's properties, including ANY permanent weapon "
                "enchantment or elemental chakra binding. The enchantment stays "
                "off its displayed name and appears here instead. Item rarity is "
                "never shown. Details increase with Examine mastery. Each valid "
                "examination gives a chance to increase Examine skill and earn "
                "10 ninja XP per 1% proficiency gained, using normal first-practice "
                "and mastery limits. Empty and invalid examinations do not train."),
    "craft": ("CRAFT WEAPON <type> <custom name> | CRAFT ARMOR <slot> <custom name> | "
              "CRAFT TOOL <rod|axe|pickaxe> <iron|steel|chakra> | CRAFT PILL <antidote|medicine> <level>",
              "Weapons and armor ask which metal tier to use: Iron, Steel, "
              "or Chakra Steel. Forging consumes TWO ingots of the chosen metal, "
              "with no wood required. The chosen metal controls Hitroll/Damroll "
              "for weapons or Armor Class for armor, and real material provenance "
              "is saved independently of the player-created name. Bukijutsu "
              "blacksmiths can use all metal tiers; other qualified classes are "
              "restricted to the first tier. Separately, job tools continue to "
              "require the correct wood AND metal combination. Every item is "
              "subject to the normal crafting rank and resources."),
    "chop": ("CHOP", "Hold an axe and chop in forests. Axe and Lumberjack job levels "
             "both limit available wood. Steel Ironwood and Chakra Steel Heartwood "
             "axes sharply reduce Kindling/Birch Branch and other low-level wood "
             "drops, without completely eliminating earlier resources. Elder Oak "
             "Log unlocks at Lumberjack level 60 and retains its 6% base weight "
             "before high-tier tool weighting."),
    "perform": ("PERFORM <learned jutsu> [target]",
                "Jutsu now spend increasing Chakra or Stamina based on caster "
                "ninja level, the jutsu's tier and the actor's maximum resource "
                "pool. Chakra Control discounts still apply where supported. "
                "Repeated high-tier casts are expensive; individual attacks "
                "deal substantially more damage and many effects last longer. "
                "Hard controls have finite PvP limits. Ongoing toggled upkeep "
                "retains its own existing maintenance cost."),
    "jutsu": ("JUTSU | JUTSU ALL | JUTSU SHORTS",
              "See learned techniques, the full catalog and known shortcuts. "
              "Technique help pages show unlock level, category, base attack "
              "range, tier, cooldown and the level-scaled resource formula. "
              "Base damage is before mastery, chakra-nature and other modifiers."),
    "ban": ("BAN LIST | BAN IP <address|CIDR> [reason] | BAN REMOVE IP <address|CIDR>",
             "Staff-only. IP and country bans are saved independently of "
             "player data. Automated same-IP grouping bans last 30 minutes "
             "and expire automatically; BAN LIST shows remaining duration."),
}

def _entry(key, title, body, aliases=()):
    return {"primary_keyword": key, "keywords": list(dict.fromkeys([key, *aliases])),
            "title": title, "body": body,
            "created_by": "System", "updated_by": "System", "updated_at": 0.0}

def _clean_description(handler):
    doc = inspect.getdoc(handler) or ""
    first = re.split(r"\n\s*\n", doc, maxsplit=1)[0].replace("\n", " ")
    first = " ".join(first.split())
    if not first or any(word in first.casefold() for word in
                        ("password", "easter egg", "secret", "hidden exit", "private key")):
        return ""
    return first[:500]

def populate(entries, commands):
    """Add a help entry for every public command and catalog technique."""
    by_key = {entry["primary_keyword"].casefold(): entry for entry in entries}
    for key, handler in sorted(commands.items()):
        key = key.casefold()
        override = COMMAND_OVERRIDES.get(key)
        if override:
            syntax, body = override
            entry = _entry(key, key.title(), f"Syntax: {syntax}\n\n{body}")
            if key in by_key:
                if by_key[key].get("created_by") == "System":
                    by_key[key]["body"] = entry["body"]
                    COVERED.add(key)
            else:
                entries.append(entry)
                by_key[key] = entry
                COVERED.add(key)
            continue
        if key in by_key:
            continue
        if key in SECRET_KEYS:
            continue
        description = _clean_description(handler)
        entry = _entry(key, key.replace("_", " ").title(),
                       f"Syntax: {key} [arguments]\n\n" +
                       (description or f"Use {key.upper()} to access this registered game command. "
                        "Try the command without arguments to see available options."))
        entries.append(entry)
        by_key[key] = entry
        COVERED.add(key)

    # The jutsu registry is authoritative; no ability is left without a page.
    # Keep gated/secret techniques subject to the existing visibility checks.
    for key, art in sorted(data_jutsu.JUTSU.items()):
        if key in by_key or key in SECRET_KEYS or art.get("secret"):
            continue
        kind = art.get("jutsu_type", "attack")
        damage = art.get("damage")
        details = (f"Class/category: {art.get('class_requirement', 'general').title()}. "
                   f"Unlocks at level {art.get('level_requirement', 1)}. "
                   f"Tier {art.get('tier', 1)}. "
                   f"Cooldown {art.get('cooldown', 0):g} seconds. "
                   f"Base Chakra {art.get('chakra_cost', 0)}, "
                   f"Stamina {art.get('stamina_cost', 0)} before level scaling.")
        if art.get("element") and art["element"] != "none":
            details += f" Requires {art['element'].title()} nature."
        if damage:
            details += f" Base {art.get('damage_type') or 'physical'} damage {damage[0]}-{damage[1]} before the power boost."
        if art.get("effect"):
            details += f" Can inflict {art['effect'].replace('_', ' ')}."
        if kind:
            details += f" Technique kind: {kind.replace('_', ' ')}."
        if art.get("scroll_only"):
            details += " Requires its teaching scroll."
        entry = _entry(key, art["display_name"],
                       f"Syntax: PERFORM {key} [target]\n\n{details}\n\n"
                       "Damage and duration bonuses are technique-specific; "
                       "actual cast cost increases with ninja level and maximum resource pool.")
        entries.append(entry)
        by_key[key] = entry
        COVERED.add(key)

    # Public, nonsecret resource catalogs (one searchable entry per gatherable).
    import fishing
    import mining
    import lumberjack
    import farming
    for profession, module, verb in (
        ("Fishing", fishing, "fish"),
        ("Mining", mining, "mine"),
        ("Lumberjack", lumberjack, "chop"),
        ("Farming", farming, "farm"),
    ):
        for name, level, weight, xp in getattr(module, "FIND_TABLE", ()):
            key = name.casefold().strip()
            if key in by_key or key in SECRET_KEYS:
                continue
            body = (f"Found through {profession} at job level {level} or higher, "
                    f"with a suitable tool and location. Base table weight {weight}; "
                    f"grants {xp} base job XP on a successful find. "
                    f"Use {verb.upper()} to gather it. Tool tiers can modify "
                    "drop weights and impose further requirements.")
            entry = _entry(key, name.title(), body)
            entries.append(entry)
            by_key[key] = entry
            COVERED.add(key)

    import data_crafting
    for name, material in sorted(data_crafting.MATERIALS.items()):
        key = name.casefold()
        if key in by_key:
            continue
        entry = _entry(key, name.title(),
                       f"Crafting ingredient: {name}. Intrinsic stat value: "
                       f"{material['stat_value']}. Trade reference price: "
                       f"{material.get('price_ryo', 0)} ryo. Equipment forging "
                       "uses metal ingots, whereas upgraded gathering tools "
                       "require their exact wood and ingot recipe.")
        entries.append(entry)
        by_key[key] = entry
        COVERED.add(key)

    import status_effects
    for key, definition in sorted(status_effects.EFFECT_DEFS.items()):
        topic = f"effect {key.replace('_', ' ')}"
        if topic in by_key:
            continue
        flags = []
        for attr in ("blocks_action", "blocks_movement", "blocks_jutsu",
                     "accuracy_penalty", "damage_penalty_pct", "damage_reduction_pct",
                     "damage_per_tick", "chakra_drain_per_tick", "stamina_drain_per_tick"):
            if definition.get(attr):
                flags.append(f"{attr.replace('_', ' ')}: {definition[attr]}")
        entry = _entry(topic, definition.get("display_name", key).title() + " Effect",
                       f"Status effect: {definition.get('display_name', key)}. "
                       f"Base duration: {definition.get('duration', 0)} pulses. "
                       + (". ".join(flags) if flags else "See the jutsu that applies this effect.")
                       + " Actual jutsu-applied duration may be extended by the caster's "
                         "technique and reduced by the defender's resistances.")
        entries.append(entry)
        by_key[topic] = entry
        COVERED.add(topic)

    return COVERED
