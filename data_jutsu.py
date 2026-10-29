"""
Jutsu data table.

Every player gets exactly the same starting kit regardless of primary
class: one active jutsu per combat category (Ninjutsu/Taijutsu/Genjutsu/
Bukijutsu) plus a passive (see data_passives.py). class_requirement is
kept on each entry for CATEGORIZATION only (prac's category grouping,
and dispatch_line's "Taijutsu/Bukijutsu can be used by bare name" rule)
-- it is NOT an access gate anymore; combat.use_jutsu no longer checks
it, since every player knows all four jutsu regardless of their chosen
class.

There is no level-gated unlock tier system anymore (Section 13's
tiered progression is retired in favor of "everyone starts with
everything") -- these are all level_requirement 1.
"""

# damage is (min, max). effect is an optional status-effect key applied
# to the target (see status_effects.py).
# Teacher practice stops at DEFAULT_PRACTICE_CAP_PERCENT (50%), but
# normal qualifying skill/jutsu usage can improve proficiency at ANY
# point below 100%, including before reaching the practice cap.
# Past the teacher cap only actual usage can raise it further.
# PRACTICE_CAP_PERCENT holds exceptions to the universal cap -- Shadow
# Clone Jutsu (20%) and Handsigns (1%).
DEFAULT_PRACTICE_CAP_PERCENT = 50

PRACTICE_CAP_PERCENT = {
    "Shadow Clone Jutsu": 20,
    "Handsigns": 1,  # confirmed design ("1% non practiceable") -- see data_handsigns.py
}


