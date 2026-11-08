# Nindo_mud release contents

## Permanent drag-and-drop update guarantee

Stop the MUD, unpack the complete release into the existing game program
directory, and overwrite program files. **Never replace, remove, package or
overwrite the live `data/` directory.** It holds saved players, accounts,
world edits, seal records, and staff-created content. Every release build
rejects archives containing `data/` entries; the overlay regression test
checks existing saves remain byte-for-byte intact. Keep the existing directory
and always make a backup before updating.

This is a complete source release. Extract the archive into a copy of your
existing server installation, keeping the server's `data/` directory intact.

## Recent changes included

- **15.447 Mission point scaling:** Each completed mission rolls a random point reward in its rank's overlapping band: D 1–5, C 4–9, B 7–13, A 11–17, S 15–20. Same payout for all mission types; S-Rank caps at 20, and `mission info` displays the range.
- **15.446 Mission fallback:** When no eligible rank-matched Mission mob exists, the game offers a randomized item-recovery or courier delivery objective. Both types also grant rank-based mission points.

- **15.445 Courier missions:** `mission request delivery <rank>` gives a unique sealed parcel bound to the requesting ninja. Deliver it to a real village NPC using `deliver` or `give parcel <npc>` within 30 minutes. Cargo cannot be dropped, traded, auctioned, sold or stored. This feature changes only source; all live `data/` files are preserved.
- **15.444 Eight Inner Gates:** Taijutsu levels 20/40/65/90/120/155/195/240 gain eight progressively stronger Gates with Stamina upkeep and higher-tier Health drain; the final Gate lasts 30 seconds and is fatal to the user. Six follow-up moves unlock across the Gates. `gates status`, `gates <1-8>`, `gates off`, `gates safe`; Eighth Gate requires explicit `gates 8 confirm`. Battle Ready only selects Gates 1-7 and is OFF by default.

- Visual area builder version 15.312: named browser autosave drafts, explicit save,
  a switchable project library, and portable `*.nindo-project.json` backup
  files. Work-in-progress backups are separate from game-ready area exports.
- Extended offline editor forms cover room programs, doors/locks/key items,
  shopkeepers and shop inventory, all persistent prototype attributes,
  class/teacher fields, item equipment and medical properties, mob/item programs,
  spawn caps, SMAUG dice overrides, and area treasury income.
- Server import/export now round-trips supported advanced settings with
  validation and stale-state checks; no runtime/player ownership data is exposed.
  Legacy basic packages still import. Existing live data/ and other builder-created
  areas are never replaced by this editor.
- The release workflow runs unit tests and builds `Nindo_mud.zip` via
  `scripts/build_release.py`; check the workflow result before deployment.


- Clan selection is mandatory during character creation. Choose a clan from
  your village; blank answers and `none` are rejected. Confirmation also checks
  the selection. Use `clan join <name>` later to switch to another valid clan.

- `gold` is an alias for `bank`. The daily `lottery` draws four digits every
  24 hours. Tickets cost 1,000 ryo, increase the jackpot, and a missed draw
  adds 25,000 ryo. Winning shares go into the players' banks; the next pot
  starts at 25,000 ryo.
- Mangekyo targets mobs. Kamui can also send its caster into a solo pocket;
  the caster can extinguish owned Amaterasu fire. Positive dodge bonuses are
  reduced by 10% while base Dexterity dodge remains intact.

- Administrator `mstat <player>` now names the player's assigned Mangekyo
  Eye 1 and Eye 2 techniques in the hidden Kekkei Genkai block.

- The archive includes individual JSON pages in `helpfiles/`, including
  `jubaku_satsu.json` and the three Taijutsu stances. Restart the Python
  server to seed them into its existing `data/help/` without replacing
  staff-written pages. `help jubaku`, `help kihon`, and other unambiguous
  jutsu abbreviations now resolve to their individual pages.

- In-game help now covers every executable command and every registered jutsu.
  New pages explain Izanagi, Izanami guessing, Tsukuyomi actions, Sage training,
  each family's Sage Mode, and combined Sharingan upkeep. Existing system-owned
  Sharingan and Barrier pages refresh with their current behavior.

- Barrier negates 25% of incoming damage for three minutes or until the player
  changes rooms, without changing Armor Class. Sharingan upkeep still charges on each combat or idle tick, but
  reports a combined Chakra and Stamina total every three minutes or when
  Sharingan turns off.

