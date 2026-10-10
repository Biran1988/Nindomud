"""Item-local blade states and cut-gem crystals for the seasonal visitor.

Each state has an exact-name prototype. Inventory/equipment names therefore
save the individual blade's color and switch position without changing other
owners' weapons or introducing a second item persistence system.
"""

import inventory
import storage

FIRST_VNUM = 999900
COLORS = {"green": "&[46]", "white": "&[255]", "blue": "&[39]",
          "red": "&[196]", "cyan": "&[51]"}
GEM_COLORS = {"a cut quartz": "white", "a cut sapphire": "blue",
              "a cut ruby": "red", "a cut diamond": "cyan"}
BLADE_DAMAGE = 8
COMMAND_NAMES = {"lightsaber", "activate", "deactivate", "insert"}


def item_name(color="green", active=False):
    return f"A {color.title()} Lightsaber" + ("" if active else " Hilt")


def state(item):
    import ninja_arts
    base = ninja_arts.base_item(item)
    for color in COLORS:
        for active in (False, True):
            if base == item_name(color, active):
                return color, active
    return None


def register_items():
    import olc
    for offset, color in enumerate(COLORS):
        for active in (False, True):
            vnum = FIRST_VNUM + offset * 2 + int(active)
            if vnum in olc.OBJECT_TEMPLATES:
                continue
            obj = olc.default_object(vnum, item_name(color, active))
            obj.update({"item_type": "weapon", "weapon_type": "sword" if active else "blunt",
                        "wear_loc": "wielded", "wear_flags": ["take", "wield"],
                        "rarity": "rare", "weight": 1, "cost": 0,
                        "damage": BLADE_DAMAGE if active else 0,
                        "extra_flags": ["glow"] if active else [],
                        "description": "A strange metal hilt with a cut-gem crystal chamber. "
                                       "Activate or deactivate it; insert a cut gem to change its blade color.",
                        "stat_bonuses": {"hitroll": 2} if active else {}})
            olc.OBJECT_TEMPLATES[vnum] = obj


def display_name(item):
    info = state(item)
    return f"{COLORS[info[0]]}{item}&x" if info else item


def _owned(player, query="lightsaber"):
    # Default to the blade in hand; indexed queries still select one exact unit.
    candidates = [("equipment", slot, item) for slot, item in player.equipment.items()
                  if state(item)]
    candidates += [("inventory", i, item) for i, item in enumerate(player.inventory)
                   if state(item)]
    index, words = inventory.parse_indexed_query(query)
    matches = [entry for entry in candidates
               if all(word in entry[2].lower() for word in words.lower().split())]
    return matches[index - 1] if 1 <= index <= len(matches) else None


def owns_saber(player):
    return player is not None and _owned(player) is not None


def can_read(session, entry):
    if entry["primary_keyword"].lower() != "lightsaber":
        return True
    import seasonal_events
    return seasonal_events.may_fourth_active() or owns_saber(session.player)


def _replace(player, owned, replacement, gem=None):
    location, key, old = owned
    updated = list(player.inventory)
    if location == "inventory":
        updated.pop(key)
    if gem:
        updated.remove(gem)
    if location == "inventory":
        ok, reason = inventory.add_item(updated, replacement)
        if not ok:
            return False, reason
        updated.insert(min(key, len(updated) - 1), updated.pop())
    player.inventory[:] = updated
    if location == "equipment":
        player.equipment[key] = replacement
    return True, None


def _new_name(old, color, active):
    import ninja_arts
    base = ninja_arts.base_item(old)
    return item_name(color, active) + old[len(base):]


def switch(session, active=None, query="lightsaber"):
    import commands
    owned = _owned(session.player, query)
    if not owned:
        session.send("You aren't carrying or wielding that lightsaber.")
        return
    color, was_active = state(owned[2])
    active = not was_active if active is None else active
    if was_active == active:
        session.send("That lightsaber is already " + ("ignited." if active else "retracted."))
        return
    register_items()
    updated = _new_name(owned[2], color, active)
    ok, reason = _replace(session.player, owned, updated)
    if not ok:
        session.send(inventory.full_message(reason, updated))
        return
    if active and owned[0] == "equipment":
        message = commands._learn_weapon_skill_if_new(session.player, "sword")
        if message:
            session.send(message)
    storage.save_player(session.player)
    session.send(f"{COLORS[color]}" + (f"You ignite a humming {color} blade!" if active
                 else "You retract the blade into its metal hilt.") + "&x")
    session.broadcast_room(f"{COLORS[color]}{session.player.name} "
                           + (f"ignites a humming {color} lightsaber!" if active
                              else "retracts a lightsaber blade.") + "&x", exclude_self=True)


def insert_gem(session, args):
    words = list(args)
    if "into" in [word.lower() for word in words]:
        split = next(i for i, word in enumerate(words) if word.lower() == "into")
        gem_query, saber_query = " ".join(words[:split]), " ".join(words[split + 1:])
    else:
        gem_query, saber_query = " ".join(words), "lightsaber"
    if not gem_query or not saber_query:
        session.send("Usage: insert <cut gem> [into <lightsaber>]")
        return
    owned = _owned(session.player, saber_query)
    if not owned:
        session.send("You aren't carrying or wielding that lightsaber.")
        return
    if state(owned[2])[1]:
        session.send("Deactivate the lightsaber before opening its crystal chamber.")
        return
    if getattr(session, "combat_target", None) is not None or getattr(session, "pvp_target", None) is not None:
        session.send("You can't replace a lightsaber crystal while fighting.")
        return
    import commands
    gem = commands.find_indexed_item(gem_query, [item for item in session.player.inventory
                                               if item.lower() in GEM_COLORS])
    color = GEM_COLORS.get(gem.lower()) if gem else None
    if not color:
        session.send("You need a carried Cut Quartz, Cut Sapphire, Cut Ruby, or Cut Diamond.")
        return
    register_items()
    updated = _new_name(owned[2], color, False)
    ok, reason = _replace(session.player, owned, updated, gem)
    if not ok:
        session.send(inventory.full_message(reason, updated))
        return
    storage.save_player(session.player)
    session.send(f"You fit {gem} into the hilt, consuming the gem and replacing its old crystal. "
                 f"The blade will now glow {COLORS[color]}{color}&x.")


def command(session, args):
    if not args:
        owned = _owned(session.player)
        if not owned:
            session.send("You aren't carrying or wielding a lightsaber.")
            return
        color, active = state(owned[2])
        session.send(f"{display_name(owned[2])}: {'ignited' if active else 'retracted'}. "
                     "Activate/deactivate <lightsaber>; insert <cut gem> into <lightsaber>.")
        return
    action = args[0].lower()
    if action in ("on", "activate", "ignite", "off", "deactivate", "retract"):
        switch(session, action in ("on", "activate", "ignite"), " ".join(args[1:]) or "lightsaber")
    elif action in ("gem", "insert", "crystal"):
        insert_gem(session, args[1:])
    else:
        session.send("Usage: lightsaber on|off [lightsaber], or lightsaber gem <cut gem> [into <lightsaber>]")


def activate(session, args):
    switch(session, True, " ".join(args) or "lightsaber")


def deactivate(session, args):
    switch(session, False, " ".join(args) or "lightsaber")


def use(session, query):
    _, words = inventory.parse_indexed_query(query)
    if not words or not _owned(session.player, query):
        return False
    switch(session, query=query)
    return True
