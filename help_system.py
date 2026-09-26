"""
In-game help file system.

Staff author help topics live with `hedit`, guided step-by-step (primary
keyword -> extra keywords -> title -> full body via the same interactive
line editor `rset` uses), rather than a single one-line command with
every field crammed in. Players look topics up with `help <keyword>`.
Each topic is its own JSON file under data/help/, so it survives
restarts and is easy to hand-edit/back up like any other save file.
"""

import json
import os
import time
from typing import List, Optional

import storage

HELP_DIR = os.path.join(storage.DATA_DIR, "help")
AUDIT_LOG_PATH = os.path.join(storage.DATA_DIR, "help_audit.log")

# Help authoring is lower-risk than world editing, so it's open to
# "helper" and up, not just builder-and-above like rset/mset/oset.
STAFF_CAN_AUTHOR_HELP = {"helper", "builder", "area leader", "administrator", "implementor"}

def _slug(keyword: str) -> str:
    return keyword.strip().lower().replace(" ", "_")


def ensure_dirs() -> None:
    os.makedirs(HELP_DIR, exist_ok=True)


def _path(primary_keyword: str) -> str:
    return os.path.join(HELP_DIR, f"{_slug(primary_keyword)}.json")


def save_entry(entry: dict) -> None:
    ensure_dirs()
    with open(_path(entry["primary_keyword"]), "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)


# Default helpfiles seeded once at startup (main.py), so genuinely
# useful reference content exists out of the box rather than requiring
# a staff member to author it by hand first. Idempotent -- seed_default_help()
# checks for an existing file before writing, so it NEVER overwrites a
# staff member's edited version of the same topic; it only fills in a
# topic that's missing entirely. Still fully editable afterward via
# `hedit` like any other helpfile -- this is just how it starts out.
DEFAULT_HELP_ENTRIES = [
    {
        "primary_keyword": "colors",
        "keywords": ["colors", "color", "colour", "color codes", "ansi"],
        "title": "Color Codes",
        "body": (
            "Syntax: prompt <text with &&codes>  |  description <text with &&codes>  |  biography <text with &&codes>\n"
            "\n"
            "Description: Color codes add color to text you write yourself -- your prompt ('prompt'), description ('description'), and biography ('biography') all support them.\n"
            "\n"
            "A code is an && followed by one letter, applying to everything after it until the next code or a reset. Always end colored text with &&x to reset back to normal.\n"
            "\n"
            "Standard colors:\n"
            "  &&R red      &&G green    &&Y yellow   &&B blue\n"
            "  &&C cyan     &&M magenta  &&W white    &&D dark gray\n"
            "\n"
            "Bright/bold versions -- same letters, lowercase:\n"
            "  &&r bright red      &&g bright green    &&y bright yellow   &&b bright blue\n"
            "  &&c bright cyan     &&m bright magenta  &&w bright white    &&d bright gray\n"
            "\n"
            "Two more:\n"
            "  &&O orange (a convenience shortcut -- see below for how it's made)\n"
            "  &&x reset -- turns color back off; always use this when you're done\n"
            "\n"
            "256-color codes: &&[N] where N is a number from 0 to 255, for finer shades than the named codes above (&&O orange is actually &&[208] under the hood). Example: &&[196] is a bright red, &&[27] is a deep blue.\n"
            "\n"
            "Example: prompt &&RHP:%h&&x sets your prompt so 'HP:' shows in red and the rest stays normal.\n"
            "\n"
            "(If a code ever needs to appear as plain text instead of applying its color -- like every example on this very page -- type &&&& instead of a single &&.)\n"
            "\n"
            "If you'd rather see plain text with no color at all, ask a staff member -- there's no player-facing toggle for this yet.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "attributes",
        "keywords": ["attributes", "attribute", "stats", "stat", "strength", "wisdom",
                     "constitution", "intelligence", "dexterity", "luck", "perception",
                     "willpower", "chakra control"],
        "title": "Attributes",
        "body": (
            "Syntax: train <attribute|str|wis|con|int|dex|luk|per|wil|cc>\n"
            "\n"
            "Description: Your nine core attributes, trained one point at a time with 'train <attribute>' using training points earned each level. Short forms like 'train str' and 'train con' work too. Every attribute is capped at 75.\n"
            "\n"
            "&CStrength&x - Increases your damage in combat: +1 to your basic attack's damage for every 4 points.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CDexterity&x - Improves your reflexes: increases your Dodge Chance (see 'help combatstats'), feeds other combat stats, and grows your Stamina gain each level (+0.5/point above 10, uncapped).\n"
            "  &G[Active]&x\n"
            "\n"
            "&CIntelligence&x - Determines how much proficiency you gain each time you practice a skill, and is the majority share (75%) of how much Chakra you gain each level.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CWisdom&x - More practice points each level (up to +6 bonus at maxed Wisdom, 9 total; base is 3). Also a minor (25%) share of your Chakra gain, alongside Intelligence.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CLuck&x - Increases your Critical Chance, landing hits that deal 50% extra damage (see 'help combatstats').\n"
            "  &G[Active]&x\n"
            "\n"
            "&CConstitution&x - Increases how much max Health you gain each level: base 8 HP/level, plus +0.5 HP for every point above 10, with no cap of its own.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CPerception&x - Intended to represent awareness and attentiveness.\n"
            "  &R[Not Yet Implemented -- planned for a future update]&x\n"
            "\n"
            "&CWillpower&x - Intended to represent mental fortitude and resistance to fear or illusion effects.\n"
            "  &R[Not Yet Implemented -- planned for a future update]&x\n"
            "\n"
            "&CChakra Control&x - Each point trained above 10 permanently adds 10 max Chakra right away (not tied to leveling). Also discounts Genjutsu/Ninjutsu chakra costs by up to 50%, and boosts chakra regen past the usual cap.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(See also: 'help combatstats', 'help scoresheet')&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "combatstats",
        "keywords": ["combatstats", "combat stats", "armor class", "hit roll",
                     "damage roll", "initiative", "dodge chance", "critical chance", "ac"],
        "title": "Combat Stats",
        "body": (
            "Syntax: score\n"
            "\n"
            "Description: Six stats shown on your score sheet ('score'), derived from your attributes rather than trained directly.\n"
            "\n"
            "&CArmor Class&x - Lower is better (a classic convention). Improves as your Dexterity rises, and further with any worn armor's own crafted Armor Class bonus (stacks across every piece worn). Reduces the chance an incoming attack lands, on top of Dodge Chance below.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CHit Roll&x - Rises with Dexterity, and further with your wielded weapon's own crafted Hit Roll bonus, if it has one. Improves your own chance of landing a hit, against a target's Armor Class.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CDamage Roll&x - Rises with Strength.\n"
            "  &R[Not Yet Implemented as its own mechanic -- your Strength DOES affect your real damage directly (see 'help attributes'), and so does your wielded weapon's own type (a Sword hits harder than a Kunai, etc.), but this particular displayed number isn't yet what combat actually uses]&x\n"
            "\n"
            "&CInitiative&x - Rises with Dexterity.\n"
            "  &R[Not Yet Implemented -- there's no turn-order system yet for this to affect]&x\n"
            "\n"
            "&CDodge Chance&x - Your percent chance to fully avoid an incoming attack. 5% at baseline Dexterity, up to 40% at a maxed Dexterity -- a completed armor set's bonus can push this even higher.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CCritical Chance&x - Your percent chance for an attack to land as a critical hit (50% extra damage). 5% at baseline Luck, up to 30% at a maxed Luck -- a completed armor set's bonus can push this even higher.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(See also: 'help attributes')&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "group",
        "keywords": ["group", "grouping", "party", "shared xp", "shared experience"],
        "title": "Grouping",
        "body": (
            "Syntax: group invite <player>  |  group accept  |  group  |  group leave  |  group kick <player>  |  group disband\n"
            "\n"
            "Description: A group shares experience from mob kills -- form one with a party of up to 6 to level up together, rather than every kill only benefiting whoever lands the final blow. Groups are temporary: they aren't saved, and only exist while members are actually online.\n"
            "\n"
            "&Cgroup invite <player>&x - Invites someone in your current room. Starts a new group if you weren't already leading one.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cgroup accept&x - Joins the group that just invited you.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cgroup&x (no arguments) - Shows your group's roster and everyone's current HP.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cgroup leave&x - Leaves your current group. If you were the leader, leadership passes to another member automatically.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cgroup kick <player>&x / &Cgroup disband&x - Leader-only: removes one member, or dissolves the whole group.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(Shared XP only -- ryo, loot, and mission progress from a kill still go solely to whoever landed the kill, not split with the group. Only every group member who's in the SAME ROOM as the kill, and still alive, gets a share -- an equal split of the kill's full reward, not everyone getting the full amount.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "team",
        "keywords": ["team", "teams"],
        "title": "Teams",
        "body": (
            "Syntax: team create <name>  |  team invite <player>  |  team accept  |  team  |  team leave  |  team disband\n"
            "\n"
            "Description: A genuinely different, longer-lived system from 'group' (see 'help group') -- a team's roster persists whether or not its members are online, up to 4 total including the leader. Fighting alongside a teammate you're ALSO grouped with grants a permanent +10% bonus to the experience you'd normally earn from that kill.\n"
            "\n"
            "&Cteam create <name>&x - Forms a new team with you as leader. Requires Chunin rank or higher, and you can't be on the 24-hour cooldown from recently leaving or disbanding a team.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cteam invite <player>&x - Leader-only. Invites someone by name, whether they're online or not -- they'll see the invite the next time they're online and check 'team accept'.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cteam accept&x - Joins the team that invited you, provided you aren't already on one and aren't on the 24-hour cooldown.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cteam&x (no arguments) - Shows your team's full roster and each member's online/offline status.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cteam leave&x / &Cteam disband&x - Leaves your team, or (leader-only) dissolves it entirely for every member. Either way starts a 24-hour cooldown before you (or, for a disband, every member) can join or create another team.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(The XP bonus specifically requires BOTH being on the same team AND actively grouped together via 'group invite' -- being teammates alone, with no active group, earns nothing extra.)&x\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "trade",
        "keywords": ["trade", "trading"],
        "title": "Trade",
        "body": (
            "Syntax: trade <player>  |  trade add <item>  |  trade remove <item>  |  trade ryo <amount>  |  trade confirm  |  trade  |  trade cancel\n"
            "\n"
            "Description: A full negotiated trade with another player -- items and ryo, staged and reviewed by both sides before anything actually moves. Both players must stay in the SAME ROOM for the entire negotiation; either side leaving cancels the trade outright, with nothing exchanged.\n"
            "\n"
            "&Ctrade <player>&x - Proposes a trade to someone in the room, or accepts a pending proposal from them.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Ctrade add <item>&x / &Ctrade remove <item>&x - Adds or removes an item from YOUR OWN offer. You can never touch the other side's offer, only see it.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Ctrade ryo <amount>&x - Sets how much ryo you're offering, replacing any amount set before.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Ctrade confirm&x - Locks in your current offer as final. The trade only completes once BOTH sides have confirmed.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Ctrade&x (no arguments) - Shows both offers side by side and each side's confirmation status.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Ctrade cancel&x - Backs out entirely, before or after accepting. Nothing is ever exchanged unless both sides confirm.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(Changing your offer in any way -- adding, removing, or changing the ryo amount -- resets BOTH sides' confirmations, even if the OTHER side already confirmed. A trade can never complete on terms that weren't both agreed to at the same moment.)&x\n"
            "\n"
            "Date: 2026-08-25"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "duel",
        "keywords": ["duel", "duels", "dueling"],
        "title": "Duel",
        "body": (
            "Syntax: duel <player>  |  duel  |  duel cancel\n"
            "\n"
            "Description: A formal, friendly 1v1 fight, staged in a dedicated 10-room arena spanning five biomes (forest, mountain, desert, swamp, plains) -- real biomes, so elemental jutsu affinity genuinely applies there.\n"
            "\n"
            "&Cduel <player>&x - Challenges someone in the room, or accepts a pending challenge from them. The instant BOTH sides have accepted, you're both pulled straight into the arena -- but to two DIFFERENT starting rooms, not the same one. Finding each other through the arena's maze-like layout is part of the challenge.\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cduel&x (no arguments) - Shows who you're currently dueling (or who you've challenged/been challenged by).\n"
            "  &G[Active]&x\n"
            "\n"
            "&Cduel cancel&x - Backs out. Before acceptance, this simply calls off the challenge. Mid-duel, it ends things the same way a real defeat would -- both of you are pulled back out and returned home.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(A duel only ever ends in a genuine defeat -- there's no yield or concede. Unlike ordinary PvP, though, losing a duel costs you nothing: no experience lost, no ryo lost, no trip to the hospital. Both fighters are simply healed up a bit and sent back to wherever they started from before the challenge began.)&x\n"
            "\n"
            "Date: 2026-08-25"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "silence",
        "keywords": ["silence", "unsilence"],
        "title": "Silence",
        "body": (
            "Syntax: silence <player name> <hours>  |  unsilence <player name>  (administrator+ only)\n"
            "\n"
            "Description: A staff punishment command. Blocks the named player from 'say', 'ooc', and village chat entirely for the given number of hours, as a punishment. Works on an online OR offline player -- an offline target's silence is checked (and, if the time is already up, automatically cleared) the moment they next try to speak.\n"
            "\n"
            "Automatically lifts itself once the time is up -- no need to remember to undo it. 'unsilence' lifts it early if needed.\n"
            "\n"
            "Say, ooc, and village chat also apply this same silence AUTOMATICALLY, no staff involved, if a player sends too many messages too quickly (spamming). An automatic silence lasts 10 minutes and works exactly the same as a staff-issued one.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "levelup",
        "keywords": ["levelup", "level up"],
        "title": "Levelup",
        "body": (
            "Syntax: levelup <player name>  (administrator+ only)\n"
            "\n"
            "Description: Levels the named player up exactly ONE level, as a real reward -- genuinely the same as if they'd earned it through normal XP gain, not just a bare number change. Grants the real max HP/Chakra/Stamina increase (with a fresh full heal), new training points and practice points to spend, and unlocks any jutsu tied to the new level -- so a player can go train stats or practice skills naturally with what they were just given. Works on an online OR offline player. Always requires a target -- never applies to your own character.\n"
            "\n"
            "Genuinely separate from 'mset' -- this exists outside the raw prototype editor specifically as its own reward tool, not a field to poke directly.\n"
            "\n"
            "Already at the level cap (100)? Refuses outright rather than doing nothing silently.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "jail",
        "keywords": ["jail", "unjail"],
        "title": "Jail",
        "body": (
            "Syntax: jail <player name> <hours>  |  unjail <player name>  (administrator+ only)\n"
            "\n"
            "Description: A staff punishment command. Teleports the named player to a dedicated jail cell with no exits, and keeps them there for the given number of hours -- as a punishment. Works on an online OR offline player -- an offline target is teleported the moment they next log in and the sentence is checked.\n"
            "\n"
            "Automatically releases the player once the time is up, sending them to their home village's own starting room. 'unjail' releases them early if needed, to the same destination.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "classes",
        "keywords": ["classes", "class", "jutsu"],
        "title": "Classes",
        "body": (
            "Syntax: help <class name>  (e.g. help ninjutsu)\n"
            "\n"
            "Description: Your primary class, chosen at character creation, decides which jutsu you're granted automatically as you level -- see 'help <class name>' for each one's own full list. The four classes are:\n"
            "\n"
            "&CNinjutsu&x -- elemental and utility techniques, most of them requiring hand signs. See 'help ninjutsu'.\n"
            "\n"
            "&CGenjutsu&x -- illusion and mental techniques. See 'help genjutsu'.\n"
            "\n"
            "&CTaijutsu&x -- pure physical combat techniques, no hand signs, no chakra cost. See 'help taijutsu'.\n"
            "\n"
            "&CBukijutsu&x -- weapon and thrown-item techniques. See 'help bukijutsu'.\n"
            "\n"
            "Your primary class only decides which jutsu you're automatically granted -- it doesn't restrict which weapons you can wield or which skills you can practice.\n"
            "\n"
            "Each class also gives a real, one-time +4 boost to two attributes at character creation: Ninjutsu boosts Intelligence and Constitution, Genjutsu boosts Intelligence and Wisdom, Taijutsu boosts Strength and Dexterity, and Bukijutsu boosts Strength and Constitution.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "personality",
        "keywords": ["personality", "personality trait", "traits"],
        "title": "Personality Traits",
        "body": (
            "Syntax: (chosen once, permanently, at character creation)\n"
            "\n"
            "Description: Your personality trait gives a real, permanent trade-off to two of your combat stats -- one genuine upside, one genuine downside. There are 8 to choose from:\n"
            "\n"
            "&CReckless&x -- more damage, weaker armor class.\n"
            "&CConfident&x -- better hit roll, worse dodge chance.\n"
            "&CLoyal&x -- +10% experience whenever you're fighting alongside others (any real group, not just a formal team) -- this stacks with the team bonus. Fighting alone is completely ordinary, no bonus and no penalty.\n"
            "&CReserved&x -- better dodge chance, less damage.\n"
            "&CCalm&x -- stronger armor class, worse hit roll.\n"
            "&CHot-headed&x -- better critical chance, worse hit roll.\n"
            "&CCunning&x -- better critical chance, weaker armor class.\n"
            "&CCheerful&x -- better dodge chance, worse critical chance.\n"
            "\n"
            "Chosen once at character creation and permanent -- there's no way to change it afterward.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "ninjutsu",
        "keywords": ["ninjutsu"],
        "title": "Ninjutsu",
        "body": (
            "Syntax: perform <jutsu name> <target>\n"
            "\n"
            "Description: One of the four primary classes (see 'help classes'). Ninjutsu techniques cover elemental attacks and a few utility jutsu, most of them requiring hand signs (see 'help handsigns') and a real casting delay before they land.\n"
            "\n"
            "Jutsu granted automatically as a Ninjutsu character levels: Shadow Shuriken Technique (1), Fireball/Water Dragon/Wind Blade/Lightning Strike Jutsu/Earth Wall Crusher (20 -- each requires your own chakra nature to genuinely match its element, see 'help elements'), Shadow Clone Jutsu (30).\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "genjutsu",
        "keywords": ["genjutsu"],
        "title": "Genjutsu",
        "body": (
            "Syntax: perform <jutsu name> <target>\n"
            "\n"
            "Description: One of the four primary classes (see 'help classes'). Genjutsu techniques deal mental damage and often carry a lingering status effect, and (like Ninjutsu) require hand signs and a real casting delay before they land.\n"
            "\n"
            "Jutsu granted automatically as a Genjutsu character levels: Demonic Illusion: Hell Viewing Technique (1), Narakumi (15).\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "taijutsu",
        "keywords": ["taijutsu"],
        "title": "Taijutsu",
        "body": (
            "Syntax: <jutsu name> <target>\n"
            "\n"
            "Description: One of the four primary classes (see 'help classes'). Taijutsu techniques are pure physical combat -- no hand signs, no chakra cost, and no casting delay, unlike Ninjutsu/Genjutsu. Used directly by name rather than through 'perform'.\n"
            "\n"
            "Jutsu granted automatically as a Taijutsu character levels: Dynamic Entry (1).\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "bukijutsu",
        "keywords": ["bukijutsu"],
        "title": "Bukijutsu",
        "body": (
            "Syntax: <jutsu name> <target>\n"
            "\n"
            "Description: One of the four primary classes (see 'help classes'). Bukijutsu techniques center on weapons and thrown items -- like Taijutsu, no hand signs and no casting delay. Some genuinely consume an inventory item on use.\n"
            "\n"
            "Jutsu granted automatically as a Bukijutsu character levels: Throw Shuriken (1), Throw Kunai (15), Counter Kunai (25, passive), Explosive Tag Kunai (30).\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "jobs",
        "keywords": ["jobs", "job", "job levels", "fishing", "mining", "lumberjack",
                     "weaponsmith", "armorsmith", "gemcutter", "cooking", "farming"],
        "title": "Jobs",
        "body": (
            "Syntax: jobs\n"
            "\n"
            "Description: Shows your progress in every job -- a RuneScape-style leveling track completely separate from your ninja level and experience. A job's level and xp only rise from doing that job's own activity, never from combat or missions, and every registered job is shown even if you've never touched it (level 1, 0 xp) rather than only listing what you've already started.\n"
            "\n"
            "&CFishing&x - Buy a starter rod from any village General Store, then 'fish' at a water biome (e.g. Konoha Riverside, off the Outskirts). Higher rod tiers are crafted, not bought.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CCooking&x - Buy a cooking pot (6 tiers, levels 1-99), hold it, then 'cook <fish>' -- no biome needed. Real chance to burn the dish; a successful one gets a quality tier (Common/Uncommon/Rare/Epic/Legendary, built around your pot's own tier) that scales its sell price and how much Stamina it restores if eaten.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CFarming&x - Buy a hoe, hold it, then 'farm' at a plains biome (e.g. a village Farmland, off the Villager's House). Real chance to come up with nothing; crops are sellable.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CMining&x - Buy a starter pickaxe, then 'mine' at a mountain biome (e.g. Konoha Mountain Path). Produces ore and ingots that feed Weaponsmith, Armorsmith, and Fishing's own rod crafting, plus raw gems for Gemcutter.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CLumberjack&x - Buy a starter axe, then 'chop' at a forest biome (e.g. Konoha Forest Grove). Produces logs that feed Fishing's rod crafting and Weaponsmith.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CWeaponsmith&x - Crafting-only, no gathering command of its own. 'craft' with no arguments to see recipes -- turns Mining's ore into forged weapons.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CArmorsmith&x - Crafting-only, same as Weaponsmith -- turns Mining's ore into forged armor.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CGemcutter&x - Hold a Copper Chisel (VNUM 20803) and use 'gemcut <raw gem>' to cut mining gems.\n"
            "  &G[Active]&x\n"
            "\n"
            "See 'craft' with no arguments for the full recipe list across every crafting-capable job at once.\n"
            "\n"
            "&D(See also: 'help scoresheet')&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "scoresheet",
        "keywords": ["scoresheet", "score sheet"],
        "title": "Score Sheet",
        "body": (
            "Syntax: score\n"
            "\n"
            "Description: An overview of every 'score' sheet section not already covered by 'help attributes' or 'help combatstats'.\n"
            "\n"
            "&CRank&x - Your current village rank (e.g. Genin), raised through missions and time in service.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CClan&x - A family affiliation chosen at creation, or changed later with 'clan join'.\n"
            "  &R[Not Yet Implemented -- cosmetic only, no mechanical bonus yet]&x\n"
            "\n"
            "&CLevel / Experience&x - Your overall combat level and progress toward the next one, gained from defeating enemies and completing missions.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CRyo&x - Your spendable currency, earned from missions, corpses, and jobs, spent at shops and on crafting materials.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CHealth / Chakra / Stamina&x - Your combat resources. Health reaching 0 defeats you; jutsu cost Chakra; physical actions cost Stamina. All three regenerate naturally over time, faster while resting.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CPosition / Fighting&x - Whether you're standing, sitting, or resting, and who (if anyone) you're currently fighting.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CPractice Points / Training Points&x - How many skill-practice and attribute-training uses you have banked right now (see 'help attributes').\n"
            "  &G[Active]&x\n"
            "\n"
            "&CPlayer Kills / Deaths&x - Your PvP record.\n"
            "  &G[Active]&x\n"
            "\n"
            "&CTotal Play Time&x - How long you've spent logged in and playing.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(See also: 'help attributes', 'help combatstats', 'help jobs')&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "look",
        "keywords": ["look", "l"],
        "title": "Look",
        "body": (
            "Syntax: look  |  look <name>  |  look self  |  look me\n"
            "\n"
            "Description: Shows the room you're in: its name, anyone/anything present, and its exits. 'look <name>' examines a player, mob, or item in the room or your own inventory instead -- 'look self' or 'look me' shows your own description.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "scan",
        "keywords": ["scan"],
        "title": "Scan",
        "body": (
            "Syntax: scan <direction>  (n, s, e, w, ne, nw, se, sw, u, d also work)\n"
            "\n"
            "Description: General Skill learned at level 3. See the visible players, mobs, corpses, and ground items in one adjacent room. Invisible targets do not appear. Closed doors and hidden exits block scanning.\n"
            "\n"
            "Date: 2026-09-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "open",
        "keywords": ["open"],
        "title": "Open",
        "body": (
            "Syntax: open <direction>\n"
            "\n"
            "Description: Opens a closed door on one of the room's exits. Refuses if that exit isn't a door, or if the door is locked -- unlock it first.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "close",
        "keywords": ["close"],
        "title": "Close",
        "body": (
            "Syntax: close <direction>\n"
            "\n"
            "Description: Closes an open door on one of the room's exits.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "lock",
        "keywords": ["lock"],
        "title": "Lock",
        "body": (
            "Syntax: lock <direction>\n"
            "\n"
            "Description: Locks a door. The door must already be closed. Anyone can lock a door they're standing at -- there's no key requirement to lock, only to unlock one that needs a specific key item or passcode.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "help",
        "keywords": ["help"],
        "title": "Help",
        "body": (
            "Syntax: help  |  help <topic>\n"
            "\n"
            "Description: With no topic, lists every available help topic. With a topic name (or one of its listed alternate keywords), shows that topic's help text. Covers every command, jutsu, and passive skill, plus deeper reference pages on attributes, combat stats, the score sheet, jobs, and grouping.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "unlock",
        "keywords": ["unlock"],
        "title": "Unlock",
        "body": (
            "Syntax: unlock <direction> [passcode]\n"
            "\n"
            "Description: Unlocks a locked door. If the door requires a specific key item, you need it in your inventory. If it requires a passcode, type it as the second word.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "recall",
        "keywords": ["recall"],
        "title": "Recall",
        "body": (
            "Syntax: recall\n"
            "\n"
            "Description: Teleports you back to your home village's square.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "anki",
        "keywords": ["anki"],
        "title": "Anki",
        "body": (
            "Syntax: anki\n"
            "\n"
            "Description: A General Skill known by every character from the start. Teleports you straight to your own village's Kage room -- unlike 'recall', which takes you home to your apartment. Can't be used while fighting, and has a 5-minute cooldown between uses.\n"
            "\n"
            "Date: 2026-09-07"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "goto",
        "keywords": ["goto", "teleport"],
        "title": "Goto",
        "body": (
            "Syntax: goto <vnum>  |  goto <player name>\n"
            "\n"
            "Description: (Staff only.) Teleports you directly to a room by vnum, or to wherever an online player currently is. Bypasses any locked/private room restrictions, same as staff already can when walking normally. Going to a vnum with no room there yet creates one on the spot (a bare 'An Unfinished Room', same placeholder 'rset bexit' uses) and teleports you there.\n"
            "\n"
            "'rset goto <vnum>' does the same teleport, then leaves you there editing that room with rset -- see 'help rset'.\n"
            "\n"
            "Date: 2026-08-28"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "transfer",
        "keywords": ["transfer"],
        "title": "Transfer",
        "body": (
            "Syntax: transfer <player name>\n"
            "\n"
            "Description: (Staff only.) Teleports another online player directly to your own current location. Their own real room is saved first, so 'return' can send them back later -- transferring the same player again while they're still away just updates that saved room to wherever they were at that moment, rather than remembering every past location.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "return",
        "keywords": ["return"],
        "title": "Return (staff)",
        "body": (
            "Syntax: return\n"
            "\n"
            "Description: (Staff only.) Sends whoever you most recently transferred back to wherever they originally were. Takes no argument -- it always targets your own last transfer, not a name you specify fresh. Refuses cleanly if that player has logged off, or if they've already been sent back.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "spawnpoint",
        "keywords": ["spawnpoint", "spawn point", "load", "setspawn", "spawn cap", "population cap"],
        "title": "Spawnpoint (staff)",
        "body": (
            "Syntax: spawnpoint add mob|item <vnum>  |  spawnpoint remove mob|item <vnum>  |  spawnpoint remove all  |  spawnpoint list\n"
            "        spawnpoint cap mob|item <vnum> <total> <per_period>  |  spawnpoint cap mob|item <vnum>\n"
            "\n"
            "Description: Registers a persistent spawn point in the room you're standing in right now (always wherever you are, same as rset -- no separate targeting) -- a mob or item prototype that should always exist there, saved so it survives a server restart. This automatically saves the mob or item's own prototype too, not just the fact that it belongs here -- a custom one made with 'mset create'/'oset create' survives a restart correctly on its own, with no need to also run 'save world'. Adding one spawns an instance immediately too, not just on the next restart. 'spawnpoint list' shows what's registered in your current room, including each one's own current caps; 'remove' unregisters one (without touching whatever's already spawned) -- and it STAYS removed across every future restart, since the game itself doesn't hardcode any mob or item to always exist anywhere. 'remove all' unregisters every spawn point in the room at once. Every single NPC in the game -- bankers, shopkeepers, villagers, weapon vendors, wandering bandits, gambling attendants, quest guardians, everything -- exists only because a spawn point puts it there; a fresh, brand-new server has none of them until you register them yourself.\n"
            "\n"
            "For a mob specifically, dying and coming back afterward was already automatic (the existing respawn timer) -- a spawn point's job is just guaranteeing it's there in the first place, including after a restart. Every area also resets on a fixed 15-minute timer (see 'help area'): whenever that fires, a mob spawn point in that area gets swept and respawned if missing, checked across the WHOLE area (not just its own spawn room, so a mob that's simply wandered elsewhere isn't wrongly treated as missing). An item spawn point isn't automatically restocked the moment someone picks it up mid-session, and isn't affected by area resets either -- see 'help reload' to bring back anything missing from your CURRENT room specifically, mobs and items alike, right now rather than waiting on a timer.\n"
            "\n"
            "'spawnpoint cap' (per direct request/confirmation -- this used to be its own separate command, 'setspawn', now folded in here as one subcommand instead of a whole second command) caps how many of a given vnum are allowed to exist across the WHOLE area at once, and how many new ones a single area reset is allowed to add. If no spawn point already exists here for that vnum, one is registered first, same as 'spawnpoint add' would. Example: 'spawnpoint cap mob 9500 10 2' allows up to 10 of mob 9500 to exist across the whole area at once, with each area reset adding at most 2 new ones -- never exceeding the total of 10, even across many resets. Use 'off' in place of either number to remove that cap. With no numbers at all, shows that one spawn point's current caps instead of changing them. The per-period cap can never be set higher than the total cap. An uncapped spawn point (the default, or after clearing both with 'off') behaves exactly like a plain add -- one instance kept alive, nothing more. Caps are enforced by the same area-reset sweep described above -- mob spawn points only, in practice, since that's the only sweep that currently exists.\n"
            "\n"
            "'mset spawn <vnum> <room_vnum>' and 'oset load <vnum>' place a single instance right now with no persistence at all -- for something you don't want to always be there, use those instead.\n"
            "\n"
            "Date: 2026-09-12"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "reload",
        "keywords": ["reload"],
        "title": "Reload (staff)",
        "body": (
            "Syntax: reload\n"
            "\n"
            "Description: Spawns back any mob or item spawn point registered in the room you're standing in right now that's genuinely missing -- confirmed to only spawn what's actually absent, never a duplicate of something already there. Checks this ROOM specifically, not the whole area (unlike a mob spawn point's own automatic area-reset sweep -- see 'help spawnpoint').\n"
            "\n"
            "Useful right after clearing out a room by hand, or any time you don't want to wait for the next area reset. Reports exactly how many mobs and items were actually brought back; says so plainly if there was nothing missing to begin with.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-27"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "purge",
        "keywords": ["purge"],
        "title": "Purge",
        "body": (
            "Syntax: purge\n"
            "\n"
            "Description: (Staff only.) Deletes every mob, ground item, and corpse in the room you're currently standing in, all at once -- a quick way to clean up a test area or clear out clutter. Always targets your current room; no argument needed.\n"
            "\n"
            "Mobs removed this way still respawn normally later if they're a respawning template -- purge clears the room right now, it doesn't permanently depopulate it.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "say",
        "keywords": ["say"],
        "title": "Say",
        "body": (
            "Syntax: say <message>\n"
            "\n"
            "Description: Speaks a message aloud to everyone else in the room.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "ask",
        "keywords": ["ask"],
        "title": "Ask",
        "body": (
            "Syntax: ask <name> <topic>\n"
            "\n"
            "Description: Asks an NPC in the room about a topic -- some mobs (like a village Kage) respond to specific keywords such as 'promotion'.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "promotion",
        "keywords": ["promotion", "promote", "rank"],
        "title": "Promotion",
        "body": (
            "Syntax: ask <kage> about promotion\n"
            "\n"
            "Description: Ranks run Academy Student -> Genin -> Chunin -> Special Jonin -> Jonin -> Elite Jonin -> Village Elder -> Kage. Every character starts as an Academy Student, with full access to combat and missions from the very first moment -- Academy Student carries no gate of its own.\n"
            "\n"
            "Academy Student -> Genin isn't automatic and doesn't come from the Kage at all -- it's earned by finding a real teacher NPC (see 'help teacher') built with a mob program (see 'help programs') that promotes you when its own condition is met, the same way a village's own academy is set up. There's no fixed level or mission requirement for this specific step; it's entirely up to however that NPC is configured.\n"
            "\n"
            "Genin -> Chunin is earned by passing the Chunin Exam ('help exam'), not by asking the Kage.\n"
            "\n"
            "Every rank above Chunin is earned by asking your village's Kage about promotion while standing in their chamber, which checks your level and completed mission count against that rank's requirements:\n"
            "\n"
            "  Special Jonin: level 40, 50 completed missions\n"
            "  Jonin: level 60, 100 completed missions\n"
            "  Elite Jonin: level 80, 500 completed missions\n"
            "  Village Elder: level 95, 1000 completed missions\n"
            "\n"
            "Kage itself is never earned through a level/mission check -- it's appointed directly by staff (only one Kage per village at a time), and can also never be granted through a mob program's 'set_rank' action, specifically to protect that one-per-village rule.\n"
            "\n"
            "Every rank also carries its own headband, with a progressively larger Armor Class bonus -- promotion swaps it automatically, whichever of the paths above actually granted it.\n"
            "\n"
            "Every real rank change in the game -- Academy Student -> Genin via a teacher NPC, Genin -> Chunin via the exam, or any Kage-granted promotion -- announces itself to EVERY connected player, not just the one being promoted: \"[Name] has been promoted to [Rank]!\"\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "exam",
        "keywords": ["exam", "chunin exam", "forest of death"],
        "title": "Chunin Exam",
        "body": (
            "Syntax: exam\n"
            "\n"
            "Description: Enters the Forest of Death to attempt the Chunin Exam -- the only way to be promoted from Genin to Chunin. Requires at least level 10 and 25 completed missions, but is NOT level-capped beyond that minimum; a Genin who qualified a while ago can still take it at any time.\n"
            "\n"
            "On entry, you're given one of two scroll types (a Heaven Scroll or an Earth Scroll) at random. To pass, you need BOTH -- get the one you're missing by defeating one of the two scroll guardian mobs deep in the forest (each always drops one specific type) and looting its corpse, or by defeating ANOTHER exam candidate and taking theirs. Once you have both, reach the tower and 'submit' to complete the exam and be promoted on the spot, headband and all.\n"
            "\n"
            "Need a break? 'leave' takes you back to your village without forfeiting anything -- your scrolls and progress are kept, and 'exam' brings you right back to the entrance whenever you're ready to continue.\n"
            "\n"
            "Re-entering after leaving (e.g. a hospital respawn from a PvP loss) does not re-roll or top up a scroll you've already lost -- the exam is meant to be survived, not retried for free.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "submit",
        "keywords": ["submit", "submit scrolls"],
        "title": "Submit",
        "body": (
            "Syntax: submit\n"
            "\n"
            "Description: Completes the Chunin Exam -- must be standing at the tower in the Forest of Death, with both a Heaven Scroll and an Earth Scroll in hand. Consumes both scrolls and promotes you to Chunin immediately, headband included.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "leave",
        "keywords": ["leave", "leave exam"],
        "title": "Leave (Chunin Exam)",
        "body": (
            "Syntax: leave\n"
            "\n"
            "Description: Voluntarily exits the Forest of Death back to your village, without finishing or forfeiting the Chunin Exam. Any scrolls you've collected and your exam progress are unaffected -- 'exam' takes you right back to the entrance whenever you're ready to continue. Only works while actually in the exam.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "restore",
        "keywords": ["restore"],
        "title": "Restore",
        "body": "Syntax: restore\n\nDescription: Administrator/Implementor only. Fills HP, chakra, and stamina to each online player's own maximum, including players in editors. Does not change maximum stats, clear effects, stop combat, or edit offline saves.\n\nDate: 2026-09-20",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "respawn",
        "keywords": ["respawn"],
        "title": "Respawn",
        "body": "Syntax: respawn\n\nDescription: Administrator/Implementor only. Immediately restores missing registered mob populations throughout the MUD, plus pending timer respawns. Honors total population caps but bypasses per-period limits. Existing mobs (including wanderers within their area) are counted and left untouched. Uncapped populations use one mob per template per area; unassigned rooms are checked individually. Does not spawn unused prototypes or items, alter saved world data, or send area reset messages.\n\nDate: 2026-09-20",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "emotes",
        "keywords": ["emotes", "emojis", "emote", "socials"],
        "title": "Text Emotes",
        "body": (
            "Syntax: emotes  |  @<name>  |  ooc @<name>\n\n"
            "Description: Browse 80 cosmetic text emotes. Use @yawn to show "
            "your current room that you yawn, or ooc @yawn to show everyone "
            "online [OOC] followed by your character's name and action.\n\n"
            "Names are case-insensitive. Examples: @wave, @bow, @facepalm, "
            "@headband, ooc @laugh. No target or extra words are accepted.\n\n"
            "Silence and shared chat spam limits apply. OOC emotes are recorded "
            "in chatlog; room emotes are not. These actions do not change stats, "
            "combat, or the world.\n\n"
            "Date: 2026-09-19"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "ooc",
        "keywords": ["ooc"],
        "title": "OOC",
        "body": (
            "Syntax: ooc <message>\n"
            "\n"
            "Description: Sends a message on the server-wide out-of-character channel -- everyone online sees it, regardless of room or village.\n"
            "\n"
            "The last 25 OOC messages are saved -- see 'help chatlog' to review them.\n"
            "\n"
            "Filtered words are automatically censored. Sending too many messages too quickly (say/ooc/village chat combined) triggers an automatic 10-minute silence -- see 'help silence'.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "chatlog",
        "keywords": ["chatlog", "chat log"],
        "title": "Chatlog",
        "body": (
            "Syntax: chatlog\n"
            "\n"
            "Description: Shows the last 25 messages sent on the 'ooc' channel, oldest first. Persists across server restarts -- the log isn't lost when the server reboots.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "village",
        "keywords": ["village", "vchat", "vc"],
        "title": "Village Chat",
        "body": (
            "Syntax: village <message>  (aliases: vchat, vc)\n"
            "\n"
            "Description: Sends a message to everyone in your own village, regardless of which room they're in.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "kekkei genkai",
        "keywords": ["kekkei genkai", "kkg", "bloodline", "sharingan overview"],
        "title": "Kekkei Genkai",
        "body": (
            "Syntax: help kekkei genkai\n"
            "\n"
            "Description: A Kekkei Genkai is a rare bloodline ability, inherited (or not) at character creation based on which clan you were born into -- there's no way to earn one afterward, and no way to know for certain whether you have one until it's formally awakened. Most players don't have one at all, and that's by design: a character without a Kekkei Genkai is meant to stay every bit as viable as one with one.\n"
            "\n"
            "Awakening isn't something you trigger yourself, and there's no quest to accept or command to type for it -- once you're level 50 or higher, it can happen at any moment during real combat, entirely on its own. When it does, everyone connected sees a global announcement that someone's bloodline has awakened, though it never says whose or which one -- that part stays yours to discover, or keep to yourself. Once awakened, a Kekkei Genkai can develop further the more it's actually used, becoming sharper and more capable with real experience rather than all at once.\n"
            "\n"
            "&WThe Sharingan&x is the one Kekkei Genkai with real, playable abilities right now. Its core: an active toggle ('sharingan' -- see 'help sharingan' for the command itself) that sharpens your senses in combat at a small ongoing cost, growing more capable the more tomoe you carry. Broadly, across its full progression: better instincts for reading and avoiding attacks, sharper offense, resistance to being caught off guard by illusion techniques, a technique of its own to cast, and -- at its rarest -- the fleeting ability to read and turn an opponent's own technique back on them. Not every Sharingan is destined to develop the same way or reach the same heights; some simply have more room to grow than others.\n"
            "\n"
            "The other four known Kekkei Genkai (Byakugan, Shikotsumyaku, Ice Release, Hydrification) exist and can be inherited and awakened the same way, but don't have abilities built out yet.\n"
            "\n"
            "Staff: see 'help bloodstat' and 'help bloodset' for the tools to inspect and edit a player's hidden Kekkei Genkai state, and 'help awaken' for force-awakening one directly.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "sharingan",
        "keywords": ["sharingan", "shar", "tomoe"],
        "title": "Sharingan",
        "body": (
            "Syntax: sharingan  |  shar\n"
            "\n"
            "Description: Toggles the 1-tomoe Sharingan's first ability: reading an opponent's attacks well enough to dodge them, a real bonus on top of your normal dodge chance while it's active. Costs chakra and stamina every combat round it stays on, and a smaller amount of chakra even while you're not fighting -- having it active costs something at all times, more so mid-combat -- and turns itself off automatically if you can't afford the upkeep anymore, rather than draining you into the negatives. Costs nothing to toggle off. At 2 tomoe, the chakra cost drops -- the technique becomes less taxing with more eyes open; the dodge bonus itself doesn't change.\n"
            "\n"
            "The Sharingan can develop further with real use in combat -- up to 3 tomoe in each eye. Each stage brings its own new edge, sharper than the last. How quickly, and exactly what each one brings, isn't something you can see directly; toggling this command will always tell you how many tomoe you currently have, so you'll know the moment your eyes sharpen. Not every Sharingan is destined to reach the full 6 -- some eyes simply have more to give than others.\n"
            "\n"
            "Requires an awakened Sharingan with at least 1 tomoe. If you don't have one, this behaves like any other skill or jutsu you haven't learned. See 'help kekkei genkai' for the bigger picture of what a Kekkei Genkai is and how the Sharingan fits in.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "unleash beast",
        "keywords": ["unleash beast", "unleash"],
        "title": "Unleash Beast (staff)",
        "body": (
            "Syntax: unleash beast\n"
            "\n"
            "Description: (Staff only.) Releases a random Tailed Beast into the world -- picked from whichever of the 9 real beasts (Shukaku through Kurama) isn't currently sealed into some player, online or offline. A released beast spawns somewhere random (never in a safe room), roams on its own every 10-15 minutes, attacks any player it encounters, and despawns after 2 hours if nobody defeats or seals it. Announces globally which beast was released, so every player knows one is loose.\n"
            "\n"
            "Only one Tailed Beast can be loose in the world at a time -- refuses if a beast is already out there, and also refuses if every single beast is already held by a player.\n"
            "\n"
            "Date: 2026-09-06"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "sealing jutsu",
        "keywords": ["sealing jutsu", "jinchuriki"],
        "title": "Sealing Jutsu",
        "body": (
            "Syntax: perform sealing jutsu <beast name>\n"
            "\n"
            "Description: A level 100 technique, learned from a scroll, that seals a defeated Tailed Beast into you instead of letting it die. Only works once the beast has already been brought down through ordinary combat and is genuinely awaiting a final blow -- attacking it further does nothing once it's collapsed. You have exactly one real minute to seal it before it dies for good.\n"
            "\n"
            "Once sealed, you carry the beast permanently -- even through your own death -- until someone else defeats you in combat and knows the separate Release Jutsu. You can only ever hold one beast at a time.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "release jutsu",
        "keywords": ["release jutsu"],
        "title": "Release Jutsu",
        "body": (
            "Syntax: perform release jutsu <player name>\n"
            "\n"
            "Description: A level 100 technique, learned from a scroll, genuinely separate from Sealing Jutsu. Tears a Tailed Beast out of another player and releases it back into the world -- but only once you've already defeated that player in real combat. The beast spawns fresh, roaming and attackable again just like any other release.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "beastmode",
        "keywords": ["beastmode", "tailed beast mode"],
        "title": "Beastmode",
        "body": (
            "Syntax: beastmode\n"
            "\n"
            "Description: Toggles Tailed Beast Mode on and off, much like the Sharingan's own toggle. Only usable once you've mastered your sealed beast completely (100% mastery, earned slowly through real combat while carrying it). Grants a real, always-controlled boost to your damage, hit roll, and armor class -- no downside at all -- with the exact size scaling by which specific beast you hold: a stronger, higher-tailed beast grants noticeably more than a weaker one.\n"
            "\n"
            "Before reaching full mastery, carrying a beast carries real risk instead: a small, ever-present chance each combat round of losing control entirely in a rampage -- unable to act, auto-attacking everyone nearby, for several real minutes, though genuinely stronger while it lasts. That risk disappears entirely once your mastery is high enough.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "tailed beast bomb",
        "keywords": ["tailed beast bomb"],
        "title": "Tailed Beast Bomb",
        "body": (
            "Syntax: perform tailed beast bomb <target>\n"
            "\n"
            "Description: A devastating signature technique, usable only while Beastmode is active. Deals real, heavy damage scaled by which specific beast you carry -- a higher-tailed beast's Bomb hits noticeably harder. Works on a mob or another player. Has a real cooldown between casts.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "aff",
        "keywords": ["aff", "affects", "effects"],
        "title": "Aff",
        "body": (
            "Syntax: aff\n"
            "\n"
            "Description: Shows every status effect currently active on you (stunned, bleeding, confused, frightened, silenced, entangled, and so on) along with how many pulses each has left. Also shows if the Sharingan is currently toggled on. Same info 'score' already shows, without the rest of the score sheet around it.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "afk",
        "keywords": ["afk"],
        "title": "AFK",
        "body": (
            "Syntax: afk\n"
            "\n"
            "Description: Toggles your AFK (away from keyboard) status on or off.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "wimpy",
        "keywords": ["wimpy"],
        "title": "Wimpy",
        "body": (
            "Syntax: wimpy <0-100>\n"
            "\n"
            "Description: Sets an auto-flee threshold as a percentage of your max health -- once your health drops to or below it during a fight (PvE or PvP), you automatically attempt 'flee' on your own behalf. 0 disables it, the default. With no argument, shows your current setting instead of changing it.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "consider",
        "keywords": ["consider"],
        "title": "Consider",
        "body": (
            "Syntax: consider <mob>\n"
            "\n"
            "Description: Gauges how dangerous a mob would be to fight, based on the level gap between it and you -- a quick, cheap check before committing to 'attack', not a full combat simulation. Mobs only; a player's level/rank is already visible via 'who' or 'look' for a PvP read.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "weather",
        "keywords": ["weather", "time of day", "day", "night"],
        "title": "Weather",
        "body": (
            "Syntax: weather\n"
            "\n"
            "Description: Reports the current world-wide weather (clear/rain/storm/snow/fog) and time of day (day/night). Both change periodically on their own schedule, not per-room.\n"
            "\n"
            "These aren't just flavor text: Rain/Storm improve the odds at every gathering job (Fishing/Mining/Lumberjack/Farming/Cooking); Snow worsens them; Storm/Fog reduce combat accuracy for everyone, player and mob alike; and Night gives players a small Dodge Chance boost.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "auction",
        "keywords": ["auction", "auction house", "ah"],
        "title": "Auction",
        "body": (
            "Syntax: auction list  |  auction sell <item> <starting bid> [buyout price] [duration minutes]  |  auction bid <id> <amount>  |  auction buyout <id>  |  auction cancel <id>\n"
            "\n"
            "Description: The Auction House -- list an item from your inventory for other players to bid on, with an optional instant buyout price. Duration defaults to 1 hour (5 minutes to 24 hours if given). A 5% fee is taken from a successful sale. You can only have one active listing at a time -- sell, buyout, or cancel it before starting another.\n"
            "\n"
            "'auction cancel' only works before anyone's bid -- once a bid is in, that bidder is owed a fair shot at winning it. Bids aren't held in escrow: a bid is a promise, checked again for real ryo when the listing actually closes, so spending that ryo elsewhere before then can cost you the win. Works whether you're online or offline when a listing resolves -- you'll see the result waiting for you either way.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "area",
        "keywords": ["area", "areas", "vnum reservation"],
        "title": "Area",
        "body": (
            "Syntax: area create <name> [size]  |  area set <name> income <n>  |  area set <name> resetmsg <text|off>  |  area list\n"
            "\n"
            "Description: (Staff only.) Reserves a contiguous block of room vnums for a named area -- 1000 by default -- so builders working on different areas can't accidentally collide with each other's rooms. 'area create' auto-allocates the next free block; 'area list' shows every reservation, who created it, and its territory income if set.\n"
            "\n"
            "'area set <name> income <n>' sets the area's per-tick territory income (see 'help territory') -- an area with income set and at least one room flagged CapturePoint (see 'help flags') becomes real, ownable war/territory content, no other setup needed. Use 'astat <name>' to see an area's full details, including how many of its rooms are actually built and which are capture points.\n"
            "\n"
            "'area set <name> resetmsg <text|off>' sets (or clears) an area-wide atmospheric flavor line -- shown to every player standing anywhere within the area every 15 minutes, on a fixed timer (e.g. 'A soft breeze blows through the village.'). A specific room's own override (see 'help rset', 'rset resetmsg') always wins over the area's message if both are set. Every area reset also sweeps that area's own registered mob spawn points (see 'help spawnpoint') and respawns any that are missing -- checked across the WHOLE area, not just a mob's own spawn room, so a mob that's simply wandered elsewhere in the area is correctly left alone rather than duplicated. See 'help aset' for a shorter way to run 'area set'.\n"
            "\n"
            "Room-vnums only, not mobs/objects -- this project has always used separate numbering spaces for those. 'rset create <vnum>' notes if the vnum you pick falls outside every registered area, or inside one reserved by someone else, but doesn't block you either way -- it's a heads-up, not a hard limit.\n"
            "\n"
            "Each of the 5 villages has its own core area (named leaf/stone/water/cloud/sand), covering its original 100-vnum block, PLUS a separate, genuinely-1000-vnum '<village>-expansion' area (e.g. leaf-expansion) for new building -- the core blocks sit packed too tightly against each other to widen in place without relocating already-built rooms, so the expansion areas are where new village content should actually go. Everything else pre-existing (Main Street, apartment/shop expansions) lives in legacy-world/legacy-expansions instead.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "aset",
        "keywords": ["aset"],
        "title": "Aset",
        "body": (
            "Syntax: aset income <n>  |  aset resetmsg <text|off>  |  aset <name> income <n>  |  aset <name> resetmsg <text|off>\n"
            "\n"
            "Description: (Staff only.) Shorthand for 'area set' (see 'help area') -- same command, same validation, same everything, just shorter to type.\n"
            "\n"
            "Leave the area name out and it uses whichever area contains the room you're currently standing in -- 'aset income 25' from anywhere inside Leaf sets Leaf's own income, with no need to type 'leaf' at all. Give an explicit name instead (e.g. 'aset stone income 15') to edit a DIFFERENT area than the one you're standing in. If you're not currently inside any registered area at all and leave the name out, it'll tell you so and ask for an explicit name instead of guessing.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "astat",
        "keywords": ["astat"],
        "title": "Astat (staff)",
        "body": (
            "Syntax: astat [name or vnum]\n"
            "\n"
            "Description: Shows an area's full stat block -- by exact name, by a vnum (finds whichever area's reserved range contains it), or with no argument, the area containing the room you're standing in.\n"
            "\n"
            "Shows the reserved vnum range and size, the creator, how many of those vnums actually have a real room built yet, and (if set) the area's territory income, which of its rooms are currently flagged as capture points, and its reset message (see 'help area').\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "shop",
        "keywords": ["shop", "player shop", "main street"],
        "title": "Shop",
        "body": (
            "Syntax: buy shop  |  give <item> <shopkeeper>  |  price <item> <amount>  |  shop  |  shop name <text>  |  shop desc <text>  |  sell shop\n"
            "\n"
            "Description: Player shops -- one per player, along Main Street (5 rooms north of the Hokage's Kage Chamber, with a shop slot east and west of each). Costs 1,000,000 ryo to claim. Meant for anyone leveling a job (Cooking, Farming, Weaponsmith, etc.) to actually sell what they produce.\n"
            "\n"
            "Give an item to your own shopkeeper, then set its price -- other players can then 'buy' it there like any other shop. Capped at 20 items in stock at once (the same item can appear more than once; each is a separate sale). 'shop name'/'shop desc' work only while standing inside your own shop, same as an apartment.\n"
            "\n"
            "'sell shop' closes it down: every unsold item is returned to your inventory if there's room, or dropped on the shop's floor otherwise, and the room becomes vacant again for someone else to claim. No refund of the purchase price.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "price",
        "keywords": ["price"],
        "title": "Price",
        "body": (
            "Syntax: price <item> <amount>\n"
            "\n"
            "Description: Sets the sell price for an item already given to your own shopkeeper (see 'help shop'). If you've given more than one of the same item and none of them have a price yet, this sets all of them at once.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "combat",
        "keywords": ["combat", "fighting"],
        "title": "Combat",
        "body": (
            "Syntax: attack <target>  |  <jutsu name> <target>  |  perform <jutsu name> <target>\n"
            "\n"
            "Description: Combat can be a normal weapon attack ('attack', or an unarmed strike with none wielded) or a jutsu (see 'help classes'). Once you're fighting, your character keeps swinging automatically every round without needing the command repeated.\n"
            "\n"
            "Your own Strength and Damage Roll (plus your wielded weapon's own damage and Damage Roll bonus) all genuinely increase how hard you hit, on both regular attacks and jutsu alike.\n"
            "\n"
            "Casting a Ninjutsu or Genjutsu jutsu involves a real hand-sign delay before it lands (see 'help handsigns') -- if this is what starts the fight, combat doesn't actually begin until the jutsu resolves, hit or miss. Once you're already fighting, though, your ordinary attacks keep landing normally the whole time a jutsu is forming -- the jutsu just lands separately on top once it resolves.\n"
            "\n"
            "Being defeated in normal combat costs real experience and ryo, and sends you to your village hospital to recover -- a 'duel' (see 'help duel') is the one exception, costing nothing at all either way.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "attack",
        "keywords": ["attack", "kill"],
        "title": "Attack",
        "body": (
            "Syntax: attack <target>  (alias: kill)\n"
            "\n"
            "Description: Starts a fight with a mob in the room, or (if 'group' or PvP is set up) with another player. Once combat starts, your basic attack resolves automatically every pulse until the fight ends -- you don't need to re-type it each round. The verb shown (slash/stab/punch/etc.) matches whatever you're wielding. See 'help combatstats' for how Hit Roll, Armor Class, Dodge, and Critical Chance factor into each swing.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "flee",
        "keywords": ["flee", "run", "escape"],
        "title": "Flee",
        "body": (
            "Syntax: flee\n"
            "\n"
            "Description: Attempts to escape an ongoing fight (PvE or PvP), flavored as using the Body Replacement Technique (Kawarimi) -- the classic Naruto substitution jutsu -- to slip away rather than a generic 'you run.' Not guaranteed: there's a real chance the technique fumbles and the fight continues, costing you that round. On success, moves you to a random valid exit from the room (a closed door still blocks it, same as normal movement) and ends the fight -- in PvP, your opponent is notified and released from the fight too.\n"
            "\n"
            "&D(This is the low-level version -- a flat chance, no stat scaling. A higher-tier technique that flees AND lands a free attack on the way out is planned as a later addition.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "track",
        "keywords": ["track", "tracking"],
        "title": "Track",
        "body": (
            "Syntax: perform track <mob or player name>\n"
            "\n"
            "Description: A scroll-taught technique (learn it from a Track Scroll) that picks up a trail and follows it automatically. Name any mob or player anywhere in the world -- you don't need to be near them -- and your character will walk itself, one room per pulse, toward wherever they currently are.\n"
            "\n"
            "Tracking is scoped to the target's own area -- it won't path across the whole map, only within the region they're actually in. It respects closed and locked doors just like normal movement. It runs quietly in the background, so you can keep doing other things while it walks you there, but it automatically pauses the instant you're in a fight (PvE or PvP) and picks back up the moment that fight ends.\n"
            "\n"
            "It costs a small amount of chakra every pulse it's active, and stops on its own if you run out. It also ends cleanly -- with a message telling you so -- the moment the trail goes cold: your target logs off, dies, leaves their own area, or you simply arrive.\n"
            "\n"
            "Date: 2026-09-03"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "summon",
        "keywords": ["summon", "summoning", "contract"],
        "title": "Summoning Contracts",
        "body": (
            "Syntax: (find and sign a summoning contract at its own hidden hideout, then use that family's own jutsu to summon)\n"
            "\n"
            "Description: Five real summoning contracts exist -- Toad, Snake, Slug, Ninken, and Monkey -- each tied to its own secret hideout somewhere in the world. Signing a contract unlocks a whole progressive ladder of summons from that family, not just one fixed creature: the summon you actually get scales with your own level, from a modest starting form at level 20 up to that family's own strongest, named summon much later.\n"
            "\n"
            "A summon's real strength is your own current level multiplied by that specific tier's own power -- so the same contract gets meaningfully stronger as you level, without needing to re-sign anything. Only one summon can ever be active at a time; summoning a new one dismisses whatever was already out.\n"
            "\n"
            "Every contract's strongest tier has its own genuinely unique battle role, not just bigger numbers -- some heal you, some trap or bind an enemy, one can save you from a killing blow, and one doesn't fight at all but makes your own attacks hit harder instead. Discovering exactly what each family's top tier does is part of the fun.\n"
            "\n"
            "Date: 2026-09-03"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "yes",
        "keywords": ["yes"],
        "title": "Yes",
        "body": (
            "Syntax: yes\n"
            "\n"
            "Description: A direct answer to a real, active choice in front of you right now. Outside of that specific moment, this does nothing.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "no",
        "keywords": ["no"],
        "title": "No",
        "body": (
            "Syntax: no\n"
            "\n"
            "Description: A direct answer to a real, active choice in front of you right now. Outside of that specific moment, this does nothing.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "release",
        "keywords": ["release"],
        "title": "Release",
        "body": (
            "Syntax: release <player>\n"
            "\n"
            "Description: Ends your own active Illusion Walk genjutsu on someone early. This is the only way it ever ends besides running its own course (see 'help illusion walk') -- only the person who actually cast it on them can release it.\n"
            "\n"
            "Date: 2026-09-04"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "illusion walk",
        "keywords": ["illusion walk", "illusion"],
        "title": "Illusion Walk",
        "body": (
            "Syntax: perform illusion walk <player>\n"
            "\n"
            "Description: A Genjutsu technique that traps someone in an illusion of endless walking -- they keep seeing new surroundings every time they try to move, but never actually go anywhere at all. Works on another player only, in your own room.\n"
            "\n"
            "Every step the victim takes -- including the moment the illusion slips -- costs them half their current stamina, so it drains fast the longer they wander (2000 becomes 1000, then 500, then 250, and so on). If it drops to 10 or below, sheer exhaustion shatters the illusion outright and they can see and act normally again immediately.\n"
            "\n"
            "The higher your own mastery of this technique, the longer the victim can wander before the illusion slips and shows them their real surroundings again -- though that moment doesn't end the genjutsu itself. If they try to move again, the illusion starts fooling them right back. While genuinely trapped -- in any fake room, or even the room they started in -- the victim can't see or attack anyone real at all, you included, even though everyone else can still see and attack them completely normally. The only way it truly ends (short of exhaustion) is if you release them yourself (see 'help release').\n"
            "\n"
            "A defender with strong enough genjutsu resistance sees through this completely and can't be caught by it at all.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "silent genjutsu",
        "keywords": ["silent genjutsu", "silent"],
        "title": "Silent Genjutsu",
        "body": (
            "Syntax: (a passive skill -- learned automatically at level 75, never used directly)\n"
            "\n"
            "Description: Once learned, every Genjutsu you already know can be cast by its bare name alone, with no 'perform' needed, and lands instantly with no hand-sign delay at all -- this works whether you're casting on a mob or another player.\n"
            "\n"
            "At full (100%) mastery of this skill specifically, casting on another player stops showing them any sign a jutsu was used at all -- no name, no cast message, nothing beyond the real effect actually landing (the damage, the fear, whatever the technique does). You yourself always see your own full, normal cast message regardless of your mastery level.\n"
            "\n"
            "Date: 2026-09-05"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "perform",
        "keywords": ["perform", "per"],
        "title": "Perform",
        "body": (
            "Syntax: perform <jutsu name> <target>  (alias: per)\n"
            "\n"
            "Description: Uses a Ninjutsu or Genjutsu technique on a target -- these classes require the deliberate 'perform' command rather than a bare jutsu name. Taijutsu and Bukijutsu jutsu can instead be used by typing their name directly (e.g. 'dynamic entry <target>'). Works against another player too, not just mobs -- same targeting rules as 'attack' (a PvP-safe room blocks it, an already-defeated player can't be targeted).\n"
            "\n"
            "Ninjutsu and Genjutsu specifically involve forming hand signs first (see 'help handsigns') -- there's a real delay before the technique actually goes off, but your ordinary attacks keep landing normally the whole time, and the jutsu lands separately on top once it resolves. If this is what starts the fight (you weren't already fighting anything), combat doesn't actually begin until the jutsu itself resolves -- hit or miss -- not the instant you give the command.\n"
            "\n"
            "Jutsu damage scales with your own Strength and Damage Roll, plus your wielded weapon's own damage and Damage Roll bonus -- the same things that make a regular weapon attack hit harder also make your jutsu hit harder.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "handsigns",
        "keywords": ["handsigns", "hand signs", "hand sign"],
        "title": "Handsigns",
        "body": (
            "Syntax: (no command of its own -- happens automatically when you 'perform' a Ninjutsu or Genjutsu technique)\n"
            "\n"
            "Description: Every Ninjutsu and Genjutsu technique requires forming a fixed sequence of hand signs before it actually goes off -- Taijutsu and Bukijutsu never do. The exact signs are specific to each jutsu, always the same sequence, and shown to EVERYONE in the room as you perform them, not just to you.\n"
            "\n"
            "Forming the signs takes real time -- a genuine delay before the jutsu resolves. You can't start a different jutsu or move away during that time, but your ordinary attacks keep landing normally the whole while, and the jutsu lands separately on top once it resolves. Handsigns mastery shortens the delay considerably, from a few seconds down to under one at full mastery.\n"
            "\n"
            "Handsigns itself is granted automatically at level 20, regardless of your class. It's notoriously difficult to train directly -- practice can only ever bring it to 1%. Past that, the only way to improve it is landing real hits with hand-sign jutsu in actual combat.\n"
            "\n"
            "Since everyone in the room can see your hand signs, a sharp opponent can try to counter your jutsu with one of their own -- see 'help counter jutsu'.\n"
            "\n"
            "Date: 2026-08-27"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "counter jutsu",
        "keywords": ["counter jutsu", "counter-jutsu", "countering", "elemental collision", "overpower"],
        "title": "Counter Jutsu",
        "body": (
            "Syntax: (no command of its own -- happens automatically when two opposing-element jutsu collide)\n"
            "\n"
            "Description: If you and another player are both mid-cast at each other in the same room, and your hand signs finish within about a second of theirs, the two jutsu can collide in mid-air -- but only if your elements genuinely oppose each other, following a fixed cycle: Water beats Fire, Fire beats Wind, Wind beats Lightning, Lightning beats Earth, and Earth beats Water. Same-element jutsu never collide this way, no matter how close the timing.\n"
            "\n"
            "A genuine collision cancels BOTH jutsu outright -- neither lands its usual damage or effect on its target. Instead, the clash leaves a real, temporary mark on the room itself (a burst of steam for Water and Fire, churned mud for Earth and Water, and so on), visible to anyone who looks, until it fades on its own after about a minute.\n"
            "\n"
            "The elementally favored side isn't guaranteed a clean win, though: level and mastery both count. If the favored side's combined level-plus-mastery is at least 30 points higher than the other side's, its jutsu overpowers instead of just cancelling -- it still lands on its target, but at a genuinely reduced strength, since it had to punch through the clash to get there. The overpowered side's own jutsu still does nothing either way.\n"
            "\n"
            "This works in PvP only, between two players' own casts.\n"
            "\n"
            "Date: 2026-08-27"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "elements",
        "keywords": ["elements", "element", "chakra nature"],
        "title": "Elements",
        "body": (
            "Syntax: help <element name>  (e.g. help fire)\n"
            "\n"
            "Description: Your own chakra nature is secretly decided the moment your character is created, and only revealed by channeling a Chakra Paper (see 'help channel'). There are five real elements: Fire, Water, Wind, Earth, and Lightning.\n"
            "\n"
            "A jutsu carrying a real element (see each element's own helpfile for its jutsu) can ONLY be cast if that element genuinely matches your own chakra nature -- primary or secondary (see 'help channel' for the level 100 second reveal). There's no casting a jutsu outside your own element, at any effectiveness.\n"
            "\n"
            "The room you're standing in also matters: certain biomes boost or weaken certain elements' damage (a desert boosts Fire and Wind but weakens Water, for instance) -- see each element's own helpfile for which biomes favor it.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "fire",
        "keywords": ["fire"],
        "title": "Fire",
        "body": (
            "Syntax: (no command of its own -- a personal trait revealed by channeling a Chakra Paper, see 'help channel')\n"
            "\n"
            "Description: One of the five chakra natures (see 'help elements'). Fireball Jutsu (Ninjutsu, level 20) requires Fire to cast at all, and carries a real chance to set the target Burning -- steady HP damage each round for a few rounds.\n"
            "\n"
            "Boosted in desert biomes. Weakened near open water (ocean, river, lake).\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "water",
        "keywords": ["water"],
        "title": "Water",
        "body": (
            "Syntax: (no command of its own -- a personal trait revealed by channeling a Chakra Paper, see 'help channel')\n"
            "\n"
            "Description: One of the five chakra natures (see 'help elements'). Water Dragon Jutsu (Ninjutsu, level 20) requires Water to cast at all, and carries a real chance to inflict Drained -- steadily sapping the target's own chakra each round for a few rounds.\n"
            "\n"
            "Boosted near open water (ocean, river, lake) and in swamps. Weakened in the desert.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "wind",
        "keywords": ["wind"],
        "title": "Wind",
        "body": (
            "Syntax: (no command of its own -- a personal trait revealed by channeling a Chakra Paper, see 'help channel')\n"
            "\n"
            "Description: One of the five chakra natures (see 'help elements'). Wind Blade Jutsu (Ninjutsu, level 20) requires Wind to cast at all, and carries a real chance to knock the target Off Balance -- steadily draining their own stamina each round for a few rounds.\n"
            "\n"
            "Boosted in forests and deserts. Weakened in the mountains.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "earth",
        "keywords": ["earth"],
        "title": "Earth",
        "body": (
            "Syntax: (no command of its own -- a personal trait revealed by channeling a Chakra Paper, see 'help channel')\n"
            "\n"
            "Description: One of the five chakra natures (see 'help elements'). Earth Wall Crusher (Ninjutsu, level 20) requires Earth to cast at all. Unlike the other four elements, Earth carries no lingering status effect -- instead, it just hits noticeably harder up front than any of the others.\n"
            "\n"
            "Boosted in forests, mountains, and swamps.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "lightning",
        "keywords": ["lightning"],
        "title": "Lightning",
        "body": (
            "Syntax: (no command of its own -- a personal trait revealed by channeling a Chakra Paper, see 'help channel')\n"
            "\n"
            "Description: One of the five chakra natures (see 'help elements'). Lightning Strike Jutsu (Ninjutsu, level 20) requires Lightning to cast at all, and carries a real (if rarer) chance to Paralyze the target -- completely unable to act for their next couple of rounds.\n"
            "\n"
            "Boosted in the mountains. Weakened in swamps.\n"
            "\n"
            "Date: 2026-08-26"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "score",
        "keywords": ["score", "sc"],
        "title": "Score",
        "body": (
            "Syntax: score  (alias: sc)\n"
            "\n"
            "Description: Shows your full character sheet: identity, combat stats, attributes, and mission info. See 'help scoresheet', 'help attributes', and 'help combatstats' for what each field means.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "skills",
        "keywords": ["skills"],
        "title": "Skills",
        "body": (
            "Syntax: skills\n"
            "\n"
            "Description: Lists every jutsu and passive skill you know, ordered by the level you unlocked it at (lowest first), each colored by its class (Ninjutsu, Taijutsu, Genjutsu, Bukijutsu, or General Skills). Doesn't show proficiency -- see 'prac' for that.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "taijutsu stances",
        "keywords": ["taijutsu stances", "kihon dachi", "neko ashi dachi", "sanchin dachi"],
        "title": "Taijutsu Stances",
        "body": (
            "Syntax: kihon dachi | neko ashi dachi | sanchin dachi\n\n"
            "Description: Taijutsu class unlocks Kihon Dachi at level 5 (+2 damage roll, -2 AC), "
            "Neko Ashi Dachi at level 15 (+2 hit roll, -4 AC), and Sanchin Dachi at level 30 "
            "(+4 damage roll). Only one stance can be active. Change or leave a stance outside "
            "combat; using the active stance again returns to normal. Activation costs stamina. "
            "Your stance remains active across reconnects. See 'aff' or 'score'.\n\nDate: 2026-09-26"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "taijutsu strikes",
        "keywords": ["taijutsu strikes", "choku zuki", "mae geri", "oi zuki", "sokuto", "kumade", "tamashiwara"],
        "title": "Taijutsu Strikes",
        "body": (
            "Syntax: <technique> [target]\n\n"
            "Description: Taijutsu unlocks Choku Zuki (level 3), Mae Geri (5), Oi Zuki (10), "
            "Sokuto (15), Kumade (25), and Tamashiwara (35). Type the technique "
            "name directly, with a target or during combat. Kumade may blind the target "
            "and reduce accuracy; Tamashiwara may cause bleeding. Each costs stamina.\n\nDate: 2026-09-26"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "ushiro shishou",
        "keywords": ["ushiro shishou", "ushiro"],
        "title": "Ushiro Shishou",
        "body": (
            "Syntax: perform ushiro shishou <target>\n\n"
            "Description: A level 30 Ninjutsu opening strike. Sneak up on an unhurt target before "
            "combat starts for increased damage. It costs chakra and cannot be used "
            "mid-fight or against an already hurt target.\n\nDate: 2026-09-26"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "inventory",
        "keywords": ["inventory", "i"],
        "title": "Inventory",
        "body": (
            "Syntax: inventory  (alias: i)\n"
            "\n"
            "Description: Lists everything you're carrying. Items with the same name stack into one line (up to 64 per stack, 20 distinct stacks total) rather than listing each copy separately.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "equipment",
        "keywords": ["equipment", "eq"],
        "title": "Equipment",
        "body": (
            "Syntax: equipment  (alias: eq)\n"
            "\n"
            "Description: Shows every wear location, including empty slots, along with what you currently have worn, wielded, and held.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "prompt",
        "keywords": ["prompt"],
        "title": "Prompt",
        "body": (
            "Syntax: prompt [format string]\n"
            "\n"
            "Description: Shows or changes your combat prompt format (the HP/Chakra/Stamina/XP/Ryo line shown after most commands). With no argument, shows your current format.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "config",
        "keywords": ["config"],
        "title": "Config",
        "body": (
            "Syntax: config [setting] [on|off]\n"
            "\n"
            "Description: Shows or changes your personal settings, such as auto-looting ryo/gear from corpses, auto-sacrificing them, or the periodic tip-of-the-day broadcast. Run 'config' alone to see every available setting and its current state. Every setting defaults on for a brand-new character, and is reset back on for every character at the start of every server session -- you can still turn any of them off yourself any time, it just isn't remembered as your starting state across a restart.\n"
            "\n"
            "Staff have their own, separate set -- see 'help staffconfig'.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "staffconfig",
        "keywords": ["staffconfig", "staff config"],
        "title": "Staffconfig (staff)",
        "body": (
            "Syntax: staffconfig [setting] [on|off]\n"
            "\n"
            "Description: Staff's own, separate set of personal settings -- distinct from the regular 'config' every player has. Covers staff-specific display/notification preferences: whether you get a live ping when a player submits a bug report, and whether you see vnums -- room headers, and any mob or item wherever it's listed (a room, your own inventory). Both default on. Run 'staffconfig' alone to see every setting and its current state.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "password",
        "keywords": ["password"],
        "title": "Password",
        "body": (
            "Syntax: password <old> <new>\n"
            "\n"
            "Description: Changes your account password.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "commands",
        "keywords": ["commands"],
        "title": "Commands",
        "body": (
            "Syntax: commands\n"
            "\n"
            "Description: Lists every command verb the game recognizes, player and staff commands together, in one combined list.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "who",
        "keywords": ["who"],
        "title": "Who",
        "body": (
            "Syntax: who\n"
            "\n"
            "Description: Lists everyone currently online in one flat list, with village, rank, level, and clan shown for each.\n"
            "\n"
            "Date: 2026-09-08"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "whois",
        "keywords": ["whois"],
        "title": "Whois",
        "body": (
            "Syntax: whois <player name>\n"
            "\n"
            "Description: Shows an online player's description plus basic info -- village, level, class, rank, and clan. Works server-wide, unlike 'look', which only shows a description for a player standing in the same room as you.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "wear",
        "keywords": ["wear"],
        "title": "Wear",
        "body": (
            "Syntax: wear <item>  |  wear all\n"
            "\n"
            "Description: Equips armor or a weapon from your inventory into its own slot. 'wear kunai' wields the kunai, just like 'wield kunai'. Use 'hold' for tools. 'wear all' equips armor, weapons, and tools into their own free slots, skipping any occupied slot.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "wield",
        "keywords": ["wield"],
        "title": "Wield",
        "body": (
            "Syntax: wield <item>\n"
            "\n"
            "Description: Equips a weapon from your inventory. Only accepts an actual weapon -- armor or a tool is refused here (see 'wear'/'hold' instead). Swapping weapons automatically unequips whatever was wielded before. The first time you wield a weapon of a given type, you automatically learn its weapon skill (see 'prac').\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "hold",
        "keywords": ["hold"],
        "title": "Hold",
        "body": (
            "Syntax: hold <item>\n"
            "\n"
            "Description: Equips a tool -- a fishing rod, pickaxe, axe, hoe, or cooking pot -- in its own slot, separate from your wielded weapon and worn armor, so you can hold a tool and still fight with your weapon equipped. Only accepts an actual tool -- armor or a weapon is refused here (see 'wear'/'wield' instead).\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "remove",
        "keywords": ["remove"],
        "title": "Remove",
        "body": (
            "Syntax: remove <item>  |  remove all\n"
            "\n"
            "Description: Unequips a worn or wielded item back into your inventory. 'remove all' unequips everything at once -- if inventory fills up partway through, whatever's left stays equipped rather than being lost.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "examine",
        "keywords": ["examine"],
        "title": "Examine",
        "body": (
            "Syntax: examine <item>\n"
            "\n"
            "Description: Inspects an item closely. Requires Examine (unlocked at character level 20) -- how much detail you see scales with your Examine proficiency, from just its rarity at low proficiency up to full set bonus details at 80%+. At 40%+, shows the item's type, its real wear location, and a full stat breakdown -- every category (Armor Class, Hitroll, Damroll, Max Health/Chakra/Stamina, and each attribute) on its own line, never hidden in the item's own name or description.\n"
            "\n"
            "Date: 2026-08-27"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "give",
        "keywords": ["give"],
        "title": "Give",
        "body": (
            "Syntax: give <item> <player>\n"
            "\n"
            "Description: Hands an item from your inventory to another player in the same room. Refuses if their inventory has no room for it.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "drop",
        "keywords": ["drop", "drop.all"],
        "title": "Drop",
        "body": (
            "Syntax: drop <item>  |  drop all  |  drop.all\n"
            "\n"
            "Description: Drops an item (or your entire inventory) on the ground in the current room. Dropped items can be picked back up with 'get', by you or anyone else who finds them.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "get",
        "keywords": ["get"],
        "title": "Get",
        "body": (
            "Syntax: get <item>  |  get <item> from <container>\n"
            "\n"
            "Description: Picks up an item lying on the ground in the current room, subject to the same inventory stacking limits as everything else. A small number of items -- cosmetic room decoration like furniture, signs, or plants -- are flagged not to be picked up at all (see 'help flags', the 'no_take' item flag) and will refuse instead.\n"
            "\n"
            "'get <item> from <container>' instead takes an item OUT of a real container (a backpack or anything else set up with a real capacity via 'oset <vnum> concap <n>') and back into your ordinary inventory -- see 'help put' and 'help containers'.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "put",
        "keywords": ["put", "backpack", "container", "containers"],
        "title": "Put (containers)",
        "body": (
            "Syntax: put <item> in <container>  |  get <item> from <container>\n"
            "\n"
            "Description: A real container item -- a backpack, or anything else a builder has set up this way -- has its own real, separate storage capacity, entirely apart from your normal 20-slot inventory. Items sitting inside a container don't count against that limit at all. 'put' moves an item from your ordinary inventory into a container you're carrying; 'get <item> from <container>' moves it back out. A container doesn't need to be worn to be used -- carrying it anywhere in your inventory is enough; wearing one (in the 'back' slot, if it has a real wear_loc set) is purely cosmetic.\n"
            "\n"
            "If you're carrying more than one container with the exact same name, use the same real 'N.keyword' targeting every other command in the game supports -- 'put kunai in 2.backpack' means the SECOND backpack, not the first. Two identically-named containers never share contents; each one's own real, separate storage is tracked independently, no matter how many you're carrying.\n"
            "\n"
            "A container that's genuinely full refuses further items until something's taken back out. Staff sets a real item's own container capacity with 'oset <vnum> concap <n>' -- 0 (the default) means that item isn't a container at all; any positive number makes it one, holding up to that many items.\n"
            "\n"
            "Date: 2026-09-13"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "buy",
        "keywords": ["buy"],
        "title": "Buy",
        "body": (
            "Syntax: buy <item>\n"
            "\n"
            "Description: Purchases an item from a shopkeeper in the room. Your level must be at least the item's level; if it is too low, the purchase is refused without charging you. Use 'list' to see prices and item level requirements.\n"
            "\n"
            "'buy apartment' and 'buy room <type> <direction>' are special cases -- see 'help apartment' for details. At your own village's Kage chamber, 'buy' also purchases village-wide perks and legendary items from the Kage instead -- see 'help legendary items'.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "legendary items",
        "keywords": ["legendary items", "legendary item", "kage items"],
        "title": "Legendary Items",
        "body": (
            "Syntax: list  (at your own village's Kage chamber)  |  buy <item>\n"
            "\n"
            "Description: Every village's Kage sells legendary gear -- one-of-a-kind items with far larger stat bonuses than anything craftable, priced in a large number of mission points rather than ryo. Purchasable by ANY player who can afford it, not just the Kage themselves. Each is a single unique item -- once you own one, buying it again is refused (\"only one to a customer\"). Mostly armor, but at least one legendary weapon is in the lineup too -- 'list' shows the full, current selection, and some slots have more than one option worth comparing before you commit.\n"
            "\n"
            "Like anything else you wear, it goes on with 'wear' and comes back off with 'remove'. 'examine' shows its full stat breakdown (requires Examine, see 'help examine').\n"
            "\n"
            "Date: 2026-08-19"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "sell",
        "keywords": ["sell"],
        "title": "Sell",
        "body": (
            "Syntax: sell <item>\n"
            "\n"
            "Description: Sells an item from your inventory to a shopkeeper, if they buy that category of item.\n"
            "\n"
            "'sell apartment' and 'sell room <type>' are special cases -- see 'help apartment' for details.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "list",
        "keywords": ["list"],
        "title": "List",
        "body": (
            "Syntax: list\n"
            "\n"
            "Description: Shows what a shopkeeper in the room has for sale, with prices.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "eat",
        "keywords": ["eat"],
        "title": "Eat",
        "body": (
            "Syntax: eat <item>\n"
            "\n"
            "Description: Eats a food item for an immediate effect (typically restoring Stamina). Only accepts food-category items.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "drink",
        "keywords": ["drink"],
        "title": "Drink",
        "body": (
            "Syntax: drink <item>\n"
            "\n"
            "Description: Drinks a beverage item for an immediate effect (typically restoring Chakra). Only accepts drink-category items.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "use",
        "keywords": ["use"],
        "title": "Use",
        "body": (
            "Syntax: use <item>\n"
            "\n"
            "Description: Uses a medical item. Its configured Health, Chakra, and/or Stamina recovery arrives gradually over time, including during combat; status cures take effect on use. Only accepts medical-category items.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "read",
        "keywords": ["read", "study"],
        "title": "Read",
        "body": (
            "Syntax: read <scroll>  (alias: study)\n"
            "\n"
            "Description: Learns the jutsu inscribed on a scroll -- an alternate way to pick up a jutsu beyond your starting kit. The scroll is consumed on a successful read; it isn't consumed if it's blank or teaches something you already know.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "channel",
        "keywords": ["channel", "chakra paper"],
        "title": "Channel",
        "body": (
            "Syntax: channel <chakra paper>\n"
            "\n"
            "Description: Reveals your own chakra nature -- one of the five elements (Fire, Water, Wind, Earth, Lightning), secretly decided the moment your character was created and never shown to you before now. Requires level 50 -- below that, the paper simply doesn't react and is NOT consumed, so you can hold onto it and try again once you're ready. Once it does react, the paper is consumed.\n"
            "\n"
            "At level 100, a second Chakra Paper reveals a genuinely SECOND chakra nature -- a completely independent, freshly-rolled element, guaranteed different from your first but otherwise picked with no regard for whether the two make thematic sense together (fire and water can both be yours at once). You must have already revealed your first nature before the second can be revealed, even if you're already well past level 100.\n"
            "\n"
            "Once you've revealed everything there is to know, channeling further Chakra Paper does nothing at all and won't consume the sheet.\n"
            "\n"
            "A nature you've genuinely revealed shows up on your 'score' sheet from then on -- a handy way to check whether you've already discovered one (or both) before buying another paper. An unrevealed nature never appears there.\n"
            "\n"
            "Date: 2026-08-25"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "fish",
        "keywords": ["fish"],
        "title": "Fish",
        "body": (
            "Syntax: fish\n"
            "\n"
            "Description: Casts a line for the Fishing job. Needs a fishing rod held and a water biome (river/ocean/lake/swamp) to stand in. Costs 1-2 Stamina. Takes a few seconds to resolve. A held rod loses one use per attempt and breaks after 250 uses by default.\n"
            "\n"
            "There are 6 rods (Kindling, Birch, Oak, Ironwood, Masterwork Oak, Heartwood -- required levels 1/20/40/60/80/99), one for each Lumberjack log type. Every fish species has a full Common-through-Legendary tier ladder; your rod is built around a specific tier and shifts the odds sharply toward it, so a better rod always matters more than levels alone. Only the Heartwood rod gives a real (though still not guaranteed) shot at Legendary catches -- every other rod can land one, but it's nearly never.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "mine",
        "keywords": ["mine"],
        "title": "Mine",
        "body": (
            "Syntax: mine\n"
            "\n"
            "Description: Swings a pickaxe for the Mining job. Needs a pickaxe held and a mountain biome to stand in. Costs 1-2 Stamina and takes a few seconds. A held pickaxe loses one use per attempt and breaks after 250 uses by default.\n"
            "\n"
            "There are 6 pickaxes (Copper, Iron, Steel, Chakra Steel, Blacksteel, Diamond-Tipped -- required levels 1/20/40/60/80/99). Rock Salt, Copper, Tin, and Silver ore each have a full Common-through-Legendary tier ladder, built around your pickaxe's own tier -- a better pickaxe always matters more than levels alone, and only the Diamond-Tipped pickaxe gives a real (though still not guaranteed) shot at Legendary ore. Iron/Steel/Chakra Steel ore (see 'help smelt') and raw gems (feeding Weaponsmith/Armorsmith/Gemcutter) are still findable at their usual fixed rarity alongside the tiered ore.\n"
            "\n"
            "There's also a small, flat chance (the same no matter your pickaxe or job level) of a random bonus gem turning up alongside the normal find -- Quartz, Jade, Amber, Garnet, Amethyst, Topaz, Sapphire, Emerald, Ruby, or Diamond, each with its own color and rarity. Very rare across the board, especially the higher-rarity ones.\n"
            "\n"
            "Mining also raises your Max Stamina -- each Mining level adds its own level number, stacking cumulatively (Farming and Lumberjack contribute to the same Max Stamina pool too, so leveling more than one adds up together). See 'help farm' for the exact math.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "smelt",
        "keywords": ["smelt", "smelting"],
        "title": "Smelt",
        "body": (
            "Syntax: smelt <ore>\n"
            "\n"
            "Description: Converts a raw ore (from Mining) into its ingot -- An Iron Ore into An Iron Ingot, A Steel Ore into A Steel Ingot, A Chakra Steel Ore into A Chakra Steel Ingot. Gated by Mining level (1/20/50 respectively). The 20 tiered ore species (Rock Salt/Copper/Tin/Silver, Common through Legendary) are also smeltable, each tier into its own matching-tier ingot -- always level 1, since these aren't part of any level-gated crafting-chain progression, just flavor/sell value. Costs 1-2 Stamina and takes a real delay to resolve, but always succeeds once you meet the level requirement and still have the ore -- the randomness already happened when you found the ore in the first place. No tool or location required; works anywhere.\n"
            "\n"
            "Ingots are what every crafting recipe in the game (Weaponsmith, Armorsmith, and every job's own tool-crafting) actually uses -- smelting is simply how you turn what Mining finds into something craftable.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "chop",
        "keywords": ["chop"],
        "title": "Chop",
        "body": (
            "Syntax: chop\n"
            "\n"
            "Description: Swings an axe for the Lumberjack job. Needs an axe held and a forest biome to stand in. Costs 1-2 Stamina and takes a few seconds. A held axe loses one use per attempt and breaks after 250 uses by default.\n"
            "\n"
            "There are 6 axes (Copper, Iron, Steel, Chakra Steel, Blacksteel, Diamond-Edged -- required levels 1/20/40/60/80/99). Pine, Maple, Redwood, and Ebony wood each have a full Common-through-Legendary tier ladder, built around your axe's own tier -- a better axe always matters more than levels alone, and only the Diamond-Edged axe gives a real (though still not guaranteed) shot at Legendary wood. Kindling, Birch, Oak, Ironwood, Masterwork Oak, and Heartwood logs (feeding Fishing's own rod crafting) are still findable at their usual fixed rarity alongside the tiered wood.\n"
            "\n"
            "Lumberjack also raises your Max Stamina -- each Lumberjack level adds its own level number, stacking cumulatively (Farming and Mining contribute to the same Max Stamina pool too, so leveling more than one adds up together). See 'help farm' for the exact math.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "cook",
        "keywords": ["cook", "cooking"],
        "title": "Cook",
        "body": (
            "Syntax: cook <fish>\n"
            "\n"
            "Description: Cooks a raw fish into a dish for the Cooking job. Hold a Copper Cooking Pot, or stand in your own apartment kitchen to cook without one. Costs 1-2 Stamina and takes a few seconds. Meals can burn. Each pot used loses one use per attempt, even when a meal burns, and breaks after 250 uses by default. Cooking in your own kitchen without a pot uses no tool.\n"
            "\n"
            "Cooking also raises your Max Chakra -- each Cooking level adds its own level number, stacking cumulatively, same math as Farming uses for Max Stamina. See 'help farm' for the exact math.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "farm",
        "keywords": ["farm", "farming"],
        "title": "Farm",
        "body": (
            "Syntax: farm\n"
            "\n"
            "Description: Tends crops for the Farming job. Hold a Copper Hoe (VNUM 20802) with 'hold hoe' first; carrying it is not enough. Farm in a plains biome. Costs 1-2 Stamina and takes a few seconds; harvests can fail. The Copper Hoe is sold in general stores. Each attempt wears the hoe by one use; it breaks after 250 uses by default.\n"
            "\n"
            "Farming level unlocks eight crop types, from Carrot and Potato at level 1 through Pepper at level 80. Crops are standalone sellable goods.\n"
            "\n"
            "Farming also raises your Max Stamina -- each Farming level adds its own level number, stacking cumulatively (level 1 gives +1, level 2 adds +2 more for +3 total, level 3 adds +3 more for +6 total, and so on). At level 23 that's +276 Max Stamina total. Lumberjack and Mining raise Max Stamina the same way (all three stack into the same pool); Cooking, Weaponsmith, and Armorsmith raise Max Chakra the same way; Gemcutter raises Max Health at DOUBLE this rate -- see their own helpfiles.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "gemcut",
        "keywords": ["gemcut", "gemcutting"],
        "title": "Gemcut",
        "body": (
            "Syntax: gemcut <raw gem>\n\n"
            "Description: Hold a Copper Chisel (item VNUM 20803), then cut a Rough Quartz, Raw Sapphire, Raw Ruby, or Raw Diamond found while mining. Gemcutter levels 1, 25, 55, and 80 unlock them respectively. Quartz is Uncommon (+2 Hitroll and +2 Damageroll), Sapphire and Ruby are Epic (+5 each), and Diamond is Legendary (+8 each). The cut gems store these stats for future weapon upgrades; carrying them does not yet boost combat. Cutting costs 1-2 Stamina and takes a few seconds. Each completed cut wears the chisel by one use; it breaks after 250 uses by default. Other job tools wear on every completed attempt, including failed gathers and burned meals. Remaining uses appear in inventory and eq.\n"
            "\nDate: 2026-09-25"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "craft",
        "keywords": ["craft"],
        "title": "Craft",
        "body": (
            "Syntax: craft weapon <type> <name>\n"
            "       craft armor <slot> <name>\n"
            "\n"
            "Description: A real Bukijutsu skill -- unlocked at Bukijutsu level 25+, or any class at level 70+. Combines exactly 2 materials (see 'help materials') into a brand-new item you name yourself. Their own individual stat values simply add together: a weapon gets that combined number as both bonus Hit Roll and bonus Damage Roll; armor gets it as Armor Class (better defense).\n"
            "\n"
            "<type> is one of: kunai, sword, shuriken, blunt, polearm, exotic.\n"
            "<slot> is one of: head, body, legs, feet, hands, waist, finger, neck, piercing, back, chakra aura.\n"
            "\n"
            "After naming your item, you'll be asked which 2 materials to combine (e.g. 'iron ingot, yew log') -- the same material can be used twice for a weaker but simpler craft. Takes a short delay to resolve, and re-checks you still have both materials at that point.\n"
            "\n"
            "Date: 2026-09-07"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "materials",
        "keywords": ["materials", "crafting materials"],
        "title": "Crafting Materials",
        "body": (
            "Syntax: craft weapon <type> <name>  |  craft armor <slot> <name>\n"
            "\n"
            "Description: The 9 real materials usable with 'craft' (see 'help craft'), gathered via Mining and Lumberjack. Each has its own fixed stat value -- higher-tier materials give a stronger crafted item, and combining 2 strong materials gives the best results of all.\n"
            "\n"
            "Iron Ingot (5), Sturdy Oak Log (6), Ironwood Log (8), Steel Ingot (12), Masterwork Oak Log (14), Alloy Ingot (22), Ancient Heartwood Log (26), Yew Log (26), Chakra Steel Ingot (30) -- the strongest material overall.\n"
            "\n"
            "Date: 2026-09-07"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "pullweeds",
        "keywords": ["pullweeds"],
        "title": "Pull Weeds",
        "body": (
            "Syntax: pullweeds\n"
            "\n"
            "Description: Pulls a bundle of weeds from a villager's garden -- feeds the 'Weed the Garden' mission, but works even without that mission active. Needs a villager NPC in the room.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "deliver",
        "keywords": ["deliver"],
        "title": "Deliver",
        "body": (
            "Syntax: deliver\n"
            "\n"
            "Description: Hands over every bundle of weeds you're carrying to a villager NPC in the room, advancing the 'Weed the Garden' mission. Partial delivery across multiple trips works fine.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "missions",
        "keywords": ["missions"],
        "title": "Missions",
        "body": (
            "Syntax: missions\n"
            "\n"
            "Description: At a village Mission Board, lists every D-Rank mission posted there and whether you've already accepted it or it's on cooldown. Away from the board, shows your active mission journal and progress instead -- both D-Rank and any dynamic C-Rank+ mission you've requested. For C-Rank and above, see 'help request' -- those aren't posted on any board.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "accept",
        "keywords": ["accept"],
        "title": "Accept",
        "body": (
            "Syntax: accept <keyword>\n"
            "\n"
            "Description: At a village Mission Board, accepts a posted D-Rank mission matching the keyword (e.g. 'accept clear' or 'accept weed'). Refused if it's already active, still on cooldown from your last completion, or your level is below that mission's requirement. For C-Rank and above, see 'help request' instead -- those aren't posted on any board.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "request",
        "keywords": ["request", "request mission"],
        "title": "Request",
        "body": (
            "Syntax: request <c-rank|b-rank|a-rank|s-rank>\n"
            "\n"
            "Description: Requests a C-Rank, B-Rank, A-Rank, or S-Rank mission -- works from anywhere, no need to stand at a village board. Unlike D-Rank ('accept' at a village Mission Board, a fixed posted mission), these ranks are dynamic: a real mob is picked at random from every mob in the game flagged Mission (see 'help flags'), filtered to a level range relative to YOUR OWN current level -- a higher rank reaches for a much higher-level mob than a lower one does, so the same rank can mean something very different depending on how strong you already are. The pool is pulled from globally, not just your own village.\n"
            "\n"
            "Requires a minimum level to request each rank (C-Rank 10, B-Rank 25, A-Rank 50, S-Rank 80). Each rank has its own separate cooldown after requesting -- requesting one rank doesn't block requesting a different rank in the meantime. If no Mission-flagged mob exists at your current level for that rank, the request is refused rather than handing you an impossible or absurdly easy target.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "loot",
        "keywords": ["loot"],
        "title": "Loot",
        "body": (
            "Syntax: loot [corpse]\n"
            "\n"
            "Description: Takes the ryo and items off a corpse in the room. If your inventory can't fit everything, takes what it can and leaves the rest on the corpse.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "sacrifice",
        "keywords": ["sacrifice", "sac"],
        "title": "Sacrifice",
        "body": (
            "Syntax: sacrifice <corpse>  |  sacrifice <item>  |  sacrifice all  (alias: sac)\n"
            "\n"
            "Description: Destroys a corpse for a small flat ryo reward, regardless of what's still on it -- any un-looted ryo or items are forfeited, not transferred to you. Corpses are checked first.\n"
            "\n"
            "An item lying on the ground can be sacrificed too, for half of what selling it would give (floored at 1 ryo) -- a way to get rid of anything you can't otherwise sell, not a substitute for 'sell' when a shop's actually available. An item still in your OWN inventory cannot be sacrificed at all -- drop it first.\n"
            "\n"
            "'sacrifice all' sacrifices everything currently in the ROOM -- every corpse and every item on the ground, all at once, for their combined ryo reward.\n"
            "\n"
            "A small number of special items may be flagged 'no_sac' (see 'help flags') to protect them from being destroyed this way; attempting to sacrifice one, individually or via 'sacrifice all', simply leaves it untouched.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "prac",
        "keywords": ["prac", "practice"],
        "title": "Prac",
        "body": (
            "Syntax: prac [skill name]  (alias: practice)\n"
            "\n"
            "Description: With no argument, lists every skill and jutsu you've already learned, each with your current proficiency percentage. Skills you haven't learned yet don't show up at all -- this part works from anywhere, no teacher needed. With a skill name and practice sessions available, spends one to raise that skill's proficiency -- THIS requires a real teacher-flagged mob (see 'help teacher') sharing your room, one whose own class matches the skill's class (a Genjutsu teacher can't teach a Bukijutsu skill). Any teacher can teach a General Skills-category skill (universal starting skills, weapon skills, Handsigns, Examine), since those aren't tied to a class at all.\n"
            "\n"
            "Practice alone can only raise any skill or jutsu up to 50% (Shadow Clone Jutsu is the one exception, capped lower at 20%). Past that, only actual usage in combat can raise it further, all the way to 100%: a jutsu needs to genuinely land a hit (a miss doesn't count), while a weapon skill (Sword, Kunai, etc.) can grow from any attack made while that weapon is equipped, hit or miss. Usage growth needs no teacher at all -- only the deliberate practice command does.\n"
            "\n"
            "Past the practice cap, each qualifying use is a genuine chance to grow, not a guarantee -- and that chance shrinks the closer you already are to mastery. Fresh past the cap, growth is fast and reliable; right at the edge of true mastery, every last bit is a real grind.\n"
            "\n"
            "Each category heading is colored by class (Ninjutsu, Taijutsu, Genjutsu, Bukijutsu), and each skill's percentage is colored on a smooth red-to-green scale based on how close it is to mastery.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "train",
        "keywords": ["train"],
        "title": "Train",
        "body": (
            "Syntax: train <attribute|str|wis|con|int|dex|luk|per|wil|cc>\n"
            "\n"
            "Description: Spends a training point to raise one attribute by one point, up to the cap of 75. See 'help attributes' for what each attribute does.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "convert",
        "keywords": ["convert"],
        "title": "Convert",
        "body": (
            "Syntax: convert\n"
            "\n"
            "Description: Exchanges 5 unused practice points for 1 training point at a teacher, letting you accelerate your attribute training with practice points you aren't otherwise spending. Requires a real teacher physically present (any teacher counts, not just one matching a specific skill's class) -- see 'help train' for what training points are spent on.\n"
            "\n"
            "Date: 2026-09-06"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "biography",
        "keywords": ["biography", "bio"],
        "title": "Biography",
        "body": (
            "Syntax: biography [text]  (alias: bio)\n"
            "\n"
            "Description: Shows or sets your character's freeform biography, shown to others who look at you.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "description",
        "keywords": ["description"],
        "title": "Description",
        "body": (
            "Syntax: description [text]\n"
            "\n"
            "Description: Shows or sets your character's physical description, shown to others who look at you.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "clan",
        "keywords": ["clan", "clans"],
        "title": "Clan",
        "body": (
            "Syntax: clan join <clan name>  |  clan leave\n"
            "\n"
            "Description: Joins or leaves a clan available to your village. Clans are cosmetic only right now -- no mechanical bonus yet.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "apartment",
        "keywords": ["apartment", "housing"],
        "title": "Apartment",
        "body": (
            "Syntax: apartment name <text>  |  apartment desc <text>\n"
            "\n"
            "Description: Renames or redescribes your owned apartment. You must be standing inside it. Buying/selling an apartment is done via 'buy apartment'/'sell apartment' while standing in an available unit.\n"
            "\n"
            "&WRoom expansions:&x once you own an apartment, 'buy room <type> <direction>' (while standing inside your apartment OR any room you've already built) builds a new room off it in a direction of your choice -- one of each type max. The whole complex counts as your own space, so a room can branch off another (build a bedroom off your hallway, say), not only directly off the base apartment. Costs 200,000 ryo for the 1st, doubling per room already owned (200k/400k/800k/1.6M/3.2M/6.4M).\n"
            "\n"
            "&CHallway&x - A basic room, nothing special.\n"
            "&CBedroom&x - Recovers Health/Chakra/Stamina faster, same as a village Hospital.\n"
            "&CKitchen&x - Lets you 'cook' without holding a Cooking Pot.\n"
            "&CPond&x - A water biome, so you can 'fish' here.\n"
            "&CFarming&x - A plains biome, so you can 'farm' here.\n"
            "&CStorage&x - Whatever you leave here survives a server restart, unlike anywhere else in the game.\n"
            "\n"
            "&WSelling:&x 'sell room <type>' tears out one expansion room, refunding 50% of what it actually cost (the rest of the apartment stays yours) -- or 'sell apartment' gives up everything at once (base apartment plus every room you built), refunding 50% of each. Either way, the exit to that room is disconnected -- the direction is free again, the same as if it had never been built, so you (or a later owner, for the base apartment) can build something new there.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "gamble",
        "keywords": ["gamble", "chouhan"],
        "title": "Gamble",
        "body": (
            "Syntax: gamble chou|han <wager>  (alias: chouhan)\n"
            "\n"
            "Description: Plays chou-han (odd/even dice) with a gambler NPC -- you must be sitting/resting first. Wagers are in ryo; a win pays 3x. Takes about a minute to resolve, with flavor messages along the way.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "slots",
        "keywords": ["slots"],
        "title": "Slots",
        "body": (
            "Syntax: slots [tier]\n"
            "\n"
            "Description: With no argument, shows the slot machine's wager tiers and current jackpots. With a tier, pulls the lever -- wagers are in ryo, and each tier has its own progressive jackpot that grows from every pull across all players.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "roulette",
        "keywords": ["roulette"],
        "title": "Roulette",
        "body": (
            "Syntax: roulette number <0-36> <wager>  |  roulette <red|black|odd|even|low|high> <wager>\n"
            "\n"
            "Description: Plays roulette with a gambler NPC. Wagered in MISSION POINTS, not ryo. A straight number pays 36x; the other bet types pay 2x.\n"
            "\n"
            "Each village has its own dedicated Roulette Room, connected off the Gambling Den.\n"
            "\n"
            "Date: 2026-08-27"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "leaderboard",
        "keywords": ["leaderboard", "leaderboards", "top"],
        "title": "Leaderboard",
        "body": (
            "Syntax: leaderboard [category]  (aliases: leaderboards, top)\n"
            "\n"
            "Description: Shows the top-ranked characters in a tracked category (level, kills, ryo, etc.). With no category, lists what's available.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "bingobook",
        "keywords": ["bingobook"],
        "title": "Bingo Book",
        "body": (
            "Syntax: bingobook\n"
            "\n"
            "Description: Lists every posted bounty, grouped by village, and whether you've already claimed each one. Bounties are posted by staff via the 'bounty' command.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "bounty",
        "keywords": ["bounty"],
        "title": "Bounty (staff)",
        "body": (
            "Syntax: bounty create mob <mob vnum> <village> <reward_ryo> <reward_mission_points> <description...>  |  bounty create player <name> <reward_ryo> <reward_mission_points> <description...>  |  bounty remove <id>\n"
            "\n"
            "Description: Posts or removes a Bingo Book bounty on a mob prototype or a player. IDs are auto-assigned within the target's own village's fixed ID range. Unlike the player-facing 'place bounty', this requires no payment and isn't subject to the same-village restriction.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "place",
        "keywords": ["place", "place bounty"],
        "title": "Place Bounty",
        "body": (
            "Syntax: place bounty <player name> <reward_ryo> <reward_mission_points> <description...>\n"
            "\n"
            "Description: Posts a bounty on another player to the Bingo Book -- in person, at a mob flagged as a Bingo Book office. You pay the full reward up front (deducted immediately), so make sure you can afford it. Whoever defeats that player in PvP first claims the reward automatically, the same way a mob bounty pays out on a kill.\n"
            "\n"
            "You can't place a bounty on yourself or on a fellow villager -- bounties are for rival-village ninja, not internal betrayal.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "territory",
        "keywords": ["territory", "war", "capture point", "capture points"],
        "title": "Territory / War",
        "body": (
            "Syntax: territory  (alias: war)\n"
            "\n"
            "Description: Shows every capture point in the game, who currently owns each one, its garrison, its income, and the current war window status.\n"
            "\n"
            "A capture point only changes hands during an active war window -- randomly scheduled ahead of time and announced server-wide, never a fixed predictable slot and never always-on. To take a point: clear out every defender stationed there, then have your village hold it alone, uncontested, for the full duration shown. If the owning village restocks the garrison, or your presence there drops to nothing, the clock resets. Holding it out flips ownership -- the new owner's garrison starts empty.\n"
            "\n"
            "Each point's income (paid into your village's shared treasury every few minutes, on top of a small base income every village gets regardless) comes from its own area -- see 'help garrison' for how that treasury gets spent on defense.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "garrison",
        "keywords": ["garrison", "garrison buy"],
        "title": "Garrison",
        "body": (
            "Syntax: garrison buy <tier>  (tiers: recruit, veteran, elite -- each stronger and more expensive than the last)\n"
            "\n"
            "Description: Stations a new defense mob at the capture point you're standing in, paid for out of your village's shared treasury (see 'territory' to check the balance). Only your village's Kage can do this -- it's communal funds, not your own ryo. You have to be standing at a point your own village already controls, and a point can hold up to 3 defenders at once.\n"
            "\n"
            "A point's garrison has to be cleared out entirely before anyone can start capturing it, so a well-stocked garrison is real, meaningful defense -- not just flavor.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "report",
        "keywords": ["report", "bug", "bug report"],
        "title": "Report",
        "body": (
            "Syntax: report <what went wrong>\n"
            "\n"
            "Description: Logs a bug report for staff to review -- what you type is saved along with your name, village, and the room you were standing in when you sent it, so staff have context without needing to ask. Works from anywhere, anytime, for any player.\n"
            "\n"
            "For staff: any online staff member with the 'staff_notify_reports' setting on (the default -- toggle with 'staffconfig staff_notify_reports off') gets a live, in-game message the instant a player submits one. The full history lives outside the game entirely, in a running text file any player's report gets appended to -- ask whoever manages the server's files if you need to review it directly. Genuinely separate from 'idea' (see 'help idea') -- the two are logged to their own files with their own independent notification settings.\n"
            "\n"
            "This isn't a live chat with staff -- there's no in-game reply. If you need an immediate answer, use a normal channel instead (see 'help say'/'help ooc').\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "idea",
        "keywords": ["idea", "ideas", "suggestion", "suggest"],
        "title": "Idea",
        "body": (
            "Syntax: idea <your suggestion>\n"
            "\n"
            "Description: Logs a suggestion for staff to review -- what you type is saved along with your name, village, and the room you were standing in when you sent it, so staff have context without needing to ask. Works from anywhere, anytime, for any player.\n"
            "\n"
            "Genuinely separate from 'report' -- suggestions and bug reports are logged to their own separate plain-text files, and staff can turn notifications for one off without affecting the other (see 'config').\n"
            "\n"
            "For staff: any online staff member with the 'staff_notify_ideas' setting on (the default -- toggle with 'staffconfig staff_notify_ideas off') gets a live, in-game message the instant a player submits one. The full history lives outside the game entirely, in a running text file any player's idea gets appended to -- ask whoever manages the server's files if you need to review it directly.\n"
            "\n"
            "This isn't a live chat with staff -- there's no in-game reply. If you need an immediate answer, use a normal channel instead (see 'help say'/'help ooc').\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "bank",
        "keywords": ["bank", "banker", "deposit", "withdraw"],
        "title": "Bank",
        "body": (
            "Syntax: bank  |  bank deposit <amount>  |  bank withdraw <amount>\n"
            "\n"
            "Description: A safe place to store ryo away from death-penalty loss -- losing a fight (PvE or PvP) only ever costs you ryo you're carrying on hand, never anything sitting in the bank. There's no way for another player to take ryo from you directly either, so a banked balance is fully safe from other players too.\n"
            "\n"
            "Pays a small amount of interest over time -- applied automatically whenever you interact with your balance in any way, including just checking it with a bare 'bank'. Checking your balance works from anywhere; depositing or withdrawing requires standing at a banker, found in every village square.\n"
            "\n"
            "The bank can hold up to 1,000,000,000 (1 billion) ryo -- a deposit that would go over that is refused outright, not silently capped, so you'll know exactly how much room is left.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "trap",
        "keywords": ["trap", "trap buy", "bomb", "snare", "entangled"],
        "title": "Trap",
        "body": (
            "Syntax: trap buy <type>  (types: snare, bomb)\n"
            "\n"
            "Description: Places a trap in the room you're standing in, funded by your village's shared treasury -- guarding the APPROACH to a capture point rather than the point itself. Requires being that village's Kage, and standing within 1-2 rooms of a capture point your own village already controls.\n"
            "\n"
            "A snare trap deals moderate damage and entangles its target so they can't move for a while -- it stays in place and can trigger again on the next enemy who walks in. A bomb deals bigger damage but doesn't entangle, and is destroyed after going off once.\n"
            "\n"
            "A trap only ever triggers on a player from a DIFFERENT village than the one who placed it, and only while a war window is active -- it's inert the rest of the time. A trap is a real, visible mob standing in the room (not hidden), so an enemy who spots it can fight and destroy it before it goes off.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "rest",
        "keywords": ["rest"],
        "title": "Rest",
        "body": (
            "Syntax: rest\n"
            "\n"
            "Description: Sits down to recover Health/Chakra/Stamina faster than standing. Moving, attacking, or using a jutsu automatically stands you back up.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "sleep",
        "keywords": ["sleep"],
        "title": "Sleep",
        "body": (
            "Syntax: sleep\n"
            "\n"
            "Description: Lies down to recover even faster than resting. Same auto-wake behavior as resting.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "stand",
        "keywords": ["stand", "wake"],
        "title": "Stand",
        "body": (
            "Syntax: stand  (alias: wake)\n"
            "\n"
            "Description: Stands back up from resting or sleeping.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "changes",
        "keywords": ["changes"],
        "title": "Changes",
        "body": (
            "Syntax: changes\n"
            "\n"
            "Description: Shows the in-game changelog, newest entry first. Long enough now that it pages 20 lines at a time -- press enter to see more.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "save",
        "keywords": ["save"],
        "title": "Save",
        "body": (
            "Syntax: save\n"
            "\n"
            "Description: Manually saves your character. Also happens automatically on quit, after every level-up, and periodically in the background.\n"
            "\n"
            "For saving the WORLD itself (rooms/mobs/items), see 'help save world' -- a completely separate, Implementor-only command.\n"
            "\n"
            "Date: 2026-08-20"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "save world",
        "keywords": ["save world", "world persistence", "world save"],
        "title": "Save World (staff)",
        "body": (
            "Syntax: save world\n"
            "\n"
            "Description: Writes a full snapshot of every room, mob prototype, and item prototype currently live in the game to disk. From that point on, every future server restart -- a crash, a manual reboot, or deploying a newly packaged version of the code -- loads this exact saved state back in, on top of whatever the code itself would otherwise build, instead of silently discarding anything built or edited since the code was last written.\n"
            "\n"
            "This is a full snapshot, not just what's new -- it captures the CURRENT state of everything, built-in content and anything you've built or edited alike. Saved data always wins: if you edit an existing room and save, that edit survives every future restart even though the code itself would otherwise rebuild that room differently. There's no autosave -- nothing is written to disk until you explicitly run this, matching the classic 'save the world when you're ready' convention this game's own design is built around, so you can build freely without every single edit hitting disk.\n"
            "\n"
            "&D(Staff only -- requires Implementor access, the same tier 'reboot' requires, given how much this affects: it permanently determines what every future restart loads from here on.)&x\n"
            "\n"
            "Date: 2026-08-20"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "quit",
        "keywords": ["quit"],
        "title": "Quit",
        "body": (
            "Syntax: quit\n"
            "\n"
            "Description: Saves your character and disconnects.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "mset",
        "keywords": ["mset"],
        "title": "Mset (staff)",
        "body": (
            "Syntax: mset create <vnum> <name>  |  mset <vnum> <field> <value>  |  mset spawn <vnum> <room>  |  mset list\n"
            "        mset fields [mob|player]  |  mset <vnum> <field> (show current value and options)\n"
            "\n"
            "Description: Creates and edits mob prototypes field by field -- level, stats, damage dice, flags, shop/gambler/teacher fields, mob programs, and more. 'mset fields' shows grouped mob fields; 'mset fields player' shows player fields. Use 'mset <vnum> flags Wander' for mob flags. Field names can be typed without underscores; the older names still work. See 'mstat <vnum>' to review a prototype.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "builder commands",
        "keywords": ["builder commands", "mcreate", "ocreate", "rcreate", "minvoke", "oinvoke", "mfind", "ofind", "rfind", "mlist", "olist", "rlist"],
        "title": "SMAUG Builder Commands (staff)",
        "body": (
            "Syntax: mcreate <vnum> <name>  |  ocreate <vnum> <name>  |  rcreate <vnum> <name>\n"
            "        mcopy <source vnum> <new vnum>  |  ocopy <source vnum> <new vnum>\n"
            "        minvoke <mob vnum>  |  oinvoke <object vnum>\n"
            "        mfind/ofind/rfind <keyword>\n"
            "        mlist/olist/rlist [first vnum] [last vnum]\n"
            "\n"
            "Description: Familiar SMAUG-style shortcuts for creating, copying, finding, listing, and invoking prototypes. 'mcopy'/'ocopy' duplicate every prototype field into a free VNUM, including flags, stats, programs, and shop stock, without spawning an instance or sharing mutable lists with the source. The create commands use the same validated prototypes as mset/oset/rset. Invoke places a mob or object in your current room. Find searches names and keywords and always displays matching vnums. List optionally limits output to an inclusive vnum range.\n"
            "\n"
            "Use mstat, ostat, or rstat to inspect the result. Changes become reboot-safe when an Implementor runs 'save world'. Mob experience is calculated automatically from level and cannot be set on a prototype.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-09-22"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "mcopy",
        "keywords": ["mcopy"],
        "title": "Mcopy (staff)",
        "body": (
            "Syntax: mcopy <source mob vnum> <new mob vnum>\n\n"
            "Description: Copies a mob prototype, including its stats, flags, shop stock, and programs, to an unused VNUM. The copy is independent of the original. It is not spawned or given a spawn point; use 'minvoke' or 'spawnpoint add mob' when ready. Inspect it with 'mstat'.\n\n"
            "Date: 2026-09-25"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "ocopy",
        "keywords": ["ocopy"],
        "title": "Ocopy (staff)",
        "body": (
            "Syntax: ocopy <source object vnum> <new object vnum>\n\n"
            "Description: Copies an object prototype, including its stats, flags, and programs, to an unused VNUM. The copy is independent of the original. It is not placed or stocked automatically; use 'oinvoke' or 'mset additem' when ready. Inspect it with 'ostat'.\n\n"
            "Date: 2026-09-25"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "experience",
        "keywords": ["experience", "xp", "experience curve", "mob xp", "leveling"],
        "title": "Experience and Leveling",
        "body": (
            "Syntax: score  |  prompt\n"
            "\n"
            "Description: Ninja levels use a progressive cumulative curve: the total XP at the start of a level is (level - 1) cubed, times 1,000. Each level therefore takes more experience than the one before it. Existing characters are migrated once while preserving the percentage they had already completed toward their next level.\n"
            "\n"
            "A mob at your level awards about 5% of your current level band before bonuses. Easier mobs award 10% less for every level below you and reach zero at ten levels below. Harder mobs gain 3% per level, capped at 130%. In a group, that calculation is made separately for each member before the group split.\n"
            "\n"
            "Date: 2026-09-22"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "damage messages",
        "keywords": ["damage messages", "damage words", "damage colors", "colored damage"],
        "title": "Damage Messages",
        "body": (
            "Syntax: (automatic during combat)\n"
            "\n"
            "Description: Combat reports damage with a colored severity word instead of exposing the raw number. The scale runs from TRIVIAL and GLANCING through DEVASTATING and OBLITERATING, then reaches REALITY-SHATTERING and EXTINCTION-LEVEL for the strongest hits. Every tier has its own 256-color shade.\n"
            "\n"
            "Date: 2026-09-22"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "teacher",
        "keywords": ["teacher", "sensei", "instructor"],
        "title": "Teacher",
        "body": (
            "Syntax: (mechanic, not a command -- see 'help prac'/'help mset')\n"
            "\n"
            "Description: Per direct request/confirmation (Section 110): practicing any skill or jutsu now requires a real teacher-flagged mob physically present in your room -- see 'help prac'/'help practice' for the practice command itself.\n"
            "\n"
            "A teacher's own class (Ninjutsu, Taijutsu, Genjutsu, or Bukijutsu) determines what they can teach -- they can only help you practice a skill from their OWN class. The one exception: 'General Skills' (universal starting skills, weapon skills like Kunai/Sword, Handsigns, Examine) aren't tied to any one class, so ANY teacher can help you practice those, regardless of their own specialty.\n"
            "\n"
            "If no matching teacher is present, 'practice'/'prac <skill>' refuses outright and names the class you need to go find.\n"
            "\n"
            "For staff: 'mset <vnum> teacher <class>' marks a mob as a teacher of that class (ninjutsu/taijutsu/genjutsu/bukijutsu); 'mset <vnum> teacher off' clears it back to not-a-teacher. Like shopkeepers and gamblers, a teacher can't be attacked. See 'help mset'.\n"
            "\n"
            "Worked example: 'mset create 5100 a ninjutsu instructor', then 'mset 5100 teacher ninjutsu', then 'mset spawn 5100 <room>' -- players sharing that room can now practice any Ninjutsu skill they know, plus any General Skills-category skill.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "programs",
        "keywords": ["programs", "program", "mob program", "triggers", "addprogram"],
        "title": "Programs (staff)",
        "body": (
            "Syntax: mset addprogram <mob vnum> <trigger> <action> <args...>  (mob)\n"
            "        rset addprogram <trigger> <action> <args...>  (room, always your current room)\n"
            "        oset addprogram <item vnum> <trigger> <action> <args...>  (item)\n"
            "\n"
            "Description: A small, safe scripting system -- builders choose WHEN something fires and WHICH of a fixed set of actions runs; there's no free-form code. 'mstat'/'rstat'/'ostat' show a prototype's current programs with their index, for 'removeprogram <index>'.\n"
            "\n"
            "&WTriggers, by source:&x\n"
            "  Mob:  greet   -- a player enters the mob's room\n"
            "        death   -- the mob is defeated\n"
            "        random  -- a small per-pulse chance while a player shares its room\n"
            "        speech  -- a player 'say's a matching keyword nearby. The ONLY trigger with an extra keyword field: 'mset addprogram <vnum> speech <keyword> <action> <args...>'. Every program sharing that same keyword fires together, so a single line of dialogue, an item, and some ryo can all be stacked under one keyword for a real quest turn-in.\n"
            "        move    -- a player tries to leave the mob's own room in a specific direction. Only min_level/max_level use this trigger -- see below\n"
            "  Item: wear    -- worn or wielded\n"
            "        get     -- added to inventory via a shop purchase\n"
            "  Room: enter   -- a player walks in\n"
            "        random  -- a small per-pulse chance while a player is present\n"
            "\n"
            "&WActions (the same fixed set everywhere):&x\n"
            "  say <text>                    -- speaks the text\n"
            "  emote <text>                  -- shows the text as an emote\n"
            "  give <item vnum>               -- gives the player a real copy of that item\n"
            "  take <item vnum>               -- removes a matching item from the player's inventory, if they have one\n"
            "  heal <n>                       -- heals the player n HP (capped at their max)\n"
            "  teleport <room vnum>            -- moves the player to that room\n"
            "  drop_chance <pct 1-100> <item vnum> -- pct% chance (rolled once, at fire time) to give that item -- natural fit for a mob's 'death' trigger\n"
            "  give_mission_points <n>         -- grants n mission points (spendable AND counted toward the lifetime leaderboard)\n"
            "  give_ryo <n>                    -- grants n ryo\n"
            "  give_xp <n>                     -- grants n experience, handling any level-up exactly like combat XP does\n"
            "  learn_skill <skill name>        -- grants that skill directly, bypassing the normal level/teacher requirement\n"
            "  require_item <item vnum>        -- a gate, not a reward: if the player doesn't have that item, every LATER action in this same program is skipped entirely\n"
            "  remember_keyword                -- (speech only) marks this player as having triggered the current keyword on this mob -- the same player triggering that keyword again gets nothing, forever. Shared by every spawned copy of the mob, since it's stored on the mob's own template\n"
            "  min_level <direction> <n> [message] -- (move only) blocks a player from leaving in that direction if their level is BELOW n -- a guard requiring you to be strong enough. An optional custom message after n replaces the generic default line (e.g. 'min_level north 20 You aren't ready for this yet, kid.')\n"
            "  max_level <direction> <n> [message] -- (move only) blocks a player from leaving in that direction if their level is AT OR ABOVE n -- stopping someone too experienced from entering somewhere (e.g. a low-level-only area). Also takes an optional custom message, same as min_level\n"
            "  set_rank <rank>                 -- promotes the player to that rank, applies the correct headband for it, and fires the same global \"[Name] has been promoted to [Rank]!\" announcement every other promotion path uses (see 'help promotion'). Every real rank works EXCEPT \"kage\" -- appointing a Kage stays exclusive to the real staff command, since it's the only one that enforces one Kage per village.\n"
            "  wear_message <text>             -- (wear trigger only, on an ITEM's own program) shows <text> to the player AND everyone else in the room the moment the item is worn, wielded, or held -- the same real 'wear' trigger already fires for all 3\n"
            "\n"
            "Worked example: an academy proctor NPC that promotes a player from Academy Student to Genin the moment they say a specific keyword nearby -- 'mset create 5000 an academy proctor', then 'mset addprogram 5000 speech graduate set_rank genin'. Standing near that mob and typing 'say graduate' now genuinely promotes you.\n"
            "\n"
            "Worked example: a one-time quest reward that requires proof and never repeats -- 'mset addprogram 5001 speech turnin require_item 9700', 'mset addprogram 5001 speech turnin take 9700', 'mset addprogram 5001 speech turnin give_xp 500', 'mset addprogram 5001 speech turnin remember_keyword'. A player without the item gets nothing; a player with it turns it in, earns the XP, and can never repeat the turn-in.\n"
            "\n"
            "Worked example: a gate guard blocking the road south below level 20, and a separate mob keeping anyone level 50+ out of a low-level-only area to the north -- 'mset create 5002 a gate guard', 'mset addprogram 5002 move min_level south 20'; 'mset create 5003 an academy sentry', 'mset addprogram 5003 move max_level north 50'. Staff always pass through regardless.\n"
            "\n"
            "Not yet built: an item 'drop' trigger, and firing an item's 'get' from looting a corpse (currently only fires from a shop purchase).\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "mstat",
        "keywords": ["mstat"],
        "title": "Mstat (staff)",
        "body": (
            "Syntax: mstat <vnum or name>\n"
            "\n"
            "Description: Shows a mob prototype's full stat block -- works on a live spawned mob or an offline prototype by vnum. Also works on a player's name, showing their score sheet instead. If you're an administrator (or higher), a player's mstat also appends their hidden Kekkei Genkai status (clan, bloodline, Potential, Talent, awakened, mastery) -- see 'help bloodstat'. Builder-level staff see the normal score sheet with nothing extra; this data stays hidden below administrator, same as 'bloodstat' itself.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "bloodstat",
        "keywords": ["bloodstat"],
        "title": "Bloodstat (staff)",
        "body": (
            "Syntax: bloodstat <player>\n"
            "\n"
            "Description: Shows a player's hidden Kekkei Genkai state: clan, bloodline (if any), Potential, Talent, awakened status, and mastery (shown as a fraction and percent of that player's own Potential, plus whether they meet BOTH conditions a future stage-2 awakening quest would require -- 90+ raw Potential AND fully-maxed mastery) -- plus, for a Sharingan specifically, tomoe count against their Potential-based cap (not every Sharingan can reach the full 6; a lower Potential caps the ceiling itself, independent of mastery progress) and whether it's currently toggled active. Never shown to the player themselves anywhere else in the game -- see 'bloodset' to edit these values. The same information also appears automatically at the end of 'mstat <player>' if you're an administrator (or higher) -- 'bloodstat' is useful when you want just this, without the full score sheet around it.\n"
            "\n"
            "&D(Staff only -- requires administrator access or higher.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "bloodset",
        "keywords": ["bloodset"],
        "title": "Bloodset (staff)",
        "body": (
            "Syntax: bloodset <player> bloodline <kkg_id|none>  |  bloodset <player> potential <0-100>  |  bloodset <player> talent <0-100>  |  bloodset <player> awakened <yes|no>  |  bloodset <player> mangekyo <yes|no>  |  bloodset <player> mastery <int>  |  bloodset <player> tomoe <int>  |  bloodset <player> awaken\n"
            "\n"
            "Description: Force-edits a player's hidden Kekkei Genkai state, for testing. 'awaken' calls the real awakening framework. 'mangekyo yes' requires an awakened Sharingan and assigns two distinct random eye techniques from the normal pool; repeating it preserves existing eyes. 'mangekyo no' disables Mangekyo but keeps the assigned eyes. You can also use 'mset <player> mangekyo on|off'. 'tomoe' only matters for a Sharingan. Assigning a bloodline with no Potential/Talent rolls both automatically.\n"
            "\n"
            "&D(Staff only -- requires administrator access or higher.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "awaken",
        "keywords": ["awaken"],
        "title": "Awaken (staff)",
        "body": (
            "Syntax: awaken <player>\n"
            "\n"
            "Description: Force-awakens a player's Kekkei Genkai (if they have one), immediately, regardless of level -- there's no level gate to bypass here in the first place, since the underlying framework function has never checked level at all; a future \"Level 50\" awakening quest is conceptual only, not built yet, and would presumably call this same function once it exists. Calling it again on an already-awakened bloodline just reports the existing state rather than re-granting anything. Same effect as 'bloodset <player> awaken' -- this is just its own dedicated verb, see 'help bloodset' for the full set of Kekkei Genkai staff tools.\n"
            "\n"
            "&D(Staff only -- requires administrator access or higher.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "setkage",
        "keywords": ["setkage"],
        "title": "Setkage (staff)",
        "body": (
            "Syntax: setkage <player>  |  setkage <player> remove\n"
            "\n"
            "Description: Appoints a player as their village's Kage -- the one rank in the game that's never reachable through the normal level/mission-based promotion ladder. Intended for someone voted in by their own community; the vote itself happens outside the game, but only an Implementor can make it official. The target must already be a Village Elder. At most one Kage per village at a time -- appointing a new one automatically relieves whoever held it before, back to Village Elder. 'setkage <player> remove' relieves the current Kage without appointing a replacement.\n"
            "\n"
            "&D(Staff only -- requires Implementor access.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "award",
        "keywords": ["award", "mset mission_points"],
        "title": "Award (staff)",
        "body": (
            "Syntax: award <player> <amount>\n"
            "\n"
            "Description: Adds `amount` mission points to a player's current balance -- unlike 'mset <player> mission_points <n>', which can only overwrite the balance outright to an exact value, this adjusts it relative to whatever it already is. A negative amount deducts instead; the balance never goes below 0.\n"
            "\n"
            "Matches exactly how a real mission completion grants points: both the spendable balance and the player's lifetime mission-points-earned total (used for leaderboards) move together on a grant -- except the lifetime total only ever increases, even on a deduction, since it's meant to record real history, not track a net balance.\n"
            "\n"
            "&D(Staff only -- requires administrator access.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "addtip",
        "keywords": ["addtip", "tips"],
        "title": "Addtip (staff)",
        "body": (
            "Syntax: addtip <text>  |  addtip\n"
            "\n"
            "Description: Adds a new tip to the rotation shown to players who have 'config tips on' (the default) -- one tip is broadcast to everyone with tips on every 30 minutes, cycling through the list in order so nothing repeats back-to-back and every tip eventually gets seen. With no arguments, lists every tip currently in the rotation with its number, for use with 'remtip'. See 'config' for the player-facing toggle.\n"
            "\n"
            "&D(Staff only -- requires builder access.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "remtip",
        "keywords": ["remtip"],
        "title": "Remtip (staff)",
        "body": (
            "Syntax: remtip <number>\n"
            "\n"
            "Description: Removes a tip from the rotation by its number, matching the numbering 'addtip' (with no arguments) shows.\n"
            "\n"
            "&D(Staff only -- requires builder access.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "oset",
        "keywords": ["oset"],
        "title": "Oset (staff)",
        "body": (
            "Syntax: oset create <vnum> <name...>  |  oset <vnum> <field> <value...>  |  oset load <vnum>  |  oset list\n"
            "'oset <vnum> <field> -<value>' removes one entry from a list field instead of adding.\n"
            "\n"
            "Description: Creates and edits item prototypes field by field. Shops stocking this item's VNUM use the edited name, price, and combat stats immediately. 'oset load <vnum>' places one instance on the ground in the room you're standing in right now, with no persistence -- see 'help spawnpoint' for a version that survives a server restart.\n"
            "\n"
            "&WText fields:&x short, long, description, itemtype, weapontype, scrolljutsu, rarity, wearloc\n"
            "  itemtype      -- category (weapon/armor/tool/trash/scroll/material/etc.); drives shop pricing and more\n"
            "  weapontype    -- kunai/sword/shuriken/blunt/polearm/exotic; sets itemtype weapon and wearloc wielded automatically. Use 'none' to clear it before changing itemtype\n"
            "  wearloc       -- where this item can be equipped (head/body/legs/feet/hands/waist/finger/neck/piercing/back/chakra aura for armor, or wielded/tool). itemtype weapon/tool auto-fills this if left blank\n"
            "  rarity         -- common/uncommon/rare/epic/legendary; drives display color everywhere the item's name is shown\n"
            "  scrolljutsu   -- set alongside itemtype scroll to make this item teach a jutsu on 'read'\n"
            "\n"
            "&WNumber fields:&x weight, cost, level, condition, setbonuspercent, concap, hitroll, damageroll, damage, heal, healtime, uses\n"
            "  hitroll/damageroll -- bonuses while wielded; 0 clears the bonus\n"
            "  damage        -- fixed base damage for this item, overriding the weapontype default (0 or higher)\n"
            "  heal/healtime -- total restoration per healflag, delivered over this many seconds for a medical item\n"
            "  uses          -- number of attempts before each copy of a job tool breaks (default 250)\n"
            "\n"
            "&WList fields:&x keywords, flags, wear, setvnums, healflags\n"
            "  healflags      -- add health, chakra, or stamina; prefix - to remove one (e.g. -health)\n"
            "  flags          -- item flags such as 'nosac' or 'notake'; see 'help flags'\n"
            "  wear           -- item's wear permissions (e.g. take); wearloc chooses the actual slot\n"
            "  setvnums       -- the OTHER object vnums that must also be worn to complete this item's armor set\n"
            "  Older underscore field names still work. Type 'oset fields' for the short reference.\n"
            "\n"
            "&WStat perks:&x 'oset <vnum> statbonus <stat> <n>' remains available for other bonuses such as armor_class; direct 'oset <vnum> hitroll <n>' and 'oset <vnum> damageroll <n>' set the same weapon bonuses. Positive armor_class is beneficial (lower is better). 'ostat' shows Hitroll/Damageroll/Damage for wielded items.\n"
            "&WArmor:&x 'oset <vnum> resist sword 25' reduces sword weapon damage by 25% while worn. Use any weapontype; 0 clears a resistance. Multiple worn pieces stack. AC still determines hit chance.\n"
            "&WMedicine:&x set itemtype medical, heal 100, healtime 20, and healflags health (or chakra/stamina). Each flagged resource recovers 100 over 20 seconds, including in combat.\n"
            "\n"
            "&WValue slots:&x 'oset <vnum> value <index 0-3> <number>' -- 4 raw numeric slots for anything not covered by a named field above.\n"
            "\n"
            "&WItem programs:&x\n"
            "  addprogram <vnum> <trigger> <action> <args...>\n"
            "  removeprogram <vnum> <index>  -- index shown by 'ostat'\n"
            "\n"
            "Use 'ostat <vnum>' to view the full stat block.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "ostat",
        "keywords": ["ostat"],
        "title": "Ostat (staff)",
        "body": (
            "Syntax: ostat <vnum or name>\n"
            "\n"
            "Description: Shows an item prototype's full stat block, including weapon resistances and timed medical healing. Wielded items show Hitroll, Damageroll, and Damage. Set them directly with 'oset <vnum> hitroll|damageroll|damage <n>'; damage overrides the weapontype default for that item.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "rset",
        "keywords": ["rset", "redit"],
        "title": "Rset (staff)",
        "body": (
            "Syntax: rset create <vnum>  |  rset goto <vnum>  |  rset <subcommand> ...  (alias: redit)\n"
            "rset always acts on the room you're physically standing in, right now -- no separate, stale 'editing' state to track. 'create'/'goto' teleport you to the target room first, so every other subcommand naturally follows.\n"
            "\n"
            "Description: Creates and edits rooms field by field.\n"
            "\n"
            "&WCreation/navigation:&x\n"
            "  create <vnum>              -- makes a new, blank room, teleports you into it, and starts editing it\n"
            "  goto <vnum>                -- teleports you to an existing room to edit it (same as the standalone 'goto' command)\n"
            "  show                       -- same as 'rstat' on the room you're standing in\n"
            "\n"
            "&WBasic fields:&x\n"
            "  name [text]                -- room name; no text opens a line editor\n"
            "  desc [text]                -- room description; no text opens a full editor\n"
            "  sector <type>              -- terrain/sector label (mostly cosmetic)\n"
            "  biome <type>               -- tags the room for elemental jutsu affinity and gathering-job placement\n"
            "  resetmsg [text|off]        -- room-specific atmospheric flavor line, shown every 15 minutes on the fixed area reset timer -- overrides the containing area's own message (see 'help area') if both are set; 'off' clears it\n"
            "\n"
            "&WExits:&x\n"
            "  exit <direction> <vnum>    -- one-way exit only\n"
            "  bexit <direction> <vnum>   -- two-way exit (this room <-> that room, both directions linked); an unrecognized vnum is created automatically as a blank room\n"
            "  bunlink <direction>        -- removes an exit and its reverse\n"
            "  exitflag <direction> <flag> [value] -- door/locked/hidden/keyitem/passcode on a specific exit\n"
            "\n"
            "&WFlags and special states:&x\n"
            "  safe on|off                -- PvP-safe zone toggle (blocks attacking other players here)\n"
            "  apartment on|off           -- marks this room as a purchasable apartment shell (see 'help apartment')\n"
            "  flags <flagname>           -- toggles a recognized room flag on/off (CapturePoint, accelerated_healing) -- see 'help flags'\n"
            "\n"
            "&WRoom programs:&x\n"
            "  addprogram <trigger> <action> <args...>\n"
            "  removeprogram <index>      -- index shown by 'rstat'\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-21"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "rstat",
        "keywords": ["rstat"],
        "title": "Rstat (staff)",
        "body": (
            "Syntax: rstat [vnum]\n"
            "\n"
            "Description: Shows a room's full stat block -- the room you're standing in by default, or a specific vnum.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "flags",
        "keywords": ["flags", "room flags", "extra_flags", "act_flags", "capturepoint", "no_sac", "no_take", "nosac", "notake", "banker", "bountyoffice"],
        "title": "Flags (staff)",
        "body": (
            "Syntax: rset flags <flagname>  (room flags -- toggle)\n"
            "        oset <vnum> flags <flagname>  (item flags -- prefix - to remove)\n"
            "        mset <vnum> flags <flagname>  (mob flags -- prefix - to remove)\n"
            "\n"
            "Description: Only a recognized flag can be set on any of the three -- an unknown name (including a typo) is refused outright, telling you the valid list. Matching is case-insensitive; whichever way you type a valid flag, it's stored under its one correct/canonical casing shown below, so it's always recognized correctly by whatever system actually checks for it.\n"
            "\n"
            "&WRoom flags:&x\n"
            "  CapturePoint       -- makes this room a war/territory control point; see 'help territory'\n"
            "  accelerated_healing -- faster regen in this room (set automatically on every hospital; rarely needs setting by hand)\n"
            "\n"
            "&WItem flags:&x\n"
            "  no_sac             -- protects this item from being destroyed by 'sacrifice', including 'sacrifice all'\n"
            "  no_take            -- protects this item from being picked up with 'get' at all -- for cosmetic room decoration (furniture, signs, plants) placed via 'oset load' or a registered spawn point, meant to stay exactly where it's put\n"
            "\n"
            "&WMob flags:&x\n"
            "  Banker             -- lets a player 'bank'/'bank deposit'/'bank withdraw' at this mob\n"
            "  BountyOffice       -- lets a player claim a bounty in person at this mob\n"
            "  Wander             -- gives this mob a small per-tick chance to move through a random available exit (moves roughly every few minutes, not constantly; never into an apartment room)\n"
            "  Sentinel           -- a hard override blocking wander behavior for this mob, even if Wander is also set\n"
            "  Garrison           -- war/territory defender designation; set automatically and accurately on every garrison mob, see 'help territory'\n"
            "  Trap               -- war/territory trap designation; set automatically and accurately on every trap mob, see 'help trap'\n"
            "  Npc                -- base flag every non-player mob carries; a pure category label, no mechanical effect of its own by design\n"
            "  Shopkeeper         -- the real shop mechanism is a separate field set elsewhere; this flag alone has no mechanical check\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "hedit",
        "keywords": ["hedit"],
        "title": "Hedit (staff)",
        "body": (
            "Syntax: hedit create <keyword>  |  hedit <keyword>\n"
            "\n"
            "Description: Creates or edits an in-game helpfile -- title, keywords, and body text via the same interactive editor 'rset desc' uses.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "vnum",
        "keywords": ["vnum"],
        "title": "Vnum (staff)",
        "body": (
            "Syntax: vnum <mob|room|item> <vnum> <on|off>\n"
            "\n"
            "Description: Globally enables or disables a prototype. Disabled mobs stop spawning; disabled rooms are closed to ordinary players.\n"
            "\n"
            "&D(Staff only.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "reboot",
        "keywords": ["reboot"],
        "title": "Reboot (staff)",
        "body": (
            "Syntax: reboot\n"
            "\n"
            "Description: Saves every connected player, warns everyone, and restarts the whole server in place.\n"
            "\n"
            "&D(Staff only -- requires Implementor access, the single highest staff tier, given how disruptive this is.)&x\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "dynamic entry",
        "keywords": ["dynamic entry"],
        "title": "Dynamic Entry",
        "body": (
            "Syntax: dynamic entry <target>\n"
            "\n"
            "Description: A Taijutsu jutsu, part of every character's starting kit. Used by typing its name directly -- no 'perform' needed for Taijutsu/Bukijutsu. 5-9 physical damage, costs 5 Stamina, 2 second cooldown.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "throw shuriken",
        "keywords": ["throw shuriken"],
        "title": "Throw Shuriken",
        "body": (
            "Syntax: throw shuriken <target>\n"
            "\n"
            "Description: A Bukijutsu jutsu, part of every character's starting kit. Used by typing its name directly. 5-9 physical damage, costs 5 Stamina, 2 second cooldown.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "throw kunai",
        "keywords": ["throw kunai"],
        "title": "Throw Kunai",
        "body": (
            "Syntax: throw kunai <target>\n"
            "\n"
            "Description: A Bukijutsu jutsu, unlocked at level 15. Used by typing its name directly. 9-15 physical damage, costs 8 Stamina, 2.5 second cooldown.\n"
            "\n"
            "Requires an actual kunai in your inventory -- it's genuinely thrown, not just a flavor name. The kunai is consumed and lands on the ground where you're standing, whether the throw hits or misses, so you (or anyone else) can pick it back up with 'get'.\n"
            "\n"
            "Date: 2026-08-23"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "counter kunai",
        "keywords": ["counter kunai"],
        "title": "Counter Kunai",
        "body": (
            "Syntax: (none -- this is a passive ability, it triggers automatically)\n"
            "\n"
            "Description: A Bukijutsu jutsu, unlocked at level 25. Once learned, it works entirely on its own -- whenever someone throws Throw Shuriken, Throw Kunai, or Explosive Tag Kunai at you, and you're carrying a kunai of your own, you automatically whip it out and deflect the attack completely, taking zero damage. Your own kunai is consumed in the process. Without a kunai on hand, the attack lands normally -- there's no other cost or cooldown to worry about.\n"
            "\n"
            "Date: 2026-08-23"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "explosive tag kunai",
        "keywords": ["explosive tag kunai", "explosive tag"],
        "title": "Explosive Tag Kunai",
        "body": (
            "Syntax: explosive tag kunai <target>\n"
            "\n"
            "Description: A Bukijutsu jutsu, unlocked at level 30. Used by typing its name directly. 9-15 physical damage, costs 15 Chakra and 10 Stamina, 6 second cooldown.\n"
            "\n"
            "Same kunai-consuming, ground-dropping mechanics as Throw Kunai -- but there's a 30% chance the kunai is rigged to detonate instead, dealing a much bigger 25-40 explosive hit rather than the normal damage. It's always one or the other on a given throw, never both.\n"
            "\n"
            "Date: 2026-08-23"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "shadow shuriken technique",
        "keywords": ["shadow shuriken technique"],
        "title": "Shadow Shuriken Technique",
        "body": (
            "Syntax: perform shadow shuriken technique <target>\n"
            "\n"
            "Description: A Ninjutsu jutsu, part of every character's starting kit. Ninjutsu requires the deliberate 'perform' command. 6-10 chakra damage (Wind element -- boosted or weakened by the room's biome), costs 8 Chakra, 2 second cooldown.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "demonic illusion",
        "keywords": ["demonic illusion"],
        "title": "Demonic Illusion: Hell Viewing Technique",
        "body": (
            "Syntax: perform demonic illusion hell viewing technique <target>\n"
            "\n"
            "Description: A Genjutsu jutsu, part of every character's starting kit. 4-8 mental damage and inflicts Frightened (reduces the target's own damage output for a while). Costs 10 Chakra, 3 second cooldown.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "narakumi",
        "keywords": ["narakumi"],
        "title": "Narakumi",
        "body": (
            "Syntax: perform narakumi <target>\n"
            "\n"
            "Description: A Genjutsu jutsu, unlocked at level 15. 10-18 mental damage, with a 50% chance to also inflict Narakumi -- dulling the target's reflexes and lowering their own chance to land hits for a few rounds. Costs 18 Chakra, 4 second cooldown.\n"
            "\n"
            "Date: 2026-08-22"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "fireball jutsu",
        "keywords": ["fireball jutsu", "fireball"],
        "title": "Fireball Jutsu",
        "body": (
            "Syntax: perform fireball jutsu <target>\n"
            "\n"
            "Description: A Ninjutsu jutsu, unlocked at level 20. 12-20 damage, with a 40% chance to also set the target Burning -- steady damage each round for a few rounds. Costs 20 Chakra, 5 second cooldown.\n"
            "\n"
            "Requires your own chakra nature (primary or secondary) to genuinely be Fire -- this jutsu cannot be cast at all otherwise, even if it shows up in your learned skills. See 'help channel' for how to discover your chakra nature.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "water dragon jutsu",
        "keywords": ["water dragon jutsu", "water dragon"],
        "title": "Water Dragon Jutsu",
        "body": (
            "Syntax: perform water dragon jutsu <target>\n"
            "\n"
            "Description: A Ninjutsu jutsu, unlocked at level 20. 12-20 damage, with a 40% chance to also inflict Drained -- steadily sapping the target's own chakra each round for a few rounds. Costs 20 Chakra, 5 second cooldown.\n"
            "\n"
            "Requires your own chakra nature (primary or secondary) to genuinely be Water -- this jutsu cannot be cast at all otherwise, even if it shows up in your learned skills.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "wind blade jutsu",
        "keywords": ["wind blade jutsu", "wind blade"],
        "title": "Wind Blade Jutsu",
        "body": (
            "Syntax: perform wind blade jutsu <target>\n"
            "\n"
            "Description: A Ninjutsu jutsu, unlocked at level 20. 12-20 damage, with a 40% chance to also knock the target Off Balance -- steadily draining their own stamina each round for a few rounds. Costs 20 Chakra, 5 second cooldown.\n"
            "\n"
            "Requires your own chakra nature (primary or secondary) to genuinely be Wind -- this jutsu cannot be cast at all otherwise, even if it shows up in your learned skills.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "lightning strike jutsu",
        "keywords": ["lightning strike jutsu", "lightning strike"],
        "title": "Lightning Strike Jutsu",
        "body": (
            "Syntax: perform lightning strike jutsu <target>\n"
            "\n"
            "Description: A Ninjutsu jutsu, unlocked at level 20. 12-20 damage, with a 30% chance to also Paralyze the target -- completely unable to act for their next couple of rounds. Costs 22 Chakra, 6 second cooldown.\n"
            "\n"
            "Requires your own chakra nature (primary or secondary) to genuinely be Lightning -- this jutsu cannot be cast at all otherwise, even if it shows up in your learned skills.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "earth wall crusher",
        "keywords": ["earth wall crusher"],
        "title": "Earth Wall Crusher",
        "body": (
            "Syntax: perform earth wall crusher <target>\n"
            "\n"
            "Description: A Ninjutsu jutsu, unlocked at level 20. 20-32 raw damage -- noticeably harder-hitting than the other elemental jutsu, since Earth carries no lingering effect at all, just brute upfront force. Costs 20 Chakra, 5 second cooldown.\n"
            "\n"
            "Requires your own chakra nature (primary or secondary) to genuinely be Earth -- this jutsu cannot be cast at all otherwise, even if it shows up in your learned skills.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "shadow clone jutsu",
        "keywords": ["shadow clone jutsu", "shadow clone", "clone jutsu"],
        "title": "Shadow Clone Jutsu",
        "body": (
            "Syntax: perform shadow clone jutsu  (no target -- this summons clones, it doesn't attack anything directly)\n"
            "\n"
            "Description: A Ninjutsu jutsu, unlocked at level 30. Summons 1 to 3 real shadow clones, standing right there in the room with you -- they look exactly like you (same name, same description) to anyone who looks at them, with no way to tell them apart from the real you at a glance. How many you get depends on your current mastery of this jutsu: under 34% summons 1, 34-66% summons 2, 67% and up summons the full 3. Costs 40 Chakra to cast, 10 second cooldown.\n"
            "\n"
            "Clones can be summoned before a fight and stick around independently -- they aren't tied to being in combat at all, and don't follow you if you walk away from them. Each clone has its own health (a flat 25% of your OWN current max health) and can be attacked directly by anyone, same as any other mob in the room; enough hits and one goes down, vanishing in a puff of smoke with nothing to loot and no reward for whoever did it. While you're actively fighting something, your clones automatically join in and attack it too, each using your own stats and weapon at half your own damage.\n"
            "\n"
            "Active clones drain 25 Chakra per clone every round, combat or not, for as long as they're out -- if you can't afford the full upkeep, clones dispel one at a time rather than all at once. Recasting dismisses any clones you already have and resummons fresh at your current mastery, rather than stacking more on top.\n"
            "\n"
            "Mastery can be raised by 'practice' up to 20% -- past that, only actually casting this jutsu in combat raises it further, all the way to 100%.\n"
            "\n"
            "Date: 2026-08-24"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "strong fist style",
        "keywords": ["strong fist style"],
        "title": "Strong Fist Style",
        "body": (
            "Syntax: skills  (shows this skill's current proficiency; it's never used or practiced directly)\n"
            "\n"
            "Description: A passive skill every character starts with. Unlike jutsu, it's never used directly -- it grows automatically from being in melee combat (never from 'practice'), and its proficiency percentage boosts your basic attack damage, up to +10% at 100% mastery.\n"
            "\n"
            "Date: 2026-08-17"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
]


def seed_default_help() -> None:
    for entry in DEFAULT_HELP_ENTRIES:
        path = _path(entry["primary_keyword"])
        if not os.path.isfile(path):
            save_entry(entry)
        elif entry["primary_keyword"] in {"jobs", "farm", "fish", "mine", "chop", "cook", "oset"}:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("updated_by") == "System" and existing.get("body") != entry["body"]:
                save_entry(entry)
    # Earlier releases seeded a separate help file for the old, conflicting
    # staff command. Redirect the stock entry without overwriting staff edits.
    old_path = _path("release beast")
    if os.path.isfile(old_path):
        with open(old_path, "r", encoding="utf-8") as f:
            old_entry = json.load(f)
        if (old_entry.get("updated_by") == "System" and
                old_entry.get("body", "").startswith("Syntax: release beast\n")):
            old_entry["title"] = "Release Beast (renamed)"
            old_entry["body"] = (
                "Syntax: unleash beast\n\n"
                "The staff command for releasing a random Tailed Beast is now "
                "'unleash beast'. 'release <player>' frees your own Illusion Walk target."
            )
            save_entry(old_entry)


def delete_entry(primary_keyword: str) -> bool:
    path = _path(primary_keyword)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def all_entries() -> List[dict]:
    ensure_dirs()
    entries = []
    for filename in sorted(os.listdir(HELP_DIR)):
        if filename.endswith(".json"):
            with open(os.path.join(HELP_DIR, filename), "r", encoding="utf-8") as f:
                entries.append(json.load(f))
    return entries


def find_by_keyword(query: str) -> Optional[dict]:
    query = query.strip().lower()
    if not query:
        return None
    for entry in all_entries():
        if query == entry["primary_keyword"].lower():
            return entry
        if query in [k.lower() for k in entry.get("keywords", [])]:
            return entry
    return None


def can_author(session) -> bool:
    return session.account is not None and session.account.staff_level in STAFF_CAN_AUTHOR_HELP


def _log(staff_name: str, keyword: str, description: str) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {staff_name} | help '{keyword}' | {description}\n"
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


# --- Player-facing lookup -------------------------------------------------

def cmd_help(session, args: List[str]) -> None:
    if not args:
        _show_help_index(session)
        return
    entry = find_by_keyword(" ".join(args))
    if not entry:
        session.send("This helpfile doesn't exist, contact an admin to create it.")
        return
    lines = [f"&Y{entry['title']}&x", "", entry["body"]]
    if len(entry.get("keywords", [])) > 1:
        lines.append("")
        lines.append("&D(Keywords: " + ", ".join(entry["keywords"]) + ")&x")
    session.send("\n".join(lines))


def _show_help_index(session) -> None:
    lines = ["Type 'commands' for a full list of commands."]
    entries = all_entries()
    if entries:
        lines.append("")
        lines.append("&WHelp topics:&x " + ", ".join(sorted(e["primary_keyword"] for e in entries)))
        lines.append("Type 'help <topic>' for details.")
    else:
        lines.append("No help topics exist yet.")
    session.send("\n".join(lines))


# --- Staff authoring (hedit) ----------------------------------------------

def cmd_hedit(session, args: List[str]) -> None:
    if not can_author(session):
        session.send("You do not have help-authoring access.")
        return
    if not args:
        session.send(
            "Usage: hedit create [keyword]\n"
            "       hedit edit <keyword>\n"
            "       hedit list\n"
            "       hedit show <keyword>\n"
            "       hedit delete <keyword>"
        )
        return

    sub, rest = args[0].lower(), args[1:]

    if sub == "list":
        entries = all_entries()
        if not entries:
            session.send("No help files exist yet.")
            return
        lines = ["Help files:"]
        for e in entries:
            lines.append(f"  {e['primary_keyword']:20s} - {e['title']}")
        session.send("\n".join(lines))
        return

    if sub == "show":
        if not rest:
            session.send("Usage: hedit show <keyword>")
            return
        entry = find_by_keyword(" ".join(rest))
        if not entry:
            session.send("No such help file.")
            return
        session.send(
            f"Primary keyword: {entry['primary_keyword']}\n"
            f"All keywords: {', '.join(entry['keywords'])}\n"
            f"Title: {entry['title']}\n"
            f"Last updated by: {entry.get('updated_by', 'unknown')}\n"
            f"--- body ---\n{entry['body']}\n--- end ---"
        )
        return

    if sub == "delete":
        if not rest:
            session.send("Usage: hedit delete <keyword>")
            return
        entry = find_by_keyword(" ".join(rest))
        if not entry:
            session.send("No such help file.")
            return
        delete_entry(entry["primary_keyword"])
        _log(session.player.name, entry["primary_keyword"], "deleted")
        session.send(f"Help file '{entry['primary_keyword']}' deleted.")
        return

    if sub == "create":
        keyword_arg = " ".join(rest).strip()
        if keyword_arg and find_by_keyword(keyword_arg):
            session.send(f"A help file for '{keyword_arg}' already exists. Use 'hedit edit {keyword_arg}' instead.")
            return
        _begin_guided_creation(session, primary_keyword=keyword_arg or None)
        return

    if sub == "edit":
        if not rest:
            session.send("Usage: hedit edit <keyword>")
            return
        entry = find_by_keyword(" ".join(rest))
        if not entry:
            session.send("No such help file. Use 'hedit create <keyword>' first.")
            return
        _begin_guided_edit(session, entry)
        return

    session.send("Unknown hedit subcommand.")


def _begin_guided_creation(session, primary_keyword: Optional[str]) -> None:
    """Walks a builder/helper through keyword -> extra keywords -> title ->
    full body (via the shared line editor), one question at a time."""
    state: dict = {}

    def ask_primary_keyword(line: str) -> None:
        keyword = line.strip()
        if not keyword:
            session.send("A primary keyword is required. Help file creation cancelled.")
            return
        if find_by_keyword(keyword):
            session.send(f"A help file for '{keyword}' already exists. Cancelled.")
            return
        state["primary_keyword"] = keyword
        session.enter_single_line(
            "Enter any additional keywords, comma-separated (or press enter for none):",
            ask_additional_keywords,
        )

    def ask_additional_keywords(line: str) -> None:
        extra = [k.strip() for k in line.split(",") if k.strip()]
        state["keywords"] = [state["primary_keyword"]] + extra
        session.enter_single_line("Enter a short title for this help topic:", ask_title)

    def ask_title(line: str) -> None:
        state["title"] = line.strip() or state["primary_keyword"].title()
        session.enter_editor(
            save_body, initial_text="",
            header=f"Write the help text for '{state['primary_keyword']}'.",
        )

    def save_body(text: str) -> None:
        entry = {
            "primary_keyword": state["primary_keyword"],
            "keywords": state["keywords"],
            "title": state["title"],
            "body": text,
            "created_by": session.player.name,
            "updated_by": session.player.name,
            "updated_at": time.time(),
        }
        save_entry(entry)
        _log(session.player.name, entry["primary_keyword"], "created")
        session.send(f"Help file '{entry['primary_keyword']}' created.")

    if primary_keyword:
        ask_primary_keyword(primary_keyword)
    else:
        session.enter_single_line("Enter the primary keyword for this new help file:", ask_primary_keyword)


def _begin_guided_edit(session, entry: dict) -> None:
    """Same guided flow as creation, but pre-filled with the existing
    values -- press enter on any prompt to keep the current value."""
    state = dict(entry)

    def ask_keywords(line: str) -> None:
        line = line.strip()
        if line:
            extra = [k.strip() for k in line.split(",") if k.strip()]
            state["keywords"] = [state["primary_keyword"]] + extra
        session.enter_single_line(
            f"Enter a new title (current: '{state['title']}'), or press enter to keep it:",
            ask_title,
        )

    def ask_title(line: str) -> None:
        line = line.strip()
        if line:
            state["title"] = line
        session.enter_editor(
            save_body, initial_text=state["body"],
            header=f"Editing help text for '{state['primary_keyword']}'.",
        )

    def save_body(text: str) -> None:
        state["body"] = text
        state["updated_by"] = session.player.name
        state["updated_at"] = time.time()
        save_entry(state)
        _log(session.player.name, state["primary_keyword"], "edited")
        session.send(f"Help file '{state['primary_keyword']}' updated.")

    session.send(f"Editing help file '{entry['primary_keyword']}'.")
    current_extra = ", ".join(entry["keywords"][1:]) or "none"
    session.enter_single_line(
        f"Enter additional keywords, comma-separated (current: {current_extra}), or press enter to keep them:",
        ask_keywords,
    )
