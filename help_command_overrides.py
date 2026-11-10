"""Reviewed command help for verbs that lacked actionable usage instructions.

This table is sourced from the actual command handlers. It is consumed by
help_audit.populate at startup and does not replace staff-written data/help.
Keep syntax here synchronized with commands.py / olc.py when adding commands.
"""
from datetime import date


def page(syntax, description):
    return ("Syntax: " + syntax + "\n\nDescription: " + description
            + "\n\nDate: 2026-11-10")


# Primary commands whose dynamically generated pages previously just said
# "[arguments]" or "try the command with no arguments".
PAGES = {
    "mcreate": page("mcreate <vnum> <mob name>",
        "Builder+. Create a new mob prototype with the specified number and name; edit it with MSET. MCREATE is a convenience alias for MSET CREATE."),
    "ocreate": page("ocreate <vnum> <item name>",
        "Builder+. Create an object prototype with the chosen number and name, then set its properties with OSET. OCREATE is a convenience alias for OSET CREATE."),
    "rcreate": page("rcreate <vnum> [room name]",
        "Builder+. Reserve/create a room within your assigned area, move into it and optionally name it. Existing rooms are not replaced. See HELP RSET."),
    "mfind": page("mfind <name or keyword>",
        "Builder+. Find mob prototypes by a case-insensitive name or keyword and see their VNUMs. Use MSTAT <vnum> for details."),
    "ofind": page("ofind <name or keyword>",
        "Builder+. Search object prototype names/keywords and return VNUMs. Use OSTAT <vnum> for details."),
    "rfind": page("rfind <room name or description text>",
        "Builder+. Search live room names/descriptions for text and list matching VNUMs. Use GOTO <vnum> or RSTAT <vnum> for details."),
    "mlist": page("mlist [all] [low_vnum high_vnum]",
        "Builder+. List mob prototypes associated with the area you are standing in. ALL lists prototypes across registered areas; an optional inclusive VNUM range filters results. An area's mobs are identified by actual placements, not by requiring their prototype VNUM to fall in its room range."),
    "olist": page("olist [all] [low_vnum high_vnum]",
        "Builder+. List object prototypes belonging to the current area by actual spawns/shop stock. ALL lists all object prototypes; an optional VNUM pair filters the listing."),
    "rlist": page("rlist [all] [low_vnum high_vnum]",
        "Builder+. List all rooms in the current area. ALL includes the whole world. Optionally filter by a lower and upper room VNUM."),
    "minvoke": page("minvoke <mob vnum> [room vnum]",
        "Builder+. Spawn one live instance of an existing mob prototype into the current room, or the specified existing room. This does not create a new prototype or permanently change spawn points."),
    "oinvoke": page("oinvoke <object vnum> [room vnum]",
        "Builder+. Place an instance of an existing object prototype on the ground in your current room, or the specified existing room. Use OSET LOAD as another current-room method."),
    "mpstat": page("mpstat <mob vnum>",
        "Builder+. Show all programs attached to this mob prototype, their zero-based indices, triggers, chance and script lines. Edit with MPEDIT or MSET ADDPROGRAM; change execution chance with MPSET."),
    "rpstat": page("rpstat [room vnum]",
        "Builder+. List the current room's scripts (or another existing room VNUM), including indices, triggers and script lines. See RPEDIT, RSET ADDPROGRAM and RSET REMOVEPROGRAM."),
    "opstat": page("opstat <object vnum>",
        "Builder+. List programs on the selected object prototype, including triggers, indices and script lines. See OPEDIT and OSET ADDPROGRAM."),
    "mpset": page("mpset <mob vnum> <script index> <chance 1-100>",
        "Builder+. Set an existing mob script's trigger chance. Obtain its zero-based script index using MPSTAT. The selected entry must be a multiline script rather than a legacy single action."),
    "mpedit": page("mpedit <mob vnum> [script index] [trigger] [speech keyword]",
        "Builder+. Open the multiline mob-program editor for a new or existing script. Use MPSTAT to inspect current indices. Triggers include greet, speech, random, death and move. The editor accepts Smaug-style lines such as say, emote, mpecho, mptransfer, mpmload, mpoload, mpforce and if/or/else/endif. Save with /s; abort with /a. See HELP PROGRAMS."),
    "rpedit": page("rpedit [room vnum] [script index] [trigger]",
        "Builder+. Open the multiline room-program editor. Room programs can react to entry and random triggers. Use RPSTAT for script indices, /s to save and /a to abort. See HELP PROGRAMS."),
    "opedit": page("opedit <object vnum> [script index] [trigger]",
        "Builder+. Edit or create an object script using the multiline editor. Object triggers include wear and get; consult OPSTAT for indices. Use /s to save or /a to abort."),
    "practice": page("practice <learned skill or jutsu>  (alias: prac <name>)",
        "Spend one practice session with a teacher who teaches that skill's actual category. You must already know it. Practice raises proficiency to its teacher cap (usually 50%); using the technique raises it further. Ordinary newly unlocked jutsu must be practiced once before use; scroll-taught arts waive this first lesson, even if learned from another class. Passives train through combat rather than teacher sessions. PRAc without arguments shows your learned skills."),
    "battle": page("battle ready | battle ready config | battle ready status | battle ready <name> on|off",
        "Alias of BATTLE READY (also BREADY). Activate selected known combat preparations without re-casting ones already on. Each ability retains its own requirements, resource costs, cooldowns and first-practice gate. Configure which are included; off-class scroll-learned preparations can be included when otherwise eligible. See HELP BATTLE READY."),
    "eightgates": page("gates [status|safe|off|1..8 [confirm]]",
        "Alias of GATES. Taijutsu shinobi must unlock and practice each Gate. SAFE selects the highest currently learned safe Gate (1-7); OFF closes a closable Gate. The Eighth Gate requires explicit confirmation, cannot be closed, and ends in defeat. See HELP EIGHT GATES."),
    "jutsu": page("jutsu all | jutsu shorts  (also: skills all)",
        "ALL browses your primary class's current/future jutsu, shared abilities and any personally acquired techniques from other classes. SHORTS lists learned one-word shortcuts. Learned off-class scroll techniques appear under their original category. An entry's level indicates minimum unlock level, not guaranteed access. See HELP READ."),
    "inlay": page("inlay <forged item> with <cut gem>",
        "Place a cut gem into a uniquely forged weapon or armor in inventory. Hold the appropriate gemcutter's chisel and meet its job-level and stamina requirements; inlay consumes the gem and uses tool durability. Inspect the item afterward with EXAMINE. The inlay changes properties without adding a name suffix."),
    "clone": page("clone status | clone control | clone disperse",
        "Manage an elemental clone after summoning it. STATUS shows the connection. CONTROL transfers your viewpoint into an eligible clone if you are not in combat or busy; DISPERSE ends the control/clone. Clone control ends on defeat and does not permit normal player actions while scouting. See HELP SHADOW CLONE JUTSU."),
    "drop.all": page("drop.all  (equivalent to: drop all)",
        "Drop all eligible items carried in your inventory into the current room. Normal binding, restricted-item and room checks still apply. Use DROP <item> to drop one object instead."),
    "unfollow": page("unfollow  (equivalent to: follow off)",
        "Stop following your current leader. Leaving a follow relationship is separate from leaving an active combat GROUP; use GROUP LEAVE if you also want to exit that party."),
    "unjail": page("unjail <player name>",
        "Administrator+. Release the named jailed player early using the same return-to-village process as a naturally expiring jail timer. The player must currently have an active jail sentence."),
    "unsilence": page("unsilence <player name>",
        "Administrator+. Remove an active staff silence from the named player before its timer expires."),
    "unleash": page("unleash beast [tail number 1-9]",
        "Builder+. Spawn a real roaming Tailed Beast, randomly from available beasts or by requested tail count. Cannot release an already sealed beast. Does not erase the current holder's seal. See HELP UNSEAL for staff extraction."),
    "teleport": page("teleport halloween | teleport return",
        "Use the Halloween portal while the event is active and you are not in combat or jailed. RETURN takes you out of the event. This command cannot enter arbitrary rooms. See HELP HALLOWEEN."),
    "trickortreat": page("trickortreat",
        "Inside active Halloween Town, ask an eligible trick-or-treat NPC for one treat per Detroit calendar day per character, with an occasional trick. The event must be active."),
}


