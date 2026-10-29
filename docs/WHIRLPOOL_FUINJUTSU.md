# Whirlpool Fuinjutsu — staff reference

These jutsu are restricted to characters who belong to the Whirlpool village
**and** the Uzumaki clan. The village is intentionally absent from public
creation menus and normal help indices. Do not include this document or any
sealing jutsu in a public changelog, teaser, menu, or event announcement.

The techniques are automatically learned at the indicated character level,
including when an older character next logs in. As with ordinary techniques,
each requires one lesson from a teacher before its first use. New spells are
listed under `jutsu all` when learned, and can be cast with `perform ...` or
stable one-word shortcuts. Active suppression is checked for every jutsu path.

## Target seals

| Level | Name / usage | Chakra | Duration / effect |
| --- | --- | ---: | --- |
| 25 | `perform chakra suppression seal <player>` | 42 | Blocks Ninjutsu for 18 seconds, not Genjutsu |
| 35 | `perform mind suppression seal <player>` | 46 | Blocks Genjutsu for 18 seconds, not Ninjutsu |
| 40 | `perform binding formula seal <player>` | 34 | Roots target for 10 seconds; no movement/stamina loss |
| 45 | `perform chakra siphon seal <player>` | 50 | Removes up to 20% of target max Chakra and refunds half to caster |
| 55 | `perform chakra lock seal <player>` | 55 | Stops Chakra Charge and natural chakra regeneration for 20 seconds |
| 60 | `perform hand sign suppression seal <player>` | 70 | Blocks Ninjutsu, Genjutsu, and Whirlpool seal casting for 11 seconds |
| 65 | `perform seal release <self|player|barriers>` | 40 | Clears temporary Whirlpool target seals or remotely dismisses all caster-owned barriers |

Target seals only affect live players in the same room, and never apply in a
PvP-safe room. Already active effects cannot be refreshed prematurely.
They last for real time; reconnecting does not reset the expiration time.
Seal Release does **not** open the Reaper Death Seal or release Tailed Beasts.

## Exit walls

| Level | Name / usage | Initial cost | Lifetime |
| --- | --- | ---: | --- |
| 30 | `perform flowing barrier seal <direction>` | 36 Chakra | 6 Chakra every 5 seconds, indefinitely while the caster is online |
| 50 | `perform timed barrier seal <direction>` | 75 Chakra | 180 real seconds |
| 70 | `perform imbued barrier seal <direction> <chakra>` | 50–1000 Chakra | Imbued Chakra × 3 real seconds, maximum 30 minutes |

Each seals **one directed exit**. It does not affect the reverse direction,
transports, teleporting, or builder world editing. It blocks regular player
movement without charging stamina. A caster may move arbitrarily far away from
all wall types. Fixed and imbued walls remain even after logout and reboot;
flowing walls end upon logout/disconnection or insufficient Chakra.
No more than three active barriers may belong to a single caster. An exit
cannot carry more than one active Whirlpool barrier. Barriers cannot seal
safe rooms, destinations that are safe, nonexistent exits, or reaper prisons.
Staff may bypass them for moderation. If a builder removes or redirects an
exit, a barrier tied to the old exit is dissolved rather than sealing an
unrelated connection.

Durable barriers are written atomically to `data/whirlpool_barriers.json`;
they are **not** part of builder area files. Never overwrite the server's live
`data/` directory when deploying the code.

## Future jutsu concepts (not implemented yet)

- **Summoning Contract Seal** — temporary prevention of summons and creature control.
- **Chakra Anchor Array** — hold an enemy's chakra signature visible to a sensor for a short time.
- **Five-Point Reversal Seal** — remove a hostile curse or seal at significant chakra cost.
- **Weapon Containment Scroll** — store and later retrieve equipment from a designated scroll.
- **Barrier Reflection Formula** — return a portion of ninjutsu damage once, then shatter.
- **Eight Trigram Perimeter Seal** — advanced, high-cost seal that covers more than one exit.
- **Teleportation Anchor Seal** — suppress room-recall and space-time travel briefly, excluding staff.
- **Linked Sealing Array** — two Uzumaki coordinate an area-wide protective formation.