JUTSU = {
    "soto uke": {
        "jutsu_id": "taijutsu_soto_uke", "display_name": "Soto Uke",
        "class_requirement": "taijutsu", "level_requirement": 19,
        "chakra_cost": 0, "stamina_cost": 10, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 1, "element": "none", "jutsu_type": "combat_passive",
    },
    "weapon expert": {
        "jutsu_id": "bukijutsu_weapon_expert", "display_name": "Weapon Expert",
        "class_requirement": "bukijutsu", "level_requirement": 36,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none", "jutsu_type": "combat_passive",
    },
    "dual wield": {
        "jutsu_id": "bukijutsu_dual_wield", "display_name": "Dual Wield",
        "class_requirement": "bukijutsu", "level_requirement": 70,
        "chakra_cost": 0, "stamina_cost": 5, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 3, "element": "none", "jutsu_type": "dual_wield",
    },
    "chokkan": {
        "jutsu_id": "genjutsu_chokkan", "display_name": "Chokkan",
        "class_requirement": "genjutsu", "level_requirement": 70,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 12.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 3, "element": "none", "jutsu_type": "chokkan",
    },
    "1000 years of death": {
        "jutsu_id": "general_1000_years_of_death", "display_name": "1000 Years of Death",
        "class_requirement": "general", "level_requirement": 1,
        "chakra_cost": 100, "stamina_cost": 20, "cooldown": 60.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none", "jutsu_type": "instant_kill", "scroll_only": True,
    },
    "shadow shuriken technique": {
        "jutsu_id": "ninjutsu_starter", "display_name": "Shadow Shuriken Technique",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 10, "stamina_cost": 0, "cooldown": 2.0,
        "damage": (12, 20), "damage_type": "chakra", "effect": None,
        "tier": 1, "element": "none",
    },
    "dynamic entry": {
        "jutsu_id": "taijutsu_starter", "display_name": "Dynamic Entry",
        "class_requirement": "taijutsu", "level_requirement": 1,
        "chakra_cost": 0, "stamina_cost": 6, "cooldown": 2.0,
        "damage": (10, 18), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none",
    },
    "choku zuki": {
        "jutsu_id": "taijutsu_choku_zuki", "display_name": "Choku Zuki",
        "class_requirement": "taijutsu", "level_requirement": 3,
        "chakra_cost": 0, "stamina_cost": 5, "cooldown": 2.0,
        "damage": (8, 15), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none",
    },
    "mae geri": {
        "jutsu_id": "taijutsu_mae_geri", "display_name": "Mae Geri",
        "class_requirement": "taijutsu", "level_requirement": 5,
        "chakra_cost": 0, "stamina_cost": 7, "cooldown": 2.5,
        "damage": (12, 20), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none",
    },
    "oi zuki": {
        "jutsu_id": "taijutsu_oi_zuki", "display_name": "Oi Zuki",
        "class_requirement": "taijutsu", "level_requirement": 10,
        "chakra_cost": 0, "stamina_cost": 8, "cooldown": 3.0,
        "damage": (16, 25), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none",
    },
    "sokuto": {
        "jutsu_id": "taijutsu_sokuto", "display_name": "Sokuto",
        "class_requirement": "taijutsu", "level_requirement": 15,
        "chakra_cost": 0, "stamina_cost": 10, "cooldown": 3.5,
        "damage": (22, 34), "damage_type": "physical", "effect": None,
        "tier": 2, "element": "none",
    },
    "empi": {
        "jutsu_id": "taijutsu_empi", "display_name": "Empi",
        "class_requirement": "taijutsu", "level_requirement": 20,
        "chakra_cost": 0, "stamina_cost": 11, "cooldown": 4.0,
        "damage": (24, 37), "damage_type": "physical", "effect": None,
        "tier": 2, "element": "none",
    },
    "kumade": {
        "jutsu_id": "taijutsu_kumade", "display_name": "Kumade",
        "class_requirement": "taijutsu", "level_requirement": 25,
        "chakra_cost": 0, "stamina_cost": 13, "cooldown": 5.0,
        "damage": (27, 41), "damage_type": "physical", "effect": "blinded", "effect_chance_pct": 35,
        "tier": 2, "element": "none",
    },
    "nidan kyten geri": {
        "jutsu_id": "taijutsu_nidan_kyten_geri", "display_name": "Nidan Kyten Geri",
        "class_requirement": "taijutsu", "level_requirement": 30,
        "chakra_cost": 0, "stamina_cost": 16, "cooldown": 5.5,
        "damage": (32, 47), "damage_type": "physical", "effect": None,
        "tier": 3, "element": "none",
    },
    "tamashiwara": {
        "jutsu_id": "taijutsu_tamashiwara", "display_name": "Tamashiwara",
        "class_requirement": "taijutsu", "level_requirement": 35,
        "chakra_cost": 0, "stamina_cost": 17, "cooldown": 6.0,
        "damage": (34, 50), "damage_type": "physical", "effect": "bleeding", "effect_chance_pct": 40,
        "tier": 3, "element": "none",
    },
    "kihon dachi": {
        "jutsu_id": "taijutsu_kihon_dachi", "display_name": "Kihon Dachi",
        "class_requirement": "taijutsu", "level_requirement": 5,
        "chakra_cost": 0, "stamina_cost": 10, "cooldown": 0.0,
        "jutsu_type": "stance", "damage": None, "damage_type": None, "effect": None,
        "tier": 1, "element": "none",
    },
    "neko ashi dachi": {
        "jutsu_id": "taijutsu_neko_ashi_dachi", "display_name": "Neko Ashi Dachi",
        "class_requirement": "taijutsu", "level_requirement": 15,
        "chakra_cost": 0, "stamina_cost": 12, "cooldown": 0.0,
        "jutsu_type": "stance", "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none",
    },
    "sanchin dachi": {
        "jutsu_id": "taijutsu_sanchin_dachi", "display_name": "Sanchin Dachi",
        "class_requirement": "taijutsu", "level_requirement": 30,
        "chakra_cost": 0, "stamina_cost": 14, "cooldown": 0.0,
        "jutsu_type": "stance", "damage": None, "damage_type": None, "effect": None,
        "tier": 3, "element": "none",
    },
    "ushiro shishou": {
        "jutsu_id": "ninjutsu_ushiro_shishou", "display_name": "Ushiro Shishou",
        "class_requirement": "ninjutsu", "level_requirement": 30,
        "chakra_cost": 18, "stamina_cost": 0, "cooldown": 8.0,
        "jutsu_type": "ambush", "ambush_multiplier": 1.5,
        "damage": (28, 44), "damage_type": "physical", "effect": None,
        "tier": 2, "element": "none",
    },
    "hidden mist jutsu": {
        "jutsu_id": "ninjutsu_hidden_mist", "display_name": "Hidden Mist Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 40,
        "chakra_cost": 40, "stamina_cost": 0, "cooldown": 30.0,
        "jutsu_type": "mist", "damage": None, "damage_type": None, "effect": None,
        "tier": 3, "element": "water",
    },
    "demonic illusion hell viewing technique": {
        "jutsu_id": "genjutsu_starter", "display_name": "Demonic Illusion: Hell Viewing Technique",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 12, "stamina_cost": 0, "cooldown": 3.0,
        "damage": (8, 16), "damage_type": "mental", "effect": "frightened",
        "tier": 1, "element": "none",
    },
    "narakumi": {
        "jutsu_id": "genjutsu_narakumi", "display_name": "Narakumi",
        "class_requirement": "genjutsu", "level_requirement": 15,
        "chakra_cost": 22, "stamina_cost": 0, "cooldown": 4.0,
        "damage": (20, 36), "damage_type": "mental", "effect": "narakumi", "effect_chance_pct": 50,
        "tier": 2, "element": "none",
    },
    "shadow clone jutsu": {
        "jutsu_id": "ninjutsu_shadow_clone", "display_name": "Shadow Clone Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 30,
        "chakra_cost": 50, "stamina_cost": 0, "cooldown": 10.0,
        "jutsu_type": "summon", "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none",
        # No damage roll at all -- this jutsu summons a clone (or
        # clones) that fight alongside the player each round instead
        # of dealing damage itself. See combat.use_shadow_clone_jutsu.
    },
    "track": {
        "jutsu_id": "general_track", "display_name": "Track",
        "class_requirement": "general", "level_requirement": 30,
        "chakra_cost": 15, "stamina_cost": 0, "cooldown": 5.0,
        "jutsu_type": "track", "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none",
        # No damage roll at all -- this jutsu begins a real, ongoing
        # tracking session (see tracking.py) that autonomously walks
        # the caster toward a chosen mob or player, one room per real
        # pulse, rather than resolving anything in a single moment.
        # "general" class_requirement per direct confirmation
        # ("Track can only be learned from a scroll by any class" ->
        # confirmed display category: "General Skills").
    },
    "sealing jutsu": {
        "jutsu_id": "general_sealing_jutsu", "display_name": "Sealing Jutsu",
        "class_requirement": "general", "level_requirement": 100,
        "chakra_cost": 100, "stamina_cost": 0, "cooldown": 0.0,
        "jutsu_type": "sealing", "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # No damage roll at all -- per direct request/confirmation
        # (Section 127 continued): cast on a Tailed Beast already at
        # 0 HP (see combat.handle_mob_defeat's own real "downed,
        # awaiting sealing" state) to seal it into the caster instead
        # of an ordinary kill. Genuinely a real, deliberate SECOND
        # action, not automatic -- confirmed directly the player must
        # already have brought the beast down through ordinary
        # combat first. "general" class_requirement, matching Track's
        # own real precedent for a scroll-taught technique open to
        # any class.
    },
    "release jutsu": {
        "jutsu_id": "general_release_jutsu", "display_name": "Release Jutsu",
        "class_requirement": "general", "level_requirement": 100,
        "chakra_cost": 100, "stamina_cost": 0, "cooldown": 0.0,
        "jutsu_type": "beast_release", "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # No damage roll at all -- a genuinely SEPARATE jutsu from
        # Sealing Jutsu, confirmed directly (its own scroll, its own
        # level requirement, same 100 here). Extracts a Tailed Beast
        # from another player who was just defeated in real PvP
        # combat, per direct confirmation, putting the beast back
        # into the wild (a fresh real release, same as 'release
        # beast' -- full roaming schedule and despawn timer) rather
        # than killing the former jinchuriki's own character.
    },
    "tailed beast bomb": {
        "jutsu_id": "general_tailed_beast_bomb", "display_name": "Tailed Beast Bomb",
        "class_requirement": "general", "level_requirement": 100,
        "chakra_cost": 150, "stamina_cost": 0, "cooldown": 30.0,
        "jutsu_type": "beast_bomb", "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # No fixed damage tuple -- per direct confirmation (Section
        # 127 continued): "with its own real damage scaling by tail
        # count too (a 9-tail's Bomb hits much harder than a
        # 1-tail's)." The real amount is computed live from the
        # caster's own specific beast (see tailed_beasts.
        # bomb_damage), not a static range like an ordinary jutsu.
        # Only usable while Tailed Beast Mode is genuinely toggled on
        # (confirmed directly), refused otherwise.
    },
    "illusion walk": {
        "jutsu_id": "genjutsu_illusion_walk", "display_name": "Illusion Walk",
        "class_requirement": "genjutsu", "level_requirement": 20,
        "chakra_cost": 12, "stamina_cost": 0, "cooldown": 3.0,
        "jutsu_type": "illusion_walk", "damage": None, "damage_type": None, "effect": None,
        "tier": 1, "element": "none",
        # No damage roll at all -- a pure illusion/control effect, per
        # direct request/confirmation (Section 120): the victim's own
        # real room_vnum never changes at all while this is active;
        # only what they personally SEE when they try to move is
        # faked (see combat.py's own illusion_walk handling). Genuinely
        # player-only -- confirmed directly, since a mob has no real
        # output stream of its own to fake.
    },
    "throw shuriken": {
        "jutsu_id": "bukijutsu_starter", "display_name": "Throw Shuriken",
        "class_requirement": "bukijutsu", "level_requirement": 1,
        "chakra_cost": 0, "stamina_cost": 6, "cooldown": 2.0,
        "damage": (10, 18), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none", "jutsu_type": "thrown",
    },
    "throw kunai": {
        "jutsu_id": "bukijutsu_throw_kunai", "display_name": "Throw Kunai",
        "class_requirement": "bukijutsu", "level_requirement": 15,
        "chakra_cost": 0, "stamina_cost": 10, "cooldown": 2.5,
        "damage": (18, 30), "damage_type": "physical", "effect": None,
        "tier": 1, "element": "none", "jutsu_type": "thrown", "requires_item": "kunai",
        # Genuinely consumes a real kunai from inventory and drops it
        # on the ground where thrown -- see combat.use_jutsu's
        # requires_item handling. Confirmed: consumed/dropped
        # regardless of hit or miss, since a thrown kunai leaves your
        # hand either way.
    },
    "counter kunai": {
        "jutsu_id": "bukijutsu_counter_kunai", "display_name": "Counter Kunai",
        "class_requirement": "bukijutsu", "level_requirement": 25,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none", "jutsu_type": "counter",
        # A genuinely passive jutsu, never cast directly -- confirmed
        # design ("passively block another's kunai throw if you have
        # one in your inventory and it will consume the kunai").
        # Checked automatically whenever an incoming attack is
        # jutsu_type "thrown" (see combat._try_counter_kunai), not
        # through 'perform' at all.
    },
    "silent genjutsu": {
        "jutsu_id": "genjutsu_silent_passive", "display_name": "Silent Genjutsu",
        "class_requirement": "genjutsu", "level_requirement": 75,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 3, "element": "none", "jutsu_type": "silent_genjutsu_passive",
        # A genuinely passive jutsu, never cast directly -- per direct
        # request/confirmation (Section 122): "removes the requirement
        # to have perform before the genjutsu name your casting and
        # the jutsu is instant with no handsigns required...it also
        # at 100% mastery the other player won't see the jutsu name
        # being cast." Confirmed directly: applies to EVERY Genjutsu
        # the player already knows, always on once learned (no
        # toggle), regardless of target (mob or player -- that part
        # is about the caster's own casting style). The 100%-mastery
        # message-hiding is genuinely PvP-only and one-directional --
        # the CASTER always sees their own full normal message
        # regardless of mastery; only the TARGET's own message is
        # affected. Checked automatically in commands.dispatch (for
        # the bare-name/no-perform part) and combat.begin_pending_cast/
        # use_jutsu_on_player (for the instant-cast and message-hiding
        # parts), not through 'perform' itself.
    },
    "explosive tag kunai": {
        "jutsu_id": "bukijutsu_explosive_tag_kunai", "display_name": "Explosive Tag Kunai",
        "class_requirement": "bukijutsu", "level_requirement": 30,
        "chakra_cost": 19, "stamina_cost": 12, "cooldown": 6.0,
        "damage": (18, 30), "damage_type": "physical", "effect": None,
        "tier": 2, "element": "none", "jutsu_type": "thrown", "requires_item": "kunai",
        "explosive_chance_pct": 30, "explosive_damage": (50, 80),
        # Confirmed design: a SINGLE roll picks EITHER the normal
        # kunai damage range above OR the bigger explosive_damage
        # range -- never both on the same throw. Same requires_item
        # consumption as Throw Kunai (this is thematically the same
        # basic kunai, just occasionally rigged to detonate).
    },
    **{
        name.lower(): {
            "jutsu_id": "arts_" + name.replace(" ", "_"), "display_name": name.title(),
            "class_requirement": category, "level_requirement": level,
            "chakra_cost": chakra, "stamina_cost": stamina, "cooldown": cooldown,
            "damage": damage, "damage_type": "physical" if category == "bukijutsu" else "chakra",
            "effect": effect, "tier": 1 if level < 25 else 2 if level < 50 else 3,
            "element": element, "jutsu_type": kind,
            **({"requires_item": item} if item else {}),
            **({"requires_item_count": 3} if name.startswith("Multi-") else {}),
            **({"effect_chance_pct": chance} if chance else {}),
        }
        for name, category, level, chakra, stamina, cooldown, damage, effect, element, kind, item, chance in [
            ("Multi-Shuriken Throw", "bukijutsu", 10, 0, 12, 4.0, (18, 32), None, "none", "thrown", "shuriken", 0),
            ("Multi-Kunai Throw", "bukijutsu", 20, 0, 16, 4.5, (26, 42), None, "none", "thrown", "kunai", 0),
            ("Demon Wind Shuriken", "bukijutsu", 35, 20, 22, 7.0, (36, 58), "bleeding", "none", "thrown", "demon wind shuriken", 35),
            ("Toxin Binding", "bukijutsu", 30, 45, 15, 8.0, None, None, "none", "weapon_art", None, 0),
            ("Exploding Note", "bukijutsu", 25, 25, 12, 6.0, None, None, "none", "trap", "exploding note", 0),
            ("Smoke Bomb", "bukijutsu", 30, 30, 12, 7.0, None, None, "none", "trap", "smoke bomb", 0),
            ("Poison Gas Bomb", "bukijutsu", 40, 40, 15, 8.0, None, None, "none", "trap", "poison gas bomb", 0),
            ("Exploding Clay", "bukijutsu", 50, 50, 20, 9.0, None, None, "none", "trap", "exploding clay", 0),
            ("Trap Disabling", "bukijutsu", 25, 15, 10, 5.0, None, None, "none", "trap_disable", None, 0),
            ("Weapon Enchantment", "bukijutsu", 55, 60, 20, 10.0, None, None, "none", "weapon_art", None, 0),
            ("Disenchantment", "bukijutsu", 45, 30, 12, 7.0, None, None, "none", "weapon_art", None, 0),
            ("Fan Techniques", "bukijutsu", 40, 35, 20, 7.0, (30, 48), "off_balance", "wind", "fan_art", None, 35),
            ("Water Release: Glue Technique", "ninjutsu", 35, 35, 0, 7.0, None, None, "water", "weapon_art", None, 0),
        ]
    },
    "samurai sabre": {
        "jutsu_id": "arts_samurai_sabre", "display_name": "Samurai Sabre",
        "class_requirement": "bukijutsu", "level_requirement": 35,
        "chakra_cost": 35, "stamina_cost": 10, "cooldown": 25.0,
        "jutsu_type": "sabre_buff", "required_weapon_types": ("sword",),
        "damage": None, "damage_type": None, "effect": None,
        "tier": 2, "element": "none",
    },
    "flying swallow": {
        "jutsu_id": "arts_flying_swallow", "display_name": "Flying Swallow",
        "class_requirement": "bukijutsu", "level_requirement": 45,
        "chakra_cost": 30, "stamina_cost": 18, "cooldown": 7.0,
        "jutsu_type": "blade_strike", "required_weapon_types": ("sword", "kunai"),
        "damage": (38, 58), "damage_type": "physical", "effect": "bleeding",
        "effect_chance_pct": 30, "accuracy_bonus": 15,
        "wind_damage_bonus_pct": 15, "tier": 2, "element": "none",
    },
    "fireball jutsu": {
        "jutsu_id": "ninjutsu_fireball", "display_name": "Fireball Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "burning", "effect_chance_pct": 40,
        "tier": 2, "element": "fire",
        # HARD elemental gate (Section 85, confirmed: "a person cant
        # cast jutsu that is not theire element") -- only castable by
        # a player whose chakra_nature (primary OR secondary) is
        # genuinely "fire", checked in combat._can_use_jutsu. A 40%
        # chance to also inflict Burning (HP damage over time, a
        # genuine standalone per-round timer -- see
        # combat.tick_effects_pulse/tick_all_mob_effects).
    },
    "water dragon jutsu": {
        "jutsu_id": "ninjutsu_water_dragon", "display_name": "Water Dragon Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "drained", "effect_chance_pct": 40,
        "tier": 2, "element": "water",
        # Same hard gate as Fireball Jutsu above, requiring "water".
        # 40% chance to inflict Drained (chakra loss over time --
        # confirmed design distinct from Off Balance's stamina drain,
        # even though both reduce a resource, per direct request to
        # differentiate Water from Wind).
    },
    "wind blade jutsu": {
        "jutsu_id": "ninjutsu_wind_blade", "display_name": "Wind Blade Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "off_balance", "effect_chance_pct": 40,
        "tier": 2, "element": "wind",
        # Same hard gate, requiring "wind". 40% chance to inflict Off
        # Balance (stamina loss over time -- confirmed flavor:
        # "knocked off balance", explicitly NOT a dodge/accuracy
        # effect, explicitly NOT the same mechanic as Water's chakra
        # drain despite the surface-level similarity).
    },
    "lightning strike jutsu": {
        "jutsu_id": "ninjutsu_lightning_strike", "display_name": "Lightning Strike Jutsu",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 28, "stamina_cost": 0, "cooldown": 6.0,
        "damage": (24, 40), "damage_type": "chakra", "effect": "paralyzed", "effect_chance_pct": 30,
        "tier": 2, "element": "lightning",
        # Same hard gate, requiring "lightning". A genuinely lower 30%
        # chance than the other 3 (12/18/-- wait, matches their 40%
        # actually not applicable) -- Paralyzed blocks the target's
        # entire next action outright (reusing the same blocks_action
        # mechanic already proven by genjutsu_locked/stunned), a
        # stronger effect than a damage/resource drain over time, so
        # it's intentionally rarer to trigger.
    },
    "earth wall crusher": {
        "jutsu_id": "ninjutsu_earth_wall_crusher", "display_name": "Earth Wall Crusher",
        "class_requirement": "ninjutsu", "level_requirement": 20,
        "chakra_cost": 25, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (40, 64), "damage_type": "chakra", "effect": None,
        "tier": 2, "element": "earth",
        # Same hard gate, requiring "earth". Confirmed design: Earth
        # deliberately carries NO status effect at all -- instead, its
        # own damage range (20-32) is noticeably higher than the
        # other 4 elemental jutsu above (12-20), reflecting "raw,
        # upfront damage" per direct confirmation, rather than a
        # lingering effect.
    },
    "tsukuyomi": {
        "jutsu_id": "mangekyo_tsukuyomi", "display_name": "Tsukuyomi",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 65, "stamina_cost": 0, "cooldown": 90.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): casting immediately
        # moves BOTH caster and target into a shared, real torture
        # room (mangekyo.open_tsukuyomi), unlike Kamui's own 2-step
        # entry. A real random number from 5-10 (hidden from both
        # players) sets how many of the caster's own real actions the
        # technique lasts -- see the 5 real torture commands (stab/
        # impale/burn/crush/unmake) in commands.py's own cmd_stab
        # etc.
        "jutsu_type": "mangekyo_tsukuyomi",
        "kkg_gate": "mangekyo_technique",
    },
    "amaterasu": {
        "jutsu_id": "mangekyo_amaterasu", "display_name": "Amaterasu",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 60, "stamina_cost": 0, "cooldown": 30.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): gated by genuinely
        # having rolled Amaterasu as one of the player's own 2 real
        # Mangekyo eye techniques, checked via combat._can_use_jutsu's
        # own real kkg_gate handling (see "mangekyo_technique" there).
        # No fixed real damage tuple -- the actual effect (a genuinely
        # permanent player-burn AND a real, separate room-fire) is
        # applied directly by commands.py's own dispatch, see its
        # "mangekyo_amaterasu" jutsu_type branch.
        "jutsu_type": "mangekyo_amaterasu",
        "kkg_gate": "mangekyo_technique",
    },
    "kamui pocket dimension": {
        "jutsu_id": "mangekyo_kamui_pocket_dimension", "display_name": "Kamui: Pocket Dimension",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 0, "stamina_cost": 0, "cooldown": 0.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): a real, deliberate
        # 2-step cast -- casting on a TARGET opens the dimension and
        # sends them alone; casting again on ONESELF joins them there.
        # No chakra cost to enter (confirmed directly) -- real upkeep
        # only starts once the caster is actually inside (see
        # mangekyo.process_kamui_pocket_dimensions). Shares
        # mangekyo_roster_key with the other 2 real Kamui jutsu below,
        # since all 3 are unlocked by a single real roll of "kamui".
        "jutsu_type": "mangekyo_kamui_pocket_dimension",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kamui",
    },
    "kamui intangibility": {
        "jutsu_id": "mangekyo_kamui_intangibility", "display_name": "Kamui: Intangibility",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 40, "stamina_cost": 0, "cooldown": 60.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): a real, guaranteed
        # 3-round window (data_mangekyo.KAMUI_INTANGIBILITY_ROUNDS)
        # where every incoming attack simply misses. Applied via the
        # real kamui_intangibility_rounds_left counter on Player,
        # checked at every real hit-roll site.
        "jutsu_type": "mangekyo_kamui_intangibility",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kamui",
    },
    "kamui limb removal": {
        "jutsu_id": "mangekyo_kamui_limb_removal", "display_name": "Kamui: Limb Removal",
        "class_requirement": "ninjutsu", "level_requirement": 1,
        "chakra_cost": 80, "stamina_cost": 0, "cooldown": 45.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): a long, real,
        # interruptible 6-8 second cast (data_mangekyo.
        # KAMUI_LIMB_REMOVAL_CAST_SECONDS); if it lands, a one-time
        # burst of roughly 1200-1600 damage (data_mangekyo.
        # KAMUI_LIMB_REMOVAL_DAMAGE). Uses the same real delayed-cast
        # system as Amaterasu/Illusion Walk, just with a genuinely
        # longer, randomized real delay instead of the usual
        # Handsigns-based one.
        "jutsu_type": "mangekyo_kamui_limb_removal",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kamui",
    },
    "izanami": {
        "jutsu_id": "mangekyo_izanami", "display_name": "Izanami",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 70, "stamina_cost": 0, "cooldown": 60.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): traps a target in a
        # real, recursive loop -- a fixed real number from 1-25, set
        # once and never re-rolled, that the target must correctly
        # guess (one real guess per round) to escape. Cannot be
        # attacked by anyone while looped, confirmed directly. No cap
        # on duration at all -- only ends on a correct guess. The
        # CASTER is completely free to act normally elsewhere while
        # it's running, confirmed directly.
        "jutsu_type": "mangekyo_izanami",
        "kkg_gate": "mangekyo_technique",
    },
    "kekkei no me": {
        "jutsu_id": "mangekyo_kekkei_no_me", "display_name": "Kekkei no Me",
        "class_requirement": "genjutsu", "level_requirement": 1,
        "chakra_cost": 50, "stamina_cost": 0, "cooldown": 120.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 5, "element": "none",
        # Per direct confirmation (Section 140): transforms the
        # CURRENT room in place (no one moves) into the caster's own
        # real, active chakra-nature element. The caster gets a real
        # +50% damage bonus to their own matching-element jutsu while
        # inside; everyone else takes real chakra AND stamina drain
        # per tick. Lasts a real 90 seconds.
        "jutsu_type": "mangekyo_kekkei_no_me",
        "kkg_gate": "mangekyo_technique",
        "mangekyo_roster_key": "kekkei_no_me",
    },
}

