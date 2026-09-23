"""
Clan data (flavor only for this pass), grouped by village.

Section 48 explicitly reserves clans/bloodlines/kekkei genkai as a later
mechanical system. This module adds the clan NAME as a purely cosmetic
attribute (shown on the score sheet, who-list, etc.) with no stat bonuses
or special abilities attached -- those come later, and this table is
exactly where they'd be hooked in when they do.

Clans are grouped by village: a character can only join a clan that
belongs to their own village (see CLANS_BY_VILLAGE / commands.cmd_clan).
"""

CLANS_BY_VILLAGE = {
    "leaf": ["uchiha", "hyuga", "nara", "uzumaki",
             "akimichi", "yamanaka", "inuzuka", "aburame", "sarutobi", "senju"],
    "cloud": ["yotsuki", "chinoike", "kinkaku", "jugo",
              "nii", "kirabi", "dobutsu", "karui", "samui", "darui"],
    "water": ["hozuki", "yuki", "kaguya", "hoshigaki",
              "terumi", "fuguki", "raiga", "mangetsu", "chojuro", "momochi"],
    "sand": ["inugami", "chikamatsu", "shirogane", "pakura",
             "sasori", "chiyo", "baki", "yashamaru", "sabaku"],
    "stone": ["kamizuru", "oyama", "deidara", "gari",
              "akatsuchi", "kurotsuchi", "han", "roshi", "ohnoki"],
}

