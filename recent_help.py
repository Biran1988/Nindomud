"""Individual help pages for the newer combat arts and medical supplies.

Keep mechanical numbers in data_jutsu; only the descriptions and command
shapes live here. System-owned pages are refreshed on login by help_system.
"""

import data_jutsu
import status_effects


DESCRIPTIONS = {
    "soto uke": "A passive Taijutsu block against ordinary physical hits. Successful blocks cost 10 Stamina; mastery improves the chance.",
    "weapon expert": "A passive Bukijutsu weapon skill. Armed ordinary attacks can deal 50% extra damage, with a chance based on mastery.",
    "dual wield": "Equip a second weapon in your off hand. Mastery can grant one extra off-hand attack each combat round for 5 Stamina.",
    "chokkan": "Toggle inner intuition on for 25 Chakra. While active, successful mastery checks halve your hand-sign casting delay.",
    "1000 years of death": "An instant-kill technique learned only by reading its scroll. It uses normal mob and PvP defeat handling; safe areas and protected targets remain protected.",
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
    "samurai sabre": "Toggle a chakra edge on a wielded sword. Ordinary sword hits deal 20% more damage while active. Costs 4 Chakra per idle 10 seconds, or 6 Chakra and 2 Stamina per combat round. Switch weapons or use it again to turn it off.",
    "flying swallow": "A chakra-extended sword or kunai strike with +15 accuracy and a chance to cause bleeding. Wind chakra nature adds 15% damage but is optional.",
    "tsukuyomi": "Mangekyo technique that brings caster and target into a shared torture room. The target is frozen and cannot attack, cast jutsu, move, or use staff actions, even as an immortal; existing fights and queued casts stop. The caster's torture actions determine the ordeal, which lasts a hidden 5-10 actions. If either player disconnects, the illusion ends and both return.",
    "amaterasu": "Mangekyo black flames burn a player until they are defeated and ignite a separate room fire for five minutes. Surviving a fatal hit through Izanagi, an immortal safeguard, or a summon does not extinguish the player burn. There is no in-game sealing cure yet.",
    "kamui pocket dimension": "Cast on yourself to open and enter your own pocket dimension immediately. Or cast on a same-room target to send them there first, then cast on yourself to join them. Upkeep begins while the caster is inside and joins the six-minute summary. Only one dimension can be open per caster, and a player already inside another pocket dimension cannot be moved into a new one. Collapse or disconnect returns its occupants to their original rooms. Paid maintenance can improve mastery even outside combat.",
    "kamui intangibility": "Kamui phases the caster through incoming attacks for three rounds.",
    "kamui limb removal": "An interruptible 6-8 second Kamui cast that deals a major single burst if it completes.",
    "izanami": "Traps a target in a recursive loop. The target guesses one fixed hidden number, one guess per round, to escape; others cannot attack the trapped target.",
    "kekkei no me": "Transforms the current room for 90 seconds. Matching-element jutsu from the caster gain 50% damage; others in the room lose Chakra and Stamina over time.",
}

