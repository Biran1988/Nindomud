"""Individual help pages for the newer combat arts and medical supplies.

Keep mechanical numbers in data_jutsu; only the descriptions and command
shapes live here. System-owned pages are refreshed on login by help_system.
"""

import data_jutsu


DESCRIPTIONS = {
    "choku zuki": "A direct punch.",
    "mae geri": "A forward kick.",
    "oi zuki": "A stepping punch.",
    "sokuto": "A driving side kick.",
    "empi": "An elbow strike.",
    "kumade": "A clawing strike with a chance to blind the target.",
    "nidan kyten geri": "A two-stage kick.",
    "tamashiwara": "A heavy blow with a chance to cause bleeding.",
    "kihon dachi": "A stance granting +2 damage roll and 2 points of Armor Class protection.",
    "neko ashi dachi": "A stance granting +2 hit roll and 4 points of Armor Class protection.",
    "sanchin dachi": "A stance granting +4 damage roll.",
    "multi-shuriken throw": "Throws three carried shuriken in one attack. Spent shuriken land on the room floor.",
    "multi-kunai throw": "Throws three carried kunai in one attack. Spent kunai land on the room floor.",
    "demon wind shuriken": "Throws one carried Demon Wind Shuriken, which lands on the room floor and can cause bleeding.",
    "toxin binding": "Permanently binds poison to one carried or wielded weapon. A poisoned hit can inflict Poisoned. Disenchant the weapon before binding a different property.",
    "exploding note": "Attaches a consumed Exploding Note to a target. It detonates after two combat pulses for 28-46 damage unless disabled.",
    "smoke bomb": "Attaches a consumed Smoke Bomb. After two combat pulses it deals 5-12 damage and blinds the target unless disabled.",
    "poison gas bomb": "Attaches a consumed Poison Gas Bomb. After two combat pulses it deals 12-23 damage and poisons the target unless disabled.",
    "exploding clay": "Attaches a consumed Wad of Exploding Clay. After two combat pulses it detonates for 45-70 damage unless disabled.",
    "trap disabling": "Disarms attached traps on the selected target (or yourself when no target is given). Failure triggers the trap against you.",
    "weapon enchantment": "Permanently binds one property to a carried or wielded weapon: flaming, frost, life, sharp, vorpal, or shocking. Disenchant before changing the property.",
    "disenchantment": "Removes the item-bound Ninja Art property from a carried or wielded weapon.",
    "fan techniques": "A Mighty Fan attack that may knock the target off balance. If a surviving target and an open exit are specified, the gust pushes them through that exit; closed doors and hidden exits block it.",
    "water release: glue technique": "Requires Water chakra nature, a Pot of Glue, and a carried item. Consumes the pot and glues the item to you so it cannot be dropped or traded.",
    "samurai sabre": "Flows chakra through a wielded sword. Ordinary sword hits deal 20% more damage for five pulses; other weapon types do not benefit.",
    "flying swallow": "A chakra-extended sword or kunai strike with +15 accuracy and a chance to cause bleeding. Wind chakra nature adds 15% damage but is optional.",
    "tsukuyomi": "Mangekyo technique that brings caster and target into a shared torture room. The caster's actions there determine the ordeal; it lasts a hidden 5-10 actions.",
    "amaterasu": "Mangekyo black flames burn a player and ignite a separate room fire.",
    "kamui pocket dimension": "Kamui first sends a target into a pocket dimension. Cast again on yourself to join them; upkeep begins while the caster is inside.",
    "kamui intangibility": "Kamui phases the caster through incoming attacks for three rounds.",
    "kamui limb removal": "An interruptible 6-8 second Kamui cast that deals a major single burst if it completes.",
    "izanami": "Traps a target in a recursive loop. The target guesses one fixed hidden number, one guess per round, to escape; others cannot attack the trapped target.",
    "kekkei no me": "Transforms the current room for 90 seconds. Matching-element jutsu from the caster gain 50% damage; others in the room lose Chakra and Stamina over time.",
}

