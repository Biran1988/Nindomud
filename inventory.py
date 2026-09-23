"""
Inventory stacking (Section 62).

Items with the same name stack together, up to MAX_STACK_SIZE units
per stack; a player can hold at most MAX_INVENTORY_SLOTS distinct
stacks at once (a "slot" is a distinct item name, not a single unit --
64 Sardines is one slot, not 64).

The underlying `player.inventory` list is UNCHANGED in shape: it's
still one string per unit (three kunai is the string "A Basic Kunai"
appearing three times), not a list of (name, count) pairs. That
deliberate choice means every existing piece of code that reads
inventory -- matching an item by partial name, removing one unit,
checking `item in player.inventory` -- keeps working exactly as
before with zero changes. Only two things change: what gets ADDED
(gated through add_item() below, replacing a bare `.append()`) and
how it's DISPLAYED (consolidated into "Name (xN)" lines by
commands.cmd_inventory, replacing one line per unit).
"""

MAX_STACK_SIZE = 64
MAX_INVENTORY_SLOTS = 20


def parse_indexed_query(query: str) -> tuple:
    """Per direct confirmation (Section 158): "a real general N.keyword
    targeting convention...usable anywhere a name is currently typed
    to target an item or mob -- inventory, equipment, room contents,
    and mobs." Splits a real query like "2.backpack" into (2,
    "backpack") -- the Nth match for that keyword, 1-indexed. A bare
    query with no real "N." prefix (or an invalid/non-numeric prefix)
    returns (1, query) unchanged -- "the first match", exactly
    matching every existing caller's own real behavior before this
    convention existed."""
    if "." in query:
        prefix, _, rest = query.partition(".")
        if prefix.isdigit() and rest:
            index = int(prefix)
            if index >= 1:
                return index, rest
    return 1, query


def slot_counts(player_inventory: list) -> dict:
    """Item name -> how many units of it are carried, in first-seen
    order (relied on so display order doesn't jump around)."""
    counts = {}
    for item in player_inventory:
        counts[item] = counts.get(item, 0) + 1
    return counts


def add_item(player_inventory: list, item_name: str):
    """Attempts to add one unit of item_name. Returns (True, None) on
    success (the item IS appended to player_inventory as a side
    effect), or (False, reason) if it doesn't fit, leaving
    player_inventory unchanged. reason is "stack_full" (already
    carrying the max of this exact item) or "no_slots" (already
    carrying MAX_INVENTORY_SLOTS distinct items and this would be a
    new one) -- distinguished so callers can give a precise message."""
    counts = slot_counts(player_inventory)
    if item_name in counts:
        if counts[item_name] >= MAX_STACK_SIZE:
            return False, "stack_full"
    elif len(counts) >= MAX_INVENTORY_SLOTS:
        return False, "no_slots"
    player_inventory.append(item_name)
    return True, None


def add_items(player_inventory: list, item_names: list):
    """Adds as many of item_names as fit, in order, stopping (not
    skipping ahead) at the first one that doesn't. Returns
    (added: list, leftover: list) -- leftover is every item from
    item_names, in original order, that wasn't added, whether because
    it was the one that didn't fit or because it came after that point
    in the list. Used by corpse looting, where the remainder should
    stay ON the corpse rather than being silently dropped."""
    added = []
    for i, name in enumerate(item_names):
        ok, _ = add_item(player_inventory, name)
        if not ok:
            return added, item_names[i:]
    return added, []


def full_message(reason: str, item_name: str) -> str:
    if reason == "stack_full":
        return f"You're already carrying the maximum of {item_name} ({MAX_STACK_SIZE})."
    return f"Your inventory is full ({MAX_INVENTORY_SLOTS} different items max)."
