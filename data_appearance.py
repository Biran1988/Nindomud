"""
Character appearance/personality choices at creation (Section 62): sex,
skin tone, hair color, eye color, build, and personality trait. All
permanent flavor choices shown on the score sheet and mstat, same
treatment as village/class/clan -- cosmetic identity, not mechanical
(none of these affect any stat, jutsu, or combat roll).

Note on scope: elemental affinity (fire/water/wind/earth/lightning as
a personal trait, not just a biome effect) was considered for chargen
too, but is deliberately NOT here -- the plan is to make it something
a character trains into later during play, not a creation-time pick.
See biomes.py for the existing biome-based elemental system, which
this would eventually sit alongside rather than replace.
"""

SEX_OPTIONS = ["male", "female"]

# Ordered white -> almost black, matching the "display them using white
# to almost black" gradient. Plain descriptive labels, not a resolved
# palette -- there's no single real-world "correct" set of skin tone
# words, so this is a straightforward, small, ordered list rather than
# an attempt at an exhaustive or authoritative scale.
SKIN_TONES = [
    "pale white",
    "fair",
    "light tan",
    "olive",
    "tan",
    "brown",
    "dark brown",
    "almost black",
]

# Vibrant/unusual hair colors are normal for this genre, not just
# natural human ones -- matching the source material's own convention
# (bright pink, blue, white hair are all common there without any
# in-story explanation needed).
HAIR_COLORS = ["black", "brown", "blonde", "red", "white", "silver", "pink", "blue"]

EYE_COLORS = ["black", "brown", "blue", "green", "gray", "amber", "violet", "red"]

BUILDS = ["lean", "athletic", "muscular", "stocky", "slender", "heavyset"]

# Purely cosmetic/roleplay flavor, same as everything else in this
# module -- no mechanical effect on any stat, jutsu, or combat roll.
PERSONALITY_TRAITS = [
    "reckless", "confident", "loyal", "reserved",
    "calm", "hot-headed", "cunning", "cheerful",
]


def sex_display(sex: str) -> str:
    return sex.capitalize() if sex in SEX_OPTIONS else "Unknown"


def skin_tone_display(tone: str) -> str:
    return tone.capitalize() if tone in SKIN_TONES else "Unknown"


def hair_color_display(color: str) -> str:
    return color.capitalize() if color in HAIR_COLORS else "Unknown"


def eye_color_display(color: str) -> str:
    return color.capitalize() if color in EYE_COLORS else "Unknown"


def build_display(build: str) -> str:
    return build.capitalize() if build in BUILDS else "Unknown"


def personality_trait_display(trait: str) -> str:
    return trait.capitalize() if trait in PERSONALITY_TRAITS else "Unknown"


def sex_menu() -> str:
    # One consistent color for both options -- deliberately not a
    # blue/pink split, since that's not a distinction this menu needs.
    return "  " + " / ".join(f"&C{s}&x" for s in SEX_OPTIONS)


def skin_tone_menu() -> str:
    # A genuine light-to-dark 256-color gradient, roughly matching each
    # described tone, rather than a flat color -- the one menu here
    # where "what color is this" is literally the content being chosen.
    gradient = [255, 223, 216, 180, 137, 94, 58, 232]
    lines = []
    for i, tone in enumerate(SKIN_TONES):
        color = gradient[i] if i < len(gradient) else 255
        lines.append(f"  {i + 1}. &[{color}]{tone}&x")
    return "\n".join(lines)


def hair_color_menu() -> str:
    # Same "the color IS the content" reasoning as skin tone -- each
    # option colored to roughly match what it names.
    colors = {
        "black": 235, "brown": 94, "blonde": 220, "red": 160,
        "white": 255, "silver": 251, "pink": 218, "blue": 39,
    }
    lines = []
    for i, color_name in enumerate(HAIR_COLORS):
        xterm = colors.get(color_name, 255)
        lines.append(f"  {i + 1}. &[{xterm}]{color_name}&x")
    return "\n".join(lines)


def eye_color_menu() -> str:
    colors = {
        "black": 235, "brown": 94, "blue": 39, "green": 34,
        "gray": 249, "amber": 178, "violet": 99, "red": 160,
    }
    lines = []
    for i, color_name in enumerate(EYE_COLORS):
        xterm = colors.get(color_name, 255)
        lines.append(f"  {i + 1}. &[{xterm}]{color_name}&x")
    return "\n".join(lines)


def build_menu() -> str:
    # No natural color mapping for a build description (unlike hair/
    # eye/skin, where the word itself names a color) -- one consistent
    # accent, same reasoning as sex_menu().
    return "\n".join(f"  {i + 1}. &C{b}&x" for i, b in enumerate(BUILDS))


def personality_trait_menu() -> str:
    return "\n".join(f"  {i + 1}. &C{t}&x" for i, t in enumerate(PERSONALITY_TRAITS))