SYNTAX = {
    "trap disabling": "trap disabling [target]",
    "toxin binding": "toxin binding <weapon>",
    "weapon enchantment": "weapon enchantment <weapon> <flaming|frost|life|sharp|vorpal|shocking>",
    "disenchantment": "disenchantment <weapon>",
    "fan techniques": "fan techniques <target> [direction]",
    "water release: glue technique": "perform water release: glue technique <item>",
    "samurai sabre": "samurai sabre",
    "kamui pocket dimension": "perform kamui pocket dimension <target|self>",
    "kamui intangibility": "perform kamui intangibility",
    "kekkei no me": "perform kekkei no me",
}


def _page(key):
    jutsu = data_jutsu.JUTSU[key]
    kind = jutsu.get("jutsu_type")
    syntax = SYNTAX.get(key, ("perform " if jutsu["class_requirement"] in ("ninjutsu", "genjutsu") else "")
                        + key + ("" if kind == "stance" else " <target>"))
    if kind == "stance":
        syntax = key
    details = DESCRIPTIONS[key]
    if kind == "stance":
        details += " Only one stance can be active; switch or leave it outside combat. Using the current stance again ends it. The stance persists through reconnects."
    if jutsu.get("required_weapon_types"):
        details += " Requires a wielded " + " or ".join(jutsu["required_weapon_types"]) + "."
    if jutsu.get("requires_item"):
        details += f" Requires a carried {jutsu['requires_item']}."
    if jutsu["element"] != "none":
        details += f" Requires {jutsu['element'].capitalize()} chakra nature."
    if jutsu["damage"] is not None:
        details += f" Base damage: {jutsu['damage'][0]}-{jutsu['damage'][1]}."
    if jutsu.get("effect"):
        chance = jutsu.get("effect_chance_pct", 100)
        details += f" {chance}% chance to inflict {jutsu['effect'].replace('_', ' ')}."
    if jutsu.get("kkg_gate"):
        details += " Requires an awakened Sharingan with this Mangekyo eye technique assigned; it is not a normal level unlock."
    else:
        details += f" {jutsu['class_requirement'].capitalize()} unlocks at level {jutsu['level_requirement']}."
    details += (f" Costs {jutsu['chakra_cost']} Chakra and {jutsu['stamina_cost']} Stamina; "
                f"{jutsu['cooldown']:g} second cooldown.")
    return {
        "primary_keyword": key, "keywords": [key], "title": jutsu["display_name"],
        "body": f"Syntax: {syntax}\n\nDescription: {details}\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    }


PAGES = [_page(key) for key in DESCRIPTIONS]

PAGES += [
    {
        "primary_keyword": "medicinal herbs", "keywords": ["medicinal herbs", "herbs"],
        "title": "Medicinal Herbs",
        "body": "Syntax: craft pill medicine <level>  |  craft pill antidote <level>\n\nDescription: Buy Medicinal Herbs from a village general store. Bukijutsu at level 25 or higher consumes one herb to craft either pill at a chosen level no higher than the crafter's level. See 'help medicinal pill' and 'help antidote pill'.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "medicinal pill", "keywords": ["medicinal pill", "medicine pill"],
        "title": "Medicinal Pill",
        "body": "Syntax: craft pill medicine <level>  |  examine <pill>  |  use <pill>\n\nDescription: Bukijutsu level 25+ crafts one pill from Medicinal Herbs. Choose a level from 1 to your own level; it is saved in item data and shown by examine, not in the name. Using it restores Health, Chakra, and Stamina by 100 + six times its level, each over 30 seconds. It does not cure status effects. Use 2.pill to select the second matching pill.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "antidote pill", "keywords": ["antidote pill", "antidote"],
        "title": "Antidote Pill",
        "body": "Syntax: craft pill antidote <level>  |  examine <pill>  |  use <pill>\n\nDescription: Bukijutsu level 25+ crafts one pill from Medicinal Herbs. Choose a level from 1 to your own level; it is saved in item data and shown by examine, not in the name. It cures poison only and is not consumed when you are not poisoned. Use 2.pill to select the second matching pill.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
]
