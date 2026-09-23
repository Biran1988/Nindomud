"""
Consumable items: food, drinks, and medical supplies.

These are immediate-effect items (eat food -> restore stamina, drink a
drink -> restore chakra, use a medical item -> restore health and cure
certain status effects) -- NOT a hunger/thirst survival meter, which
Section 48 explicitly reserves for later. Each item is data-driven here
so adding new consumables later is just a new dict entry; nothing in
commands.py needs to change.
"""

from typing import Optional, Tuple

CONSUMABLES = {
    "a rice ball": {
        "category": "food", "restore": "stamina", "amount": 25,
        "message": "You eat {item} and feel refreshed.",
    },
    "a bowl of ramen": {
        "category": "food", "restore": "stamina", "amount": 40,
        "message": "You slurp down {item}. Delicious!",
    },
    "a canteen of water": {
        "category": "drink", "restore": "chakra", "amount": 20,
        "message": "You drink from {item}, feeling your chakra settle.",
    },
    "a cup of green tea": {
        "category": "drink", "restore": "chakra", "amount": 15,
        "message": "You sip {item} slowly, calming your mind.",
    },
    "a healing salve": {
        "category": "medical", "restore": "health", "amount": 35,
        "cures": ["bleeding"],
        "message": "You apply {item}. Your wounds begin to close.",
    },
    "a soldier pill": {
        "category": "medical", "restore": "chakra", "amount": 40,
        "cures": ["silenced"],
        "message": "You swallow {item}. A surge of chakra floods through you.",
    },
    # Cooking's own dishes (cooking.py) -- registered under their BASE
    # name (no quality suffix); find_consumable() matches bidirectionally
    # so a suffixed full item name like "A Cooked Sardine (Good)" still
    # correctly classifies as food and eats correctly.
    "a cooked minnow": {
        "category": "food", "restore": "stamina", "amount": 20,
        "message": "You eat {item}. Simple, but filling.",
    },
    "a cooked sardine": {
        "category": "food", "restore": "stamina", "amount": 25,
        "message": "You eat {item}. Not bad at all.",
    },
    "a cooked trout": {
        "category": "food", "restore": "stamina", "amount": 35,
        "message": "You eat {item}. Nicely done.",
    },
    "a cooked bass": {
        "category": "food", "restore": "stamina", "amount": 40,
        "message": "You eat {item}. A satisfying meal.",
    },
    "a cooked salmon": {
        "category": "food", "restore": "stamina", "amount": 55,
        "message": "You eat {item}. Rich and hearty.",
    },
    "a cooked swordfish": {
        "category": "food", "restore": "stamina", "amount": 60,
        "message": "You eat {item}. A fine catch, well prepared.",
    },
    "a cooked golden koi": {
        "category": "food", "restore": "stamina", "amount": 80,
        "message": "You eat {item}. A meal fit for a feast.",
    },
    "a leviathan fillet": {
        "category": "food", "restore": "stamina", "amount": 100,
        "message": "You eat {item}. You feel utterly restored.",
    },
}

# Which command verb is expected for each category -- eating a healing
# salve or drinking a rice ball should be refused with a hint at the
# right verb, not silently accepted.
VERB_CATEGORY = {"eat": "food", "drink": "drink", "use": "medical"}


def find_consumable(item_name: str) -> Tuple[Optional[str], Optional[dict]]:
    query = item_name.strip().lower()
    for name, data in CONSUMABLES.items():
        if query in name or name in query:
            return name, data
    return None, None


def consume(session, verb: str, query: str) -> None:
    player = session.player
    if not query:
        session.send(f"{verb.capitalize()} what?")
        return

    # Word-level match (not a plain contiguous substring): a query
    # that skips a middle word, like a crafted item's stat-bonus
    # suffix, should still match -- see commands._item_matches for the
    # full reasoning; inlined here rather than imported to avoid a
    # circular import (commands.py imports consumables.py).
    query_words = query.lower().split()
    match = next(
        (item for item in player.inventory if all(w in item.lower() for w in query_words)),
        None,
    )
    if not match:
        session.send(f"You aren't carrying anything like '{query}'.")
        return

    _name, data = find_consumable(match)
    if not data:
        session.send(f"You can't {verb} {match}.")
        return

    expected_category = VERB_CATEGORY[verb]
    if data["category"] != expected_category:
        right_verb = next(v for v, cat in VERB_CATEGORY.items() if cat == data["category"])
        session.send(f"You can't {verb} that. Try '{right_verb}' instead.")
        return

    resource = data["restore"]
    amount = data["amount"]
    current = getattr(player, resource)
    maximum = getattr(player, f"maximum_{resource}")
    new_value = min(maximum, current + amount)
    actual_gain = new_value - current
    setattr(player, resource, new_value)

    player.inventory.remove(match)
    session.send(data["message"].format(item=match))
    if actual_gain > 0:
        session.send(f"You recover {actual_gain} {resource}.")
    else:
        session.send(f"You were already at full {resource}.")

    for effect_name in data.get("cures", []):
        if effect_name in player.active_status_effects:
            del player.active_status_effects[effect_name]
            session.send(f"You are no longer {effect_name}.")
