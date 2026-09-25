"""
Account and Player data models.

Player carries the recommended field set from Section 45 of the design
brief. Protected fields (village, primary_class, level, experience,
staff_level, security_level) are only ever written by chargen, admin
tools, or the (future) leveling system -- never by ordinary player
commands. This module only defines the shape of the data; storage.py
handles reading/writing it to disk.
"""

from dataclasses import dataclass, field, fields, asdict
from typing import Dict, List, Optional
import time


@dataclass
class Account:
    name: str
    salt_hex: str
    hash_hex: str
    staff_level: str = "player"          # Section 33 staff levels
    forced_reset: bool = False           # e.g. after staff setpassword
    failed_attempts: int = 0
    locked_until: float = 0.0
    previous_hash: Optional[List[str]] = None  # [salt_hex, hash_hex] of prior pw

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Account":
        """See Player.from_dict's own docstring for the full story --
        the same fix, applied proactively here too, since a future
        field removed from THIS class would cause the identical real
        crash otherwise."""
        valid_names = {f.name for f in fields(Account)}
        return Account(**{k: v for k, v in d.items() if k in valid_names})


@dataclass
class Player:
    name: str
    account_name: str

    # Permanent choices (Section 3) -- protected from player edits
    village: Optional[str] = None
    village_rank: str = "academy student"
    primary_class: Optional[str] = None

    level: int = 1
    experience: int = 0
    # Version 2 is the cumulative cubic progression curve. Existing saves
    # without this field are detected and migrated by storage.load_player.
    experience_curve_version: int = 2
    ryo: int = 0

    health: int = 100
    maximum_health: int = 100
    chakra: int = 75
    maximum_chakra: int = 75
    stamina: int = 100
    maximum_stamina: int = 100

    strength: int = 10
    wisdom: int = 10
    constitution: int = 10
    intelligence: int = 10
    dexterity: int = 10
    luck: int = 10
    perception: int = 10
    willpower: int = 10
    chakra_control: int = 10

    training_points: int = 0
    practice_points: int = 0
    mission_points: int = 0

    hospital_vnum: Optional[int] = None
    prompt_string: str = ""
    color_enabled: bool = True
    afk: bool = False

    # Roleplay customization (Section 51) -- description is a short
    # blurb shown when another player 'look's at this character;
    # biography is a longer backstory shown via a dedicated command.
    # Both are written with the same guided line editor used for
    # help-topic authoring.
    description: str = ""
    biography: str = ""

    # Player housing (Section 52). Rooms themselves are NOT persisted to
    # disk across restarts (a pre-existing project limitation -- the
    # whole world is rebuilt fresh from content.py + any rset-created
    # rooms every startup), so this field on the player -- which IS
    # saved -- is the durable source of truth for apartment ownership.
    # world.reconcile_apartment_ownership(), called once at startup
    # after the world is built, re-applies Room.owner from every
    # player's saved apartment_room_vnum.
    apartment_room_vnum: Optional[int] = None
    apartment_name: Optional[str] = None
    apartment_description: Optional[str] = None

    # Apartment room expansions (Section 72) -- room_type -> {"direction":
    # str, "cost": int} recorded at purchase time (e.g. {"bedroom":
    # {"direction": "north", "cost": 200000}}), the durable source of
    # truth for rebuilding these rooms at startup, same reasoning as
    # apartment_room_vnum above (rooms aren't persisted). The cost is
    # tracked per room (not just recomputed from the current room
    # count) so a 50% sell refund is always exactly half of what THAT
    # room actually cost, even after a sell/rebuy cycle changes what
    # the "next" room would cost today.
    apartment_expansions: Dict[str, dict] = field(default_factory=dict)
    # The storage room's contents specifically -- unlike every other
    # room in the game (including the other apartment expansion
    # rooms), whatever's left here survives a restart. At startup
    # reconciliation, the storage room's ground_items list is set to
    # THIS SAME list object (not a copy), so any later drop/get there
    # mutates this field directly with no separate sync step needed.
    storage_room_items: List[str] = field(default_factory=list)

    # Player shops (Section 75) -- one per player, along Main Street.
    # Same "rooms aren't persisted, rebuild from the player's saved
    # fields at startup" reasoning as apartment_room_vnum above.
    shop_room_vnum: Optional[int] = None
    shop_name: Optional[str] = None
    shop_description: Optional[str] = None
    # Each entry: {"item_name": str, "price": Optional[int]} -- price
    # is None until set via the `price` command. Capped at
    # playershops.MAX_STOCK_ITEMS (20) entries; the SAME item name can
    # appear more than once (each a separate sale), matching how
    # "give an item" is a per-instance action, not a stack-quantity edit.
    shop_stock: List[dict] = field(default_factory=list)

    recently_defeated_timer: float = 0.0
    # Staff punishment commands (Section 94), per direct request:
    # "Create a silence command...also add jail player name hours...
    # automatically being released when timer is up." Real Unix
    # timestamps, matching Account.locked_until's own established
    # pattern -- 0.0 means "not currently silenced/jailed". Checked
    # directly wherever the punishment applies (say/ooc/village chat
    # for silence, movement for jail) and cleared automatically once
    # expired, rather than needing a separate always-on background
    # sweep -- the check-and-clear happens the moment the player next
    # tries to do the very thing they're restricted from.
    silenced_until: float = 0.0
    jailed_until: float = 0.0
    active_status_effects: Dict = field(default_factory=dict)
    # Each dose tracks elapsed real time and HP already paid out so saving
    # and reconnecting cannot restart or duplicate a course of healing.
    medical_healing: List[dict] = field(default_factory=list)
    active_missions: List = field(default_factory=list)
    completed_missions: List = field(default_factory=list)
    mission_cooldowns: Dict[str, float] = field(default_factory=dict)  # mission_id -> ready-again timestamp
    village_reputation: Dict = field(default_factory=dict)

    learned_skills: List[str] = field(default_factory=list)
    skill_proficiencies: Dict[str, int] = field(default_factory=dict)
    jutsu_tiers: Dict[str, int] = field(default_factory=dict)
    cooldowns: Dict[str, float] = field(default_factory=dict)

    equipment: Dict[str, str] = field(default_factory=dict)   # slot -> item name
    # A backpack's own real, separate contents (Section 158, per
    # direct request: "have we added backpocks yet that can hold
    # items" -> confirmed a genuinely separate container, not just a
    # bump to the normal inventory limit). Keyed by the backpack's
    # own real, CURRENT position in player.inventory (a plain int,
    # stored as a string key since JSON object keys must be strings)
    # -- confirmed directly this is raw list-position tracking, an
    # accepted risk if the player drops/picks up something else and
    # shifts later positions in between uses of the same backpack.
    backpack_contents: Dict[str, List[str]] = field(default_factory=dict)
    inventory: List[str] = field(default_factory=list)

    room_vnum: int = 0

    # Rest state for natural regen (Section 16's internal-conditions list
    # includes Standing/Sleeping -- Resting is added here purely as a
    # regen-rate toggle, not a combat stance/action-economy system).
    position: str = "standing"

    # Player-configurable convenience settings (see the `config` command).
    auto_loot_ryo: bool = True
    auto_loot_gear: bool = True
    auto_sac_corpse: bool = True
    tips: bool = True                 # periodic tip-of-the-day display (tips.py) -- default on, per explicit request
    staff_show_vnums: bool = True     # staff-only config -- room-header vnum/flags display specifically, separate from access-control uses of staff status
    staff_notify_reports: bool = True  # staff-only config -- live ping when a player submits 'report'
    staff_notify_ideas: bool = True  # staff-only config -- live ping when a player submits 'idea', genuinely separate from staff_notify_reports

    # Clan is cosmetic-only for now (Section 48 defers bloodline mechanics);
    # freely changeable, unlike village/class.
    clan: str = "none"
    # Kekkei Genkai (bloodline) -- rolled once at character creation
    # (session.py), never re-rolled. ALL of these are hidden from the
    # player entirely until a future Level 50 awakening quest (not
    # built yet) reveals the result -- see data_kekkei_genkai.py's own
    # docstring for the full security reasoning. bloodline_id is the
    # data_kekkei_genkai.KEKKEI_GENKAI key, or None if this character
    # has no bloodline at all (true for the vast majority of
    # characters, even those from an eligible clan). potential/talent
    # are both 0 when bloodline_id is None.
    bloodline_id: Optional[str] = None
    bloodline_potential: int = 0    # 1-100 -- the mastery ceiling, never raised by training
    bloodline_talent: int = 0       # 1-100 -- learning/mastery speed, does NOT raise the ceiling
    bloodline_awakened: bool = False   # only True after the future awakening quest (or a staff force-awaken)
    bloodline_mastery: int = 0      # framework placeholder for future progression stages -- unused until then
    # Mangekyo Sharingan unlock (Section 116, per direct request):
    # "the second stage of sharingan mangekyo can only be unlocked
    # with the friendship/most grouped player by killing them...that
    # player will end up in a 'downed' state and the sharingan user
    # will have to choose yes or no to finish them off...this is the
    # cost of gaining sharingan mangeko beytraing your friend."
    # Confirmed design: Sharingan-only (the other 4 bloodlines can't
    # attempt this even if they meet the same eligibility numbers);
    # only reachable by a player already eligible_for_awakening_quest
    # (Potential>=90, fully-maxed mastery) fighting their own,
    # secretly-tracked most-grouped partner (combat_partner_counts
    # below) in real PvP -- the normal defeat moment becomes a real
    # "downed" state with a yes/no prompt instead, every time, for
    # that specific pairing. "yes" sets this flag True permanently
    # AND applies real, confirmed penalties to the downed player (25%
    # of total XP, half their ryo, every practiced skill reduced 25%)
    # AND starts their frozen_until lock below. "no" is a completely
    # ordinary PvP defeat, no special consequence at all. Confirmed:
    # this pass only ever flips this flag -- Mangekyo's own real
    # combat abilities are deliberately out of scope, a separate
    # future follow-up.
    bloodline_mangekyo: bool = False
    # The 2 guaranteed-different real Mangekyo techniques rolled from
    # data_mangekyo.TECHNIQUE_ROSTER the instant bloodline_mangekyo is
    # set (Section 140, per direct confirmation: "each eye gets its
    # own ability"). Susanoo is deliberately NOT one of these -- it's
    # a real, universal ability every Mangekyo user gets automatically,
    # checked via bloodline_mangekyo alone, not stored here at all.
    mangekyo_eye_1: Optional[str] = None
    mangekyo_eye_2: Optional[str] = None
    # Izanagi (Section 140, if rolled): a real, deliberate stance the
    # player must proactively activate -- confirmed directly NOT
    # automatic. Stays active indefinitely (no separate expiration of
    # its own) until it's actually triggered by a real near-death
    # moment, at which point it's consumed and izanagi_cooldown_until
    # is set (a real, once-per-real-day cooldown, confirmed directly).
    izanagi_active: bool = False
    izanagi_cooldown_until: float = 0.0
    # Amaterasu (Section 140, if rolled): a real, genuinely PERMANENT
    # burn on the target -- confirmed directly it has NO duration of
    # its own, burning forever until sealed by a future, scroll-taught
    # sealing jutsu (not yet built). Travels with the player wherever
    # they go, genuinely separate from the room's own fire (see
    # world.Room.amaterasu_fire_caster), which stays behind if they
    # leave.
    mangekyo_amaterasu_burning: bool = False
    # Kamui's own real pocket dimension (Section 140, if rolled) -- a
    # genuinely unique, per-caster room (never shared between
    # different Mangekyo users). kamui_pocket_dimension_vnum is set
    # the instant the caster opens it on a real target (step 1 of the
    # confirmed 2-step entry); kamui_pocket_dimension_active only
    # becomes True once the caster has separately cast it on
    # THEMSELVES to actually join (step 2) -- real chakra upkeep only
    # starts ticking from that point on.
    kamui_pocket_dimension_vnum: Optional[int] = None
    kamui_pocket_dimension_active: bool = False
    # Kamui: Intangibility (Section 140, if rolled) -- a real,
    # guaranteed window (data_mangekyo.KAMUI_INTANGIBILITY_ROUNDS)
    # where every incoming attack simply misses, confirmed directly.
    # Decremented by 1 at every real hit-roll site while > 0.
    kamui_intangibility_rounds_left: int = 0
    # Izanami (Section 140, if rolled) -- a real, recursive loop
    # trapping a target. izanami_target_number is set ONCE at the
    # start and never changes (confirmed directly), so the target can
    # narrow it down over repeated guesses. izanami_return_room_vnum
    # is where they were before being looped, restored the instant
    # they guess correctly. izanami_trapped marks them as genuinely
    # immune to attack while looped, confirmed directly.
    izanami_target_number: Optional[int] = None
    izanami_return_room_vnum: Optional[int] = None
    izanami_trapped: bool = False
    # Tsukuyomi (Section 140, if rolled) -- a real, shared torture
    # room. tsukuyomi_actions_remaining is the real, hidden countdown
    # (5-10, rolled once at the start, confirmed directly never
    # revealed to either player) of the CASTER's own real actions
    # left before it ends. tsukuyomi_return_room_vnum is the TARGET's
    # own real room from before being pulled in, restored the instant
    # it ends. tsukuyomi_frozen marks the target as genuinely frozen
    # in place, unable to act, confirmed directly.
    tsukuyomi_actions_remaining: int = 0
    tsukuyomi_return_room_vnum: Optional[int] = None
    tsukuyomi_frozen: bool = False
    # The NAME of whichever player the caster is currently torturing
    # inside their own active Tsukuyomi -- set on the caster, not the
    # target, so the 5 real torture commands (stab/impale/burn/crush/
    # unmake) know who they're actually affecting.
    tsukuyomi_active_target_name: Optional[str] = None
    # The real, dedicated shared room's own vnum, and the caster's
    # own real room to return to once it ends -- both stored on the
    # CASTER (the target's own return room is tracked separately, see
    # tsukuyomi_return_room_vnum above).
    tsukuyomi_room_vnum: Optional[int] = None
    tsukuyomi_caster_return_vnum: Optional[int] = None
    # Set the instant a player is put into the "downed" state
    # described above, to the ATTACKER's own name -- lets the yes/no
    # prompt route to the right session and stops any other player
    # from being able to interfere with (or accidentally trigger) a
    # decision that isn't theirs to make. Cleared the moment the
    # decision resolves either way.
    downed_by: Optional[str] = None
    # The real 24-hour lock a player enters after being finished off
    # (the "yes" outcome above) -- a real timestamp, exactly the same
    # pattern as silenced_until, counts down in true real time whether
    # the player is online or offline, and lifts itself automatically
    # the instant it expires, no staff action needed. While this is
    # in the future, only 'look'/'say'/'ooc' work at all -- everything
    # else is refused with a clear, in-character message.
    frozen_until: float = 0.0
    # Secret combat-partnership tracker (Section 81, per direct
    # request) -- groundwork for a future Mangekyo/stage-2 Sharingan
    # quest, not usable or surfaced by anything yet. Keyed by the
    # OTHER player's name, value is how many qualifying group kills
    # they've shared together (see combat.handle_mob_defeat's XP-split
    # loop) -- confirmed design: every member present for a kill gets
    # +1 with EVERY other member present for that same kill, not just
    # the group leader or a single designated "partner". Genuinely
    # hidden -- like bloodline_id, nothing in score/look/mstat/etc.
    # reveals this to anyone, including the player themselves.
    combat_partner_counts: dict = field(default_factory=dict)
    # Summoning contracts (Section 118, per direct request/
    # confirmation): which of the 5 real summoning contracts
    # (data_summons.CONTRACTS) this player has genuinely signed --
    # each one signed at its own dedicated secret hideout, granting
    # access to that contract's own full progressive tier ladder as
    # the player's own level rises (see data_summons.
    # best_available_tier). A plain list of contract keys, e.g.
    # ["toad"].
    signed_summoning_contracts: list = field(default_factory=list)
    # Track jutsu (Section 119, per direct request/confirmation):
    # real, active tracking state. Exactly one of tracking_target_
    # mob_id / tracking_target_player_name is ever set at a time --
    # a mob is re-identified across pulses by its own stable
    # instance_id (combat.Mob), since a template vnum alone could
    # match many different live instances. tracking_area_name pins
    # the real search scope to whatever area the target was actually
    # in the moment tracking started, per direct confirmation
    # ("only within the same area/region the target is actually
    # in, not the whole map"). tracking_paused_by_combat is True
    # while the caster is in active combat (PvE or PvP), so the
    # per-pulse tick knows to skip movement and resume automatically
    # once that fight actually ends, rather than losing the target
    # or restarting the whole search.
    tracking_target_mob_id: Optional[int] = None
    tracking_target_player_name: Optional[str] = None
    tracking_area_name: Optional[str] = None
    tracking_paused_by_combat: bool = False
    # Illusion Walk genjutsu (Section 120, per direct request/
    # confirmation: "It detects the rooms the player is near and
    # mimics them 1 room away from when the jutsu was cast...so the
    # player will remain in the room they started but looks like
    # they have moved on their output to them..when they reach a
    # room more then 1 away from thier real location it shifts them
    # back to the original..mastery allows more then 1 room to make
    # the jutsu less obvious"). The victim's own real room_vnum
    # never changes the whole time this is active -- these 4 fields
    # are the only real state tracking the illusion. Confirmed
    # directly: reaching the illusion's own range doesn't end the
    # genjutsu itself, it only snaps the victim's OWN view back to
    # their real room -- if they keep trying to move, the illusion
    # starts fooling them again, repeating indefinitely until the
    # caster ends it (no in-game "Kai"/release mechanic exists yet,
    # confirmed as a deliberate future gap).
    illusion_walk_caster: Optional[str] = None
    illusion_walk_real_room_vnum: Optional[int] = None
    illusion_walk_range: int = 0
    illusion_walk_steps_taken: int = 0
    # Transfer/Return (Section 126, per direct request/confirmation):
    # this player's own real room, saved the moment an immortal
    # transfers them elsewhere -- None if they haven't been
    # transferred (or have already been returned). A single, real
    # saved value per player: transferring them again while already
    # away just overwrites it with wherever they were at THAT moment,
    # confirmed directly -- only the most recent original room is
    # ever remembered. Persists across a logout/save, since the
    # player could log off before the immortal ever uses 'return'.
    pre_transfer_room_vnum: Optional[int] = None
    # Tailed Beasts / Jinchuriki (Section 127, per direct request/
    # confirmation): which beast (data_tailed_beasts.TAILED_BEASTS
    # key) this player currently holds, sealed via the Sealing Jutsu
    # -- None if they don't hold one. Confirmed directly to persist
    # "even at death" (a real, permanent field, not session-
    # transient) until another player defeats them in real PvP AND
    # knows the separate Release Jutsu, which extracts the beast and
    # puts it back into the wild. jinchuriki_mastery is the real,
    # hidden mastery percentage (0-100), confirmed directly to work
    # like the existing Kekkei Genkai mastery system -- grows slowly
    # through combat while jinchuriki. Real mastery-gated mechanics
    # (rampage risk, Tailed Beast Mode, the Tailed Beast Bomb) are a
    # confirmed, deliberate LATER stage of this same feature.
    jinchuriki_beast_key: Optional[str] = None
    jinchuriki_mastery: int = 0
    # The real, absolute timestamp this player's own current rampage
    # (Section 127 continued, per direct confirmation) ends -- 0.0
    # means not currently rampaging at all. Set by tailed_beasts.
    # trigger_rampage to a genuinely fresh 5-10 real-minute roll each
    # time a rampage actually begins.
    rampage_until: float = 0.0
    # Tailed Beast Mode (Section 127 continued, per direct
    # confirmation: "Tailed beast mode is much like sharingan
    # on/off") -- a real, genuine toggle, only usable once
    # jinchuriki_mastery genuinely reaches 100. Grants a real, always-
    # controlled combat/stat boost, confirmed directly to be smaller
    # and "more refined, less raw" than the rampage's own +50% --
    # scales by the specific beast's own tail count (25% at 1-tail up
    # to 55% at 9-tails), with no downside at all while toggled on.
    tailed_beast_mode_active: bool = False
    # Manda's own "bind" mechanic (Section 118) -- True for the rest
    # of a fight once its poison/bind effect has applied at least
    # once; checked directly by cmd_flee to hard-refuse a flee
    # attempt while genuinely bound. Enma's own "weapon_buff"
    # mechanic -- True while its buff is active, checked by the
    # player's own real attack-damage calculation. Both reset to
    # False the moment a fight actually ends (matching how combat
    # state itself already resets between fights), never carried
    # into a later, unrelated fight.
    summon_flee_locked: bool = False
    summon_weapon_buff_active: bool = False
    # Teams (Section 82, per direct request: "Add a teams system so if
    # you create a team you gain more experience fighting with them.
    # Only chuunin or higher rank can lead a team. A team can total 4
    # players including the team leader. 24 hour wait time on
    # disbanding your team before you can join another team.") A
    # genuinely separate, persistent system from the session-only
    # groups.py above -- a team's actual roster/leader/creation time
    # lives in the shared teams.json (storage.load_teams/save_teams),
    # since a team is multi-player shared state, not one player's own
    # data. These 2 fields are just this player's own lightweight
    # pointer into that shared state.
    team_name: Optional[str] = None
    team_disband_cooldown_until: float = 0.0
    pending_team_invite: Optional[str] = None  # the team NAME they've been invited to, if any -- confirmed to persist across logout, unlike a group invite
    # Chakra nature (Section 79, per direct request) -- a hidden,
    # one-time roll at character creation, exactly like the Kekkei
    # Genkai bloodline roll above: one of biomes.ELEMENTS (excluding
    # "none"), never shown to the player until revealed by using a
    # Chakra Paper item (see items.py/commands.py's chakra paper
    # handling). chakra_nature_revealed tracks whether that's
    # happened yet, so a second Chakra Paper can't be "wasted" if the
    # player somehow already knows (a staff mstat, a future re-reveal
    # item, etc.) -- though today Chakra Paper is the only way in.
    chakra_nature: Optional[str] = None
    chakra_nature_revealed: bool = False
    # Secondary chakra nature (Section 84, per direct follow-up
    # request) -- a second, independent hidden roll unlocked at
    # level 100, revealed through the exact same Chakra Paper/channel
    # flow as the primary nature above, just gated at level 100
    # instead of 50. Confirmed design: requires the PRIMARY nature to
    # already be revealed first (even if already level 100+) --
    # rolled fresh at the moment of that second reveal, not at
    # character creation, since nobody starts at level 100. Guaranteed
    # to differ from chakra_nature (random among the other 4 elements,
    # no thematic restriction on which -- opposing elements are
    # explicitly fine per confirmed design, "even if they oppose each
    # other").
    chakra_nature_secondary: Optional[str] = None
    chakra_nature_secondary_revealed: bool = False
    # Sharingan-specific tomoe count (1-3), per explicit request that
    # the first awakening grant exactly 1 tomoe, not a flat "fully
    # awakened" state. 0 for every other bloodline, and 0 for a
    # not-yet-awakened Sharingan too -- data_kekkei_genkai.
    # attempt_awaken() sets this to 1 the first time a Sharingan is
    # awakened. Meaningless for the other 4 bloodlines (Byakugan,
    # Shikotsumyaku, Ice Release, Hydrification), which still use
    # bloodline_awakened alone.
    bloodline_tomoe: int = 0
    # True while a player has actively toggled their 1-tomoe dodge
    # ability on (see commands.cmd_sharingan) -- costs chakra/stamina
    # per combat round while active (combat.py), not a permanent
    # passive bonus. False whenever bloodline_tomoe is 0 (can't be
    # toggled on without at least 1 tomoe).
    sharingan_active: bool = False
    # A jutsu key copied via the 5-tomoe Sharingan's Copy Jutsu perk
    # (commands.SHARINGAN_COPY_JUTSU_CHANCE_PERCENT, rolled in combat.
    # use_jutsu_on_player when an opponent casts a jutsu at this
    # player), held here until spent -- None if nothing's been copied.
    # copied_jutsu_cost is what THIS cast will cost (double what the
    # ORIGINAL caster paid, per explicit design confirmation, not this
    # player's own normal cost for that jutsu), fixed at copy time so
    # it can't drift if the source jutsu's own cost changes later.
    copied_jutsu_key: Optional[str] = None
    copied_jutsu_cost: int = 0
    # Chunin Exam (Forest of Death) -- true while a genin is actively
    # inside the exam zone. Gates the PvP scroll-theft mechanic
    # (combat.handle_pvp_defeat) to only apply there, not to every
    # fight in the game.
    in_chunin_exam: bool = False
    age: int = 16

    # Cosmetic identity choices made at creation (Section 62) -- like
    # village/class, permanent; unlike clan, not changeable later.
    sex: str = "male"
    skin_tone: str = "tan"
    hair_color: str = "black"
    eye_color: str = "brown"
    build: str = "athletic"
    personality_trait: str = "confident"

    # Auto-flee threshold (Section 66) -- a percentage of max health;
    # 0 means disabled (the default -- never auto-flee unless the
    # player explicitly sets one via 'wimpy <percent>').
    wimpy_percent: int = 0

    practice_sessions_used: int = 0
    player_kills: int = 0     # incremented in combat.py on every PvP defeat
    player_deaths: int = 0    # incremented in combat.py on every PvP defeat
    npc_kills: int = 0
    bank_balance: int = 0        # deliberately separate from player.ryo -- untouched by death-penalty ryo loss (see combat.handle_player_defeat) or anything else that only ever operates on player.ryo
    bank_last_interest_at: float = 0.0  # epoch seconds -- interest is applied lazily on next bank interaction, not on a global timer (see bank.py)
    # Lifetime total ever earned (never decremented) -- distinct from
    # mission_points itself, which IS spent on Kage perks. Both feed
    # leaderboards.py ("most earned" vs "most held").
    mission_points_earned_total: int = 0
    # Job leveling (jobs.py) -- a RuneScape-style progression track
    # entirely separate from ninja level/experience. Generic across any
    # job name so future jobs (mining, smithing, gem refining, etc.)
    # reuse these same two fields rather than needing their own.
    job_levels: dict = field(default_factory=dict)
    job_xp: dict = field(default_factory=dict)
    total_play_seconds: float = 0.0

    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Player":
        """Builds a Player from a saved dict, tolerating keys that no
        longer exist on the class -- a real, genuine production bug
        (a full server restart failure) was caused by the previous,
        naive Player(**d) here: the moment ANY field was ever removed
        from this dataclass (as happened when the academy's
        tutorial_step/tutorial_flags/has_completed_academy fields
        were deleted), every EXISTING saved character -- which still
        has those old keys sitting in their save file on disk --
        would crash the instant they tried to load, since Python
        raises a TypeError for an unrecognized keyword argument.
        Since server startup loads every saved player (see
        world.reconcile_apartment_ownership), that took down the
        WHOLE server, not just the one affected character.
        Filtering the dict down to only genuinely current field names
        first means an old, since-removed key is silently dropped
        (the character correctly loses that piece of data, since the
        field no longer exists anywhere in the running game) rather
        than crashing the entire boot."""
        valid_names = {f.name for f in fields(Player)}
        return Player(**{k: v for k, v in d.items() if k in valid_names})
