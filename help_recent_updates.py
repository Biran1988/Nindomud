"""In-game help pages for the recent world, mission and crafting updates.

Seeded into data/help by help_system.seed_default_help without overwriting
player-created or staff-edited helpfiles.
"""

def page(key, title, body, *aliases):
    return {
        "primary_keyword": key,
        "keywords": [key, *aliases],
        "title": title,
        "body": body,
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    }


PAGES = [

    page("eight gates", "The Eight Inner Gates",
         "Syntax: gates [status|safe|off|1..8 [confirm]]\\n"
         "        perform gate of opening | perform gate of death confirm\\n"
         "        perform front lotus <target> (and the other gate attacks)\\n\\n"
         "Eight learnable, Taijutsu-only Inner Gates unlock at levels "
         "20, 40, 65, 90, 120, 155, 195 and 240. Learn and practice "
         "each with a teacher first. The Gates increase physical melee "
         "and Taijutsu damage and accuracy, not unrelated Ninjutsu. "
         "They consume Stamina every three real seconds. Gates 6 and 7 "
         "also damage their own user. The Eighth Gate dramatically "
         "increases power, drains Health, and inevitably defeats the caster "
         "after 30 real seconds with normal defeat penalties; it CANNOT "
         "be closed. 'gates 8 confirm' is always required to open it. "
         "Ordinary Gates can be closed but impose exhaustion cooldowns. "
         "The six follow-up attacks are Front Lotus (Gate 1), Reverse "
         "Lotus (Gate 3), Morning Peacock (Gate 6), Daytime Tiger "
         "(Gate 7), Evening Elephant (Gate 8), and Night Guy "
         "(Gate 8, level 250). Gates also work in PvP. "
         "BATTLE READY CONFIG allows Eight Gates as an OFF-by-default "
         "option, which opens only the highest learned safe Gate (1-7), "
         "never the Eighth Gate.",
         "gates", "gate", "inner gates", "eight inner gates", "gate of death"),
    page("mission rewards", "Mission Points and Automatic Fallbacks",
         "Every completed mission, including hunts, gathering, lost-item "
         "recovery, and courier delivery, awards rank-scaled random mission "
         "points: D 1-5, C 4-9, B 7-13, A 11-17, S 15-20. These "
         "ranges intentionally overlap, with a maximum of 20 points. "
         "The rolled amount counts toward your current "
         "spendable balance and lifetime total. XP and Ryo still scale "
         "with mission rank.\\n\\n"
         "When MISSION REQUEST <rank> cannot find a Mission-flagged enemy "
         "in your rank's level band, it automatically chooses a roadside "
         "lost-item recovery or courier delivery mission at that rank. "
         "If the first option is unavailable, it tries the other. "
         "Posted D-Rank hunts have the same fallback. Item recovery takes "
         "place on mainland roads or roadside inns and is completed by GET; "
         "deliveries give you a sealed parcel for a real reachable NPC. "
         "Mission deadlines, minimum levels, and cooldowns still apply.",
         "mission fallback", "mission points", "automatic mission"),

    page("delivery missions", "Sealed Courier Delivery Missions",
         "Syntax: mission request delivery <d|c|b|a|s>\\n"
         "        mission info\\n"
         "        deliver\\n"
         "        give parcel <npc>\\n"
         "        mission fail [rank]\\n\\n"
         "You receive a unique sealed parcel immediately when the mission "
         "is assigned. Bring it to the specified LIVE village NPC in the "
         "destination room shown by MISSION INFO. DELIVER while standing "
         "beside them, or GIVE PARCEL <NPC>. Courier parcels cannot be "
         "traded, sold, auctioned, dropped or put in a backpack. "
         "The mission and parcel expire after 30 real minutes, including "
         "offline time; abandonment removes the parcel without reward. "
         "Completing a delivery pays rank-scaled XP and Ryo, randomly rolled 1-5 "
         "mission points and village reputation. These missions are "
         "independent of hunts, roadside item recovery and weed delivery.",
         "courier missions", "courier", "parcel delivery", "mission delivery"),

    page("durability", "Crafted Weapon and Armor Durability",
         "Syntax: examine <crafted item>\n\n"
         "Every uniquely forged weapon or armor piece has durability stored on its object, "
         "not in its name. Iron gear starts with 2,500 durability, Steel with 5,000, "
         "and Chakra Steel with 10,000. Wielded crafted weapons lose 1 durability "
         "per landed melee strike, including PvP. Each landed hit against a player "
         "has a small 10% chance to wear down one piece of crafted armor by 1. "
         "At zero durability the equipment breaks, disappears, and its unique "
         "item VNUM is released for future crafting. Examine displays the exact "
         "remaining and maximum durability, regardless of Examine proficiency. "
         "The item name, inventory line and equipment name never gain a durability "
         "counter or suffix. Gathering tool remaining uses also appear in EXAMINE "
         "without a visible name suffix. Ordinary non-crafted combat gear is unaffected.",
         "gear durability", "armor durability", "weapon durability", "breaking equipment"),
    page("inactive characters", "Inactive Character and Account Cleanup",
         "Characters are automatically removed after a long period with no "
         "successful login: levels 1-49 after 6 calendar months, levels 50-99 "
         "after 9 months, and levels 100-249 after 12 months. Level 250 and "
         "above is permanently exempt, as are staff accounts. The server "
         "checks on startup and once per day. Currently connected players "
         "and linkdead sessions are never purged. When a character expires, "
         "both its saved character file and its matching login account are "
         "deleted. The timer resets on each successful login, not from "
         "autosaves or training. Existing older accounts without a recorded "
         "last login are protected using the saved file's modification time.",
         "player retention", "inactive purge", "account deletion", "pfile purge"),
    page("roadside missions", "Roadside Item Recovery Missions",
         "Syntax: mission request item <D|C|B|A|S>\n"
         "        mission info\n"
         "        mission fail\n\n"
         "An item-recovery mission places one special lost item at a random "
         "reachable mainland road location or roadside inn. It never appears "
         "inside any of the five main villages. No enemy kill is needed: "
         "find and GET the assigned item before the 30-minute real-time "
         "deadline. Recoveries may involve a lost jutsu scroll, strange "
         "personal items, and other humorous errands. The item is bound to "
         "your active mission and disappears if it ends unsuccessfully.",
         "item missions", "mission request item", "lost jutsu scroll"),
    page("mission difficulty", "Relative Mission Ranks",
         "Syntax: mission request <D|C|B|A|S>\n"
         "        mission info\n\n"
         "Hunt mission ranks depend on the difference between your current "
         "level and the target mob's level, not on the mob's permanent rank. "
         "D-Rank covers weaker mobs through five levels above you; C-Rank "
         "is +6 to +20, B-Rank +21 to +40, A-Rank +41 to +70, and S-Rank "
         "+71 or higher. As you level up, the same mob can move into a "
         "lower mission rank. A hunt needs exactly ONE kill of its assigned "
         "Mission-tagged mob, has a 30-minute timer, and only works with "
         "mobs explicitly designated as current mission targets. The old "
         "built-in village mission mobs are retired.",
         "dynamic mission ranks", "mission levels", "mission hunt"),
    page("day night cycle", "Day, Night and NPC Schedules",
         "Syntax: time\n\n"
         "The world follows a repeating 24-hour clock with one game day "
         "lasting 30 real minutes. Sunrise is 6 AM and sunset is 6 PM. "
         "Certain NPCs can react to the hour: merchants with configured "
         "SHOP/MSET opening and closing times stop trading after hours, "
         "and scheduled guards can close or reopen their linked gates. "
         "Most ordinary merchants and gates remain unchanged unless staff "
         "give them a schedule.",
         "day and night", "nighttime", "npc schedules"),
    page("scheduled gates", "Shop Hours and Gate Schedules",
         "Staff setup: mset <mob vnum> shopopen <hour> / shopclose <hour>\n"
         "             mset <mob vnum> gate <room vnum> <direction>\n"
         "             mset <mob vnum> gateopen <hour> / gateclose <hour>\n\n"
         "A configured NPC can open or close a real linked gate depending "
         "on the 24-hour game clock, and merchants can close their shops. "
         "Door states are synchronized in both directions; unscheduled "
         "NPCs and doors are left alone. Use TIME to inspect the current hour.",
         "gate hours", "shop hours", "gate guards"),
    page("info scroll", "Player-Written Info Scrolls",
         "Syntax: write info scroll\n"
         "        examine <info scroll>\n\n"
         "Buy a blank Info Scroll at a village general store. Writing "
         "opens a multiline text editor; finish to store your message on "
         "that specific scroll, which retains its author and text through "
         "dropping, trading and server restarts. Examine reads the message "
         "even without the Examine skill. Info Scrolls are different "
         "from jutsu-learning scrolls.",
         "written scroll", "write scroll", "message scroll"),
    page("look equipment", "Viewing Other Players' Equipment",
         "Syntax: look <player>\n"
         "        look self\n"
         "        look <mob>\n\n"
         "LOOK shows what a visible character is wearing and holding: "
         "armor, accessories, wielded weapons, off-hand weapons and tools. "
         "It does not reveal the contents of their inventory or bypass "
         "invisibility and concealment.",
         "inspect gear", "worn equipment", "look player"),

    page("poison", "Weapon Poison and Toxins",
         "Syntax: toxin binding <weapon> | poison gas bomb <target> | "
         "disenchantment <weapon> | examine <weapon>\n\n"
         "Bukijutsu level 30 can permanently bind poison to one owned weapon "
         "using TOXIN BINDING (45 Chakra, 15 Stamina, 8-second cooldown). "
         "A successful damaging strike has a 30% chance to poison its target, "
         "dealing damage over subsequent pulses. Poison works on mobs and "
         "players, and sends combat feedback when it activates. The poison "
         "is not consumed on hit. Only one item property can be bound; "
         "DISENCHANTMENT removes it. Bukijutsu level 40 can use POISON GAS "
         "BOMB to attach a two-pulse delayed toxic trap using a consumed "
         "bomb item. Craft and USE an Antidote Pill to clear Poisoned. "
         "EXAMINE shows a weapon's poison property and durability; the "
         "item name never displays poison or enchantment suffixes.",
         "toxins", "poison weapons", "poisoned weapons", "toxin"),
    page("enchantments", "Weapon Enchantments and Effects",
         "Syntax: weapon enchantment <weapon> <property> | "
         "toxin binding <weapon> | disenchantment <weapon> | examine <weapon>\n\n"
         "Bukijutsu level 55 can apply one permanent property to a carried "
         "or wielded weapon. Traditional properties: FLAMING (25% burning), "
         "FROST (25% off balance), SHOCKING (20% stunned), LIFE (heal "
         "up to 10% of damage dealt), SHARP (+10% damage) or VORPAL "
         "(approximately +16.7% damage). Toxin Binding applies POISON "
         "(30% chance to poison) from level 30. Properties activate on "
         "successful damaging weapon strikes, including PvP. Colored "
         "combat text appears only when an effect activates.\n\n"
         "Fire, Water, Wind, Lightning and Earth elemental enchantments "
         "require a genuinely Chakra Steel-forged weapon and the "
         "enchanter's revealed chakra nature. A matching Bukijutsu wielder "
         "gains +50% weapon damage and the element's combat effect. "
         "Samurai Sabre can stack on swords, adding +5% at level 35, "
         "increasing by 5% per passive tier to +25% at level 250. "
         "DISENCHANTMENT removes a weapon's current property. "
         "EXAMINE shows it, not the visible item name. Durability and "
         "permanent gem inlays remain separate.",
         "weapon enchantments", "enchantment effects", "enchanted weapons"),
    page("samurai sabre 2", "Samurai Sabre 2 (Passive)",
         "Automatic Bukijutsu passive unlocked at ninja level 85. "
         "No scroll, manual command, or teacher practice is needed. "
         "Adds +5% sword strike damage while the original SAMURAI SABRE "
         "toggle is active, for a 10% total bonus. Does nothing while "
         "Samurai Sabre is off. See HELP SAMURAI SABRE.",
         "samurai sabre ii", "sabre 2"),
    page("samurai sabre 3", "Samurai Sabre 3 (Passive)",
         "Automatic Bukijutsu passive unlocked at ninja level 140. "
         "No scroll, manual command, or teacher practice is needed. "
         "Adds another +5% while SAMURAI SABRE is active with a sword, "
         "for a 15% total bonus. See HELP SAMURAI SABRE.",
         "samurai sabre iii", "sabre 3"),
    page("samurai sabre 4", "Samurai Sabre 4 (Passive)",
         "Automatic Bukijutsu passive unlocked at ninja level 195. "
         "No scroll, manual command, or teacher practice is needed. "
         "Adds another +5% while SAMURAI SABRE is active with a sword, "
         "for a 20% total bonus. See HELP SAMURAI SABRE.",
         "samurai sabre iv", "sabre 4"),
    page("samurai sabre 5", "Samurai Sabre 5 (Passive)",
         "Automatic Bukijutsu passive unlocked at ninja level 250. "
         "No scroll, manual command, or teacher practice is needed. "
         "Adds another +5% while SAMURAI SABRE is active with a sword, "
         "for the maximum 25% total sword strike damage bonus. "
         "See HELP SAMURAI SABRE.",
         "samurai sabre v", "sabre 5"),
    page("elemental taijutsu", "Elemental KKGK Taijutsu",
         "Syntax: <elemental taijutsu technique> <enemy> | HELP <technique>\\n\\n"
         "Taijutsu now has 33 physical Kekkei Genkai strikes: three each "
         "for Ice, Wood, Storm, Boil, Lava, Scorch, Magnet, Explosion, "
         "Flashfire, Tempest and Dust Releases. These are direct punches, "
         "kicks, palms and combinations, not projected Ninjutsu spells. "
         "They inflict physical damage, use mainly Stamina plus a smaller "
         "amount of Chakra, have no hand signs or casting delay, and can "
         "apply the same elemental status effects as their corresponding "
         "Ninjutsu releases. Their damage is set to 85% of matching-tier "
         "Ninjutsu base damage to balance their instant impact.\\n\\n"
         "First, earn a real nature-based elemental release through Chakra "
         "Paper; existing clan bloodline restrictions remain unchanged. "
         "The first three strikes unlock at levels 25, 45 and 70 for "
         "the matching release. Dust Release (Kekkei Tota) has all three "
         "techniques at level 100 and requires Earth, Wind and Fire. "
         "Taijutsu fighters learn the moves automatically when qualified, "
         "including retroactive login unlocks. Only the Taijutsu class "
         "can activate them; other classes keep their original Ninjutsu "
         "and elemental options unchanged. Use PRAC KKGK or SKILLS for "
         "your techniques, then HELP <name> for costs and effects. "
         "A first teacher practice may be required by normal skill rules.",
         "kkgk taijutsu", "taijutsu kekkei genkai", "elemental martial arts"),

    page("battle ready", "Battle Ready — Personal Combat Preparations",
         "Syntax: battle ready\\n"
         "        battle ready config\\n"
         "        battle ready <jutsu name> on|off\\n"
         "        battle ready status\\n"
         "        config battle ready [<jutsu name> on|off]\\n"
         "        bready [config|status]\\n\\n"
         "Battle Ready activates your selected known preparation abilities "
         "in one command, with no extra macro cost. Each ability pays its "
         "own normal Chakra/Stamina, obeys cooldown and first teacher-practice "
         "requirements, and must be available to your level/class/bloodline. "
         "Unlearned or locked jutsu are skipped. An already-active buff is "
         "NEVER re-cast or toggled off. The macro does not override silenced, "
         "stunned, pending casts or other combat restrictions.\\n\\n"
         "Initially enabled: Barrier, Focused Mind, Sensory Detect and "
         "Samurai Sabre (only if you qualify and wield a sword). "
         "You can separately enable Sharingan, Byakugan, Sage Mode, "
         "Susanoo, Silent Movement, Camouflage and Chisei, plus additional "
         "existing learned techniques: Sanchin Dachi, Neko Ashi Dachi, "
         "Kihon Dachi, Celestial Byakugan, Tenseigan Chakra Mode, "
         "Six Paths Mode, Tailed Beast Mode, Bijuu Cloak, Eight Gates, "
         "Kamui Intangibility and Hidden Mist Jutsu. These additional "
         "selections begin OFF and never grant an unlearned ability. "
         "Eight Gates automatically selects the best practiced Gate from 1-7; "
         "it NEVER opens the irreversible Eighth Gate. "
         "Taijutsu stances never overwrite an active stance; higher "
         "Byakugan forms require their prerequisite eyes. Sage Mode and "
         "Six Paths Mode cannot be combined. An existing stronger "
         "Bijuu transformation is never downgraded. Camouflage "
         "cannot activate during combat; delayed hand-sign jutsu are "
         "processed last, one at a time. Reuse BATTLE READY after a "
         "pending cast completes to activate the next preparation. "
         "Every selection is saved on your individual character. "
         "Use BATTLE READY CONFIG to see which options are enabled, "
         "active, learned or locked; selecting a locked option in advance "
         "does not unlock it. Example: battle ready samurai sabre on. "
         "See HELP BARRIER, HELP SAMURAI SABRE and HELP FOCUSED MIND.",
         "battleready", "bready", "combat preparations", "battle readiness"),
]