- Every registered jutsu now has an exact-name help lookup. Recent Taijutsu
  strikes and stances, Bukijutsu Ninja Arts, Mangekyo techniques, and the
  medicinal pill materials have individual pages. The Ninjutsu and Genjutsu
  expansion pages show actual damage, costs, cooldowns, and effects. System
  pages refresh on login while staff-written help text is preserved.
- Bukijutsu gains `samurai sabre` at level 35 while wielding a sword:
  it costs 35 Chakra and 10 Stamina and boosts normal sword hits 5% at level 35, with four automatic +5% passive tiers at levels 85, 140, 195 and 250 (maximum +25%) while the chakra upkeep is maintained. `flying swallow <target>` at level 45 requires a sword or
  kunai, costs 30 Chakra and 18 Stamina, gains +15 accuracy, can cause
  bleeding, and deals 15% more damage with Wind chakra nature. Both work
  against mobs; Flying Swallow also works against players where PvP is allowed.
- Taijutsu gains Empi (level 20) and Nidan Kyten Geri (level 30) as
  direct stamina strikes. Eight Inner Gates and follow-up attacks are
  implemented as of version 15.444 (see above).
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
- The in-game change history through version 15.261: `changelog.py`.
- Builder-configured Summon Elder mobs teach five possible Sage Modes. Set `mset <vnum> flags SummonElder` and `mset <vnum> summonfamily <family>`, then place the mob. Players sign one contract at level 20, and train at level 80, one attempt every real hour with a 5% chance for 1% mastery. Existing 12-hour waits are shortened on character load. Full mastery permits the chosen family's Sage Mode.
- A player's first signed summoning family is permanent. They can summon and study Sage Mode only with that family; old multi-contract saves retain the first valid signed contract. Ninken Sage Mode grants one extra ordinary attack per combat round instead of bonus dodge chance.
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

- Version 15.313 world-map editor: the offline builder accepts uploaded PNG/JPG/WebP
  backgrounds, displays and connects draggable area markers, imports many area
  packages or one full-world JSON file, and provides a portable backup containing
  map image plus linked area drafts. World map connections are visual only.
- Implementor `area exportworld` writes a complete map workspace under
  `data/world_exports/` without replacing individual area exports. The operation
  never changes rooms, mob data, or the live world; world bundles cannot be fed
  into the game's `area import` command. `test_world_map_export.py` covers this.

- Version 15.314: fixed still-apparent cohort mob wandering by giving every
  Wander mob a separately seeded RNG and its own spawn-time deadline,
  staggering nearby departures instead of shifting a whole room on a shared
  timer. Each live mob appears only once in the pulse snapshot; monsters with
  aligned due times in the same room are deferred independently. Staff can
  inspect that instance's timer with `mstat <mob name>` (or `2.name`).
  `test_independent_mob_wandering.py` covers independent clocks, same-time
  spawn waves, Sentinel override, combat pauses and single moves per pulse.

- Version 15.315 adds validated multiline Smaug-style scripts alongside
  unchanged one-action mob/room/item programs. Includes staff mpedit/mpstat,
  rpedit/rpstat, opedit/opstat, editable scripts in the HTML area builder,
  nested conditions, event variables, and safe scripted NPC actions.
  Fight, give, bribe and movement events now trigger NPC scripts.
  Saved templates and imported area packages retain bounded script data.
  Regression coverage is in test_smaug_progs.py. See
  docs/SMAUG_MOB_PROGRAMS.md for syntax and limitations.

- Version 15.316 adds the toggled `no_wander` room flag to rset and the
  HTML visual editor. It excludes protected rooms from ordinary Wander
  destination selection and tailed-beast roaming, but does not stop
  players, manual mob spawning, scripted movement, or leaving the room.
  The flag persists through save world and offline area imports.
- The Smaug-style script subset gains real non-blocking `wait` delays
  on server pulses, `entry` triggers for NPC movement, boss HP and
  room-flag condition checks, quest memory markers, area sound,
  additional resource effects, and bounded damage. Runtime and
  pending-continuation limits prevent blocking the event loop.
  See docs/SMAUG_MOB_PROGRAMS.md for supported syntax. Historical
  SMAUG commands and triggers not specifically listed remain unsupported.

- Version 15.317 adds immortal `force <player> <allowed command>` and
  SMAUG-style `mpforce $n <allowed command>`. Actions run under the
  online ordinary player's real game session, respecting combat and
  movement restrictions. Staff, account, bank/economy, quit/reboot,
  world-editor and destructive inventory commands are not forceable.
  Administrator/Implementor `force all` is restricted to basic social
  actions with a 50-character cap. Each forced target is notified, and
  immortal force commands are audit-logged. Legacy mpforce shorthand
  remains supported. Added targeted regression tests in
  `test_force_commands.py`.

