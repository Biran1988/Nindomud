"""
In-game help file system.

Staff author help topics live with `hedit`, guided step-by-step (primary
keyword -> extra keywords -> title -> full body via the same interactive
line editor `rset` uses), rather than a single one-line command with
every field crammed in. Players look topics up with `help <keyword>`.
Each topic is its own JSON file under data/help/, so it survives
restarts and is easy to hand-edit/back up like any other save file.
"""

import jutsu_colors
import json
import os
import time
from typing import List, Optional

import storage
import data_jutsu
import damage_messages
import status_effects

HELP_DIR = os.path.join(storage.DATA_DIR, "help")
AUDIT_LOG_PATH = os.path.join(storage.DATA_DIR, "help_audit.log")

# Help authoring is lower-risk than world editing, so it's open to
# "helper" and up, not just builder-and-above like rset/mset/oset.
STAFF_CAN_AUTHOR_HELP = {"helper", "builder", "area leader", "administrator", "implementor"}

def _slug(keyword: str) -> str:
    # Help topics may contain punctuation (for example, "Water Release:")
    # that Windows rejects in filenames, including packaged helpfiles.
    return keyword.strip().lower().replace(":", "").replace(" ", "_")


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
        "primary_keyword": "unseal",
        "keywords": ["unseal", "unseal mob", "immortal unseal"],
        "title": "Unseal (Immortal Tailed Beast Extraction)",
        "body": (
            "Syntax: unseal list | unseal <player> | unseal player <player> | "
            "unseal mob <beast name or tail number 1-9>\\n\\n"
            "Description: Immortal-only. Removes a sealed Tailed Beast from an "
            "online or offline jinchuriki, clearing mastery, Beast Mode and "
            "rampage, and immediately saves the character. It releases the "
            "beast as a real roaming mob, with a global announcement. "
            "Only one Tailed Beast may roam at a time. Examples: unseal list; "
            "unseal Biran; unseal mob Kurama; unseal mob 9. "
            "This command only affects captured Tailed Beasts."
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "vperk", "keywords": ["vperk", "villageperk"],
        "title": "Immortal Global Village Perks",
        "body": "Syntax: vperk list | vperk status | vperk <perk> on|off | vperk on|off <perk>\\n\\nDescription: Immortal only (helper rank and higher). Activates a perk for every player in the entire MUD for 24 hours, at no mission-point cost; survives reboots and crashes. Only one global perk per category can be active at once: experience, damage or Ryo. Re-enabling refreshes the timer; 'off' cancels that global bonus. Ordinary Kage purchases remain village-only, last one hour, and are not erased.\\n\\nExamples: vperk double exp on | vperk triple damage on | vperk double ryo off | vperk status.\\n\\nPerks: double exp, triple exp, double damage, triple damage, double ryo, triple ryo.",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "camouflage", "keywords": ["camouflage", "camoflage", "camouflag"],
        "title": "Camouflage (General Skill, level 10)",
        "body": "Syntax: camouflage [on|off] | perform camouflage [on|off]\nAll classes learn this skill at level 10. Practice with a teacher before first use. Activation costs 15 Chakra and 5 Stamina; cooldown 15 seconds. This is a persistent on/off toggle with 1 Chakra upkeep every 5 seconds. It remains active until switched off, combat reveals you, or upkeep fails; it has no duration limit. Active maintenance can improve proficiency every 10 seconds, with 10 XP per percentage point gained. Hides your character from ordinary look, scan, direct targeting and tracking, and prevents ordinary NPC recognition/aggression. It does not hide you from the who list or immortal connection tools. Sensory Detect reveals you. Hostile actions and entering combat break camouflage; it cannot be activated during combat or a pending cast. Expiry and manual release also end it. Use aff or score to check whether Camouflage is ON.",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "silent movement", "keywords": ["silent movement"],
        "title": "Silent Movement (General Skill, level 15)",
        "body": "Syntax: silent movement [on|off] | perform silent movement [on|off]\nAll classes learn this skill at level 15; teacher practice is required first. This is a manually activated toggle, not a passive skill. Use silent movement to switch it on or off, or specify on/off explicitly. It stays ON without a time limit until switched off or you lack Stamina for a step. Activation costs 10 Stamina; cooldown 15 seconds. Suppresses normal walking arrival/departure messages to ordinary observers, but does not hide your body from look or scan. Sensory Detect notices your movements. Each successful step costs 2 extra Stamina; blocked exits cost nothing. If you cannot pay the extra cost, Silent Movement ends before travel messages are sent. Combine it with Camouflage for stealth. Other actions, speech and scripted events may still be noticed. Use aff or score to see whether it is ON.",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "sensory detect", "keywords": ["sensory detect", "sensory"],
        "title": "Sensory Detect (General Skill, level 20)",
        "body": "Syntax: sensory detect [on|off] | perform sensory detect [on|off]\nAll classes learn this skill at level 20; teacher practice is required first. Activation costs 20 Chakra; cooldown 15 seconds. Duration is 60 seconds plus mastery percent. While active, you can see, scan, track and target camouflaged ninja, and notice their silent walking. Costs 1 Chakra per second and ends when upkeep cannot be paid. This is an automatic counter while active: repeating look does not reroll detection. It does not reveal immortal invisibility or negate Hidden Mist. Use aff for its remaining duration.",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "focused mind", "keywords": ["focused mind"],
        "title": "Focused Mind (General Skill, level 25)",
        "body": "Syntax: focused mind [on|off] | perform focused mind [on|off]\nAll classes learn this skill at level 25; teacher practice is required first. Activation costs 20 Chakra and 5 Stamina; cooldown 15 seconds. Duration is 60 seconds plus mastery percent. Improves hit chance by 5-10 percentage points depending on mastery for your normal attacks and offensive techniques in every class, against mobs and players. The bonus respects normal hit-chance caps and does not increase your clones or summons. Also shortens newly received ordinary Genjutsu status effects by 10-30% depending on mastery, including Nehan Shoja sleep. It stacks with existing Sharingan duration resistance and never grants immunity. While active, halves accuracy penalties from Confused, Narakumi, Soundless, Disoriented, Haze and Ringing. Does not shorten effects already applied, cancel action-blocking effects or prevent Mangekyo-specific powers. Each successful walking step costs 1 extra Stamina. Use aff for remaining duration.",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "ip", "keywords": ["ip", "connections"],
        "title": "IP connections (immortals)",
        "body": "Syntax: ip [player name or IP filter]\nLists all current connections, including players at login or in an editor, with their actual socket IP, port, country and state. Helper and higher only. Country estimates are offline and may reflect a VPN/proxy. IP geolocation by DB-IP (https://db-ip.com).",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "ban", "keywords": ["ban", "countryban", "ipban"],
        "title": "Connection bans (Administrator and Implementor)",
        "body": "Syntax: ban | ban ip <address or CIDR> [reason] | ban <IP>\nban country <full country name or two-letter code>\nban remove [ip] <address or CIDR>\nban remove country <name or code>\nExamples: ban country Australia; ban country Nigeria; ban country AU.\nBans save automatically across reboots, disconnect every matching session after saving characters, and block all matching accounts before login or character creation. Only Administrators and Implementors may manage bans. A ban matching your own connection is refused. Removing one ban does not override other matching rules. Country detection uses the bundled offline IPv4/IPv6 database; VPNs/proxies and imperfect location data affect results. Unknown/local IPs are not country-matched; IP bans still apply. IP geolocation by DB-IP (https://db-ip.com). See geoip/README.md for refresh and offline recovery instructions.",
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
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
        "primary_keyword": "halloween",
        "keywords": ["halloween", "halloween town", "pumpkin king", "trickortreat", "teleport halloween"],
        "title": "Halloween Town",
        "body": (
            "Syntax: teleport halloween | teleport return | trickortreat\\n"
            "\\n"
            "Halloween Town opens during the Monday-through-Sunday week containing "
            "October 31 (Detroit time). 'teleport halloween' enters the temporary "
            "20-room haunted town (vnums 100000-100019). 'teleport return' brings "
            "you back to the room you came from; the event also sends visitors "
            "home when the holiday ends. You cannot teleport while fighting "
            "or jailed.\\n"
            "\\n"
            "Visit the Costume Cauldron to 'list' and 'buy' wearable costumes "
            "with lasting stat bonuses. At the Witch's Candy Cauldron, buy "
            "restorative sweets; 'eat <candy>' heals and grants a nonstacking "
            "+10% mob-kill experience boost for 15 minutes. During Halloween "
            "week, defeated ordinary mobs everywhere in Nindo_mud can also drop "
            "Halloween candy (22% chance per kill).\\n"
            "\\n"
            "At Mayor Jack Lantern's Trick-or-Treat Porch, use 'trickortreat' "
            "once per day for a surprise: often candy, sometimes a hostile scarecrow. "
            "Haunted Town contains reanimated genin, zombie shinobi, phantom "
            "swordsmen, vampire rogues, undead jonin, and royal guards. "
            "All killable event enemies, including the final boss, are level 50 or lower. "
            "Deep inside the Pumpkin King's Throne, a level-50 Pumpkin King "
            "drops his legendary cursed mask with a rare 3.5% chance. The mask "
            "is wearable on the head and adds +175 maximum Health, Chakra "
            "and Stamina, +5 Strength/Dexterity/Intelligence, +12 hitroll "
            "and +12 damroll; it remains usable all year. The King respawns "
            "30 minutes after defeat; lesser undead respawn after 7 minutes.\\n"
            "\\n"
            "The festival doesn't replace or save over builder-authored areas. "
            "Halloween rooms and NPCs disappear automatically after the week.\\n"
            "\\n"
            "Date: 2026-10-23"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "holiday events",
        "keywords": ["holiday events", "easter", "christmas", "santa", "easter egg", "thanksgiving", "turkey", "july 4", "fourth of july", "uncle sam"],
        "title": "Holiday Events",
        "body": (
            "Syntax: use egg | use present | use <candy> | ask santa present | eat turkey | sell feather | ask uncle sam gifts\n"
            "\n"
            "Description: During the Monday through Sunday week ending on Easter, every ordinary defeated mob leaves a Painted Easter Egg in its corpse. Use an egg to discover candy. Candy restores Health, Chakra, or Stamina and grants +10% experience from mob kills for 15 real minutes; the perk does not stack.\n"
            "\n"
            "On U.S. Thanksgiving Thursday through Sunday, two turkeys appear in each built area. A killed turkey is replaced after 15 minutes. Its corpse carries roasted turkey and two feathers. Eat turkey to restore up to 100 each of Health, Chakra, and Stamina and receive +10% mob experience for 30 minutes. Any shopkeeper buys a feather for 500 ryo.\n"
            "\n"
            "On July 4, Uncle Sam visits every Kage chamber. Ask Uncle Sam about gifts for one box of fireworks, one Bomb Pop Popsicle, and one BBQ Platter per character per year. Use fireworks to light a colorful display; eat popsicle restores up to 60 Chakra and Stamina, and eat BBQ restores up to 100 Health and Stamina.\n"
            "\n"
            "From December 24 through 31, a Christmas tree and Santa appear in every Kage chamber. Ask Santa about a present (or say 'present') for one wrapped present per character per year. Use present to open it. Holiday dates follow Detroit time; gifts and food remain usable after the event.\n"
            "\n"
            "Date: 2026-09-29"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
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
            "Description: All nine core attributes are trainable one point at a time for one training point per increase, including Perception, Willpower, and Chakra Control. Short forms (per, wil, cc) and full names including 'train chakra control' work. All attributes are capped at 75.\n"
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
            "&CPerception&x - Expands Scan beyond the adjacent room along an open route: 1 room below 40 Perception, 2 rooms at 40-64, and 3 rooms at 65+. Never reveals invisible or camouflaged targets, hidden exits or blocked doors. Train with 'train per'.\n"
            "  &G[Active and trainable]&x\n"
            "\n"
            "&CWillpower&x - Your mental defense against ordinary Genjutsu. Each 2 points above 10 add 1% chance to resist a new Genjutsu status (up to 30%). Each 5 points above 10 add 1% per-second chance to break a Genjutsu status already on you (up to 13%). Can also resist or escape Illusion Walk; it never bypasses Mangekyo's special dimension/loop conditions. Train with 'train wil'.\n"
            "  &G[Active and trainable]&x\n"
            "\n"
            "&CChakra Control&x - Train with 'train cc' or 'train chakra control'. Each point trained above 10 immediately and permanently adds 10 maximum Chakra. Also discounts Genjutsu and Ninjutsu Chakra costs by up to 50%, and improves Chakra regeneration.\n"
            "  &G[Active]&x\n"
            "\n"
            "&D(Bloodlines are separate from trainable attributes. Every Hyuga inherits Byakugan; from level 25 it can awaken in combat. Active Byakugan improves combat accuracy, dodge, and long-range chakra sight, but does not increase your trained Perception stat. Strength, Dexterity, Perception, Willpower, and Chakra Control remain trainable up to 75.)&x\n"
            "\n"
            "&D(See also: 'help combatstats', 'help scoresheet', 'help hyuga', 'help kekkei genkai')&x\n"
            "\n"
            "Date: 2026-10-28"
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
            "&CDamage Roll&x - Rises with Strength and adds to actual basic-attack and jutsu damage, alongside weapon bonuses.\n"
            "  &G[Active]&x\n"
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
            "&D(Activated Sharingan and awakened Byakugan add special combat accuracy/evasion bonuses beyond normal trained stats; they are not permanent increases to the attributes shown by 'score'. Every Hyuga can inherit Byakugan, which can awaken from level 25 in combat. See 'help hyuga' for special techniques and rare mastery caps.)&x\n"
            "\n"
            "&D(See also: 'help attributes', 'help scoresheet', 'help hyuga')&x\n"
            "\n"
            "Date: 2026-10-28"
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
            "Ninjutsu grows from Chakra Ball and the first elemental attacks through Rasengan, elemental Rasengans, Chidori, clones, and the level-100 Nanairo no Rasengan. Matching chakra nature is required for elemental attacks. See 'skills' for your level-sorted roster and 'help <jutsu name>' for each move.\n"
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
            "Jutsu unlocks expand across levels 5-65: Henge disguises, object illusions, disorientation and control attacks, Chisei, and room-wide Nehan Shōja. Use 'skills' or 'prac' for your complete level-sorted roster; 'help <jutsu name>' explains each technique.\n"
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
            "Beyond Dynamic Entry, Taijutsu unlocks Choku Zuki, Mae Geri, Oi Zuki, Sokuto, Empi, Kumade, Nidan Kyten Geri, and Tamashiwara, plus Kihon, Neko Ashi, and Sanchin stances. See 'help <technique name>' for individual damage, costs, and effects.\n"
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
            "Jutsu granted automatically as a Bukijutsu character levels: Throw Shuriken (1), Throw Kunai (15), Counter Kunai (25, passive), Explosive Tag Kunai (30). Ninja Arts add Multi-Shuriken Throw (10), Multi-Kunai Throw (20), Exploding Note and Trap Disabling (25), Smoke Bomb and Toxin Binding (30), Demon Wind Shuriken and Samurai Sabre (35), wind-only Fan Techniques and Poison Gas Bomb (40), Flying Swallow and Disenchantment (45), Exploding Clay (50), and Weapon Enchantment (55). At level 25, Bukijutsu can also craft Antidote and Medicinal Pills from Medicinal Herbs; see 'help craft'. Consumable bombs and throwing weapons are sold at shops; enchantments bind permanently to an individual weapon until disenchanted. Weapon arts accept a carried or wielded weapon. See 'help samurai sabre' and 'help flying swallow'.\n"
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
            "&CClan / Bloodline&x - Your clan determines which inherited Kekkei Genkai you can receive. All Hyuga inherit Byakugan, Uchiha may inherit Sharingan, and rare bloodlines have distinct permanent Potential/Talent. Hyuga Byakugan can awaken in combat from level 25, but only exceptional Potential reaches the celestial forms. Bloodlines are not directly trainable attributes.\n"
            "  &G[Active]&x\n"
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
            "&D(See also: 'help attributes', 'help combatstats', 'help hyuga', 'help kekkei genkai', 'help jobs')&x\n"
            "\n"
            "Date: 2026-10-28"
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
            "Description: General Skill learned at level 3. See the visible players, mobs, corpses, and ground items in one adjacent room. Perception 40+ reveals room names and visible characters/mobs a second room away; Perception 65+ reaches a third room along the same open route. Invisible targets do not appear. Closed doors and hidden exits block scanning. Practice with a teacher before first use. Each completed scan, including an empty room, can improve proficiency using the normal jutsu usage rules: a (100 - current proficiency)% chance to gain up to 2 percentage points, capped at 100%. Each percentage point gained awards 10 character XP. Failed or blocked scans grant no growth. Scanning through a controlled elemental clone trains the real character.\n"
            "\n"
            "Date: 2026-10-23"
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
            "Academy Student -> Genin requires level 10, 100% mastery of Shadow Shuriken Technique, Dynamic Entry, Demonic Illusion: Hell Viewing Technique, Throw Shuriken, and Strong Fist Style; then find Iruka (mob VNUM 11) and use 'say Start Genin exam' to take the written Genin Exam. He selects 10 different Naruto anime questions from a 20-question pool, shuffling the four choices on each attempt. All 10 answers must be correct; one mistake ends that attempt. Passing awards a Genin headband and 50 mission points. See 'help genin exam'.\n"
            "\n"
            "Genin -> Chunin is earned by passing the Chunin Exam ('help exam') at level 15, not by asking the Kage.\n\nLevel caps: Academy Student 10, Genin 15, Chunin 35, Special Jonin 55, Jonin 80, Elite Jonin 95, Village Elder 95, Kage 100.\n"
            "\n"
            "Special Jonin, Jonin and Elite Jonin promotions currently use your village Kage's chamber and check the following level and mission requirements:\n"
            "\n"
            "  Special Jonin: level 35, 50 completed missions\n"
            "  Jonin: level 55, 100 completed missions\n"
            "  Elite Jonin: level 80, 500 completed missions\n"
            ""
            "\n"
            "Village Elder has no automatic promotion or exam. Administrators may confer it with 'mset <player> rank village elder'.\n\nKage itself is never earned through a level/mission check -- it's appointed directly by staff (only one Kage per village at a time), and can also never be granted through a mob program's 'set_rank' action, specifically to protect that one-per-village rule.\n"
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
            "Description: Clan Kekkei Genkai are inherited at character creation: Hyuga have 100% Byakugan inheritance, Uchiha have a 50% Sharingan chance, and Kaguya have a 25% Shikotsumyaku chance. Individual bloodline Potential limits the highest attainable powers; Talent governs mastery speed. Elemental releases instead depend on your revealed chakra natures. A character with a clan Kekkei Genkai cannot also gain an elemental release.\n"
            "\n"
            "Awakening is automatic and random during real combat, not an action or quest: Sharingan and Byakugan first become eligible at level 25; Shikotsumyaku and other non-eye bloodlines still require level 50. Sharingan rolls at 1 in 150 per combat round; Byakugan and other bloodlines at 1 in 300. Reaching the level is not a guarantee of immediate awakening. A global announcement reveals the player, not which bloodline awakened.\n"
            "\n"
            "&WSharingan&x unlocks its active eye toggle and tomoe growth through combat. &WByakugan&x unlocks an active chakra-vision toggle at level 25 after awakening, granting accuracy, dodge and directional chakra sensing; Gentle Fist and Eight Trigrams techniques unlock at later levels through practice and combat mastery. Potential 95+ can eventually reach Celestial Byakugan; only Potential 100 at level 100 with full mastery reaches the rare Tenseigan mode. See 'help sharingan' and 'help hyuga'.\n"
            "\n"
            "Element combinations: Water + Wind = Ice; Water + Earth = Wood; Water + Lightning = Storm; Water + Fire = Boil; Earth + Fire = Lava; Fire + Wind = Scorch; Earth + Wind = Magnet; Earth + Lightning = Explosion; Fire + Lightning = Flashfire; Wind + Lightning = Tempest. Three natures (Earth + Wind + Fire) yield the higher tier Dust Release, a Kekkei Tota. A third Chakra Paper at level 100 reveals a third distinct nature. Elemental releases have their own playable techniques.\n"
            "\n"
            "Staff: see 'help bloodstat' and 'help bloodset' for the tools to inspect and edit a player's hidden Kekkei Genkai state, and 'help awaken' for force-awakening one directly.\n"
            "\n"
            "Date: 2026-10-28"
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
            "Description: Toggles the 1-tomoe Sharingan's first ability: reading an opponent's attacks well enough to dodge them, a real bonus on top of your normal dodge chance while it's active. Costs chakra and stamina every combat round it stays on, and a smaller amount of chakra even while you're not fighting -- having it active costs something at all times, more so mid-combat -- and turns itself off automatically if you can't afford the upkeep anymore, rather than draining you into the negatives. Upkeep is combined with other maintained abilities in a report every six minutes, and any pending Sharingan total is reported when it turns off. Costs nothing to toggle off. At 2 tomoe, the chakra cost drops -- the technique becomes less taxing with more eyes open; the dodge bonus itself doesn't change.\n"
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
            "Syntax: unleash beast [1-9]\n"
            "\n"
            "Description: (Staff only.) Releases a random Tailed Beast into the world -- picked from whichever of the 9 real beasts (Shukaku through Kurama) isn't currently sealed into some player, online or offline. A released beast spawns somewhere random (never in a safe room), roams on its own every 10-15 minutes, attacks any player it encounters, and despawns after 2 hours if nobody defeats or seals it. Announces globally which beast was released, so every player knows one is loose.\n"
            "Add a tail count to choose the beast: unleash beast 2 releases Matatabi, the Two-Tails. Valid numbers are 1 through 9. Without a number, selection stays random. A selected beast must still be unsealed, and the one-roaming-beast limit still applies.\n"
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
        "primary_keyword": "jinchuriki",
        "keywords": ["jinchuriki", "mastery", "jinchuriki mastery", "tailed beast mastery"],
        "title": "Jinchuriki Mastery",
        "body": (
            "Syntax: jinchuriki | mastery\n\n"
            "Shows your sealed Tailed Beast, its tail count, and your exact mastery percentage "
            "from 0% to 100%. This is separate from ordinary skill proficiency. "
            "Mastery grows through combat while carrying a beast; rampage risk ends at 65%, "
            "and beastmode becomes available at 100%. Viewing this display costs nothing "
            "and does not toggle Beastmode. If you have no sealed beast, the command says so."
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
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
        "keywords": ["area", "areas", "vnum reservation", "area export", "area import", "area exportworld", "world map", "offline area builder"],
        "title": "Area",
        "body": (
            "Syntax: area create <name> [size]  |  area export <area name>  |  area exportworld  |  area import <file.json> [check]  |  area set <name> income <n>  |  area set <name> resetmsg <text|off>  |  area list\n"
            "\n"
            "Description: (Staff only.) Reserves a contiguous block of room vnums for a named area -- 1000 by default -- so builders working on different areas can't accidentally collide with each other's rooms. 'area create' auto-allocates the next free block; 'area list' shows every reservation, who created it, and its territory income if set.\n"
            "\n"
            "Offline builder: open builder/Nindo_Area_Builder.html in a browser, draw and connect rooms, add mob/item placements, then export a JSON package. To edit an area already in the game, an Implementor runs 'area export <area name>' and copies the file from data/area_exports/ to the browser's Open / import area JSON control. The room layout, exits, and placed mob/item prototypes open for editing. Copy the resulting JSON to data/area_imports/. An Implementor uses 'area import <file.json> check' to validate without changing the world, then 'area import <file.json>' to add or update that area and save it for reboot. Updating checks for changes made in game since export, keeps advanced room/prototype fields, and refuses missing existing rooms or prototypes. Export again if the area changed in game. New packages refuse occupied VNUMs.\n"
            "\n"
            "'area set <name> income <n>' sets the area's per-tick territory income (see 'help territory') -- an area with income set and at least one room flagged CapturePoint (see 'help flags') becomes real, ownable war/territory content, no other setup needed. Use 'astat <name>' to see an area's full details, including how many of its rooms are actually built and which are capture points.\n"
            "\n"
            "'area set <name> resetmsg <text|off>' sets (or clears) an area-wide atmospheric flavor line -- shown to every player standing anywhere within the area every 15 minutes, on a fixed timer (e.g. 'A soft breeze blows through the village.'). A specific room's own override (see 'help rset', 'rset resetmsg') always wins over the area's message if both are set. Every area reset also sweeps that area's own registered mob spawn points (see 'help spawnpoint') and respawns any that are missing -- checked across the WHOLE area, not just a mob's own spawn room, so a mob that's simply wandered elsewhere in the area is correctly left alone rather than duplicated. See 'help aset' for a shorter way to run 'area set'.\n"
            "\n"
            "Room-vnums only, not mobs/objects -- this project has always used separate numbering spaces for those. 'rset create <vnum>' notes if the vnum you pick falls outside every registered area, or inside one reserved by someone else, but doesn't block you either way -- it's a heads-up, not a hard limit.\n"
            "\n"
            "Each of the 5 villages has its own core area (named leaf/stone/water/cloud/sand), covering its original 100-vnum block, PLUS a separate, genuinely-1000-vnum '<village>-expansion' area (e.g. leaf-expansion) for new building -- the core blocks sit packed too tightly against each other to widen in place without relocating already-built rooms, so the expansion areas are where new village content should actually go. Everything else pre-existing (Main Street, apartment/shop expansions) lives in legacy-world/legacy-expansions instead.\n"
            "\n"
            "Date: 2026-10-03"
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
            "It costs 5 Chakra every pulse it's active, summarized with other upkeep every six minutes, and stops on its own if you run out. Paid maintenance can improve Track mastery by 1% on a successful roll outside combat. It also ends cleanly -- with a message telling you so -- the moment the trail goes cold: your target logs off, dies, leaves their own area, or you simply arrive.\n"
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
            "Syntax: summon sign [family] (beside a Summon Elder) | summon <toad|snake|slug|ninken|monkey> | summon dismiss\n"
            "\n"
            "Description: Five summoning families exist -- Toad, Snake, Slug, Ninken, and Monkey. A builder places a Summon Elder in that family's hideout. At level 20, stand beside it and use 'summon sign' to choose your one permanent contract. You cannot sign or summon another family afterward. Calling your family costs 40 Chakra and summons its highest tier allowed by your level.\n"
            "\n"
            "A summon's real strength is your own current level multiplied by that specific tier's own power -- so the same contract gets meaningfully stronger as you level, without needing to re-sign anything. Calling your family again replaces your current summon.\n"
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
        "primary_keyword": "sage", "keywords": ["sage", "sage mode", "senjutsu"],
        "title": "Sage Mode",
        "body": (
            "Syntax: sage [on <family>|off|status] | sage train [family]\n\n"
            "Description: Choose one permanent summoning contract and reach level 80, then find its living Summon Elder. "
            "You can only train the family you chose. One meditation attempt is allowed every real hour. "
            "Each attempt has a 5% chance of gaining just 1% mastery. "
            "Failed attempts also consume the interval. "
            "100% mastery is required to activate its Sage Mode. At least 100 successful sessions are needed.\n\n"
            "Toggle a mastered family's Sage Mode on with 'sage on <family>' and off with 'sage off'. "
            "Bare 'sage' toggles your last selected form (or your only mastered form). "
            "It stays on while you have enough resources: 12 Chakra every 10 seconds out of combat, "
            "or 16 Chakra and 8 Stamina per combat round. It turns off automatically when you cannot pay. "
            "All forms boost attack and jutsu damage by 20%, accuracy by 10, and reduce incoming combat damage by 10%. "
            "Toad adds 5 accuracy; Snake adds 10% jutsu damage; Slug heals 5% maximum health per combat round; "
            "Ninken grants one extra ordinary attack each combat round; Monkey adds 10% wielded weapon damage. "
            "Upkeep joins the combined report every six minutes; any pending Sage Mode total appears when it ends. Your toggle is saved through logout; upkeep resumes while online.\n\n"
            "Date: 2026-09-27"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "summon elder", "keywords": ["summon elder", "summonelder", "summonfamily"],
        "title": "Summon Elder (builder)",
        "body": (
            "Syntax: mset <vnum> flags SummonElder | mset <vnum> summonfamily <toad|snake|slug|ninken|monkey>\n"
            "Description: Place the mob in the chosen family's hideout with 'mset spawn <vnum> <room vnum>' "
            "or add a spawn point. Both the flag and a valid family are required. "
            "The elder must be alive and in the same room for signing contracts and Sage Mode training. "
            "Summon Elders cannot be attacked. Mstat shows their configured family.\n\n"
            "Date: 2026-09-27"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
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
            "Description: Uses a Ninjutsu or Genjutsu technique by full or partial name. Every class also has explicit one-word shortcuts: type a shortcut directly or after per (e.g. 'dyn bandit' or 'per dyn bandit'). Use jutsu shorts to list learned shortcuts. Traditional Taijutsu and Bukijutsu names still work directly (e.g. 'dynamic entry <target>'). Works against another player too, not just mobs -- same targeting rules as 'attack' (a PvP-safe room blocks it, an already-defeated player can't be targeted).\n"
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
        "primary_keyword": "level",
        "keywords": ["level"],
        "title": "Level",
        "body": (
            "Syntax: level\n"
            "\n"
            "Description: Displays your current ninja level, total experience, the cumulative experience needed to reach the next level (the same Next Level value shown by 'score'), and the exact additional XP still needed. At maximum level, XP Needed is 0.\n"
            "\n"
            "Date: 2026-10-21"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "jutsu shortcuts",
        "keywords": ["jutsu shortcuts", "jutsu shorts", "shortcuts", "shorthands"],
        "title": "One-Word Jutsu Shortcuts",
        "body": (
            "Syntax: jutsu shorts | jutsu shortcuts\n\n"
            "Every jutsu has a unique one-word shortcut. Type it directly, followed by "
            "a target or on/off when needed. Examples: dyn bandit, ras bandit, "
            "hmist on, smove off. You can also use per <shortcut>, such as per ras bandit. "
            "Without a target, offensive jutsu use your current opponent as usual.\n\n"
            "Jutsu shorts lists shortcuts for techniques you have learned. Jutsu all shows "
            "shortcuts alongside your class catalog. Help <shortcut> opens that technique's "
            "normal help page. Existing full names and older shortcuts still work. "
            "Shortcuts do not bypass learning, practice, access rules, hand signs, costs or cooldowns."
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "jutsu all",
        "keywords": ["jutsu all", "skills all", "jutsu catalog", "jutsu list"],
        "title": "Jutsu Catalog",
        "body": (
            "Syntax: jutsu all | skills all\n"
            "\n"
            "Shows obtainable techniques for your chosen combat class, "
            "including techniques not yet learned and their minimum levels. "
            "Shared general jutsu appear in a separate section. Elemental jutsu appear only after you reveal a matching nature. Release techniques appear when you actually acquire that release. Special eye techniques appear only after awakening, receiving and discovering that eye ability; unrelated Kamui variants stay hidden. Learned techniques granted outside your class appear in their own category.  "
            "Immortal accounts see the full Ninjutsu, Taijutsu, Genjutsu "
            "and Bukijutsu rosters plus shared jutsu. Conditional techniques "
            "are marked Release, Six Paths, or Scroll; levels alone do not "
            "guarantee they can be learned. Undiscovered scroll-only jutsu "
            "are not revealed to normal characters. The list is paginated "
            "(Enter for more, q to stop). 'skills' lists learned techniques. Every catalog row shows its one-word shortcut; type that shortcut directly or use jutsu shorts for a compact learned list.\n"
            "\n"
            "Date: 2026-10-22"
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
            "Syntax: skills | skills all\n"
            "\n"
            "Description: Lists every jutsu and passive skill you know, ordered by the level you unlocked it at (lowest first), each colored by its class (Ninjutsu, Taijutsu, Genjutsu, Bukijutsu, or General Skills). Only applicable learned jutsu are shown. Use skills all for the same obtainable-technique catalog as jutsu all; newly revealed natures and acquired abilities update the list automatically. Doesn't show proficiency -- see 'prac' for that.\n"
            "\n"
            "Date: 2026-09-02"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "taijutsu stances",
        "keywords": ["taijutsu stances", "stance", "stances", "kihon dachi", "neko ashi dachi", "sanchin dachi"],
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
        "keywords": ["taijutsu strikes", "choku zuki", "mae geri", "oi zuki", "sokuto", "empi", "kumade", "nidan kyten geri", "tamashiwara"],
        "title": "Taijutsu Strikes",
        "body": (
            "Syntax: <technique> [target]\n\n"
            "Description: Taijutsu unlocks Choku Zuki (level 3), Mae Geri (5), Oi Zuki (10), "
            "Sokuto (15), Empi (20), Kumade (25), Nidan Kyten Geri (30), and Tamashiwara (35). Type the technique "
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
            "mid-fight or against an already hurt target. Hidden Mist improves your chance to land the opening strike but does not lift either restriction.\n\nDate: 2026-09-26"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "hidden mist jutsu",
        "keywords": ["hidden mist", "mist jutsu", "hidden mist jutsu"],
        "title": "Hidden Mist Jutsu",
        "body": (
            "Syntax: perform hidden mist jutsu [on|off]\n\n"
            "Description: A level 40, water-only Ninjutsu room toggle. Casting costs 40 Chakra before Chakra Control discounts and has a 30-second cooldown. After hand signs, mist stays in the room where it formed with no duration limit. Upkeep is 1 Chakra every 5 seconds, including while the caster is elsewhere. Toggle it off from anywhere with the bare technique or off; on does not stack or refresh an active mist. One maintained room per caster. It ends when released, when upkeep fails, when the caster is defeated, or on disconnect. Anyone in the mist cannot target or see its caster while the caster is there. The caster gains 15 accuracy and reduces opponents' dodge by 15 in that room. Leaving loses those benefits until returning. Ushiro Shishou remains an opening-only attack against an unhurt target. Use aff to see whether you maintain mist.\n\nDate: 2026-10-24"
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
            "Description: Lists everything you're carrying. Items with the same name stack into one line (up to 2,000 per stack, 20 distinct stacks total) rather than listing each copy separately.\n"
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
        "primary_keyword": "uptime",
        "keywords": ["uptime"],
        "title": "Uptime",
        "body": (
            "Syntax: uptime\n"
            "\n"
            "Description: Shows the time since the current Nindo_mud server last started, "
            "in days, hours, minutes and seconds. The clock resets on every server "
            "restart, including a crash or reboot. Every player can use it.\n"
            "\n"
            "Date: 2026-10-22"
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
            "Description: Sells an item from your inventory to a shopkeeper, if they buy that category of item. Food Shops pay full specialty value for cooked fish, raw fish, farm crops, and other food. General shops pay half; see 'help food shop'.\n"
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
            "Description: Eats a food item for an immediate effect (usually Stamina), or consumes medicine with the same healing and cure effects as 'use'. Medical recovery still takes its normal duration; antidotes only work when you are poisoned. Examples: eat soldier pill; eat medicinal pill; eat antidote pill.\n"
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
            "Description: Uses a medical item, just like 'eat <medicine>'. Configured Health, Chakra, and/or Stamina recovery arrives gradually over time, including during combat; cures take effect immediately. Both verbs consume exactly one item and obey the same restrictions.\n"
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
            "Description: Reveals your own chakra nature -- one of the five elements (Fire, Water, Wind, Earth, Lightning), secretly decided the moment your character was created and never shown to you before now. Requires level 25 -- below that, the paper simply doesn't react and is NOT consumed, so you can hold onto it and try again once you're ready. Once it does react, the paper is consumed.\n"
            "\n"
            "At level 100, a second Chakra Paper reveals a second, distinct nature. A third paper at level 100 reveals a third distinct nature. You must reveal them in order. Element combinations can grant an elemental Kekkei Genkai, or Dust Release (Kekkei Tota) from Earth + Wind + Fire. A character with an inherited clan Kekkei Genkai cannot also gain an elemental release. See 'help kekkei genkai'.\n"
            "\n"
            "Once you've revealed everything there is to know, channeling further Chakra Paper does nothing at all and won't consume the sheet.\n"
            "\n"
            "Revealed natures and any elemental release appear on 'score'. Unrevealed natures stay hidden.\n"
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
            "       craft pill antidote <level>\n"
            "       craft pill medicine <level>\n"
            "\n"
            "Description: A real Bukijutsu skill -- unlocked at Bukijutsu level 25+, or any class at level 70+. Combines exactly 2 materials (see 'help materials') into a brand-new item you name yourself. Their own individual stat values simply add together: a weapon gets that combined number as both bonus Hit Roll and bonus Damage Roll; armor gets it as Armor Class (better defense).\n"
            "\n"
            "<type> is one of: kunai, sword, shuriken, blunt, polearm, exotic.\n"
            "<slot> is one of: head, body, legs, feet, hands, waist, finger, neck, piercing, back, chakra aura.\n"
            "\n"
            "After naming your item, you'll be asked which 2 materials to combine (e.g. 'iron ingot, yew log') -- the same material can be used twice for a weaker but simpler craft. Takes a short delay to resolve, and re-checks you still have both materials at that point.\n"
            "\n"
            "Pill crafting is Bukijutsu-only from level 25 (the level-70 general weapon/armor unlock does not apply). Each pill uses one Medicinal Herbs, sold at village general stores, and takes a short crafting delay. Choose any pill level from 1 through your own current level. The plain item name does not reveal its strength: use 'examine <pill>' to see its level and effect. 'use <pill>' consumes it; use '2.pill' or 'examine 2.pill' to select the second matching pill when carrying multiple levels. Antidote Pill cures poison, and is saved if you are not poisoned. Medicinal Pill restores Health, Chakra, and Stamina (100 + six times its level), each over 30 seconds. It does not cure status effects. These herbs make the strongest medical restorative in the game. Medicinal Herbs are separate from the two-material weapon/armor recipes.\n"
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
            "Description: With no argument, lists every skill and jutsu you've already learned, each with your current proficiency percentage. Skills you haven't learned yet don't show up at all -- this part works from anywhere, no teacher needed. With a skill name and practice sessions available, spends one to raise that skill's proficiency and permanently unlock normal skills for use. New ordinary skills must be practiced at least once with a teacher before they can be used. Passives, scroll-learned jutsu, and abilities directly granted by special powers are exempt, and first-practice unlocks persist even after proficiency is reduced. Training requires a real teacher-flagged mob (see 'help teacher') sharing your room, one whose own class matches the skill's class (a Genjutsu teacher can't teach a Bukijutsu skill). Any teacher can teach a General Skills-category skill (universal starting skills, weapon skills, Handsigns, Examine), since those aren't tied to a class at all.\n"
            "\n"
            "Practicing with a teacher raises skills up to 50% (Shadow Clone Jutsu has a lower 20% cap, and Handsigns 1%). Qualifying combat use can improve learned skills at ANY percentage, including below the practice cap. Once the cap is reached, only usage can raise them further, all the way to 100%: a jutsu needs to genuinely land a hit (a miss doesn't count), while a weapon skill (Sword, Kunai, etc.) can grow from any attack made while that weapon is equipped, hit or miss. Usage growth needs no teacher at all -- only the deliberate practice command does.\n"
            "\n"
            "At any proficiency below 100%, each qualifying use gives a chance to improve; the chance shrinks the closer you are to mastery. Sword at 7% can improve simply by attacking while wielding a sword, whether the attack hits or misses.\n"
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
            "Description: Spends one training point to raise any of the nine attributes by one, to a maximum of 75. Perception (train per), Willpower (train wil), and Chakra Control (train cc or train chakra control) are all trainable; Willpower now protects against ordinary Genjutsu, Perception extends Scan, and Chakra Control increases maximum Chakra and efficiency. See 'help attributes' for the details.\n"
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
            "Syntax: clan join <clan name>\n"
            "\n"
            "Description: Clan selection is required when creating a character. Choose one of your village's listed clans; blank answers and 'none' are not accepted. You can switch later with clan join <clan name>, but cannot leave without choosing another clan. Changing clans does not reroll inherited bloodlines or reincarnation. Existing clanless characters can use clan join to choose a clan.\n"
            "\n"
            "Date: 2026-10-12"
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
        "keywords": ["bank", "gold", "banker", "deposit", "withdraw"],
        "title": "Bank",
        "body": (
            "Syntax: bank or gold  |  gold deposit <amount>  |  gold withdraw <amount>\n"
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
        "primary_keyword": "lottery",
        "keywords": ["lottery", "lottery buy", "jackpot", "draw"],
        "title": "Daily Lottery",
        "body": (
            "Syntax: lottery  |  lottery buy <four digits|random>\n\n"
            "Description: Each ticket costs 1,000 ryo from your carried money. Pick exactly four digits, including leading zeroes, such as 0042, or type random for an automatic pick. You can buy one ticket per drawing. Every ticket adds its price to the shared jackpot.\n\n"
            "A random number from 0000 through 9999 is drawn every 24 hours. You may buy one ticket per draw, choosing four digits or letting the game pick with 'random'. If no ticket matches, 25,000 ryo is added to the jackpot and it carries over. A match wins the jackpot, deposited directly into the winner's bank. Multiple matching players split the jackpot; then the next jackpot starts at 25,000 ryo plus new ticket purchases. 'lottery' shows the next draw in UTC, the current pot, your ticket and the last number.\n\n"
            "Date: 2026-09-28"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
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
        "keywords": ["damage", "damage messages", "damage values", "damage words", "damage colors", "colored damage"],
        "title": "Damage Words and Number Ranges",
        "body": (
            "Syntax: help damage | help damage messages\n"
            "\n"
            "Description: Look up a combat damage word below to find its numeric damage range. Each word covers a range, so it cannot tell you the exact damage of an individual hit. Colors match the words used in combat. The exact scale is:\n\n"
            + damage_messages.help_scale_lines() + "\n\n"
            "Hits beyond 10,000 stay EXTINCTION-LEVEL. Damaging jutsu base hits climb this word ladder with their unlock level: level 75 reaches CATASTROPHIC, and level 100 reaches EXTINCTION-LEVEL. Multi-strike jutsu split their base across strikes. Bonuses and defenses can move a final hit to another word. Damage words appear in combat instead of raw numbers.\n"
            "\n"
            "Date: 2026-10-23"
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
            "Description: Shows a mob prototype's full stat block -- works on a live spawned mob or an offline prototype by vnum. Also works on a player's name, showing their score sheet instead. If you're an administrator (or higher), a player's mstat also appends hidden Kekkei Genkai status (clan, bloodline, Potential, Talent, awakened, mastery). For a Sharingan user it shows Mangekyo status and the assigned Eye 1 and Eye 2 techniques by name -- see 'help bloodstat'. Builder-level staff see the normal score sheet with nothing extra; this data stays hidden below administrator.\n"
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
            "Description: Shows a player's hidden Kekkei Genkai state: clan, bloodline (if any), Potential, Talent, awakened status, and mastery (shown as a fraction and percent of that player's own Potential, plus whether they meet BOTH conditions a future stage-2 awakening quest would require -- 90+ raw Potential AND fully-maxed mastery) -- plus, for a Sharingan specifically, tomoe count, active state, Mangekyo status, and both assigned eye techniques. Never shown to the player themselves -- see 'bloodset' to edit these values. The same information appears at the end of 'mstat <player>' for an administrator (or higher).\n"
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
            "Description: Force-awakens a player's Kekkei Genkai (if they have one), immediately, regardless of level -- there's no level gate to bypass here in the first place, since the underlying framework function has never checked level at all; normal automatic combat awakening requires level 25 for Sharingan or level 50 for other inherited bloodlines; this staff command bypasses those thresholds. Calling it again on an already-awakened bloodline just reports the existing state rather than re-granting anything. Same effect as 'bloodset <player> awaken' -- this is just its own dedicated verb, see 'help bloodset' for the full set of Kekkei Genkai staff tools.\n"
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
        "primary_keyword": "makeimm",
        "keywords": ["makeimm", "promote immortal"],
        "title": "Make Immortal (Implementor)",
        "body": (
            "Syntax: makeimm <account>\n"
            "\n"
            "Description: Promotes an existing player account to the Helper immortal rank and saves the change immediately, even if the target is offline. An online player should reconnect for the full staff skill set. Existing staff ranks are not changed.\n"
            "\n"
            "Only the Biran Implementor account can use this command.\n"
            "\n"
            "Example: makeimm Kakashi\n"
            "\n"
            "Date: 2026-09-29"
        ),
        "created_by": "System",
        "updated_by": "System",
        "updated_at": 0.0,
    },
    {
        "primary_keyword": "promoteimm",
        "keywords": ["promoteimm", "immortal ranks"],
        "title": "Promote Immortal (Implementor)",
        "body": (
            "Syntax: promoteimm <account> <builder|area leader|administrator>\n"
            "\n"
            "Description: Raises an existing immortal account to a higher staff rank and saves the change immediately. Use makeimm <account> first for a player account. Only Biran's Implementor account can use this command. It cannot demote staff or grant Implementor.\n"
            "\n"
            "Examples: promoteimm Kakashi builder; promoteimm Kakashi area leader; promoteimm Kakashi administrator\n"
            "\n"
            "Date: 2026-09-29"
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
        "keywords": ["demonic illusion", "demonic illusion hell viewing technique"],
        "title": "Demonic Illusion: Hell Viewing Technique",
        "body": (
            "Syntax: perform demonic illusion hell viewing technique <target>\n"
            "\n"
            "Description: A Genjutsu jutsu, part of every character's starting kit. 8-16 mental damage and inflicts Frightened for 20 seconds (reduces the target's own damage output). Costs 12 Chakra, 3 second cooldown. Active Sharingan resistance shortens the effect.\n"
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
            "Description: A Genjutsu jutsu, unlocked at level 15. 20-36 mental damage, with a 50% chance to inflict Narakumi for 24 seconds, dulling the target's reflexes and lowering their chance to land hits. Costs 22 Chakra, 4 second cooldown. Active Sharingan resistance shortens the effect.\n"
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
        "primary_keyword": "samurai sabre",
        "keywords": ["samurai sabre"],
        "title": "Samurai Sabre",
        "body": (
            "Syntax: samurai sabre\n"
            "\n"
            "Description: Bukijutsu level 35. Requires a wielded sword. Toggle the chakra edge on to increase ordinary sword hit damage by 20% while sustained. Costs 35 Chakra and 10 Stamina to activate, then 4 Chakra every 10 seconds outside combat, or 6 Chakra and 2 Stamina each combat round. Use the command again to turn it off for free. Switching away from a sword or running out of resources ends it. Upkeep joins the combined six-minute report; pending costs are reported when it ends. 25 second cooldown on activation. Active upkeep can improve Samurai Sabre mastery by 1% on a successful roll, including outside combat.\n"
            "\nDate: 2026-09-27"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    },
    {
        "primary_keyword": "flying swallow",
        "keywords": ["flying swallow"],
        "title": "Flying Swallow",
        "body": (
            "Syntax: flying swallow <target>\n"
            "\n"
            "Description: Bukijutsu level 45. Requires a wielded sword or kunai. A chakra-extended slash with +15 accuracy, 38-58 base damage and a 30% chance to cause bleeding. Wind chakra nature increases its damage by 15%, but is not required. Costs 30 Chakra and 18 Stamina; 7 second cooldown.\n"
            "\nDate: 2026-09-27"
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
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
            "Active clones drain an average 3.75 Chakra per clone every one-second pulse (15% of the previous 25), combat or not. Fractional costs carry forward and are charged as whole Chakra over subsequent pulses. If you can't afford the full upkeep, clones dispel one at a time rather than all at once. The charge is summarized with other upkeep every six minutes. Recasting dismisses any clones you already have and resummons fresh at your current mastery, rather than stacking more on top.\n"
            "\n"
            "Mastery can be raised by 'practice' up to 20%; casting and successful paid clone maintenance can improve it above that cap, even outside combat, all the way to 100%.\n"
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

# These pages use live jutsu data for their costs, cooldowns, and effects.
_EXPANSION_HELP_KEYS = (
    "ice senbon", "ice prison", "demonic mirroring ice crystals",
    "chakra ball", "rasengan", "oodama rasengan", "nanairo no rasengan", "suigadan", "juuha shou",
    "karyuu endan", "retsudotensho", "chishin", "chidori", "dual chidori",
    "full body chidori", "maximum chidori", "raikiri", "fire rasengan",
    "water rasengan", "wind rasengan", "earth rasengan", "lightning rasengan",
    "raiton kage bunshin", "mizu bunshin", "deido bunshin", "suna bunshin",
    "barrier",
    "henge", "greater henge", "ultimate henge", "kokohi arazu", "niju kokohi arazu",
    "chisei", "distortion flame", "phantom soldiers", "soundless sound", "kori shinchu",
    "oboro bunshin", "kanashibari", "snakes embrace", "devils taunt", "insect eyes",
    "kasumi juusha", "suzu senbon", "nehan shouja", "jubaku satsu", "jigaku gouka",
    "kokuangyou",
)
_EXPANSION_DESCRIPTIONS = {
    "ice senbon": "Haku's needles of ice strike one enemy and may drain Stamina through off balance.",
    "ice prison": "Encase one enemy in ice; a successful hit may briefly stop their actions.",
    "demonic mirroring ice crystals": "Haku's signature mirror assault strikes one enemy hard and may blind them.",
    "chakra ball": "Forms a compact ball of chakra for a direct hit.",
    "rasengan": "A spinning chakra sphere that strikes one target.",
    "oodama rasengan": "A larger, stronger Rasengan.",
    "nanairo no rasengan": "Seven independently rolled colors strike the target. The caster's matching chakra nature strengthens that one color; soul can poison and dark can blind.",
    "suigadan": "A water attack that requires a natural water source in the room.",
    "juuha shou": "A slicing Wind attack that can knock a target off balance.",
    "karyuu endan": "A Fire attack that can leave its target burning.",
    "retsudotensho": "A heavy Earth attack.",
    "chishin": "An earthquake that also strikes other attackable mobs in the room.",
    "chidori": "A Lightning strike that can paralyze the target.",
    "dual chidori": "A stronger two-handed Chidori that can paralyze.",
    "full body chidori": "A powerful Lightning Chidori that can paralyze.",
    "maximum chidori": "The strongest Chidori in this set, with a chance to paralyze.",
    "raikiri": "An opening-only Lightning strike against an unhurt target, dealing 50% more damage when it connects.",
    "fire rasengan": "A Fire Rasengan that can burn.",
    "water rasengan": "A Water Rasengan that can drain Chakra.",
    "wind rasengan": "A Wind Rasengan that can knock the target off balance.",
    "earth rasengan": "An Earth Rasengan that trades status effects for higher direct damage.",
    "lightning rasengan": "A Lightning Rasengan that can paralyze.",
    "raiton kage bunshin": "Summons one Lightning clone that fights with you and can paralyze.",
    "mizu bunshin": "Summons one Water clone that fights with you and can drain Chakra.",
    "deido bunshin": "Summons one Earth clone that fights with you and deals 25% more clone-attack damage.",
    "suna bunshin": "Summons one Sand clone that fights with you and can entangle a target.",
    "barrier": "A defensive chakra barrier negates 25% of incoming damage for three minutes without changing Armor Class. Leaving the room breaks it.",
    "henge": "Disguise yourself as a person in the room; casting without a target removes your disguise.",
    "greater henge": "A longer-lasting disguise as a person in the room; casting without a target removes it.",
    "ultimate henge": "The longest-lasting disguise as a person in the room; casting without a target removes it.",
    "kokohi arazu": "Change the visible name of a carried item without altering the real item.",
    "niju kokohi arazu": "Project a false copy of a carried item onto the ground; it cannot be taken or sold.",
    "chisei": "Toggle heightened Genjutsu focus and temporary maximum Chakra, maintained for 1 Chakra every 5 seconds.",
    "distortion flame": "An illusion that deals mental damage.",
    "phantom soldiers": "An illusory assault that deals mental damage.",
    "soundless sound": "Mental damage with a chance to impair accuracy.",
    "kori shinchu": "Mental damage that drains 20 Stamina and can disorient the target.",
    "oboro bunshin": "Illusory clones that can confuse the target and lower accuracy.",
    "kanashibari": "A binding illusion that can briefly paralyze the target.",
    "snakes embrace": "An illusion of snakes that can weaken the target's outgoing damage.",
    "devils taunt": "An illusion that can stun and stop an action.",
    "insect eyes": "Reflects the victim's own normal attack sequence as mental damage, including extra strikes.",
    "kasumi juusha": "Haze-like illusory warriors that sharply reduce accuracy.",
    "suzu senbon": "Bell sounds that can disrupt the target's accuracy.",
    "nehan shouja": "Attempts to put eligible enemies in the room to sleep for 12 seconds; safe rooms prevent hostile PvP.",
    "jubaku satsu": "A binding tree illusion that can stun the target.",
    "jigaku gouka": "A tormenting illusion that can dull the target's reflexes.",
    "kokuangyou": "A darkness illusion that can blind the target.",
}
import data_kekkei_genkai as _release_data
for _release_key, _release_jutsu in data_jutsu.JUTSU.items():
    _release_id = _release_jutsu.get("kkg_gate")
    if _release_id in _release_data.ELEMENTAL_RELEASE_NAMES and _release_key not in _EXPANSION_DESCRIPTIONS:
        _EXPANSION_HELP_KEYS += (_release_key,)
        _EXPANSION_DESCRIPTIONS[_release_key] = (
            f"A {_release_data.ELEMENTAL_RELEASE_NAMES[_release_id]} attack that strikes one target. "
            + {
                "off_balance": "An off-balance target loses Stamina over time.",
                "drained": "A drained target loses Chakra over time.",
                "weakened": "A weakened target deals 15% less damage.",
                "paralyzed": "Paralysis briefly blocks the target's actions.",
                "blinded": "Blindness reduces the target's accuracy.",
                "burning": "Burning deals extra damage over time.",
                "stunned": "A stun briefly blocks the target's actions.",
            }[_release_jutsu["effect"]]
        )
for _key in _EXPANSION_HELP_KEYS:
    _jutsu = data_jutsu.JUTSU[_key]
    _type = _jutsu.get("jutsu_type")
    _syntax = f"perform {_key}" if _type in ("buff", "elemental_clone") else f"perform {_key} <target>"
    if _type in ("chisei", "room_sleep"):
        _syntax = f"perform {_key}"
    if _type == "chisei":
        _syntax += " [on|off]"
    if _type == "item_illusion":
        _syntax = f"perform {_key} <carried item> as <apparent name>"
    if _type == "item_decoy":
        _syntax = f"perform {_key} <carried item>"
    _details = _EXPANSION_DESCRIPTIONS[_key] + " " + {
        "buff": "Raises a defensive barrier for three minutes (25% less incoming damage, no Armor Class bonus). Moving to another room breaks it.",
        "elemental_clone": "Summons one living clone that fights alongside you and costs an average 3.75 Chakra per round. Requires 100% Shadow Clone Jutsu mastery; recasting any clone replaces the existing clones.",
        "ambush": "An opening attack with 50% extra damage; cannot be used mid-fight or against a wounded target.",
        "area": "An earthquake that damages other attackable mobs in the room as well.",
        "sevenfold": "A level-cap Rasengan with seven separate strike rolls: fire, water, earth, wind, lightning, soul, and dark. A matching chakra nature strengthens its own color. Soul can poison and dark can blind; one cast pays one Chakra cost.",
        "disguise": "Take the appearance of a person in this room. Use without a target to release your disguise; higher Henge tiers last longer.",
        "item_illusion": "Change how a carried item looks to other players who examine you; its real identity and properties stay intact.",
        "item_decoy": "Project a false copy of a carried item on the ground. It cannot be picked up, equipped, or sold.",
        "chisei": "Gain temporary maximum Chakra and +12 accuracy for Genjutsu attacks until toggled off or upkeep fails. Off, defeat and disconnect remove the temporary bonuses; on cannot stack them. Upkeep: 1 Chakra every 5 seconds. The bare technique toggles it; on/off are also accepted.",
        "room_sleep": "Put eligible enemies in your room to sleep for 12 seconds, each with an independent resistance check; no friendly fire or PvP in safe rooms.",
        "mirror": "Mental damage scales with the opponent's own offensive strength.",
    }.get(_type, "")
    _specific = {
        "kori shinchu": " Also drains 20 Stamina on hit.",
        "kanashibari": " Its paralysis can block actions briefly.",
        "snakes embrace": " Its weakening reduces outgoing damage by 15%.",
        "oboro bunshin": " Illusory clones lower the victim's accuracy.",
        "kasumi juusha": " Its haze sharply lowers the victim's accuracy.",
        "suzu senbon": " Ringing bells impair accuracy.",
    }.get(_key, "")
    _nature = (f" Requires {_jutsu['element'].capitalize()} chakra nature."
               if _jutsu["element"] != "none" else " Usable with any chakra nature.")
    if _jutsu.get("kkg_gate") in _release_data.ELEMENTAL_RELEASE_NAMES:
        _release_name = _release_data.ELEMENTAL_RELEASE_NAMES[_jutsu["kkg_gate"]]
        _nature = f" Requires {_release_name} and its revealed chakra natures, without a clan bloodline."
    if _jutsu.get("requires_water"):
        _nature += " Requires water in the room (ocean, river, lake, or swamp)."
    _effect = (f" { _jutsu.get('effect_chance_pct', 100)}% chance to inflict {_jutsu['effect'].replace('_', ' ')}."
               if _jutsu["effect"] else "")
    if _jutsu["effect"] and _jutsu["class_requirement"] == "genjutsu":
        _effect += f" The effect lasts {status_effects.genjutsu_duration(_jutsu['effect'])} seconds before resistance."
    _damage = (f" Base damage: {_jutsu['damage'][0]}-{_jutsu['damage'][1]}."
               if _jutsu['damage'] is not None else "")
    _duration = (f" Illusion lasts {_jutsu['duration']} pulses."
                 if _jutsu.get('duration') else "")
    _costs = (f"Costs {_jutsu['chakra_cost']} Chakra and {_jutsu['stamina_cost']} Stamina; "
              f"{_jutsu['cooldown']:g} second cooldown.")
    DEFAULT_HELP_ENTRIES.append({
        "primary_keyword": _key, "keywords": [_key], "title": _jutsu["display_name"],
        "body": (f"Syntax: {_syntax}\n\nDescription: {_details}{_specific}{_nature}{_damage}{_effect}{_duration} "
                 f"Unlocks at level {_jutsu['level_requirement']}. {_costs}\n\nDate: 2026-09-27"),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    })

# Keep an individual page for every recently added fighting art. Replace the
# older Taijutsu group aliases and the short Samurai/Flying pages with their
# fuller entries; existing player-authored files still take precedence.
import recent_help

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "sixpaths", "keywords": ["sixpaths", "six paths", "six paths powers"],
    "title": "Six Paths Awakening",
    "body": (
        "Syntax: sixpaths [on|off|status]\n\n"
        "At level 75, an Indra reincarnation learns Six Paths Rinnegan, Almighty Push "
        "and Universal Pull. An Ashura reincarnation learns Six Paths Sage Mode, "
        "Six Paths Vital Surge and Truth-Seeking Orb Barrage. This unlock works for "
        "all combat classes and also catches eligible returning players at login. "
        "The two lineages cannot use each other's exclusive techniques.\n\n"
        "Activation costs 40 Chakra. While active, pay 18 Chakra every ten seconds "
        "outside combat, or 24 Chakra and 8 Stamina each combat round. The form ends "
        "when resources run out, you fall, or you log back in. Turn it off with "
        "sixpaths off. Summon Sage Mode and Six Paths mode cannot stack. "
        "At 0-100% mode mastery, gain 10-20% outgoing damage, 5-15% incoming damage "
        "reduction, and +5-10 accuracy. Practice stops at the normal 50% cap; paid "
        "maintenance can raise mode mastery toward 100%. Attack techniques have "
        "their own normal proficiency, costs and cooldowns. See each individual "
        "technique's help for details.\n\n"
        "Use perform <technique> <target>; your mode must be active. These powers "
        "use ordinary PvE/PvP targeting, safe-zone rules and damage handling. "
        "Vital Surge is self-only: perform six paths vital surge restores 25% of "
        "maximum Health and Stamina and clears poison and weakened effects. "
        "It costs 120 base Chakra and has a two-minute cooldown. "
        "Birth bonuses and reincarnation status stay permanent when the mode ends.\n\n"
        "Date: 2026-10-11"
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "reincarnation",
    "keywords": ["reincarnation", "reincarnate", "indra", "ashura", "asura"],
    "title": "Indra and Ashura Reincarnation",
    "body": (
        "Syntax: reincarnation | score\n\n"
        "Once character creation is confirmed, Uchiha characters receive one 1-in-100 "
        "chance to inherit Indra's chakra and will. Senju and Uzumaki characters receive "
        "one 1-in-100 chance to inherit Ashura's. Other clans have no eligible lineage. "
        "There are not two separate rolls: each eligible character has a 1% total chance. "
        "A successful roll permanently records the soul and creation clan. "
        "Changing clans, dying, reconnecting, rebooting, and loading a save never reroll it. "
        "Existing characters receive no retroactive roll.\n\n"
        "Both reincarnations receive +5 to all nine starting attributes: Strength, "
        "Dexterity, Constitution, Intelligence, Wisdom, Luck, Perception, Willpower, "
        "and Chakra Control. This is a one-time bonus; the normal training cap stays the same. "
        "Indra grants 10% extra starting and level-up Chakra. Ashura grants 10% extra "
        "starting and level-up Health and Stamina. Fractional gains carry forward between "
        "levels so small increases are not lost. Healing, equipment bonuses, attribute "
        "training, and staff stat edits are not multiplied. These are game balance perks, "
        "separate from the existing Kekkei Genkai inheritance roll. Reincarnation does not "
        "automatically grant Sharingan or Wood Release at birth. At level 75, Indra "
        "awakens Six Paths Rinnegan, Almighty Push and Universal Pull; Ashura awakens "
        "Six Paths Sage Mode, Six Paths Vital Surge and Truth-Seeking Orb Barrage. "
        "See help sixpaths for activation, mastery and upkeep. "
        "The Uchiha line follows Madara and Sasuke; the Senju/Uzumaki lines follow "
        "Hashirama and Naruto. Any character sex or combat class can qualify.\n\n"
        "The reincarnation command reports your result and bonuses; score shows a "
        "successful inherited soul and birth lineage. Administrators can inspect it with "
        "bloodstat <player>.\n\nDate: 2026-10-11"
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "lightsaber",
    "keywords": ["lightsaber", "lightsabers", "activate", "deactivate", "insert"],
    "title": "Lightsabers",
    "body": (
        "Syntax: wield lightsaber | activate [lightsaber] | deactivate [lightsaber]\n"
        "        use lightsaber | insert <cut gem> [into <lightsaber>]\n"
        "        lightsaber | lightsaber on|off [lightsaber]\n"
        "        lightsaber gem <cut gem> [into <lightsaber>]\n\n"
        "A mysterious Jedi visits each Kage chamber on May 4 (America/Detroit time). "
        "Ask jedi lightsaber to receive one green lightsaber hilt per character per year. "
        "The Jedi leaves after May 4, but your weapon remains usable all year. "
        "An ignited blade uses Sword proficiency, adds 8 base weapon damage and +2 Hitroll. "
        "A retracted hilt uses Blunt Weapon proficiency with no blade damage or Hitroll bonus. "
        "Use lightsaber toggles ignition. Deactivate the blade before inserting a carried cut gem; "
        "crystal changes are unavailable during combat. Quartz makes white, sapphire blue, "
        "ruby red, and diamond cyan. Inserting consumes one cut gem and replaces the old crystal. "
        "The gem changes color only. Raw gems and ordinary uncut gems do not work. "
        "Color and ignition state survive saving, trading, and rebooting. "
        "Commands default to a lightsaber in your equipment, then inventory; "
        "use 2.lightsaber to select the second match.\n\n"
        "Date: 2026-10-10"
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "signature",
    "keywords": ["signature", "signature move", "signature skill"],
    "title": "Signature Move",
    "body": (
        "Syntax: signature  |  signature <move name>  |  signature clear\n\n"
        "Choose one eligible, learned active combat jutsu after it reaches 100% proficiency. "
        "Normal practice still stops at 50%; reach 100% through use first. "
        "Once selected, raise it from 100% to 150% through successful use, not teacher practice. "
        "The bonus begins only at 150%: +25% damage for an attack, and +25% "
        "duration for status/utility effects (Chisei also boosts its temporary Chakra). "
        "Switch or clear the signature whenever you want, but the old move "
        "immediately drops back to 100%. A newly chosen move starts its own 100%-150% "
        "training. Passive, binary, and other unsupported abilities cannot be selected.\n\n"
        "Date: 2026-10-06"
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

_recent_pages = {entry["primary_keyword"]: entry for entry in recent_help.PAGES}
DEFAULT_HELP_ENTRIES = [entry for entry in DEFAULT_HELP_ENTRIES
                        if entry["primary_keyword"] not in _recent_pages]
DEFAULT_HELP_ENTRIES.extend(recent_help.PAGES)

# Several older authored pages include a fixed damage range in their prose.
# Refresh that one range from the live jutsu table after level scaling, while
# preserving their individual explanations, costs and command syntax.
import re as _damage_re

_SCALED_DAMAGE_HELP_TOPICS = set()
for _entry in DEFAULT_HELP_ENTRIES:
    _jutsu_key = _entry["primary_keyword"]
    if _jutsu_key not in data_jutsu.JUTSU:
        _jutsu_key = next((key for key in _entry["keywords"] if key in data_jutsu.JUTSU), None)
    _live = data_jutsu.JUTSU.get(_jutsu_key)
    if not _live or _live["damage"] is None:
        continue
    _new_range = f"{_live['damage'][0]}-{_live['damage'][1]}"
    _body, _count = _damage_re.subn(
        r"\b\d+-\d+(?=\s+(?:(?:physical|mental|chakra|raw|base)\s+)?damage\b)",
        _new_range, _entry["body"], count=1,
    )
    if _jutsu_key == "explosive tag kunai":
        _blast = _live["explosive_damage"]
        _body = _damage_re.sub(r"\b\d+-\d+(?=\s+explosive hit\b)",
                               f"{_blast[0]}-{_blast[1]}", _body, count=1)
    if _jutsu_key == "earth wall crusher":
        _body = _body.replace("noticeably harder-hitting than the other elemental jutsu, since Earth carries no lingering effect at all, just brute upfront force",
                              "an upfront Earth hit without a lingering status effect")
    if _body != _entry["body"]:
        _entry["body"] = _body
        _SCALED_DAMAGE_HELP_TOPICS.add(_entry["primary_keyword"])

# Build the five nature choice guides and every elemental release help page
# from the same mapping that grants releases in game.
import data_kekkei_genkai as _elemental_kkg

_ELEMENT_HELP_TOPICS = {"elements", "channel", "kekkei genkai", "fire", "water", "wind", "earth", "lightning"}
_RELEASE_HELP_TOPICS = set()
for _entry in DEFAULT_HELP_ENTRIES:
    _topic = _entry["primary_keyword"]
    if _topic in ("fire", "water", "wind", "earth", "lightning"):
        _pairs = []
        for _nature in ("fire", "water", "wind", "earth", "lightning"):
            if _nature == _topic:
                continue
            _release = _elemental_kkg.ELEMENTAL_RELEASES[frozenset((_topic, _nature))]
            _pairs.append(f"{_topic.capitalize()} + {_nature.capitalize()}: "
                          f"{_elemental_kkg.ELEMENTAL_RELEASE_NAMES[_release]} "
                          f"(help {_elemental_kkg.ELEMENTAL_RELEASE_NAMES[_release].lower()})")
        _entry["body"] += "\n\nSecond nature choices at level 25:\n" + "\n".join(_pairs)
    elif _topic == "channel":
        _entry["body"] = (
            "Syntax: channel <chakra paper>\n\nAt level 10, Chakra Paper reveals your first nature. "
            "At level 25, you are brought to your village Kage chamber to choose a different "
            "second nature. Type 'choose <element>' or the element's name. You are safe from "
            "mobs and PvP, with only help and chat available until you choose. "
            "Type 'help <your first element>' to compare all four possible releases. "
            "The choice needs no second Chakra Paper. At level 100, a further paper can reveal "
            "a third distinct nature. Clan bloodlines cannot also gain an elemental release."
        )
    elif _topic == "elements":
        _entry["body"] = (
            "Five base elements: Fire, Water, Wind, Earth, Lightning. Channel Chakra Paper "
            "at level 10 to reveal your first nature. At level 25 you choose a different "
            "second nature in your village Kage chamber. Type 'help fire', 'help water', "
            "'help wind', 'help earth', or 'help lightning' to see every pairing and its "
            "elemental Kekkei Genkai. A third paper at level 100 can reveal a third nature. "
            "Elemental jutsu still require their matching nature."
        )
    elif _topic == "kekkei genkai":
        _entry["body"] = _entry["body"].replace(
            "The Sharingan&x is the one Kekkei Genkai with real, playable abilities right now.",
            "The Sharingan&x and all elemental releases have playable abilities."
        ).replace(
            "These elemental releases have no dedicated jutsu yet.",
            "Each elemental release has three dedicated techniques."
        ) + (
            "\n\nElemental releases unlock when you choose your second nature at level 25. "
            "Every two-nature release has moves at levels 25, 45, and 70. "
            "Dust Release has three moves at level 100 after its third nature reveal. "
            "Each release has its own help page."
        )

for _release_id, _name in _elemental_kkg.ELEMENTAL_RELEASE_NAMES.items():
    _topic = _name.lower()
    _RELEASE_HELP_TOPICS.add(_topic)
    _pair = next((sorted(pair) for pair, release in _elemental_kkg.ELEMENTAL_RELEASES.items()
                  if release == _release_id), None)
    _combination = (" + ".join(n.capitalize() for n in _pair) if _pair else "Earth + Fire + Wind")
    _move_lines = [f"Level {j['level_requirement']}: {j['display_name']} (help {key})"
                   for key, j in data_jutsu.JUTSU.items() if j.get("kkg_gate") == _release_id]
    _body = (f"{_name} forms from {_combination}. Choose a second nature at level 25 after "
             "revealing your first at level 10; Dust Release additionally requires a third "
             "nature revealed at level 100. Clan Kekkei Genkai holders cannot gain an "
             "elemental release.\n\n")
    _body += ("Techniques:\n" + "\n".join(_move_lines) if _move_lines
              else "Dedicated techniques for this release have not been added yet.")
    DEFAULT_HELP_ENTRIES.append({
        "primary_keyword": _topic,
        "keywords": list(dict.fromkeys((_topic, _release_id.replace("_", " ")))),
        "title": _name,
        "body": _body, "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    })


def seed_default_help() -> None:
    old_death_page = _path("100 years of death")
    if os.path.isfile(old_death_page):
        with open(old_death_page, "r", encoding="utf-8") as file:
            old = json.load(file)
        if old.get("updated_by") == "System":
            os.unlink(old_death_page)
    for entry in DEFAULT_HELP_ENTRIES:
        path = _path(entry["primary_keyword"])
        # Preserve existing system and staff-authored pages from older Linux
        # saves that used a colon in this topic's filename.
        legacy_path = os.path.join(HELP_DIR, entry["primary_keyword"].strip().lower().replace(" ", "_") + ".json")
        if legacy_path != path and os.path.isfile(legacy_path) and not os.path.isfile(path):
            os.replace(legacy_path, path)
        if not os.path.isfile(path):
            save_entry(entry)
        elif entry["primary_keyword"] in ({"jobs", "farm", "fish", "mine", "chop", "cook", "oset", "area", "channel", "barrier", "sharingan", "mstat", "bloodstat", "ninjutsu", "genjutsu", "taijutsu", "taijutsu strikes", "bukijutsu", "demonic illusion", "narakumi", "summon", "sage", "summon elder", "damage messages", "track", "shadow clone jutsu", "lottery"}
                                           | _ELEMENT_HELP_TOPICS | _RELEASE_HELP_TOPICS
                                           | _recent_pages.keys() | set(_EXPANSION_HELP_KEYS)
                                           | _SCALED_DAMAGE_HELP_TOPICS | {"attributes", "combatstats", "scoresheet", "kekkei genkai", "hyuga", "camouflage", "scan", "unleash beast", "hidden mist jutsu", "jinchuriki", "perform", "jutsu all", "skills", "vperk"}):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if (existing.get("updated_by") == "System" and
                    any(existing.get(field) != entry[field] for field in ("body", "keywords", "title"))):
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
    entries = all_entries()
    # An exact page wins over a broad overview's alias, even when the
    # overview's filename sorts first (e.g. taijutsu strikes / Choku Zuki).
    for entry in entries:
        if query == entry["primary_keyword"].lower():
            return entry
    for entry in entries:
        if query in [k.lower() for k in entry.get("keywords", [])]:
            return entry
    # A player can cast an unambiguous abbreviated jutsu name, so the same
    # name should find its individual help page ("help jubaku", "help kihon").
    # Require the entire query to be consumed: an extra word must not resolve
    # to an unrelated jutsu page, and ambiguous prefixes stay unresolved.
    key, consumed = data_jutsu.match_prefix(query.split())
    if key and consumed == len(query.split()):
        primary = next((entry for entry in entries
                        if entry["primary_keyword"].lower() == key), None)
        return primary or next((entry for entry in entries
                                if key in [name.lower() for name in entry.get("keywords", [])]), None)
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
    import mangekyo_discovery
    import lightsabers
    if not args:
        _show_help_index(session)
        return
    entry = find_by_keyword(" ".join(args))
    if not entry or not mangekyo_discovery.can_read(session, entry) or not lightsabers.can_read(session, entry):
        session.send("This helpfile doesn't exist, contact an admin to create it.")
        return
    lines = [f"&Y{entry['title']}&x", "", entry["body"]]
    names = [entry["primary_keyword"], *entry.get("keywords", [])]
    key = next((name.lower() for name in names if name.lower() in data_jutsu.JUTSU), None)
    if key:
        lines.extend(("", "&COne-word shortcut:&x " + data_jutsu.JUTSU_SHORTCUTS[key]))
    if len(entry.get("keywords", [])) > 1:
        lines.append("")
        lines.append("&D(Keywords: " + ", ".join(entry["keywords"]) + ")&x")
    jutsu_colors.send(session, "\n".join(lines))


def _show_help_index(session) -> None:
    import mangekyo_discovery
    import lightsabers
    lines = ["Type 'commands' for a full list of commands."]
    entries = [entry for entry in all_entries() if mangekyo_discovery.can_read(session, entry)
               and lightsabers.can_read(session, entry)]
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


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "mpedit",
    "keywords": ["mpedit", "mob program", "mobprog", "mprog", "mpstat",
                 "rpedit", "rpstat", "opedit", "opstat", "mpset",
                 "smaug scripts", "smaugfuss programs"],
    "title": "Multiline Mob, Room and Object Programs",
    "body": (
        "Syntax (Builder or higher with area access):\n"
        "  mpedit <mob vnum> <greet|speech|fight|death|random|move|give|bribe|entry> [speech keyword]\n"
        "  mpedit <mob vnum> #<script index>  |  mpstat <mob vnum>\n"
        "  mpset <mob vnum> <script index> <chance 1-100>\n"
        "  rpedit <enter|random>  |  rpedit #<index>  |  rpstat\n"
        "  opedit <item vnum> <get|wear>  |  opedit <vnum> #<index>  |  opstat <vnum>\n"
        "  rset flags no_wander  (toggle protected NPC roaming destination)\n\n"
        "Multiline editor: type one script instruction per line; use /l to list, /c to clear, "
        "/a to cancel, /s or a single period to save. Save world when finished.\n\n"
        "Branching: if level($n) < 10, or ..., else, endif. Nested branches allowed. "
        "Other conditions: rank($n), clan($n), room($n), ryo($n), name($n), "
        "hasitem($n, 9101), random(25), ispc($n), direction($d), "
        "object($o), bribe($b), hitprcnt($i), health($n), chakra($n), stamina($n), "
        "roomflag($r, no_wander), remembered($n, academy_pass).\n"
        "Commands: say, emote, mpecho, mpechoat, mpechoaround, "
        "mpgive, mpheal, mptransfer, mpgoto, mpmload, mpoload, "
        "mpforce $n <approved game command> (or legacy mpforce <command>), "
        "wait 1-120 (non-blocking), "
        "mphealmana/mphealchakra, mphealmove/mphealstamina, mpdamage, mpasound, mpjunk, mpremember, mpforget.\n"
        "Variables: $n player, $i NPC, $r room, $v mob vnum, $d direction, "
        "$o given object, $b bribe amount. Double-dollar $$ emits a literal dollar.\n\n"
        "Legacy addprogram remains supported. To remove programs use mset/oset/rset "
        "removeprogram with the zero-based index. Give items with 'give <item> <npc>'; "
        "offer ryo with 'bribe <amount> <npc>'. All scripts are validated sandboxed "
        "data and cannot execute Python, shell commands or privileged commands.\n"
        "More details: docs/SMAUG_MOB_PROGRAMS.md (shipped with Nindo_mud source)."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "no_wander",
    "keywords": ["no_wander", "nowander", "no wander", "room wandering",
                 "rset flags no_wander"],
    "title": "Room Flag: No Wander",
    "body": (
        "Builder syntax: rset flags no_wander\n"
        "Toggles the no_wander flag on your current room. Use rstat to "
        "inspect room flags and save world to persist your changes.\n\n"
        "Ordinary mobs with the Wander act flag, and randomly roaming "
        "tailed beasts, will never pick this flagged room as a random "
        "exit destination. They can choose other eligible exits instead. "
        "When every destination is blocked they stay put, then retry "
        "at their own next independent movement time.\n\n"
        "no_wander does not affect players, existing monsters, deliberate "
        "spawns, summoned allies, or explicit scripted mob movement. "
        "Monsters already inside a no_wander room may still wander out. "
        "This flag is also available in the offline Nindo_mud visual "
        "area builder's room flag selector, and remains in area exports."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "force",
    "keywords": ["force", "immortal force", "mpforce", "mforce", "force all"],
    "title": "Immortal Force / Mob Program MPforce",
    "body": (
        "Immortal command (Helper rank or higher):\n"
        "  force <online player name> <allowed player command>\n"
        "  force Sakura north\n"
        "  force Sakura say Prepare for the Chuunin Exams!\n"
        "  force Sakura @yawn\n"
        "  force Sakura attack bandit\n"
        "Administrators and Implementors only (limited safe social actions):\n"
        "  force all say The Chuunin Exams have begun!\n\n"
        "Mob program script command:\n"
        "  mpforce $n <allowed player command>\n"
        "  mpforce $n north\n"
        "  mpforce $n say Welcome, student.\n"
        "  mpforce $n attack bandit\n"
        "  mpforce look  (older shorthand; targets triggering player)\n\n"
        "Forces a normal command through the target player's real command "
        "dispatcher, not a fake movement or action. Regular game rules and "
        "checks still apply. Only online ordinary player characters in the "
        "PLAYING state may be forced; staff, offline characters and "
        "characters in editors cannot be forced. The target receives a "
        "notification, and immortals' successful force actions are audited.\n\n"
        "Allowed: directional movement, look/scan, say/ask, native @social "
        "emotes, information/status commands, rest/sleep/stand, recall, "
        "ordinary combat attack/kill/flee and perform. Staff, account, "
        "bank/economy, equipment drop/trade/purchase, save, quit, world "
        "editor, force and other privileged commands are blocked. "
        "Recursive force loops are blocked. Bulk force all is limited "
        "to 50 ordinary players and basic harmless social/status commands.\n\n"
        "Full documentation: docs/SMAUG_MOB_PROGRAMS.md."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "ryo",
    "keywords": ["ryo", "drop ryo", "get ryo", "give ryo", "currency piles"],
    "title": "Physical Ryo and Player Payments",
    "body": (
        "Ryo can be carried in your wallet or left as physical coin piles.\n\n"
        "drop 500 ryo -- take 500 Ryo from your wallet and leave one pile.\n"
        "drop all ryo -- drop your entire wallet as one pile.\n"
        "look ryo -- examine a pile on the ground.\n"
        "get ryo -- collect the first pile into your wallet.\n"
        "get 500 ryo -- collect a pile worth exactly 500.\n"
        "get 2.ryo -- collect the second pile in a room.\n"
        "get all ryo -- collect every Ryo pile in the room.\n"
        "give 500 ryo <player> -- pay another player in your room.\n"
        "give all ryo <player> -- hand over your entire wallet.\n\n"
        "All amounts must be positive whole numbers and cannot exceed "
        "the Ryo you possess. Physical piles persist across server restarts; "
        "picking up Ryo does not require an inventory item slot."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "colorscheme",
    "keywords": ["colorscheme", "roomscheme", "room colors", "global colors"],
    "title": "Global Room Color Scheme (Administrator+)",
    "body": (
        "Syntax: colorscheme\\n"
        "        colorscheme name <0-255>\\n"
        "        colorscheme desc <0-255>\\n"
        "        colorscheme exits <0-255>\\n"
        "        colorscheme set <name> <desc> <exits>\\n"
        "        colorscheme show | colorscheme preview | colorscheme reset\\n"
        "Aliases: roomscheme; name/title/roomname, desc/description/roomdesc, "
        "exits/exit. You may use numeric colors or &[208] xterm tags.\\n\\n"
        "Administrator or Implementor access only. Changes affect EVERY "
        "player's future room look/scan display immediately. The command "
        "shows a preview of your current room after updating. Each accepted "
        "change is atomically and automatically saved in "
        "data/color_scheme.json, without needing save world. Colors are "
        "restored at server boot and survive reboots/crashes. Builder rooms "
        "and saved world/area files are NEVER rewritten by this command. "
        "Reset returns to Ember name 208, Sand description 223, and "
        "classic green exits."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "genin exam",
    "keywords": ["genin exam", "academy exam", "iruka", "graduation exam"],
    "title": "Iruka's Genin Graduation Exam",
    "body": (
        "Syntax: say Start Genin exam\n"
        "Answer: A, B, C or D, or answer A / answer B / answer C / answer D.\n"
        "Type cancel to abandon an active exam.\n\n"
        "To qualify: be an Academy Student at level 10 or higher and "
        "master all five fundamentals to 100%: Shadow Shuriken Technique, "
        "Dynamic Entry, Demonic Illusion: Hell Viewing Technique, "
        "Throw Shuriken, and Strong Fist Style. Strong Fist Style grows "
        "through combat, not normal practice.\n\n"
        "Iruka (mob VNUM 11) must be present. Each try chooses a fresh "
        "set of 10 questions from 20 canonical Naruto anime questions; "
        "the four answer positions are shuffled independently. "
        "All 10 must be answered correctly. One wrong answer fails "
        "the attempt, without rewards. You may retry while qualified. "
        "Passing earns Genin rank, the Genin headband, 50 mission points "
        "and the global rank-up announcement."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "clone control",
    "keywords": ["clone", "clone control", "clone disperse", "clone scout",
                 "elemental clone reconnaissance", "reconnaissance"],
    "title": "Mastered Elemental Clone Reconnaissance",
    "body": (
        "Syntax: clone control  |  clone status  |  clone disperse\n\n"
        "Master one elemental clone jutsu to 100% practice: "
        "Raiton Kage Bunshin, Mizu Bunshin, Deido Bunshin or Suna Bunshin. "
        "First create the clone with 'perform <elemental bunshin>'. "
        "Shadow Clone Jutsu 100% is still required to create it.\n"
        "You cannot enter clone control during combat, while being attacked "
        "by another player, or while casting/performing a timed action.\n\n"
        "Once connected, directions physically move the actual clone Mob "
        "through the game while YOUR ORIGINAL BODY stays in the room where "
        "you cast it. The clone looks/scans/examines, speaks and uses socials "
        "from its location, but does not fight or use your body equipment. "
        "Clones show your normal name and description; players looking at "
        "either your clone or your original body see an ordinary character. "
        "Clone speech and socials appear to come from you normally. "
        "Movement displays the room once, without duplicate travel echoes. "
        "Your original body is exposed and helpless while you're connected. "
        "The clone can be attacked and loses its own HP.\n"
        "There is no free 'return' or exit command while linked. "
        "'clone disperse' destroys the clone and restores your viewpoint. "
        "The same happens when its HP reaches zero in combat or when Chakra "
        "upkeep causes the clone to disperse. Logout/reboot does not save "
        "the link; your real body never moves in player saves.\n"
        "An aggressive NPC can attack your real clone while scouting. "
        "Room no_wander flags do not block intentional clone movement."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "aggressive mob",
    "keywords": ["aggressive", "aggressive mob", "aggressive_village",
                 "aggressive_clan", "aggressive_everyone", "mob aggro",
                 "mset aggro_village", "mset aggro_clan"],
    "title": "Mobile Aggression Flags",
    "body": (
        "Mob builder commands:\n"
        "  mset <mob vnum> flags aggressive_everyone\n"
        "  mset <mob vnum> flags aggressive_village\n"
        "  mset <mob vnum> aggro_village leaf\n"
        "  mset <mob vnum> flags aggressive_clan\n"
        "  mset <mob vnum> aggro_clan uchiha\n\n"
        "aggressive_everyone attacks any online ordinary player who comes "
        "into the NPC's room. aggressive_village attacks only players "
        "belonging to the configured target village; aggressive_clan "
        "attacks only players belonging to the configured target clan. "
        "Multiple flags combine; either matching village OR clan makes "
        "the mob hostile. A village/clan flag without a configured target "
        "does not attack anyone on that basis. Set a target to off to "
        "clear it; use mset flags -aggressive_everyone to remove a flag.\n"
        "Automatic aggression starts normal NPC combat and keeps existing "
        "loot, XP and death rules. Safe rooms, staff players and protected "
        "NPCs are exempt. Hostile mobs will also physically attack a "
        "matching player's controlled elemental clone if they encounter "
        "one. Save world to preserve the prototype flags.\n"
        "Flags and target fields are available in the offline visual builder."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "bribe",
    "keywords": ["bribe", "bribe npc", "give ryo npc"],
    "title": "Bribe an NPC",
    "body": (
        "Syntax: bribe <ryo amount> <npc name>\\n\\n"
        "Offer ryo to a non-player character with a bribe-triggered "
        "mob program. The ryo is deducted and the NPC may respond with "
        "dialogue, a quest action, or a conditional reward. Builders can "
        "use mpedit <vnum> bribe and if bribe($b) >= 500 to configure "
        "the response. NPCs without a matching bribe trigger refuse. "
        "See help mpedit for multiline scripting."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})

DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "delete",
    "keywords": ["delete character", "character deletion", "delete account"],
    "title": "Delete Your Character",
    "body": (
        "Syntax: delete <password> <password>\\n\\n"
        "Permanently deletes your own character and account. Both copies of "
        "your account password must match, and the password must be valid. "
        "Only ordinary player accounts can use this command; staff cannot. "
        "This action is permanent and cannot be undone. Your connection "
        "closes after successful deletion. Do not use this command unless "
        "you intend to lose this character and its saved progress."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


DEFAULT_HELP_ENTRIES.append({
    "primary_keyword": "hyuga",
    "keywords": ["hyuga", "hyuuga", "byakugan", "gentle fist", "eight trigrams", "tenketsu", "tenseigan"],
    "title": "Hyuga Bloodline and Byakugan Techniques",
    "body": (
        "Every Hyuga inherits the Byakugan Kekkei Genkai. Its starting "
        "inheritance is guaranteed, but each character secretly rolls their "
        "own permanent Potential (how far the eye can evolve) and Talent "
        "(how quickly mastery grows). Not every Hyuga can master the highest "
        "techniques. Existing Hyuga missing the old inheritance roll receive "
        "their bloodline on login without rerolling earlier lucky characters.\n\n"
        "Awakening: at level 25 or higher, Byakugan has the normal hidden "
        "1-in-300-per-round chance to awaken during real combat. The eye does not reveal itself "
        "early or grant combat perks until awakened.\n\n"
        "Commands: byakugan [on|off|status], byakugan scan <direction>, "
        "hyuga list, jutsu all, prac, and perform <technique> [target]. "
        "Byakugan is a chakra-upkeep toggle. See enemies' chakra and peer "
        "several rooms ahead without bypassing sealed exits or private homes. "
        "Active Byakugan (level 25+) improves accuracy and evasion. Gentle Fist techniques "
        "directly reduce chakra or stamina and may briefly close tenketsu, "
        "preventing jutsu use. Eight Trigrams Rotation and Protecting "
        "Sixty-Four Palms grant short-lived defensive effects.\n\n"
        "Advanced: progressive Vacuum Palm, 128 Palms, Twin Lion Fists and "
        "361 Palms require combat-earned mastery and level milestones. "
        "Only Potential 95+ can reach Celestial Byakugan and Fate Sight "
        "at level 100, with substantial chakra upkeep. The mythical "
        "Tenseigan Chakra Mode and Silver/Golden Wheel techniques require "
        "the absolutely rarest Potential 100 character, level 100, and "
        "full bloodline mastery; Tenseigan protection only lasts a few "
        "combat pulses before the form ends. These celestial endgame "
        "powers are NindoMUD adaptations, not standard clan techniques.\n\n"
        "Learning: new bloodline techniques appear on level-up, on login "
        "for eligible older characters, and whenever an awakened and "
        "active Byakugan grows through combat. Most individual attacks "
        "must be practiced once with a teacher before use; Byakugan "
        "activation itself does not require that first lesson."
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
})


# Every distinct Hyuga move has its own searchable helpfile and one-word
# shortcut, just like ordinary jutsu; the general "help hyuga" page is
# deliberately not a substitute for specific individual move references.
import hyuga as _hyuga_help
for _hyuga_key, _hyuga_spec in _hyuga_help.REGISTRY.items():
    _mode = _hyuga_spec["jutsu_type"] == "hyuga_mode"
    _requires = (
        f"Minimum level {_hyuga_spec['level_requirement']}, "
        f"Byakugan mastery {_hyuga_spec['hyuga_mastery']:.0%} and "
        f"inherited Potential {_hyuga_spec['hyuga_potential']} or higher. "
    )
    DEFAULT_HELP_ENTRIES.append({
        "primary_keyword": _hyuga_key,
        "keywords": [_hyuga_key, _hyuga_spec["display_name"].lower(),
                     data_jutsu.JUTSU_SHORTCUTS[_hyuga_key]],
        "title": _hyuga_spec["display_name"],
        "body": (
            f"Syntax: {'byakugan [on|off|status|scan <direction>]' if _hyuga_key == 'byakugan' else 'perform ' + _hyuga_key + (' [on|off]' if _mode else ' [target]')}\n\n"
            + _requires
            + ("This toggles Byakugan or a short-lived defensive/celestial form. "
               "Higher modes have higher chakra upkeep. " if _mode else
               "This is a clan-exclusive Gentle Fist technique, dealing damage "
               "to the opponent and targeting chakra/stamina pathways. Successful "
               "hits may seal tenketsu briefly, stopping jutsu use. ")
            + "See 'help hyuga' for full bloodline rules. "
            + "A technique only becomes available when level, mastery, and "
            + "the character's permanent bloodline potential all qualify."
        ),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    })
