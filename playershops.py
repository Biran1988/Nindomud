"""
Player shops (Section 75), per explicit request. A player who owns a
vacant shop slot along Main Street can claim it for
config.PLAYER_SHOP_COST_RYO (1,000,000 ryo) -- one per player, same
"one apartment per player" rule apartments.py already enforces, and
for the same reason (a single durable slot to build out, not a
collection).

The owner gives items to their OWN shopkeeper mob (a spawned instance
tagged with player_shop_owner, not a shared template -- every player
shop reuses the same generic "Shopkeeper" template, so ownership has
to be tracked per spawned instance) and then sets a price with the
`price` command, so other players can `buy` them. This is meant for
players leveling a job (Cooking, Farming, Weaponsmith, etc.) to
actually sell what they produce, rather than everything only ever
being sellable to a flat-rate NPC shop.

Stock is capped at config.PLAYER_SHOP_MAX_ITEMS (20) ENTRIES, not
unique item types -- giving 5 Cooked Sardines counts as 5 toward the
cap, matching how "give" is a per-instance action, not a stack-quantity
edit. Player.shop_stock is the durable source of truth (rooms/mobs
aren't persisted -- see world.reconcile_apartment_ownership's own
docstring for the established reasoning this follows), so a shop
mob's "inventory" is really just a lookup into its owner's own
shop_stock list at the moment it's needed, not tracked on the mob
itself.

Closing a shop (via `sell shop`) returns every still-unsold item to
the owner's own inventory if there's room, or drops it on the shop's
floor otherwise -- then the room resets to vacant (owner cleared) so
someone else can claim it. No refund of the purchase price, unlike
apartments -- not asked for, and a shop is closed voluntarily by
choice, not sold back as a fixed asset.
"""

SHOPKEEPER_TEMPLATE_VNUM = 9800  # the one generic "Shopkeeper" mob template every player shop reuses


def item_vnum_for_stock(item_name: str):
    """Link an exact, unique prototype name when an item enters a shop."""
    import olc
    matches = [vnum for vnum, proto in olc.OBJECT_TEMPLATES.items()
               if proto.get("short_desc", "").lower() == item_name.lower()]
    return matches[0] if len(matches) == 1 else None


def stock_item_name(entry: dict) -> str:
    """Use the current prototype name for stock linked to an item VNUM."""
    import olc
    proto = olc.OBJECT_TEMPLATES.get(entry.get("item_vnum"))
    if proto is None and not entry.get("item_vnum"):
        # Older saved shop stock has only a name. A builder rename records
        # that name on the prototype, so existing stock still follows it.
        matches = [candidate for candidate in olc.OBJECT_TEMPLATES.values()
                   if entry["item_name"].lower() in
                   (name.lower() for name in candidate.get("previous_short_descs", []))]
        proto = matches[0] if len(matches) == 1 else None
    return proto["short_desc"] if proto else entry["item_name"]


def _find_owner_player(owner_name: str):
    """Returns (player_obj, is_online). If online, player_obj IS the
    live session's own object (mutations apply immediately, nothing
    further to save); if offline, it's freshly loaded from disk and
    the caller must explicitly storage.save_player() it after
    mutating -- same online-or-offline pattern auction.py's own
    _pay_ryo/_deliver_item helpers already use."""
    from session import ACTIVE_SESSIONS, State
    for s in ACTIVE_SESSIONS:
        if s.state == State.PLAYING and s.player.name == owner_name:
            return s.player, True
    import storage
    return storage.load_player(owner_name), False


def stock_for_display(shopkeeper_mob) -> list:
    """Returns the owner's current shop_stock list (each entry has
    "item_name" and "price"), whether they're online or offline right
    now -- used by commands.cmd_list to show a player shop's current
    listings, the same online-or-offline lookup buy_from_shop already
    uses to complete a purchase. Empty list if the owner can't be
    found at all."""
    owner, _ = _find_owner_player(shopkeeper_mob.player_shop_owner)
    return [{**entry, "item_name": stock_item_name(entry)}
            for entry in owner.shop_stock] if owner else []


def buy_from_shop(shopkeeper_mob, buyer, item_query: str):
    """Returns (ok, item_name_or_error_message, price). On success,
    the second element is the item's own name (so the caller --
    commands.cmd_buy -- can format its own rarity-colored message);
    on failure, it's the error text to show directly. Works whether
    the shop's owner is online or offline right now."""
    owner_name = shopkeeper_mob.player_shop_owner
    owner, owner_online = _find_owner_player(owner_name)
    if owner is None:
        return False, "That shop's owner doesn't seem to exist anymore.", None

    match = next(
        (entry for entry in owner.shop_stock
         if entry["price"] is not None and item_query in stock_item_name(entry).lower()),
        None,
    )
    if not match:
        return False, f"{shopkeeper_mob.name.capitalize()} doesn't sell that.", None
    if buyer.ryo < match["price"]:
        return False, "You can't afford that.", None

    import inventory
    item_name = stock_item_name(match)
    ok, reason = inventory.add_item(buyer.inventory, item_name)
    if not ok:
        return False, inventory.full_message(reason, item_name), None

    price = match["price"]
    buyer.ryo -= price
    owner.shop_stock.remove(match)
    owner.ryo += price
    if not owner_online:
        import storage
        storage.save_player(owner)
    return True, item_name, price


def close_shop(player) -> list:
    """Returns every unsold item in the shop to the owner -- inventory
    if there's room, the shop floor otherwise. Clears the player's shop
    fields and the room's ownership (vacating it). Returns a list of
    (item_name, destination) tuples ("inventory" or "floor") for the
    caller to report. Does not touch ryo -- no refund, per the module
    docstring."""
    import inventory
    import world

    results = []
    room = world.WORLD.get(player.shop_room_vnum) if player.shop_room_vnum else None

    for entry in player.shop_stock:
        item_name = stock_item_name(entry)
        ok, _reason = inventory.add_item(player.inventory, item_name)
        if ok:
            results.append((item_name, "inventory"))
        else:
            if room is not None:
                room.ground_items.append(item_name)
            results.append((item_name, "floor"))

    if room is not None:
        room.owner = None
        room.name = "A Vacant Shop"
        room.description = "An empty shop stall, waiting for someone to claim it."
        # The shopkeeper mob (if any) belonged to this owner specifically --
        # remove it now that the shop is vacant, rather than leaving a
        # shopkeeper with no owner and no stock standing around.
        import combat
        for mob in list(combat.mobs_in_room(room.vnum)):
            if mob.player_shop_owner == player.name:
                combat.remove_mob(mob)

    player.shop_room_vnum = None
    player.shop_name = None
    player.shop_description = None
    player.shop_stock = []
    return results
