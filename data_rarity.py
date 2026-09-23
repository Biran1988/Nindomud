"""
Item rarity tiers (Borderlands-style), colored low-to-high.

Rarity is set by the immortal who creates the item (`oset <vnum> rarity
<tier>`), not derived automatically from anything -- it's purely a
builder's call, same as every other oset field. Every item defaults to
"common" if never explicitly set.

Each tier shows as a bracketed tag at the front of the item's name --
e.g. "[Legendary] a legendary blade" -- with the tier NAME inside the
brackets cycling through that tier's own 2-3 color codes letter-by-
letter (same alternating technique used for village names in the who
list), so higher tiers get a more eye-catching multi-tone look than a
single flat color would give.

Since player inventory is plain name strings (not linked to a vnum),
displaying a rarity tag requires a reverse lookup from the name back to
its object prototype -- see commands._find_object_prototype_by_name
and commands.rarity_colored_name(), which is the single shared function
everywhere an item name is shown to a player (inventory, equipment,
shop listings, buy/wield confirmations).
"""

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]

RARITY_TIERS = {
    "common": {
        "display_name": "Common", "color": "&w",
        "tag_colors": ["&w", "&d"],  # bright white / bright light gray -- low-key but genuinely visible, unlike the old &W/&D pairing which could look washed out or uncolored on many terminals
    },
    "uncommon": {
        "display_name": "Uncommon", "color": "&G",
        "tag_colors": ["&G", "&g"],  # green / bright green
    },
    "rare": {
        "display_name": "Rare", "color": "&B",
        "tag_colors": ["&B", "&b"],  # blue / bright blue
    },
    "epic": {
        "display_name": "Epic", "color": "&[129]",
        "tag_colors": ["&[129]", "&M"],  # purple / magenta
    },
    "legendary": {
        "display_name": "Legendary", "color": "&O",
        "tag_colors": ["&O", "&[220]"],  # orange / gold -- the classic legendary two-tone
    },
}


def display_name(rarity: str) -> str:
    return RARITY_TIERS.get(rarity, RARITY_TIERS["common"])["display_name"]


def color(rarity: str) -> str:
    return RARITY_TIERS.get(rarity, RARITY_TIERS["common"])["color"]


def colored_tag(rarity: str) -> str:
    """The '[Tiername]' tag, e.g. '[Legendary]', with the tier name's
    letters cycling through that tier's 2-3 tag_colors. Brackets
    themselves stay plain white so only the tier name itself pops."""
    tier = RARITY_TIERS.get(rarity, RARITY_TIERS["common"])
    palette = tier["tag_colors"]
    letters = []
    for i, ch in enumerate(tier["display_name"]):
        letters.append(f"{palette[i % len(palette)]}{ch}")
    return "&W[&x" + "".join(letters) + "&W]&x"