# New Ninjutsu follows the game's 1-100 progression. Elemental entries
# require the corresponding revealed chakra nature at cast time.
def _ninjutsu(name, level, cost, damage, element="none", **options):
    return {
        "jutsu_id": "ninjutsu_" + name.lower().replace(" ", "_"),
        "display_name": name, "class_requirement": "ninjutsu",
        "level_requirement": level, "chakra_cost": cost, "stamina_cost": 0,
        "cooldown": options.pop("cooldown", 5.0), "damage": damage,
        "damage_type": "chakra", "effect": options.pop("effect", None),
        "tier": 1 if level < 25 else 2 if level < 50 else 3,
        "element": element, **options,
    }


JUTSU.update({
    "chakra ball": _ninjutsu("Chakra Ball", 3, 9, (9, 16), cooldown=2.5),
    "rasengan": _ninjutsu("Rasengan", 25, 24, (27, 43)),
    "oodama rasengan": _ninjutsu("Oodama Rasengan", 45, 42, (48, 72), cooldown=8.0),
    # The original source unlocks this beyond level 100. Nindo caps at 100,
    # so its seven-stage attack is the Ninjutsu level-cap technique here.
    "nanairo no rasengan": _ninjutsu("Nanairo no Rasengan", 100, 120, (25, 38),
                                     jutsu_type="sevenfold", cooldown=25.0),
    "suigadan": _ninjutsu("Suigadan", 30, 28, (28, 46), "water", requires_water=True),
    "juuha shou": _ninjutsu("Juuha Shou", 30, 28, (28, 46), "wind", effect="off_balance", effect_chance_pct=25),
    "karyuu endan": _ninjutsu("Karyuu Endan", 40, 36, (41, 65), "fire", effect="burning", effect_chance_pct=40),
    "retsudotensho": _ninjutsu("Retsudotensho", 40, 36, (45, 69), "earth"),
    "chishin": _ninjutsu("Chishin", 50, 44, (52, 76), "earth", jutsu_type="area", cooldown=9.0),
    "chidori": _ninjutsu("Chidori", 30, 30, (33, 50), "lightning", effect="paralyzed", effect_chance_pct=15),
    "dual chidori": _ninjutsu("Dual Chidori", 45, 42, (49, 70), "lightning", effect="paralyzed", effect_chance_pct=20),
    "full body chidori": _ninjutsu("Full Body Chidori", 60, 56, (65, 90), "lightning", effect="paralyzed", effect_chance_pct=25),
    "maximum chidori": _ninjutsu("Maximum Chidori", 75, 72, (83, 115), "lightning", effect="paralyzed", effect_chance_pct=30),
    "raikiri": _ninjutsu("Raikiri", 60, 58, (70, 100), "lightning", jutsu_type="ambush", ambush_multiplier=1.5, cooldown=10.0),
})

