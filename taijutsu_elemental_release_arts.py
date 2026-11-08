"""Physical Taijutsu counterparts to every elemental Kekkei Genkai release.

These are a 1:1 companion suite to the existing elemental Ninjutsu arts:
three close-range martial attacks for each of the ten releases in
elemental_release_arts, plus three Ice Release attacks. All inherit the
same release gate, tier unlocks and status-effect theme. They never use
hand signs; attack power is physical and consumes mostly Stamina.
"""
import elemental_release_arts as ninjutsu_arts

# Release order and technique order match the Ninjutsu source exactly.
# Distinctive hand-to-hand names prevent collisions with existing jutsu.
TAIJUTSU_MOVES = {
    "ice_release": (
        ("Frost Knuckle", "A numbing ice-laced knuckle strike."),
        ("Glacier Heel", "A frozen heel kick that locks an enemy's movement."),
        ("Mirrored Lotus Rush", "A blinding flurry of mirrorlike ice strikes."),
    ),
    "wood_release": (
        ("Thornwood Jab", "A thorned wooden fist catches the opponent's stance."),
        ("Rootbreaker Sweep", "Grasping roots weaken the victim during a leg sweep."),
        ("Forest Pulse Palm", "A forceful palm strike disrupts the enemy's chakra."),
    ),
    "storm_release": (
        ("Storm Current Jab", "A sharp jab carrying a draining electric current."),
        ("Guiding Thunder Knee", "A focused rising knee briefly paralyzes."),
        ("Stormbreaker Rush", "A chain of storm-driven blows disrupts footing."),
    ),
    "boil_release": (
        ("Scalding Palm", "A heated palm burns on contact."),
        ("Vapor Rising Knee", "Steam from a rising knee clouds the enemy's sight."),
        ("Pressure Burst Fist", "A pressure-charged fist weakens the defender."),
    ),
    "lava_release": (
        ("Cinder Heel", "A molten-heeled kick burns the opponent."),
        ("Magma Hammer Fist", "A heavy magma-coated punch breaks the enemy's stance."),
        ("Volcanic Axe Kick", "A volcanic axe kick leaves searing burns."),
    ),
    "scorch_release": (
        ("Searing Elbow", "A scorching elbow ignites on impact."),
        ("Heat Mirage Roundhouse", "Shimmering heat hides the source of the kick."),
        ("Solar Flare Fist", "A blazing punch leaves the target burning."),
    ),
    "magnet_release": (
        ("Iron Sand Knuckle", "An iron-sand jab knocks the victim off balance."),
        ("Polar Lock Grip", "Magnetic force briefly locks the enemy's muscles."),
        ("Magnetic Cyclone Kick", "Whirling iron sand blinds during a spinning kick."),
    ),
    "explosion_release": (
        ("Blast Knuckle", "A small detonation follows the opening fist."),
        ("Detonation Rising Knee", "An explosive knee strike blinds with its flash."),
        ("Explosive Lotus Barrage", "A barrage of strikes ends with a stunning blast."),
    ),
    "flashfire_release": (
        ("Flash Ember Jab", "An incandescent jab leaves a lingering burn."),
        ("Blazing Flash Kick", "A flash of flame hides the kick's trajectory."),
        ("Nova Impact Palm", "A searing flash erupts from a decisive palm strike."),
    ),
    "tempest_release": (
        ("Gale Spark Step", "A fast step-through punch unbalances its target."),
        ("Thunderwind Heel", "A charged heel kick briefly paralyzes."),
        ("Tempest Spiral Rush", "A spiraling rush clouds the victim's vision."),
    ),
    "dust_release": (
        ("Particle Palm", "A vibrating particle palm disrupts the enemy's stance."),
        ("Disintegration Heel", "A charged heel kick temporarily freezes movement."),
        ("Atomic Lotus Strike", "A precise cascade of particle-charged blows weakens."),
    ),
}

# Ice Release uses the pre-existing Ice Ninjutsu three-tier definitions.
ICE_EFFECTS = (
    ("off_balance", 25),
    ("paralyzed", 45),
    ("blinded", 35),
)


def jutsu_entries():
    """Build the full, nature-locked, Taijutsu-only 33-move companion set."""
    entries = {}
    releases = set(ninjutsu_arts.ARTS) | {"ice_release"}
    if releases != set(TAIJUTSU_MOVES):
        raise ValueError("Taijutsu elemental KKGK roster must mirror all Ninjutsu releases")
    for release_id in sorted(releases):
        techniques = TAIJUTSU_MOVES[release_id]
        if release_id == "ice_release":
            effects = ICE_EFFECTS
            tiers = ninjutsu_arts.ICE_TIERS
        else:
            effects = [(effect, chance) for _name, effect, chance, _signs
                       in ninjutsu_arts.ARTS[release_id]]
            tiers = (ninjutsu_arts.DUST_TIERS if release_id == "dust_release"
                     else ninjutsu_arts.ICE_TIERS)
        if len(techniques) != len(effects) or len(effects) != len(tiers):
            raise ValueError(f"KKGK Taijutsu mismatch: {release_id}")
        for index, ((name, flavor), (effect, chance),
                    (level, source_damage, chakra_cost, cooldown, tier)) in enumerate(
                        zip(techniques, effects, tiers), start=1):
            key = name.lower()
            # Taijutsu trades Ninjutsu's cast time and high Chakra price for
            # a more demanding Stamina cost, modest Chakra and lower damage.
            # The final damage scaling is applied by data_jutsu below.
            stamina_cost = max(12, round(chakra_cost * 0.85))
            chakra_cost = max(5, chakra_cost // 4)
            entries[key] = {
                "jutsu_id": f"taijutsu_{release_id}_{index}",
                "display_name": name,
                "class_requirement": "taijutsu",
                "jutsu_type": "kkgk_taijutsu_strike",
                "level_requirement": level,
                "chakra_cost": chakra_cost,
                "stamina_cost": stamina_cost,
                "cooldown": max(3.0, cooldown * 0.75),
                "damage": source_damage,
                "damage_type": "physical",
                "effect": effect,
                "effect_chance_pct": chance,
                "tier": tier,
                "element": "none",  # The two/three-nature KKGK gate is authoritative.
                "kkg_gate": release_id,
                "melee_only": True,
                "description": flavor,
            }
    if len(entries) != 33:
        raise ValueError(f"Expected 33 KKGK Taijutsu moves, got {len(entries)}")
    return entries
