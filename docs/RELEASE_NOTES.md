# Nindo_mud release contents

This is a complete source release. Extract the archive into a copy of your
existing server installation, keeping the server's `data/` directory intact.

## Recent changes included

- Every registered jutsu now has an exact-name help lookup. Recent Taijutsu
  strikes and stances, Bukijutsu Ninja Arts, Mangekyo techniques, and the
  medicinal pill materials have individual pages. The Ninjutsu and Genjutsu
  expansion pages show actual damage, costs, cooldowns, and effects. System
  pages refresh on login while staff-written help text is preserved.
- Bukijutsu gains `samurai sabre` at level 35 while wielding a sword:
  it costs 35 Chakra and 10 Stamina and boosts normal sword hits 20% for
  five pulses. `flying swallow <target>` at level 45 requires a sword or
  kunai, costs 30 Chakra and 18 Stamina, gains +15 accuracy, can cause
  bleeding, and deals 15% more damage with Wind chakra nature. Both work
  against mobs; Flying Swallow also works against players where PvP is allowed.
- Taijutsu gains Empi (level 20) and Nidan Kyten Geri (level 30) as
  direct stamina strikes. Gates and their follow-ups remain on hold.
- Bukijutsu weapon arts now enchant, poison, or disenchant a wielded weapon
  directly. The property stays on that individual equipped item.
- Ninjutsu level 100 gains Nanairo no Rasengan: one cast sends seven
  separately rolled colors at a target. The caster's chakra nature strengthens
  its matching color; soul and dark can poison and blind. The original source's
  level requirement was beyond Nindo's level 100 cap, so this adapts it as a
  capstone with a single 120 Chakra cost and 25 second cooldown.
- Genjutsu pass: Insect Eyes reflects the target's actual attack damage and
  extra strikes. Frightened reduces damage dealt by both players and mobs;
  mob damage is reduced once per hit.
- Hidden Mist Jutsu is water-only Ninjutsu at level 40. `perform hidden mist
  jutsu` creates a 12-second effect on the room itself. Other occupants cannot
  see or target its caster. The caster gets +15 to hit and reduces a defender's
  dodge by 15 while in that room. It improves the chance of landing Ushiro,
  which still requires an unhurt target and cannot be used mid-fight.
- Bukijutsu level 25+ can `craft pill medicine <level>` or
  `craft pill antidote <level>` from one Medicinal Herbs. Level is chosen up
  to the crafter's current level and stored with each pill, visible in
  `examine` but not the item name. Antidotes cure poison only; Medicinal Pills
  restore Health, Chakra, and Stamina over 30 seconds without curing status
  effects. Indexed `use 2.pill` selects among different levels.
  Village general stores sell the herbs. Other classes
  cannot craft these pills, even at the general weapon/armor crafting unlock.
- Ninja Arts/Bukijutsu adds multi-throws, Demon Wind Shuriken, four delayed
  consumable traps, Trap Disabling, weapon poison/enchantment/disenchantment,
  wind-only Fan Techniques, and Water Release: Glue Technique. New item
  prototypes are stocked by village shopkeeper templates. Enchantments are
  attached permanently to individual weapon names, surviving normal saves.
  With a Mighty Fan equipped and wind chakra nature, use
  `fan techniques <target> <direction>` to push through an open exit.
- Puppet/Sanshōuo techniques were not included: uploaded C sources contain
  references to three puppet states but not their command implementations.
- Genjutsu gained 21 level-gated techniques, including Henge, object illusions,
  Chisei, Insect Eyes, Kokuangyō, and Nehan Shōja. Disguises and item decoys
  affect appearances without duplicating real items or player identities.
- Barrier reduces incoming damage by 10% across normal combat, jutsu, and
  damage-over-time effects. It no longer modifies Armor Class.
- Active Sharingan upkeep is doubled in and out of combat: 6 Chakra per idle
  tick, 6-12 Chakra per combat round by tomoe, and 6 Stamina per combat round.