# A focused Rasengan variant for each of the five base chakra natures.
for _element, _effect in (("fire", "burning"), ("water", "drained"),
                          ("wind", "off_balance"), ("earth", None),
                          ("lightning", "paralyzed")):
    _name = f"{_element.capitalize()} Rasengan"
    JUTSU[_name.lower()] = _ninjutsu(
        _name, 40, 38, (52, 76) if _element == "earth" else (42, 65),
        _element, effect=_effect, effect_chance_pct=25 if _effect else 0,
        cooldown=7.0,
    )

for _element, _name in (("lightning", "Raiton Kage Bunshin"),
                        ("water", "Mizu Bunshin"),
                        ("earth", "Deido Bunshin"),
                        ("earth", "Suna Bunshin")):
    JUTSU[_name.lower()] = _ninjutsu(
        _name, 45, 55, None, _element, jutsu_type="elemental_clone",
        clone_element="sand" if _name == "Suna Bunshin" else _element,
        cooldown=10.0,
    )


def _scale_base_damage_to_level() -> None:
    """Place each damaging jutsu on the 20-word damage ladder by unlock level.

    A level-75 art sits about three quarters of the way up the ladder.
    Sevenfold attacks split that cast's base damage across seven strikes.
    Special effects, bonuses, defense, and multipliers still apply in combat.
    """
    import damage_messages

    tiers = damage_messages.DAMAGE_TIERS
    for jutsu in JUTSU.values():
        if jutsu.get("damage") is None:
            continue
        original_low, original_high = jutsu["damage"]
        level = max(1, min(100, jutsu["level_requirement"]))
        # The first tier is reserved for zero/one damage; even a starting
        # attack should deal a few points. Level 100 reaches the top tier.
        index = 1 + ((level - 1) * (len(tiers) - 2) + 49) // 99
        prior_max = tiers[index - 1][0]
        minimum = prior_max + 1
        maximum = tiers[index][0] or 11000
        low = minimum + (maximum - minimum) * 3 // 10
        high = minimum + (maximum - minimum) * 7 // 10
        if jutsu.get("jutsu_type") == "sevenfold":
            low, high = max(1, low // 7), max(1, high // 7)
        jutsu["damage"] = (low, high)
        if "explosive_damage" in jutsu:
            # Preserve the explosive proc's advantage over its normal hit.
            blast_low, blast_high = jutsu["explosive_damage"]
            jutsu["explosive_damage"] = (
                max(low + 1, round(low * blast_low / original_low)),
                max(high + 1, round(high * blast_high / original_high)),
            )


JUTSU["barrier"] = {
    "jutsu_id": "general_barrier", "display_name": "Barrier",
    "class_requirement": "general", "level_requirement": 35,
    "chakra_cost": 30, "stamina_cost": 0, "cooldown": 12.0,
    "damage": None, "damage_type": None, "effect": None,
    "jutsu_type": "buff", "tier": 2, "element": "none",
}


def _genjutsu(name, level, cost, damage=None, effect=None, **options):
    return {
        "jutsu_id": "genjutsu_" + name.lower().replace(" ", "_"),
        "display_name": name, "class_requirement": "genjutsu",
        "level_requirement": level, "chakra_cost": cost, "stamina_cost": 0,
        "cooldown": options.pop("cooldown", 5.0), "damage": damage,
        "damage_type": "mental" if damage is not None else None,
        "effect": effect, "tier": 1 if level < 25 else 2 if level < 50 else 3,
        "element": "none", **options,
    }


JUTSU.update({
    "henge": _genjutsu("Henge", 5, 12, jutsu_type="disguise", duration=12),
    "greater henge": _genjutsu("Greater Henge", 25, 25, jutsu_type="disguise", duration=25),
    "ultimate henge": _genjutsu("Ultimate Henge", 55, 45, jutsu_type="disguise", duration=45),
    "kokohi arazu": _genjutsu("Kokohi Arazu", 18, 20, jutsu_type="item_illusion", duration=20),
    "niju kokohi arazu": _genjutsu("Niju Kokohi Arazu", 35, 28, jutsu_type="item_decoy", duration=20),
    "chisei": _genjutsu("Chisei", 40, 30, jutsu_type="chisei", cooldown=15),
    "distortion flame": _genjutsu("Distortion Flame", 8, 14, (12, 20)),
    "phantom soldiers": _genjutsu("Phantom Soldiers", 12, 18, (16, 25)),
    "soundless sound": _genjutsu("Soundless Sound", 22, 23, (20, 33), "soundless", effect_chance_pct=65),
    "kori shinchu": _genjutsu("Kori Shinchu", 32, 31, (24, 39), "disoriented", effect_chance_pct=65, stamina_drain=20),
    "oboro bunshin": _genjutsu("Oboro Bunshin", 17, 18, (9, 17), "confused", effect_chance_pct=80),
    "kanashibari": _genjutsu("Kanashibari", 28, 26, (4, 9), "paralyzed", effect_chance_pct=50, cooldown=8),
    "snakes embrace": _genjutsu("Snake's Embrace", 30, 28, (27, 41), "weakened", effect_chance_pct=65),
    "devils taunt": _genjutsu("Devil's Taunt", 20, 20, (10, 18), "stunned", effect_chance_pct=45),
    "insect eyes": _genjutsu("Insect Eyes", 50, 43, (15, 30), jutsu_type="mirror", cooldown=9),
    "kasumi juusha": _genjutsu("Kasumi Jūsha", 43, 34, (12, 22), "haze", effect_chance_pct=75),
    "suzu senbon": _genjutsu("Suzu Senbon", 36, 32, (29, 46), "ringing", effect_chance_pct=65),
    "nehan shouja": _genjutsu("Nehan Shōja", 65, 60, jutsu_type="room_sleep", cooldown=20),
    "jubaku satsu": _genjutsu("Jubaku Satsu", 58, 48, (42, 64), "stunned", effect_chance_pct=60, cooldown=9),
    "jigaku gouka": _genjutsu("Jigaku Gōka", 52, 44, (48, 72), "narakumi", effect_chance_pct=65),
    "kokuangyou": _genjutsu("Kokuangyō", 48, 40, (8, 16), "blinded", effect_chance_pct=75),
})

JUTSU.update({
    "ice senbon": {
        "jutsu_id": "ice_release_senbon", "display_name": "Ice Senbon",
        "class_requirement": "ninjutsu", "level_requirement": 25,
        "chakra_cost": 24, "stamina_cost": 0, "cooldown": 5.0,
        "damage": (30, 48), "damage_type": "chakra", "effect": "off_balance",
        "effect_chance_pct": 25, "tier": 2, "element": "none", "kkg_gate": "ice_release",
    },
    "ice prison": {
        "jutsu_id": "ice_release_prison", "display_name": "Ice Prison",
        "class_requirement": "ninjutsu", "level_requirement": 45,
        "chakra_cost": 42, "stamina_cost": 0, "cooldown": 14.0,
        "damage": (38, 62), "damage_type": "chakra", "effect": "paralyzed",
        "effect_chance_pct": 45, "tier": 3, "element": "none", "kkg_gate": "ice_release",
    },
    "demonic mirroring ice crystals": {
        "jutsu_id": "ice_release_mirrors", "display_name": "Demonic Mirroring Ice Crystals",
        "class_requirement": "ninjutsu", "level_requirement": 70,
        "chakra_cost": 78, "stamina_cost": 0, "cooldown": 24.0,
        "damage": (85, 125), "damage_type": "chakra", "effect": "blinded",
        "effect_chance_pct": 35, "tier": 5, "element": "none", "kkg_gate": "ice_release",
    },
})

import elemental_release_arts
JUTSU.update(elemental_release_arts.jutsu_entries())
import six_paths
JUTSU.update(six_paths.jutsu_entries())
import reaper_seal
JUTSU.update(reaper_seal.jutsu_entries())
import hyuga
JUTSU.update(hyuga.registry())
_scale_base_damage_to_level()

# The universal starting kit -- every player gets exactly these,
# regardless of class. Used by both session.py's chargen AND
# leveling.sync_universal_skills() (the login update-check), so the two
# can never drift apart -- add a jutsu here once and both paths pick it
# up automatically.
UNIVERSAL_STARTING_SKILLS = [
    "Shadow Shuriken Technique",
    "Dynamic Entry",
    "Demonic Illusion: Hell Viewing Technique",
    "Throw Shuriken",
    "Strong Fist Style",
    "Anki",
]

CHAKRA_CHARGE_LEVEL = 10

# Examine (commands.cmd_examine) is NOT part of the universal
# starting kit -- whether a player has it at all is gated by character
# LEVEL, not granted for free at creation. Unlocked automatically the
# first time a player reaches this level (leveling.py's level-up
# rewards, and leveling.sync_universal_skills() for a returning
# high-level player who predates this or never logged in to trigger
# the level-up grant).
APPRAISAL_LEVEL_REQUIREMENT = 20

# Multiple attacks per round, per explicit request. Each entry is
# (display_name, level_requirement, required_primary_class_or_None).
# Second/Third Attack are general -- any primary class gets them.
# Fourth/Fifth Attack are Bukijutsu-specific. All four are auto-granted
# the moment a qualifying character reaches the level (leveling.py's
# level-up rewards, and leveling.sync_universal_skills() for a
# returning high-level player), exactly the same mechanism as
# Examine above -- not taught by a scroll/teacher. Each is trainable
# via 'practice' afterward like any other skill; the % chance of that
# extra attack actually landing in a given combat round scales with
# proficiency (see combat.py's attack-count resolution), so a freshly
# -granted skill at 0% doesn't immediately double a character's damage
# output -- it has to be trained up first, same as everything else
# proficiency-gated in this game.
MULTI_ATTACK_SKILLS = [
    ("Second Attack", 25, None),
    ("Third Attack", 50, None),
    ("Fourth Attack", 75, "bukijutsu"),
    ("Fifth Attack", 90, "bukijutsu"),
]

# Renames of an existing skill's display name (old -> new). Empty for
# now -- exists so that if a jutsu is ever renamed, existing players'
# learned_skills/skill_proficiencies keys can be migrated automatically
# at login instead of silently going stale. See
# leveling.sync_universal_skills().
SKILL_RENAMES = {
    "Appraisal": "Examine",  # per direct request ("rename appraisal to examine like its command to use it")
}


# Confirmed design: "e" alone should never resolve to Explosive Tag
# Kunai -- a single letter is too easy to type by accident for an
# ability with real consequences (consumes a real inventory kunai, a
# genuine chance of a much bigger hit than intended). Every other
# jutsu's existing single-letter-or-more shorthand behavior is
# completely unaffected -- this is a targeted exception, not a
# general rule (confirmed directly rather than assumed either way).
GENERAL_UTILITY_SKILLS = {
    "camouflage": ("Camouflage", 10, 15, 5),
    "silent movement": ("Silent Movement", 15, 0, 10),
    "sensory detect": ("Sensory Detect", 20, 20, 0),
    "focused mind": ("Focused Mind", 25, 20, 5),
}
for _key, (_name, _level, _chakra, _stamina) in GENERAL_UTILITY_SKILLS.items():
    JUTSU[_key] = {
        "jutsu_id": "general_" + _key.replace(" ", "_"), "display_name": _name,
        "class_requirement": "general", "level_requirement": _level,
        "chakra_cost": _chakra, "stamina_cost": _stamina, "cooldown": 15.0,
        "damage": None, "damage_type": None, "effect": None,
        "tier": 1, "element": "none", "jutsu_type": "general_utility",
    }

MIN_MATCH_PREFIX_LENGTH = {
    "explosive tag kunai": 2,
}

JUTSU_ALIASES = {
    "camouflag": "camouflage",
    "camoflage": "camouflage",
    "camoflauge": "camouflage",
    "silent": "silent genjutsu",  # preserve the existing Genjutsu shorthand
    "vital surge": "six paths vital surge",
    "six paths: vital surge": "six paths vital surge",
    "demonic": "demonic illusion hell viewing technique",  # preserve the established short command
    "ex": "explosive tag kunai",  # preserve the established two-letter shortcut
    "explosive": "explosive tag kunai",  # preserve it despite new Exploding Note/Clay
    "tamashiware": "tamashiwara",  # common spelling of the new Taijutsu strike
    "n": "narakumi",  # preserve the existing perform-n shorthand after adding Neko Ashi Dachi
    "c": "counter kunai",  # preserve the existing shorthand after adding Choku Zuki
    "doton rasengan": "earth rasengan",
    "katon rasengan": "fire rasengan",
    "suiton rasengan": "water rasengan",
    "fuuton rasengan": "wind rasengan",
    "raiton rasengan": "lightning rasengan",
}


from jutsu_shortcuts import JUTSU_SHORTCUTS, SHORTCUT_JUTSU


def match_prefix(lower_words):
    """Match a jutsu from the given lowercased word list. Two things
    can happen, tried longest-input-first so the full name still works
    exactly as before:
      1. The player typed the FULL name (or more, e.g. followed by a
         target) -- the classic case, where the jutsu key is a prefix
         of what they typed.
      2. The player typed a SHORT keyword or partial name (e.g. 'demonic'
         for 'Demonic Illusion: Hell Viewing Technique', or 'shadow
         shuriken' for 'Shadow Shuriken Technique') -- what they typed
         is a prefix of the jutsu's full name instead. Tried from the
         longest plausible partial down to a single word, so a two-word
         partial like 'shadow shuriken' doesn't wrongly eat only 'shadow'
         and leave 'shuriken' to be misread as part of the target name.

    Returns (jutsu_key, word_count_consumed) or (None, 0).
    """
    # The roster and help display "Kamui: ..."; accept that spelling as
    # well as the command spelling. Bare Kamui is the pocket technique,
    # while a specified variant must never be mistaken for its target.
    if lower_words and lower_words[0] == "100":
        lower_words = ["1000", *lower_words[1:]]
    if lower_words and lower_words[0] == "kamui:":
        lower_words = ["kamui", *lower_words[1:]]
    if lower_words and lower_words[0] == "kamui":
        if len(lower_words) > 1:
            variants = [key for key in ("kamui pocket dimension", "kamui intangibility", "kamui limb removal")
                        if key.split()[1].startswith(lower_words[1])]
            if variants:
                if len(variants) == 1:
                    full_words = variants[0].split()
                    consumed = (3 if len(full_words) > 2 and len(lower_words) > 2
                                and full_words[2].startswith(lower_words[2]) else 2)
                    return variants[0], consumed
                return None, 0
        return "kamui pocket dimension", 1
    joined = " ".join(lower_words)
    # An exact technique (possibly followed by its target) outranks a
    # historical short alias such as "demonic".
    for key in sorted(JUTSU.keys(), key=lambda k: -len(k.split())):
        if joined == key or joined.startswith(key + " "):
            return key, len(key.split())
    for alias in sorted(JUTSU_ALIASES, key=lambda name: -len(name.split())):
        if joined == alias or joined.startswith(alias + " "):
            return JUTSU_ALIASES[alias], len(alias.split())

    if lower_words and lower_words[0] in SHORTCUT_JUTSU:
        return SHORTCUT_JUTSU[lower_words[0]], 1

    max_jutsu_words = max((len(k.split()) for k in JUTSU), default=1)
    for length in range(min(max_jutsu_words, len(lower_words)), 0, -1):
        candidate = " ".join(lower_words[:length])
        matches = sorted(key for key in JUTSU if key.startswith(candidate))
        if len(matches) == 1:
            if len(candidate) < MIN_MATCH_PREFIX_LENGTH.get(matches[0], 1):
                # The only match exists, but the player's own typed
                # candidate is too short for THIS specific jutsu's own
                # confirmed minimum (e.g. "e" for Explosive Tag Kunai)
                # -- treat it as no match at all rather than accepting
                # a shorthand deliberately disallowed for this one.
                continue
            return matches[0], length
        if len(matches) > 1:
            # A genuine tie at this word-length -- e.g. "shadow" alone
            # now matches both "shadow clone jutsu" and "shadow
            # shuriken technique". Refuse to guess rather than pick one
            # arbitrarily; the caller reports "you don't know a jutsu
            # by that name" and the player can be more specific (e.g.
            # "shadow shuriken" or "shadow clone", both unambiguous).
            return None, 0

    return None, 0


def jutsu_for_class_at_level(class_name: str, level: int):
    """Return jutsu keys newly unlocked exactly at this level for this
    class, called from leveling.py on every level-up. Genuinely empty
    for the original starter jutsu (level_requirement 1 -- everyone
    already has those from character creation, before this function
    is ever called), but NOT a no-op overall: every jutsu added since
    with a real level_requirement above 1 (Shadow Clone Jutsu,
    Narakumi, Throw Kunai, Counter Kunai, Explosive Tag Kunai) is
    genuinely granted through this exact path the moment a matching-
    class player reaches the right level -- verified directly, not
    assumed."""
    return [
        key for key, data in JUTSU.items()
        if data["class_requirement"] in (class_name, "general") and data["level_requirement"] == level
        and not data.get("scroll_only") and not data.get("kkg_gate")
    ]


def all_jutsu_keys():
    """Staff testing roster across classes and levels, excluding skills
    explicitly reserved for scroll learning."""
    return [key for key, data in JUTSU.items() if not data.get("scroll_only")]


def all_unlocked_for_class(class_name: str, level: int):
    return [
        key for key, data in JUTSU.items()
        if data["class_requirement"] in (class_name, "general") and data["level_requirement"] <= level
        and not data.get("scroll_only") and not data.get("kkg_gate")
    ]
