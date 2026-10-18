# Nindo_mud elemental clone reconnaissance and NPC aggression

## Elemental clone reconnaissance

Requires a living elemental clone that was actually summoned through an
elemental Bunshin jutsu, with **100% individual proficiency** in that
particular jutsu. Shadow Clone Jutsu must still have been mastered at 100%
for elemental clones to be created; it is not a substitute for mastery
of the corresponding elemental technique.

Supported live elemental clones:

- Raiton Kage Bunshin (lightning)
- Mizu Bunshin (water)
- Deido Bunshin (earth)
- Suna Bunshin (sand)

Commands:

    perform mizu bunshin
    clone status
    clone control
    north
    east
    look
    look bandit
    scan west
    say I have arrived.
    @yawn
    clone disperse

Taking control is forbidden while in PvE or PvP combat, when another player
is attacking you, when a clone is already fighting, when the character is
downed, or while another timed action is pending. This is a genuine
**reconnaissance**, not a second body that shares a full player inventory or
ability list:

- The real body stays physically in its original room, never teleports,
  and remains vulnerable to any attack there. Scout `look` uses a
  separate viewpoint copy so the original character object is never
  repositioned, not even temporarily during room inspection. The pilot
  can see and examine the original body when returning to its room,
  but **neither the pilot nor observers see a "motionless", "remote",
  or "controlling a clone" marker**. It appears as an ordinary player.
- Clone movement matches regular player movement: the pilot receives only
  the destination room view. Nearby observers see
  `<player> leaves <direction>.` and
  `<player> arrives from the <opposite direction>.` once each, with no
  `You guide your clone` message or repeated movement echo.
- Shadow and elemental clone Mob instances share the caster's visible
  name and description, even before entering clone control. They retain
  their own element data internally for combat/upkeep and physically walk
  through real enabled exits. `look` on the clone shows a normal character,
  and `say` / `@emote` use the caster's ordinary player name and formatting
  without exposing which body is speaking.
  It cannot enter disabled areas, private apartments, player shops,
  or bypass hidden/closed doors.
- The clone has its *own existing HP*, is fully attackable, and does not
  inherit the player's inventory, XP, or permanent character status.
- Its player cannot use attacks, jutsu, flee, recall, equipment changes,
  account commands, builder commands, or other physical-body actions
  until the connection ends. The original body does not autoattack.
- While in control there is **no manual return** or free switching.
  Only **clone disperse** or the clone's destruction ends the
  connection. Chakra upkeep continues; if Chakra runs out the clone
  disperses, ending control as a natural side effect.
- If another player or an aggressive NPC defeats the clone, it poofs
  immediately without a corpse, XP, or ryo reward and the player's
  viewpoint returns to their living original body.
- Clone control is a **transient Session state**, never a saved
  character room change. Disconnect/restart destroys the connection
  and reconnecting loads the player's original physical location.

The room flag no_wander only blocks ambient random NPC movement; it does
not block deliberate clone scouting.

## Automatic NPC aggression flags

Builders can add three real, attack-triggering mobile prototype flags:

    mset 5010 flags aggressive_everyone

    mset 5011 flags aggressive_village
    mset 5011 aggro_village leaf

    mset 5012 flags aggressive_clan
    mset 5012 aggro_clan uchiha

The village/clan settings are the **target identity**; they do not change
the mob's name, nationality or clan. Flags can be combined with OR
behavior. A village/clan flag with no target configured is inert, to avoid
hostile behavior from an accidental flag edit. The all-player flag needs
no target. Remove a flag by prefixing a minus, e.g.:

    mset 5010 flags -aggressive_everyone

Clear a target field using off:

    mset 5011 aggro_village off
    mset 5012 aggro_clan off

Existing mstat and mset fields output shows all flags and target fields.
All fields are part of the normal mob prototype and are persisted by
save world, the protected area JSON import/export and the visual area
builder. The HTML builder's mob flag dropdown includes the three flags,
and its mob Full Prototype Properties include aggro_village and
aggro_clan target text.

When a matching online ordinary player enters or is in the mob's room,
the NPC automatically initiates a regular PvE fight via the same engine
as a player-initiated fight. Existing fight/defeat/XP/loot systems work
normally. NPCs do not initiate aggression in PvP-safe rooms, player
apartments or player shops. Staff, incapacitated characters, immortal
mobs, teachers, bankers/shops and other protected NPCs are excluded
from automatic aggression.

While scouting, a qualifying aggressive NPC can attack the actual
controlled elemental clone in its room every five seconds. Damage
comes off **clone HP**, not character HP, and the connection ends when
the clone is destroyed. An enemy physically beside the caster's real
body can independently initiate combat against that body; the caster
cannot defend via body commands while linked, so recon is risky.

Do not overwrite deployed data/world_state.json or live area files when
deploying a new code revision. Save your world normally from inside the
game using save world.