CLANS = {
    "none": {"display_name": "None", "description": "No clan affiliation."},

    # --- Hidden Leaf ---------------------------------------------------
    "uchiha": {"display_name": "Uchiha", "description": "A clan famed for sharp reflexes and tactical brilliance in battle."},
    "hyuga": {"display_name": "Hyuga", "description": "A proud clan known for their piercing gaze and close-combat style."},
    "nara": {"display_name": "Nara", "description": "Renowned strategists, famously unhurried outside of battle."},
    "uzumaki": {"display_name": "Uzumaki", "description": "Known for vitality, powerful chakra reserves, and fuinjutsu."},
    "akimichi": {"display_name": "Akimichi", "description": "A hearty clan whose techniques draw on stored strength and size."},
    "yamanaka": {"display_name": "Yamanaka", "description": "Known for techniques that reach into the mind itself."},
    "inuzuka": {"display_name": "Inuzuka", "description": "A fierce clan that fights alongside loyal, ninken partners."},
    "aburame": {"display_name": "Aburame", "description": "A quiet clan whose bodies play host to colonies of chakra-eating insects."},
    "sarutobi": {"display_name": "Sarutobi", "description": "An old, respected lineage with a long history of producing skilled leaders."},
    "senju": {"display_name": "Senju", "description": "A storied clan remembered for vast chakra and a founder's spirit."},

    # --- Hidden Cloud -----------------------------------------------
    "yotsuki": {"display_name": "Yotsuki", "description": "Wielders of a legendary blade technique passed through generations."},
    "chinoike": {"display_name": "Chinoike", "description": "Known for striking red eyes and a calm, calculating nature."},
    "kinkaku": {"display_name": "Kinkaku", "description": "Descendants of a legendary, chakra-hungry lineage."},
    "jugo": {"display_name": "Jugo", "description": "Marked by a volatile, transformative chakra that's difficult to control."},
    "nii": {"display_name": "Nii", "description": "Known for aggressive, high-tempo fighting styles."},
    "kirabi": {"display_name": "Kirabi", "description": "Descendants of a rapping, tailed-beast-taming line of jinchuriki."},
    "dobutsu": {"display_name": "Dobutsu", "description": "Known for a close, almost familial bond with their trained animal companions."},
    "karui": {"display_name": "Karui", "description": "Known for blunt speech and an equally blunt fighting style."},
    "samui": {"display_name": "Samui", "description": "Cool-headed swordfighters known for icy composure under pressure."},
    "darui": {"display_name": "Darui", "description": "Laid-back on the surface, but masters of lightning-natured techniques."},

    # --- Hidden Mist -----------------------------------------------
    "hozuki": {"display_name": "Hozuki", "description": "Famous for bodies as fluid and resilient as water itself."},
    "yuki": {"display_name": "Yuki", "description": "Said to carry a rare affinity for ice-natured techniques."},
    "kaguya": {"display_name": "Kaguya", "description": "A fierce clan with an unusually dense, bone-hardened physiology."},
    "hoshigaki": {"display_name": "Hoshigaki", "description": "Known for sharp features and a strong affinity for water-based combat."},
    "terumi": {"display_name": "Terumi", "description": "A lineage tied to rare, corrosive chakra techniques."},
    "fuguki": {"display_name": "Fuguki", "description": "Descendants of a legendary swordsman of the Hidden Mist."},
    "raiga": {"display_name": "Raiga", "description": "Known for a wild, thunderous fighting style."},
    "mangetsu": {"display_name": "Mangetsu", "description": "A lineage said to be capable of wielding every one of the legendary blades."},
    "chojuro": {"display_name": "Chojuro", "description": "A nervous demeanor hiding real skill with the blade."},
    "momochi": {"display_name": "Momochi", "description": "Remembered for cold precision and a reputation as a Demon of the Mist."},

    # --- Hidden Sand -----------------------------------------------
    "inugami": {"display_name": "Inugami", "description": "Said to carry the rare ability to take on a jackal's shifting form."},
    "chikamatsu": {"display_name": "Chikamatsu", "description": "Skilled handlers of summoning contracts and puppetry."},
    "shirogane": {"display_name": "Shirogane", "description": "An old clan known for calm discipline and steady chakra control."},
    "pakura": {"display_name": "Pakura", "description": "Remembered for producing shinobi of exceptional heat-based skill."},
    "sasori": {"display_name": "Sasori", "description": "Master puppeteers known for precise, mechanical artistry."},
    "chiyo": {"display_name": "Chiyo", "description": "An elder lineage of puppeteers and medical specialists."},
    "baki": {"display_name": "Baki", "description": "Disciplined wind-natured fighters known for tactical restraint."},
    "yashamaru": {"display_name": "Yashamaru", "description": "Known for gentle appearances masking real medical and combat skill."},
    "sabaku": {"display_name": "Sabaku", "description": "A lineage said to carry a natural affinity for shifting sand."},

    # --- Hidden Stone -----------------------------------------------
    "kamizuru": {"display_name": "Kamizuru", "description": "Known for working closely with swarms of trained insects."},
    "oyama": {"display_name": "Oyama", "description": "An old, distinguished lineage with an unmatched natural talent for earth manipulation."},
    "deidara": {"display_name": "Deidara", "description": "Renowned for explosive, high-risk techniques."},
    "gari": {"display_name": "Gari", "description": "Known for a versatile, adaptive combat style."},
    "akatsuchi": {"display_name": "Akatsuchi", "description": "Sturdy, dependable fighters known for earth-natured strength."},
    "kurotsuchi": {"display_name": "Kurotsuchi", "description": "A sharp-tongued lineage with a knack for both earth and lava techniques."},
    "han": {"display_name": "Han", "description": "A reclusive lineage known for combining steam and armor into a fearsome style."},
    "roshi": {"display_name": "Roshi", "description": "Known for a fiery, tailed-beast-adjacent heritage."},
    "ohnoki": {"display_name": "Ohnoki", "description": "A small but formidable lineage, historically tied to the Stone's leadership."},
}


def clans_for_village(village: str):
    return CLANS_BY_VILLAGE.get(village, [])


def clan_names_display(village: str) -> str:
    lines = []
    for key in clans_for_village(village):
        c = CLANS[key]
        lines.append(f"  &C{key:12s}&x - {c['description']}")
    return "\n".join(lines)


def display_name(clan_key: str) -> str:
    return CLANS.get(clan_key, CLANS["none"])["display_name"]