PAGES.extend([
    page("advanced shadow clone jutsu", "Advanced Shadow Clone Jutsu",
         (
             "Level requirement: 75. This is a scroll-only general utility jutsu for every class. Read an Advanced Shadow Clone Scroll to learn it. It creates ONE working shadow clone (separate from combat and elemental clones) in the room where the job or training will happen. Summon the clone at the work site; it cannot walk to another site or fight.\n"
             "\n"
             "Syntax:\n"
             "  WORKCLONE MINE <chakra> [WITH <tool>]\n"
             "  WORKCLONE CHOP <chakra> [WITH <tool>]\n"
             "  WORKCLONE FISH <chakra> [WITH <tool>]\n"
             "  WORKCLONE FARM <chakra> [WITH <tool>]\n"
             "  WORKCLONE TRAIN <known attack jutsu> <chakra>\n"
             "  WORKCLONE STATUS\n"
             "  WORKCLONE RETURN\n"
             "  PERFORM ADVANCED SHADOW CLONE JUTSU <task> <chakra>\n"
             "\n"
             "Commit at least 100 Chakra at summoning. Every 500 Chakra funds 30 REAL minutes; the budget is paid up front and work continues after leaving the room or disconnecting. The character retains the task and pending rewards across reconnects. A clone can only gather by mining, lumberjacking, fishing or farming; it cannot smith, craft, cook, smelt or cut gems.\n"
             "\n"
             "For gathering, a clone has free BASIC virtual tools. To use a better real tool, supply WITH <tool> while summoning. That tool is removed from your inventory or tool slot and used at its current durability. An unbroken tool is returned; when it breaks, the clone falls back to basic tools. Job location and tool-level rules still apply.\n"
             "\n"
             "For jutsu training, summon beside a training dummy (mob vnum 6) and choose one already learned, usable ATTACK jutsu. The clone can increase that jutsu's proficiency; its gains are reported on return. The clone does not learn brand-new jutsu for you.\n"
             "\n"
             "On task completion or WORKCLONE RETURN, the clone returns and dispels. If you own an apartment, gathered materials are deposited in its storage room (when built) or main room. Otherwise they fill your available inventory slots and any overflow drops at your feet. Job XP and jutsu training gains are awarded when the clone returns.\n"
             "\n"
             "Examples: WORKCLONE MINE 500 | WORKCLONE CHOP 100 WITH steel axe | WORKCLONE TRAIN Fireball Jutsu 500 | WORKCLONE STATUS | WORKCLONE RETURN\n"
             "\n"
             "See HELP WORKCLONE for a short command guide. Normal Shadow Clone Jutsu and elemental battle clones are separate abilities."
         ),
         "working clone", "advanced clone"),
    page("workclone", "Workclone - Task Commands",
         (
             "WORKCLONE controls your one Advanced Shadow Clone workforce worker. You must first be level 75+ and learn Advanced Shadow Clone Jutsu from its scroll (HELP ADVANCED SHADOW CLONE JUTSU). You cannot summon another worker while one is active.\n"
             "\n"
             "Syntax:\n"
             "  WORKCLONE MINE|CHOP|FISH|FARM <chakra> [WITH <tool>]\n"
             "  WORKCLONE TRAIN <known attack jutsu> <chakra>\n"
             "  WORKCLONE STATUS\n"
             "  WORKCLONE RETURN\n"
             "\n"
             "Examples:\n"
             "  workclone mine 500\n"
             "  workclone chop 500 with steel axe\n"
             "  workclone fish 100\n"
             "  workclone train Fireball Jutsu 500\n"
             "  workclone status\n"
             "  workclone return\n"
             "\n"
             "Summon at a compatible gathering location or beside a training dummy (vnum 6) for jutsu practice. Minimum investment is 100 Chakra; 500 Chakra pays for 30 minutes. Workers gather with virtual basic tools unless you lend them a real improved tool. If that tool breaks, basic gathering continues. Only collecting and training are allowed, never crafting. One worker at a time.\n"
             "\n"
             "STATUS displays the active job, site, paid Chakra, pending items and remaining time. RETURN recalls the clone early; accrued rewards are delivered at return. With an owned apartment, materials are dropped there; without one, they enter your inventory and overflow drops in your current room. Unbroken loaned tools return with the haul. Saved progress persists on reconnect."
         ),
         "workclones", "working shadow clone"),
    page("elemental mastery", "Elemental Affinity and Mastery",
         (
             "Syntax: ELEMENTS (or MASTERY ELEMENTS)\n"
             "\n"
             "Each of your own chakra natures has 100% INNATE affinity once revealed with Chakra Paper. Affinity represents belonging to that element; it does NOT grant a free +100% damage bonus.\n"
             "\n"
             "A separate ELEMENTAL MASTERY meter starts at 0% for each native element and can climb to 100% through successful use of matching elemental jutsu. Progress becomes harder near 100%, similar to Sharingan training. Elemental mastery is saved independently for Fire, Water, Wind, Earth and Lightning. Successful qualifying attack-jutsu practice by an Advanced Shadow Clone may also train that element.\n"
             "\n"
             "Matching elemental jutsu damage scales from +0% at 0 mastery to up to +15% at 100 mastery. For example, 50% mastery gives +7.5% elemental damage. This is a bonus to qualifying jutsu damage, not every elemental status effect or non-elemental attack. Individual jutsu proficiency and normal restrictions still apply.\n"
             "\n"
             "ELEMENTS shows only natures you have genuinely revealed; hidden/unrevealed natures do not show. You must have the nature to build its mastery: using another element cannot unlock or train an off-element affinity. Chakra Paper still controls reveal and progression to additional elements.\n"
             "\n"
             "See HELP ELEMENTS for chakra nature selection and HELP ADVANCED SHADOW CLONE JUTSU for working clone training."
         ),
         "chakra affinity", "nature mastery", "elemental affinity"),
])
