"""Nindo_mud's shared 256-color xterm UI theme.

This changes presentation only, never persisted Room/Mob data. Custom
builder-authored &R / &[N] colors remain respected. Combat element
palettes and personalized item rarity retain their own color rules.
Use the existing colors.render() escape syntax; do not hardcode ANSI.
"""
ROOM_TITLE = "&[114]"          # jade / Hidden Leaf green  #87d787
ROOM_DESCRIPTION = "&[253]"    # soft readable silver       #dadada
EXIT_HEADING = "&[110]"        # mist blue                  #87afd7
EXIT_DIRECTION = "&[117]"      # brighter navigation blue  #87d7ff
CHARACTER = "&[151]"           # sage green                 #afd7af
NPC = "&[187]"                 # subdued parchment          #d7d7af
ITEM = "&[221]"                # golden highlights          #ffd75f
REWARD = ITEM
DANGER = "&[203]"              # warm crimson               #ff5f5f
METADATA = "&[245]"            # muted slate                #8a8a8a


def with_color(text, default):
    """Use a theme color, allowing custom codes in room descriptions.

    Color-free stored text gets a default foreground color. Any author
    supplied color codes override it in-place, just as they always have.
    """
    return f"{default}{text}&x"
