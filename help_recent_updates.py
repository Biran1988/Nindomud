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
         "counter or suffix. Ordinary non-crafted gear is unaffected.",
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
         "             mset <mob vnum> gate <exit>\n"
         "             mset <mob vnum> gateopen <hour> / gateclose <hour>\n\n"
         "A configured NPC can open or close a real linked gate depending "
         "on the 24-hour game clock, and merchants can close their shops. "
         "Door states are synchronized in both directions; unscheduled "
         "NPCs and doors are left alone. Use TIME to inspect the current hour.",
         "gate hours", "shop hours", "gate guards"),
    page("advanced tracking", "Advanced Tracking Jutsu",
         "Syntax: perform track <target>\n\n"
         "Advanced Tracking is a scroll-learned jutsu available starting "
         "at level 20. Once learned it extends the existing Track ability "
         "across area boundaries, as long as the target is reachable by "
         "connected exits. It does not bypass impassable doors, disconnected "
         "areas, or other movement restrictions. Without the upgrade, "
         "normal Track stays inside the current area.",
         "advanced track", "tracking scroll"),
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
    page("medicinal herbs", "Harvesting Medicinal Herbs",
         "Syntax: farm\n\n"
         "At Farming level 20 and above, using a hoe in a farmland biome "
         "has a small chance to harvest Medicinal Herbs in addition to "
         "regular crop farming. Each herb harvest grants 35 Farming XP. "
         "Herbs are used in existing medicinal pill crafting.",
         "herb farming", "herbs"),
    page("look equipment", "Viewing Other Players' Equipment",
         "Syntax: look <player>\n"
         "        look self\n"
         "        look <mob>\n\n"
         "LOOK shows what a visible character is wearing and holding: "
         "armor, accessories, wielded weapons, off-hand weapons and tools. "
         "It does not reveal the contents of their inventory or bypass "
         "invisibility and concealment.",
         "inspect gear", "worn equipment", "look player"),
]
