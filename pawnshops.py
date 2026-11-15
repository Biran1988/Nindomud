"""Durable, individually stocked NPC pawnshop inventory.

Each pawnshop is identified by its mob prototype and room; unlike ordinary
NPC template stock, pawned items are single copies removed from players.
Data lives in data/pawnshops.json and survives reboot. A pawnshop pays the
normal 50%-rate general buyer price and resells at 150% of *what it paid*.
Neither sale nor purchase turns unique tool strings into prototype items.
"""
from __future__ import annotations

import math
import os
import threading

import storage

_LOCK = threading.RLock()
RESALE_MULTIPLIER = 1.5


def is_pawnshop(mob) -> bool:
    import combat
    template = combat.MOB_TEMPLATES.get(getattr(mob, "template_vnum", None), {})
    import shop_flags
    return bool(shop_flags.is_shopkeeper_template(template)
                and shop_flags.specialty_from_flags(template) == "pawnshop"
                and not getattr(mob, "player_shop_owner", None))


def key(mob, room_vnum=None) -> str:
    room = getattr(mob, "room_vnum", None)
    if room is None:
        room = room_vnum
    if room is None:
        raise ValueError("Pawnshop requires a room identifier")
    return f"{int(mob.template_vnum)}:{int(room)}"


def _path():
    return os.path.join(storage.DATA_DIR, "pawnshops.json")


def _load():
    path = _path()
    if not os.path.isfile(path):
        return {}
    import json
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Invalid pawnshop stock file")
    return data


def _save(data):
    storage.ensure_dirs()
    storage._atomic_write_json(_path(), data)


def stock(mob, room_vnum=None) -> list:
    with _LOCK:
        return [dict(entry) for entry in _load().get(key(mob, room_vnum), [])]


def purchase_offer(item_name: str) -> int:
    """Price the *actual* item as other NPC buyers do, not its VNUM alone."""
    import item_types
    import cooking
    # Do not pay for prototype objects whose own declared value is zero.
    import olc
    import ninja_arts
    base = ninja_arts.base_item(item_name).casefold()
    prototypes = [proto for proto in olc.OBJECT_TEMPLATES.values()
                  if proto.get("short_desc", "").casefold() == base]
    import item_balance
    if len(prototypes) == 1 and item_balance.effective_cost(prototypes[0]) <= 0:
        return 0
    dish = cooking.price_for_dish(item_name)
    normal = dish if dish is not None else item_types.base_sell_price(item_name)
    return max(1, int(normal * 0.5)) if normal > 0 else 0


def resale_price(offer: int) -> int:
    return max(offer + 1, math.ceil(offer * RESALE_MULTIPLIER))


def sale_error(player, position: int) -> str | None:
    """Block non-transferable stock and containers with attached saved data."""
    if position < 0 or position >= len(player.inventory):
        return "That item is no longer in your inventory."
    item = player.inventory[position]
    import iron_ascension
    import courier_missions
    if item in (iron_ascension.HEART, iron_ascension.SCROLL):
        return "Soulbound items cannot be pawned."
    if courier_missions.is_parcel(item):
        return "Mission cargo cannot be pawned."
    if item.endswith(" [glued]"):
        return "Glued items cannot be pawned."
    if getattr(player, "backpack_contents", {}).get(str(position)):
        return "Empty your backpack before pawning it."
    if purchase_offer(item) <= 0:
        return "That item has no value to the pawnshop."
    return None


def sell_positions(mob, player, positions: list[int]):
    """Take selected items in descending index order, retaining exact copies.

    Returns (items, total_received, skipped, reason), with per-player rollback
    if disk stock persistence fails. No hidden price change on resale.
    """
    import inventory
    with _LOCK:
        data = _load()
        shop_key = key(mob, player.room_vnum)
        stored = data.setdefault(shop_key, [])
        prior_inventory = list(player.inventory)
        prior_bags = {k: list(v) for k, v in getattr(player, "backpack_contents", {}).items()}
        prior_ryo = player.ryo
        sold, skipped, last_reason = [], 0, None
        for index in sorted(set(positions), reverse=True):
            reason = sale_error(player, index)
            if reason:
                skipped += 1
                last_reason = reason
                continue
            item = player.inventory[index]
            offer = purchase_offer(item)
            stored.append({"item_name": item, "price": resale_price(offer),
                           "paid": offer})
            inventory.remove_carried_at(player, index)
            player.ryo += offer
            sold.append(item)
        if not sold:
            return [], 0, skipped, last_reason
        try:
            # The saved stock is separate from the live mob/prototype registry.
            _save(data)
            storage.save_player(player)
        except Exception:
            player.inventory = prior_inventory
            player.backpack_contents = prior_bags
            player.ryo = prior_ryo
            # Restore prior shop stock if player-save persistence fails.
            try:
                existing = _load()
                existing[shop_key] = stored[:-len(sold)]
                _save(existing)
            except Exception:
                pass
            raise
        return sold, player.ryo - prior_ryo, skipped, last_reason


def _match_entries(entries, query):
    import inventory
    term_no, term = inventory.parse_indexed_query(query.strip().casefold())
    from commands import _item_matches
    candidates = [(i, entry) for i, entry in enumerate(entries)
                  if _item_matches(term, entry["item_name"])]
    return candidates, term_no


def buy(mob, player, query: str, *, session=None):
    """Buy exactly one stocked copy. Returns (ok, message_or_name, cost)."""
    import inventory
    import playershops
    import crafted_provenance
    import olc
    with _LOCK:
        data = _load()
        shop_key = key(mob, player.room_vnum)
        entries = data.get(shop_key, [])
        matches, nth = _match_entries(entries, query)
        if nth > len(matches):
            return False, "The pawnshop doesn't have that item in stock.", None
        index, entry = matches[nth - 1]
        name, price = entry["item_name"], entry["price"]
        proto = playershops.stock_prototype({"item_name": name, "item_vnum": None})
        level_error = playershops.purchase_level_error(player, proto, name)
        if level_error:
            return False, level_error, None
        if crafted_provenance.denied(name, player, session=session):
            return False, crafted_provenance.DENIED, None
        if player.ryo < price:
            return False, "You cannot afford that pawnshop item.", None
        ok, reason = inventory.add_item(player.inventory, name)
        if not ok:
            return False, inventory.full_message(reason, name), None
        player.ryo -= price
        entries.pop(index)
        try:
            _save(data)
            storage.save_player(player)
        except Exception:
            player.inventory.pop()  # appended by inventory.add_item
            player.ryo += price
            try:
                current = _load()
                current.setdefault(shop_key, []).insert(index, entry)
                _save(current)
            except Exception:
                pass
            raise
        return True, name, price
