"""
Starting loadout choice (Section 61) -- a chargen step between clan
selection and the final confirmation. Three options, all built from
item prototypes that already existed (content.py's basic kunai/sword/
shuriken/shirt/pants/sandals/salve/pill), not new content: a striker
kit leaning into extra ranged weapons, a guardian kit leaning into
survival items, and balanced, which is exactly the equipment every
character got before this choice existed (so a player who just wants
the old default can still get it, and no existing assumption elsewhere
about "what a new character starts with" silently breaks).

Each option is {"display_name", "description", "inventory": [...],
"equipment": {slot: item}} -- inventory is loose carried items,
equipment is worn/wielded slots, matching Player.inventory/
Player.equipment's own shapes.
"""

LOADOUTS = {
    "balanced": {
        "display_name": "Balanced Kit",
        "description": "A dependable all-rounder: a sword, full basic armor, and a spare kunai.",
        "inventory": ["A Basic Kunai"],
        "equipment": {
            "wielded": "A Basic Ninja Sword",
            "body": "A Basic Ninja Shirt",
            "legs": "Basic Ninja Pants",
            "feet": "A Basic Ninja Sandals",
        },
    },
    "striker": {
        "display_name": "Striker Kit",
        "description": "Built for offense: extra thrown weapons, at the cost of carrying no healing item.",
        "inventory": ["A Basic Kunai", "A Basic Kunai", "A Throwing Shuriken"],
        "equipment": {
            "wielded": "A Basic Ninja Sword",
            "feet": "A Basic Ninja Sandals",
        },
    },
    "guardian": {
        "display_name": "Guardian Kit",
        "description": "Built to endure: full armor plus a healing salve and a soldier pill, but only one kunai.",
        "inventory": ["A Basic Kunai", "A Healing Salve", "A Soldier Pill"],
        "equipment": {
            "wielded": "A Basic Ninja Sword",
            "body": "A Basic Ninja Shirt",
            "legs": "Basic Ninja Pants",
            "feet": "A Basic Ninja Sandals",
        },
    },
}

LOADOUT_ORDER = ["balanced", "striker", "guardian"]


def display_menu() -> str:
    colors = {"balanced": "&C", "striker": "&R", "guardian": "&G"}
    lines = []
    for key in LOADOUT_ORDER:
        entry = LOADOUTS[key]
        color = colors.get(key, "&W")
        lines.append(f"  {color}{key}&x -- {entry['display_name']}: {entry['description']}")
    return "\n".join(lines)
