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

    rset flags no_wander             On the current room, toggle no_wander
    rstat                            Display current room flags

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
    if hitprcnt($i) <= 25
    if moblevel($i) >= 50
    if health($n) <= 50
    if chakra($n) <= 20
    if stamina($n) < 20
    if roomflag($r, no_wander)
    if remembered($n, academy_pass)

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
    mpforce $n look           Make triggering player look
    mpforce $n north          Make triggering player attempt north
    mpforce $n say TEXT       Make triggering player speak using real say
    mpforce $n attack NAME    Make triggering player attempt combat
    mpforce $n @yawn          Make triggering player perform a real social
    mpforce look              Old Nindo_mud shorthand for mpforce $n look
    mpforce say TEXT          Old Nindo_mud shorthand for mpforce $n say TEXT
    mpforce emote TEXT        Legacy custom room-emote narration remains supported
    wait SECONDS              Non-blocking script delay (1–120 s)
    mphealmana AMOUNT         Recover triggering player's chakra (also mphealchakra)
    mphealmove AMOUNT         Recover triggering player's stamina (also mphealstamina)
    mpdamage AMOUNT           Damage player without bypassing defeat flow (minimum 1 HP)
    mpasound TEXT             Announce to adjacent occupied rooms
    mpjunk ITEM_VNUM          Remove one matching room ground item (or all, up to 20)
    mpremember KEY            Remember the triggering player on this NPC prototype
    mpforget KEY              Clear the player's remembered marker

Triggers: mob greet/speech/death/fight/random/move/give/bribe/entry;
room enter/random; item get/wear; mob entry when an NPC enters a
player-occupied room by roaming or an explicit scripted NPC move.

Players can trigger the new give event by handing an item to a matching
scripted NPC with give ITEM NPCNAME. The item leaves the player's
inventory. The bribe event uses bribe RYO NPCNAME; ryo is deducted before
the script runs. Conditions object($o) and bribe($b) inspect these values.
Existing player-to-player give and player-shop stocking take priority.

The **no_wander** flag affects NPC exits, not player movement. Mark a
room using `rset flags no_wander` or the visual room flag picker, then
`save world`. Roaming Wander mobs and roaming tailed beasts cannot enter.
Mobs already inside can leave; scripted `mpgoto`, scripted spawning,
and intentional manual spawning are not blocked.

NPC quest memory uses `mpremember academy_pass` followed by
`if remembered($n, academy_pass)`. These markers are saved in the
mob template by `save world`, shared by all instances of that VNUM.
`mpforget academy_pass` clears one player's marker.

`wait 5` delays just that particular program continuation, allowing
further lines and nested branches to resume on normal one-second server
pulses; it does not block other players or the server. Delays are
transient and canceled on disconnect/restart. Limits are 120 seconds
per wait, 300 total seconds per invocation, and eight pending
continuations per player.

A 15% per-pulse random check is retained before mob/room random scripts
are considered; a script's own configured chance is applied additionally.

## Force and MPforce: character command execution

An immortal can force an **online ordinary player** to perform a permitted
player action:

    force Sakura north
    force Sakura say I am ready for the Chuunin Exams!
    force Sakura @yawn
    force Sakura attack bandit

Immortals with Helper rank or higher can use the command. Matching is
case-insensitive and requires a unique online name. Target must be in the
playing state (not in a menu/editor). NPCs and offline players are not
valid targets. **Forcing staff characters is never allowed.**

Administrator and Implementor ranks can additionally use a limited
bulk form, e.g.:

    force all say The Chuunin Exams begin!

Bulk force is limited to 50 non-staff players and safe
look/say/emote/stand/wake/rest commands. It cannot mass-attack or
mass-transfer the server. Every successful immortal force is audit
logged and each affected character is told who forced which command.

In an NPC script, use the SmaugFUSS selector `$n`:

    mpforce $n north
    mpforce $n say I accept the challenge!
    mpforce $n kill bandit

`mpforce` can only target the triggering player, never `all` or staff,
and never arbitrary other accounts. A legacy no-selector
`mpforce say TEXT` or `mpforce look` still targets the triggering player.
Legacy freeform `mpforce emote TEXT` still narrates the custom emote
without executing a privileged command.

Forced actions run through the ordinary game dispatcher, so movement
restrictions, combat checks, and resource requirements still apply.
The approved action list supports movement/directions, look, say,
ask, native `@social` emotes, basic status/information commands,
rest/sleep/stand, recall, combat attack/kill/flee, and `perform` for
ordinary player jutsu. Account, staff, world-builder, economy, item
transfer/drop, purchasing, quitting and reboot commands **cannot**
be forced. A reentrancy guard prevents a command from recursively
forcing another command. Future game commands are not implicitly
forceable; they must be explicitly reviewed and allowlisted.

## Safety and persistence

Scripts never execute Python or unrestricted commands, cannot access
the filesystem or network, and do not get staff permissions. mpforce uses only the reviewed player-action allowlist,
including combat and movement, and never allows staff/account actions. 12,000 script characters, 160 lines,
eight nested conditions, 60 executed actions and four recursive invocations
are the upper bounds. At most two scripted loads can happen per program
execution, with additional live NPC/item population limits.

All new script entries are stored alongside legacy entries in the
existing room, mob or item prototype lists. They persist with save world.
Area import/export allows validated scripts while retaining stale-import
protection. Deploy code without replacing the live data directory.

**Current limitation:** This is the usable core of a SmaugFUSS-style
interpreter, not 100% parity. Some historical triggers and ifchecks,
the full ifcheck library, arbitrary mpforce commands and unrestricted
builder scripts have not been implemented.