- Colored damage words through 10,000+ damage: `damage_messages.py`, `colors.py`,
  `combat.py`, `commands.py`, and `mangekyo.py`.
- Shopkeeper stock and item prototypes saved by `save world` and restored after
  reboot: `world_persistence.py`, `storage.py`, and `world.py`.
- Area reset messages, missing mob respawns, and a 15-minute reset interval:
  `areas.py`, `spawn_points.py`, and `server.py`.
- Global `restore` and `respawn` commands, restricted mob classes, and builder
  tools including `ostat`: `admin_actions.py`, `data_classes.py`, `olc.py`,
  and `commands.py`.
- Progressive leveling, automatic level-sensitive mob XP, and migration of
  existing characters: `leveling.py`, `combat.py`, and `storage.py`.
- The in-game change history through version 15.259: `changelog.py`.
- Builder-configured Summon Elder mobs teach five separate Sage Modes. Set `mset <vnum> flags SummonElder` and `mset <vnum> summonfamily <family>`, then place the mob. Players sign a contract at level 20, and train at level 80, one attempt per family every 12 real hours with a 50% chance for 1% mastery. Full mastery permits the family's Sage Mode.
- Sage Mode toggles on/off with `sage` or `sage on <family>` and `sage off`. It stays active until turned off or resources fail, using 12 Chakra per idle 10-second tick and 16 Chakra plus 8 Stamina per combat round. The selected form survives reconnecting.
- Natural Health, Chakra, and Stamina regeneration now runs at 20% of the prior rate: a recovery tick about every 66.7 seconds instead of 13.3 seconds. Per-tick amounts and Chakra Control bonuses remain as configured.
- `mset fields` is now grouped and wrapped for a MUD client;
  `mset fields player` displays player fields separately: `olc.py`.
- Builder commands accept compact field names, including `flags`, `wear`,
  `wearloc`, `concap`, and joined spellings for the other fields.
  `train str`, `train con`, and the other stat abbreviations work: `olc.py`,
  `commands.py`, and `help_system.py`.
- Local `say` chat displays in bright green: `commands.py`.
- `eq`/`equipment` lists every wear slot, including empty ones: `commands.py`.
- Setting `weapontype` also sets `itemtype weapon` and `wearloc wielded`;
  its matching skill shows in `ostat` and is learned when equipped.
  `wear <weapon>` and `wear all` wield weapons: `olc.py`, `commands.py`,
  `data_weapons.py`.
- `oset` accepts direct `hitroll`, `damageroll`, and fixed base `damage`
  values; explicit damage replaces the weapon type default in combat.
- Shops reflect live item prototype edits by VNUM. Player shop stock links
  prototype items to their VNUM so name edits carry through to listings and
  purchases; older stock follows stored prototype name history.
- Staff release a random Tailed Beast with `unleash beast`; `release <player>`
  remains for Illusion Walk.
- Shop purchases require a player level at least equal to the item's level;
  listings show level requirements and rejected buys leave funds unchanged.
  Kage legendary item listings and purchases also follow prototype name edits.
- `mcopy <source> <new>` and `ocopy <source> <new>` copy complete prototypes
  to unused VNUMs, with independent nested fields and no automatic spawn.
- Reaching full resources does not trigger a recovery announcement; Sharingan's
  idle upkeep remains on its 10-second timer.
- Sharingan, shadow clone, Kamui, and tracking upkeep report their real resource
  cost whenever charged. Sharingan Genjutsu is retired; `shar` toggles Sharingan.
- Staff can use `mset <player> mangekyo on` or `bloodset <player> mangekyo yes`
  for an awakened Sharingan to roll two distinct eye techniques and save them.

Verification: `python3 -m unittest discover -p 'test_*.py'` and
`python3 test_smoke.py`. The tests cover damage tiers, shop persistence,
leveling, mob XP, and the older gameplay smoke checks.