STAFF_GUIDE = {
    "primary_keyword": "immortal commands",
    "keywords": [
        "immortal commands", "imm commands", "staff commands",
        "builder commands", "staff guide", "immortal help"
    ],
    "title": "Immortal & Builder Command Reference",
    "body": (
        "Syntax: help immortal commands\n\n"
        "Description: This is the in-game reference index for authenticated staff. "
        "Most commands are role-gated; typing a command does not grant permission. "
        "Use HELP <command> for the full syntax and examples.\n\n"
        "&CHelper+:&x HEDIT CREATE/EDIT/LIST/SHOW, IP [name], FORCE <player> <safe command>, "
        "VPERK LIST/STATUS/<perk> ON|OFF, WIZINVIS ON|OFF|STATUS, "
        "UNSEAL LIST/<player>/MOB <beast>.\n"
        "&CBuilder+:&x AREA, GOTO, RSET/RSTAT/RCREATE/RFIND/RLIST, "
        "MSET/MSTAT/MCREATE/MFIND/MLIST/MINVOKE, "
        "OSET/OSTAT/OCREATE/OFIND/OLIST/OINVOKE, "
        "MPEDIT/MPSTAT/MPSET, RPEDIT/RPSTAT, OPEDIT/OPSTAT, "
        "SPAWNPOINT, PURGE, UNLEASH BEAST, MOBSCALE (higher rank required "
        "for administrator-only settings).\n"
        "&CArea Leader+:&x TRANSFER <player>, RETURN <player> for transferred players "
        "(subject to their destination/access checks).\n"
        "&CAdministrator+:&x BAN, SPY, RESTORE, JAIL/UNJAIL, SILENCE/UNSILENCE, "
        "LEVELUP <player>, SETALLPRAC, player-target MSET, MOB SCALE controls.\n"
        "&CImplementor:&x REBOOT performs a world save and a preflight before restarting; "
        "AREA EXPORTWORLD exports the map. MAKEIMM and PROMOTEIMM require the "
        "designated primary Implementor account, not merely the rank.\n\n"
        "&YIMPORTANT:&x Help pages describe syntax but do not bypass assigned-area "
        "limits, account authorization, audit logging, or persistent player data. "
        "Staff-written helpfiles are preserved when system reference pages update. "
        "Use HEDIT to maintain a custom help topic.\n\n"
        "Date: 2026-11-10"
    ),
    "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    "staff_only": True,
}
