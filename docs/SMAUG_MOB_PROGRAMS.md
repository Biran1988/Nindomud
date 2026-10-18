# Nindo_mud multiline SmaugFUSS-style programs

Nindo_mud now supports bounded multiline, conditional scripts in addition to
existing one-action addprogram entries. This is a **SmaugFUSS-inspired safe
subset**, not a complete source-compatible implementation of every SMAUG
script trigger, command, and condition.

## In-game commands

    mpedit 5010 greet               Open multiline editor for a mob
    mpedit 5010 speech academy      Speech scripts require a keyword
    mpedit 5010 fight               Combat event
    mpedit 5010 death               Death event
    mpedit 5010 give                Item handed to NPC
    mpedit 5010 bribe               Ryo handed to NPC
    mpedit 5010 move                Attempted exit event
    mpstat 5010                     List full scripts and their indices
    mpedit 5010 #0                  Edit existing script number 0
    mpset 5010 0 30                 Give script number 0 a 30% chance
    mset removeprogram 5010 0       Delete program number 0

    rpedit enter                    Edit program in current room
    rpedit random
    rpstat
    rpedit #0
    rset removeprogram 0

    opedit 9101 get                  Edit object-prototype program
    opedit 9101 wear
    opstat 9101
    opedit 9101 #0
    oset removeprogram 9101 0

The in-game multiline editor already supports /l to list text, /c to clear,
/a to abort, and . or /s to save. Follow with **save world** to make scripts
persistent after reboot. All builder area/VNUM permissions remain enforced.

The offline HTML Area Builder also has a **Multiline SMAUG script** mode for
mob, room and item prototypes, editable alongside the legacy one-action form.
Export its area JSON and validate through the usual area import checks.

## Example: Academy examiner

Start with mpedit 5010 greet and type:

    if level($n) < 10
      say You must reach level 10 to attempt this exam, $n.
      mpechoat The examiner turns you away.
    else
      if hasitem($n, 9101)
        say Your exam permit is in order. Proceed!
        mptransfer 2500
      else
        say Bring your exam permit before entering.
      endif
    endif

Enter /s to save. All statements above belong to **one program**.

## Grammar

- One statement per line. Indentation is optional.
- if CONDITION / or CONDITION / else / endif, nested to eight levels.
- An or line must immediately follow if or another or, before any
  commands or nested blocks in that branch.
- Empty lines, * comment lines, and // comment lines are ignored.
- Conditions support numeric comparisons ==, !=, >, <, >=, <= and
  case-insensitive string comparisons == and !=.

Examples:

    if level($n) < 10
    if rank($n) == genin
    if clan($n) != uchiha
    if room($n) == 2500
    if ryo($n) >= 1000
    if name($n) == Naruto
    if hasitem($n, 9101)
    if random(25)
    if ispc($n)
    if direction($d) == north
    if object($o) == 9101
    if bribe($b) >= 500

Variables: $n = triggering player, $i = NPC or room/item speaker,
$r = player's room VNUM, $v = NPC template VNUM, $d = attempted move
direction, $o = item given to NPC, $b = ryo offered to NPC, $$ = dollar sign.

Approved commands:

    say TEXT                  NPC dialogue
    emote TEXT                NPC action in room
    mpecho TEXT               Message occupants of player's room
    mpechoat TEXT             Message triggering player
    mpechoaround TEXT         Message everybody but triggering player
    mpheal AMOUNT             Heal player (positive integer up to 10000)
    mpgive ITEM_VNUM          Give one item to player, respecting inventory cap
    mptransfer ROOM_VNUM      Move player to a normal, enabled room
    mpgoto ROOM_VNUM          Move the triggering mob to an enabled room
    mpmload MOB_VNUM          Spawn an ordinary NPC (per-room cap)
    mpoload ITEM_VNUM         Spawn ground item (per-room cap)
    mpforce look              Safely cause a look
    mpforce say TEXT          Narrate player's speech
    mpforce emote TEXT        Narrate player's action

Triggers: mob greet/speech/death/fight/random/move/give/bribe;
room enter/random; item get/wear.

Players can trigger the new give event by handing an item to a matching
scripted NPC with give ITEM NPCNAME. The item leaves the player's
inventory. The bribe event uses bribe RYO NPCNAME; ryo is deducted before
the script runs. Conditions object($o) and bribe($b) inspect these values.
Existing player-to-player give and player-shop stocking take priority.

A 15% per-pulse random check is retained before mob/room random scripts
are considered; a script's own configured chance is applied additionally.

## Safety and persistence

Scripts never execute Python or unrestricted commands, cannot access
the filesystem or network, and do not get staff permissions. mpforce is
limited to look, say and emote; its implementation does not route through
the privileged command dispatcher. 12,000 script characters, 160 lines,
eight nested conditions, 60 executed actions and four recursive invocations
are the upper bounds. At most two scripted loads can happen per program
execution, with additional live NPC/item population limits.

All new script entries are stored alongside legacy entries in the
existing room, mob or item prototype lists. They persist with save world.
Area import/export allows validated scripts while retaining stale-import
protection. Deploy code without replacing the live data directory.

**Current limitation:** This is the usable core of a SmaugFUSS-style
interpreter, not 100% parity. Historical wait timers, every SMAUG trigger,
the full ifcheck library, arbitrary mpforce commands and unrestricted
builder scripts have not been implemented.