SYNTAX = {
    "soto uke": "help soto uke (passive)",
    "weapon expert": "help weapon expert (passive)",
    "dual wield": "dual wield <carried weapon>  |  remove offhand",
    "chokkan": "perform chokkan",
    "1000 years of death": "read scroll of 1000 years of death  |  perform 1000 years of death <target>",
    "trap disabling": "trap disabling [target]",
    "toxin binding": "toxin binding <weapon>",
    "weapon enchantment": "weapon enchantment <weapon> <flaming|frost|life|sharp|vorpal|shocking>",
    "disenchantment": "disenchantment <weapon>",
    "fan techniques": "fan techniques <target> [direction]",
    "water release: glue technique": "perform water release: glue technique <item>",
    "samurai sabre": "samurai sabre",
    "kamui pocket dimension": "perform kamui [pocket dimension] <target|self>",
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
    if "<target>" in syntax and kind not in {"weapon_art", "disguise", "item_illusion", "item_decoy"}:
        details += " During combat, omitting the target uses your current opponent, including an NPC that attacked you."
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
        if jutsu["class_requirement"] == "genjutsu":
            details += f" The effect lasts {status_effects.genjutsu_duration(jutsu['effect'])} seconds before resistance."
    if key == "chisei":
        details += " Maintained toggle: 1 Chakra every 5 seconds until switched off or upkeep fails."
    if key == "nehan shouja":
        details += f" Sleeping targets remain asleep for {status_effects.genjutsu_duration('asleep')} seconds before resistance."
    if jutsu.get("kkg_gate", "").startswith("six_paths_"):
        soul = jutsu["kkg_gate"].removeprefix("six_paths_").title()
        details += f" Unlocks at level 75 only for {soul} reincarnations of any combat class."
        if kind != "six_paths_mode":
            details += " Requires your Six Paths mode active. Train and use the technique to increase its mastery."
    elif jutsu.get("kkg_gate"):
        details += " Requires an active Sharingan and this Mangekyo eye technique assigned; authenticated immortals can test every Mangekyo technique without those gates. It is not a normal level unlock."
        if kind in {"mangekyo_tsukuyomi", "mangekyo_amaterasu", "mangekyo_kamui_pocket_dimension",
                    "mangekyo_kamui_limb_removal", "mangekyo_izanami"}:
            details += " The target must be in your room; moving away before a delayed cast resolves makes it fizzle."
    elif jutsu.get("scroll_only"):
        details += " Scroll-only; it is never unlocked by leveling or login backfill."
    else:
        details += f" {jutsu['class_requirement'].capitalize()} unlocks at level {jutsu['level_requirement']}."
    details += (f" Costs {jutsu['chakra_cost']} Chakra and {jutsu['stamina_cost']} Stamina; "
                f"{jutsu['cooldown']:g} second cooldown.")
    return {
        "primary_keyword": key, "keywords": [key] + (["100 years of death"] if key == "1000 years of death" else []), "title": jutsu["display_name"],
        "body": f"Syntax: {syntax}\n\nDescription: {details}\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    }


DESCRIPTIONS.update({
    "six paths rinnegan": "Indra's level-75 reincarnate form. Toggle with sixpaths on/off. This awakens Six Paths ocular power without replacing your inherited Kekkei Genkai. Activate for 40 Chakra; upkeep is 18 Chakra every ten idle seconds or 24 Chakra and 8 Stamina each combat round. At 0-100% mode mastery, gain 10-20% damage, 5-15% incoming damage reduction and +5-10 accuracy. Summon Sage Mode cannot stack with it. Paid maintenance trains mode mastery.",
    "six paths sage mode": "Ashura's level-75 reincarnate form. Toggle with sixpaths on/off. Activate for 40 Chakra; upkeep is 18 Chakra every ten idle seconds or 24 Chakra and 8 Stamina each combat round. At 0-100% mode mastery, gain 10-20% damage, 5-15% incoming damage reduction and +5-10 accuracy. Summon Sage Mode cannot stack with it. Paid maintenance trains mode mastery.",
    "almighty push": "Release Rinnegan gravity against one target in your room, dealing chakra damage with a chance to throw it off balance. This implementation does not move the target to a different room.",
    "universal pull": "Draw a target off balance with Rinnegan gravity, dealing chakra damage and disrupting its footing. This implementation affects one target already in your room.",
    "six paths vital surge": "Channel Ashura's life force to restore 25% of your maximum Health and Stamina, capped at your current maximums, and clear poisoned and weakened effects. Self only; usable during combat. Costs 120 base Chakra with the normal Chakra Control discount; two-minute cooldown. Does not restore Chakra. At full resources with no relevant ailment, it consumes nothing.",
    "truth-seeking orb barrage": "Shape Truth-Seeking Orbs into a targeted barrage, dealing chakra damage with a chance to weaken the target. It does not instantly kill or permanently erase player equipment.",
})
SYNTAX.update({"six paths rinnegan": "sixpaths [on|off|status]",
               "six paths sage mode": "sixpaths [on|off|status]",
               "six paths vital surge": "perform six paths vital surge"})
PAGES = [_page(key) for key in DESCRIPTIONS]

PAGES += [
    {
        "primary_keyword": "mangekyo help", "keywords": ["mangekyo help", "eye help"],
        "title": "Mangekyo Eye Help",
        "body": "Syntax: help <eye technique>\n\nDescription: Your individual Mangekyo eye technique helpfiles appear after you awaken the eye and successfully use its technique for the first time. Kamui's three techniques share one eye, so using any one reveals all three pages. Undiscovered pages stay out of the help index. Immortals can view every eye helpfile for testing.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "jutsu colors", "keywords": ["jutsu colors", "jutsu colours"],
        "title": "Jutsu Colors",
        "body": "Syntax: help jutsu colors\n\nDescription: Every jutsu has its own three-shade color sequence when performed and in its helpfile. Skills and practice lists retain their usual category and proficiency colors. Sessions with ANSI disabled receive plain text instead.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "genjutsu durations", "keywords": ["genjutsu durations", "illusion durations"],
        "title": "Genjutsu Status Durations",
        "body": "Syntax: help genjutsu durations\n\nDescription: Genjutsu status effects last much longer than their ordinary equivalents: stun, paralysis, and ringing last 10 seconds; sleep lasts 12; fear, disorientation, confusion, and blindness last 20; soundless, haze, weakness, and Narakumi last 24. Chisei's extra Chakra capacity lasts 60 seconds. An active four-tomoe Sharingan can shorten incoming hostile Genjutsu effects. These are status durations, independent of any damage or cooldown.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
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

# Commands that used to be deliberately undocumented. Keep the instructions
# visible now that every playable command should have a help lookup.
PAGES += [
    {
        "primary_keyword": "izanagi", "keywords": ["izanagi"],
        "title": "Izanagi",
        "body": "Syntax: izanagi\n\nDescription: Toggle this Mangekyo technique if it is one of your assigned eye abilities. Sharingan must be active to turn it on and remain active for Izanagi to save you; immortals may test without it. While active, it saves you from your next defeat, restoring full Health and switching itself off. The 24-hour real-time cooldown begins only when it actually saves you. You can toggle Izanagi off even if Sharingan fades. Your individual eye help becomes visible after your first use.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "guess", "keywords": ["guess"],
        "title": "Guess (Izanami)",
        "body": "Syntax: guess <number>\n\nDescription: If trapped in Izanami, guess the hidden number from 1 to 25. A correct guess breaks the loop immediately; a wrong guess leaves you trapped. This command has no effect outside Izanami.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
]

_TSUKUYOMI_ACTIONS = {
    "stab": "A steady attack dealing 30-50 Health damage and advancing the ordeal by one action.",
    "impale": "A heavier 60-90 Health damage attack that advances the ordeal by two actions.",
    "burn": "Deals 20-40 Health damage and drains 30-50 Stamina; advances the ordeal by one action.",
    "crush": "Deals 80-120 Health damage and has a 25% chance to end the ordeal early; advances it by one action otherwise.",
    "unmake": "Deals no direct Health damage, but drains 40-60 Chakra and 40-60 Stamina; advances the ordeal by one action.",
}
for _name, _description in _TSUKUYOMI_ACTIONS.items():
    PAGES.append({
        "primary_keyword": _name, "keywords": [_name],
        "title": f"{_name.title()} (Tsukuyomi)",
        "body": (f"Syntax: {_name}\n\nDescription: Tsukuyomi caster action, usable only while you and your target are inside its shared illusion. "
                 f"{_description} The ordeal ends when its hidden action limit is reached.\n\nDate: 2026-09-27"),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    })

PAGES += [
    {
        "primary_keyword": "imms", "keywords": ["imms", "immortal", "immortals", "staff roster"],
        "title": "Immortals",
        "body": "Syntax: imms | immortal | immortals\n\nDescription: Lists every staff account by name and rank, including Helper, Builder, Area Leader, Administrator, and Implementor. Shows whether each account is currently online.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "area", "keywords": ["area", "areas", "vnum reservation", "area delete", "area export", "area import", "area exportworld", "world map", "offline area builder"],
        "title": "Area",
        "body": "Syntax: area create <name> [size] | area export <area name> | area exportworld | area import <file.json> [check] | area assign <name> <builder account> | area unassign <name> <builder account> | area prototype <name> on|off | area list | area delete <name> <confirmation code>\n\nDescription: Areas reserve room vnum ranges. New manually created areas start as prototypes; existing system areas are live. Biran assigns one Builder account to each area and can switch its prototype flag. Builders can edit and move only within assigned ranges, including mob and item prototype vnums. They can connect two prototype areas when both have the same assigned owner. Only Biran can connect a prototype to a live area or another builder's area. Area delete is reserved for Biran's Implementor account and requires the private deletion code. It permanently removes the reservation, rooms, live mobs and ground items there, incoming exits, spawn points, and exclusive prototypes. Connected players move to a surviving room; the deletion persists after reboot. Use area set <name> income <n> or resetmsg <text|off> for area settings.\n\nOffline editor: An Implementor uses 'area export <area name>' to write a JSON package under data/area_exports/. Copy it to your computer and open it with builder/Nindo_Area_Builder.html using Open / import area JSON. Edit rooms, exits, recognized room flags, and placed mob/item prototypes, then export JSON into data/area_imports/. Run 'area import <file.json> check' first and then 'area import <file.json>' to apply. An existing area update protects against stale exports, preserves advanced settings, and refuses missing existing rooms or prototypes. A new package may only use unused VNUMs.\n\nDate: 2026-10-04",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "scavenger", "keywords": ["scavenger", "scavenger mob flag"],
        "title": "Scavenger Mob Flag",
        "body": "Syntax: mset <mob vnum> flags Scavenger\n\nDescription: Builder mob flag. Each server pulse, a living Scavenger collects takeable loose items lying on the ground in its current room. It never picks up no_take items or enters private apartment storage to clean it. Collected items are held on the live mob (visible in mstat), not saved; they disappear when the mob is removed, killed, or the server reboots. Combine with Wander to clean multiple rooms. Remove the flag with mset <mob vnum> flags -Scavenger.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "charge", "keywords": ["charge", "chakra charge"],
        "title": "Chakra Charge",
        "body": "Syntax: charge [stamina amount] | charge stop\n\nDescription: A General Skill unlocked at level 10 for every shinobi. Choose how much Stamina to convert at 1 Stamina for 2 Chakra. The chosen amount flows in over 20 seconds: 20% is processed every 4 seconds, with fractional Stamina carried into later intervals. No Stamina is spent instantly. Without an amount, charge enough to fill your Chakra. You cannot request more Stamina than you have, and charging stops when Chakra fills or Stamina runs out. Use charge stop to end it early. Sleeping or an effect that prevents action interrupts the charge. It works during or outside combat. Practice or successful use can improve mastery, but mastery does not change the exchange rate.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "walking", "keywords": ["walking", "movement stamina", "travel stamina"],
        "title": "Walking and Stamina",
        "body": "Syntax: north | south | east | west | northeast | northwest | southeast | southwest | up | down\n\nDescription: Each successful walk to another room consumes 1 or 2 Stamina. Blocked exits and closed doors cost nothing. You can still walk when exhausted; Stamina never drops below zero. Automatic Track movement also uses walking Stamina.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "jutsu upkeep", "keywords": ["jutsu upkeep", "maintenance", "upkeep"],
        "title": "Jutsu Upkeep",
        "body": "Syntax: help jutsu upkeep\n\nDescription: Active Sharingan, Sage Mode, Shadow Clones, Track, Kamui Pocket Dimension, and Samurai Sabre pay their normal resource costs at each upkeep tick. Their Chakra and Stamina costs are combined into one report every six minutes, with each ability listed separately. Turning off an ability or running out of resources reports its pending cost immediately. Learned jutsu with paid maintenance, plus active Chisei, Hidden Mist, Chokkan and general ninja toggles, have a chance to gain 1% proficiency every ten active seconds even outside combat. The chance is (100 - current proficiency)%, capped at 100%; each gain awards 10 character XP and a message. Off or expired effects do not train, and toggling repeatedly cannot produce extra maintenance rolls. Sharingan uses its own bloodline mastery progression, while Sage Mode mastery comes from training with its elder.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "sharingan upkeep", "keywords": ["sharingan upkeep", "shar upkeep"],
        "title": "Sharingan Upkeep",
        "body": "Syntax: sharingan  |  shar\n\nDescription: Active Sharingan spends 6 Chakra every 10 seconds outside combat. During combat it spends 6 Stamina and 6-12 Chakra each round, depending on tomoe. Resources are charged at every tick. Sharingan, Sage Mode, clones, tracking, Kamui Pocket Dimension, and Samurai Sabre upkeep are combined into one report every six minutes, with separate costs per ability. Turning an ability off or running out of resources prints its pending total immediately. See 'help sharingan' for the toggle.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "sage training", "keywords": ["sage training", "senjutsu training"],
        "title": "Sage Mode Training",
        "body": "Syntax: summon sign [family]  |  sage train [family]  |  sage status\n\nDescription: At level 20 or higher, permanently choose one summon family at its living elder. At level 80, train with that same elder in its hideout. You can attempt training once per real hour; each attempt has a 5% chance to add 1% mastery, so mastering all 100% takes a long time. A failed attempt still starts the hour wait. Training is unavailable during combat. Once mastered, use 'sage on <family>' or bare 'sage' to activate and 'sage off' to release it. See 'help sage' for upkeep and shared bonuses.\n\nDate: 2026-09-27",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
]

_SAGE_FAMILIES = {
    "toad": ("Mount Myoboku", "Adds 5 accuracy beyond Sage Mode's shared bonus, for +15 total."),
    "snake": ("Ryuchi Cave", "Adds 10% damage to jutsu beyond Sage Mode's shared 20% damage bonus."),
    "slug": ("Shikkotsu Forest", "Restores up to 5% of maximum Health each combat round while active."),
    "ninken": ("the Hidden Leaf Kennels", "Grants one additional ordinary attack each combat round; it does not add a dodge bonus."),
    "monkey": ("the Monkey Sanctuary", "Adds 10% damage when attacking with a weapon beyond Sage Mode's shared 20% damage bonus."),
}
for _family, (_hideout, _bonus) in _SAGE_FAMILIES.items():
    PAGES.append({
        "primary_keyword": f"{_family} sage mode",
        "keywords": [f"{_family} sage mode", f"sage {_family}"],
        "title": f"{_family.title()} Sage Mode",
        "body": (f"Syntax: sage train {_family}  |  sage on {_family}  |  sage off\n\n"
                 f"Description: Sign the permanent {_family.title()} contract at its elder in {_hideout}, then reach level 80 and train there to 100% mastery. {_bonus} "
                 "All Sage Modes grant 20% damage, +10 accuracy, and 10% less incoming damage. "
                 "Active upkeep is 12 Chakra every 10 seconds out of combat or 16 Chakra and 8 Stamina per combat round. "
                 "See 'help sage training' for the mastery process.\n\nDate: 2026-09-27"),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    })