- Version 15.318 adds `clone control` / `clone status` /
  `clone disperse` for a real, live elemental clone mastered at 100%
  proficiency in its specific elemental Bunshin skill. Entry is blocked
  during PvE/PvP combat and other pending actions. The player's original
  body never changes rooms and cannot execute combat/body commands while
  linked. The clone travels physically through real rooms and observes
  through its own location. The connection ends on explicit dispersal,
  the clone's defeat, insufficient Chakra upkeep, or disconnect.
- Mobile prototypes now support `aggressive_village`,
  `aggressive_clan`, and `aggressive_everyone` act flags. The first
  two require configuring `aggro_village` or `aggro_clan` target
  fields; matching either flag starts ordinary automatic PvE combat.
  Hostile mobs can also attack a player's remotely controlled scout
  clone, using the clone's real HP. Protected mobs, staff and safe rooms
  remain exempt. Flags and targets are available in mset and the
  visual builder. These changes use existing world save/import logic,
  never replace live data files. Tests: test_clone_recon_aggression.py.

- Version 15.320 improves the existing clone recon system without touching
  server world or area data: elemental clones now use their owner's visible
  name, the pilot's original body looks like a normal player (including
  `look <name>`), and other players see normal leave/arrive and speech/emote
  output rather than a clone label. The pilot receives one room view per
  movement with no extra guidance echo. The clone remains an independent,
  attackable Mob and its original caster stays at their physical location.
  Regression tests cover both viewing locations, speech, emotes and travel.

- Version 15.321 enables drop/pickup/transfer of any positive whole Ryo
  amount using real, numbered ground coin piles. Visible piles are ordinary
  room contents rather than mintable inventory names; picking them up credits
  their full balance and giving Ryo debits/credits the two players directly.
  Drop/get/give immediately save changed player wallets. A separate,
  auto-written data/ground_ryo.json file restores piles after startup,
  independent of save world and without replacing any builder room or area.
  Currency is intentionally excluded from world_state.json room snapshots
  to avoid double-spawning after reboot. Tests: test_currency_piles.py.

- Version 15.322: Iruka mob VNUM 11 alone conducts the Genin written
  examination. Five universal Academy techniques (Shadow Shuriken
  Technique, Dynamic Entry, Demonic Illusion: Hell Viewing Technique,
  Throw Shuriken and Strong Fist Style) require 100% proficiency, in
  addition to level 10. A random ten of twenty canonical Naruto anime
  questions appear per attempt with independently shuffled A-D options.
  Exactly ten correct answers are required; mistakes cancel that attempt.
  Legacy iruka_graduation_check programs now route to the exam, and normal
  set_rank genin mob actions cannot bypass it. Rewards keep the existing
  headband, 50 mission points and global announcement. No area or world
  files are changed. Regression tests: test_genin_exam.py.

- Version 15.323: Global room `look` output, including illusion-room
  previews and reconnaissance-room views, colors only the room name
  with xterm 114 (jade green) and description with xterm 253 (soft
  silver). Existing colors for exits, NPCs, mobs, items and combat
  stay unchanged. The official Iruka exam begins ONLY on the precise
  spoken `say Start Genin exam` command near mob VNUM 11. The older
  ask command and saved graduation mob program no longer start it.
  No player-built areas or world state files are modified.

- Version 15.324: Replaced the global room name/description theme with
  Ember & Sand: room titles are xterm-256 foreground 208 (#ff8700),
  room descriptions are xterm-256 foreground 223 (#ffd7af). Both go
  through the existing shared ui_palette helpers, so ordinary look,
  illusion rooms and scan use the new pair together. Other entity and
  navigation colors stay as-is; saved room/area/world content is not
  altered. Regression coverage: test_room_palette.py.

- Version 15.325: Introduced the administrator/Implementor-only
  `colorscheme` (alias `roomscheme`) live MUD-global palette command.
  Change title, description or exits independently with 0-255 xterm
  foreground IDs, change all three together, reset or preview the active
  room. Each valid edit atomically writes a separate synced
  `data/color_scheme.json` BEFORE changing the in-memory palette.
  The JSON file is restored at startup and is not part of `save world`.
  Builder-authored room and area files are never touched. No reboot is
  needed for changes; a player sees the colors next time they look.
  Regression coverage: test_live_color_scheme.py.

- Version 15.326: Improved all 20 preexisting mission-point Kage
  legendary items with character-specific, two-color xterm-256 names
  in shop lists, purchases, inventory, equipment and examine.
  This is presentation-only: item identifiers, stored short_desc,
  object VNUMs, prices and equipment slots have not changed.
  Nindo_mud retains prior bonuses and gains moderate combat-derived
  improvements on Deidara's pouches, Pain's piercings, Konan's flower,
  Tobi's mask, Kabuto's glasses and Jiraiya's forehead protector.
  Previously dormant hitroll/damroll prototype bonuses from nonweapon
  equipment now apply in combat. Armor Class respects existing
  negative Kage and positive headband protection conventions.
  Current bonuses on already-equipped items are recalculated live,
  so player saves do not need migration. Exact NarutoMUD external
  equipment stats are NOT known or claimed to have been reproduced;
  these additions use Nindo_mud's own combat balance. No changes to
  saved builder world/area data. Tests: test_kage_item_colors.py.

- Version 15.327: Fixed user-deployable release ZIP. Previously, the
  workflow built a standalone `Nindo_mud` server but uploaded only
  Python source, so installations launching an older standalone
  `./Nindo_mud` continued to run outdated code. Now the ZIP includes
  the freshly rebuilt runnable `Nindo_mud` file, source code, reference
  help and `UPDATE_INSTRUCTIONS.txt`. New test_release_archive.py
  asserts the ZIP contains both forms, latest features and no runtime
  `data/` files; it extracts and runs the bundled server's preflight.
  Extract into the live server folder and restart the actual running
  service. This changes NO player/area/world saves.

- Version 15.328: Restored the original user-requested distribution.
  The `Nindo_mud.zip` archive again contains only the normal Python
  source, tests, builder resources and reference helpfiles; there is no
  included standalone launcher, wrapper ZIP or extra installer.
  Deploy as before with `python3 main.py`. The release regression
  test extracts the complete archive and validates the usual
  `main.py --preflight` startup. All v15.325 color customization,
  v15.326 Kage item colors and combat bonus fixes remain included.
  No saved `data/` or user-built area/world files are overwritten.

- Version 15.329: Refined Kage legendary presentation to avoid visually
  noisy alternating bright names. Fourteen item names now use a single
  muted/controlled xterm-256 hue each. The original dual-tone names remain
  for Itachi's Ring, Tobi's Spiral Mask, Neji's Forehead Bandages,
  Deidara's Clay Pouches, Sakumo's White Fang Chakra Blade and Kakashi's
  Face Mask. The six selected palettes are unchanged from 15.326.
  This is a pure display update for the Kage `list`, inventory,
  equipped gear, purchase messages and examine. No stat or shop price
  changes, item prototype edits, or saved world/player/area rewrites.
  Source-only `Nindo_mud.zip` format is retained.

- Version 15.330: Finalized the latest requested hospital and sleeping
  healing changes: out-of-combat recovery continues everywhere;
  normal standing recovery is capped to prevent stamina-action exploits;
  sleeping is 3x the standing recovery (including at flat cap);
  accelerated_healing hospital rooms bypass the ordinary resource
  tick caps and recover at least 10x normal, with 30x when sleeping
  in the hospital, until resource maximums are reached. Includes
  compact exits, NPCs before ground items, sleep gating for look,
  and flag-based safe rooms. Corrected malformed unit test line
  continuations and ZIP build source, with no modification to
  saved builder-created rooms or areas.

- Version 15.331: The new account self-delete and skill-level EXP
  changes are documented and verified in the actual release archive.
  Non-staff players can issue `delete <password> <password>` to
  permanently remove their own character and login after password
  verification. Every actual 1% increase in practiced or used skill
  mastery, passive skill, or Shadow Clone mastery grants 10 character
  EXP; no gain at cap means no EXP. Combat-use and Shadow Clone
  growth visibly announce the EXP reward. Tests validate deletion
  and both experience paths against real isolated accounts, and
  ensure the executable/source archive contains both features,
  new help text and this version. No data/ folder or saved world,
  player or builder area content is packaged.

- Version 15.390: Standard auto-balanced mobs now spawn with **5x the
  original level-based HP baseline** at all levels (1-250). This reduces
  one-hit kills and preserves time for jutsu during longer fights. The
  adjustable `mobscale hp` percentage still applies on top of the new
  baseline and persists in existing `data/mob_balance.json`; outgoing
  mob damage is unchanged. Scripted bosses, manually exempted mobs,
  and the invulnerable training dummy keep their own behavior. Only
  newly spawned mobs receive updated stats. No player saves, world
  areas, or `data/` files are altered or packaged.

- Version 15.391: Tailed beasts (VNUM 95000–95008) are protected from
  ordinary mob HP scaling and the `mobscale` HP and damage modifiers.
  All nine beast registrations explicitly disable auto-balance and the spawn
  path refuses to auto-balance their reserved VNUMs, even if an old saved
  or builder-edited template flips the option back on. Each beast retains
  its distinct canonical maximum HP and attack dice as specified in
  `data_tailed_beasts.py`. Ordinary mobs still gain the 5x base HP.
  Sealing, capture timers, wandering, and live runtime `data/` are untouched.

- Version 15.392: The currently active EXP perk (24-hour immortal MUD-wide
  override or temporary Kage village purchase) now multiplies earned job
  experience for successful Fishing, Mining, Lumberjack, Farming, Cooking
  and Gemcutter actions, just like combat and mission XP. Double EXP grants
  2x, Triple EXP 3x; ordinary job XP returns to 1x as soon as the perk
  is turned off or expires. The effective multiplier is resolved when
  each action finishes, and job XP messages show the actual award. No
  separate stacked perk, new permanent multiplier, job level cap
  increase, or change to staff LEVELUP JOB. Runtime data/ is excluded.

- Version 15.393: Added `title <words>` (or `title set <words>`),
  `title color <name|0-255>`, and `title clear`. Validated titles up to
  40 characters appear after the real character name on global OOC chat,
  OOC emotes, and the persisted chatlog. Color is restricted to recognized
  named colors or xterm 0-255; players cannot inject custom terminal codes.
  Titles are cosmetic only and do not change actual player identity,
  in-character SAY or the WHO roster. Player saves store title/color
  automatically and all existing saves default to no title. Chatlog entries
  made before titles still load normally; runtime `data/` is excluded.

- Version 15.394: Clarified the title feature introduced in 15.393.
  Custom colored character titles now appear AFTER character names in
  WHO, WHOIS, SCORE and the room/target LOOK displays. They no longer
  appear in OOC chat, OOC emotes or CHATLOG, even when old log entries
  contain saved title snapshots. Character-save fields are unchanged
  so all existing titles and colors survive upgrades. Real names,
  player lookup and in-character combat/chat identities remain unchanged.
  Existing runtime `data/` is never packaged or overwritten.

- Version 15.395 (final title scope): Custom colored player titles are
  exclusively a `WHO` list decoration, including WHO's linkdead roster.
  WHOIS, SCORE, LOOK, ordinary room output, OOC, CHATLOG, emotes, combat,
  and all other character displays use the unmodified player name.
  `title`, `title color`, `title clear` and saved player title/color
  fields remain compatible with existing accounts. No `data/` files are
  included in the release archive.

- Version 15.396: Setting a new TITLE immediately replaces the previous
  WHO-only title; there is no need to run TITLE CLEAR first. Players may
  mix safe built-in ROM/xterm codes inside a single title, e.g.
  `title &RFlame &CIce &YMaster` or `title &[208]Orange &[39]Blue`.
  The existing `title color <color>` is the fallback color for unmarked
  spans. Validation limits titles to 40 visible characters, at most 16
  supported inline color codes and 160 characters of stored markup.
  Invalid color/control codes are rejected. Titles and default colors
  still persist in existing character saves and appear ONLY on WHO.
  This update never includes or alters the runtime `data/` directory.

- Version 15.397: Restored authenticated immortal Reaper Death Seal casting
  without ordinary scroll, level, clan, resource or proficiency gates;
  staff casts succeed automatically. Immortal targets can also be
  transported into the Reaper's stomach. Both staff casters and staff
  targets arrive as unrestricted visitors: they have no persistent
  `reaper_seal_id` movement lock, their statuses are preserved, their
  commands work, and they can teleport away at will. Regular players
  remain fully sealed and cannot escape without a legitimate reversal.
  The durable journal marks `unbound_staff` participants so reconnects
  and server restarts never imprison visitors; staff promoted while
  bound are released from old restrictions without freeing mortal peers.
  Reversal returns visitors still inside the prison but never moves
  staff who have already departed. Existing `data/reaper_seals.json`
  and all player saves remain untouched by installation; `data/` is
  excluded from packaged ZIPs.
