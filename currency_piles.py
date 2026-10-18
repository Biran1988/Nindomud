"""Physical, denomination-free Ryo piles.

Ground Ryo is stored as integer-valued piles on a Room, never as a
craftable object name or a stack of generic inventory strings. This keeps
the currency amount authoritative, prevents item-name spoofing, and allows
pickup without occupying an inventory slot. A separate, auto-written ledger
preserves currency without rewriting builder-authored world/area files.
"""
import json
import os
import re

import storage
import world


def _ledger_path():
    return os.path.join(storage.DATA_DIR, "ground_ryo.json")


def save_piles():
    """Persist every on-ground pile after a successful drop or pickup."""
    storage.ensure_dirs()
    payload = {
        str(room.vnum): [amount for amount in room.ground_ryo if type(amount) is int and amount > 0]
        for room in world.WORLD.rooms.values()
        if getattr(room, "ground_ryo", ())
    }
    path = _ledger_path()
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    os.replace(temporary, path)


def restore_piles():
    """Apply the saved currency after world rooms and apartments are loaded."""
    path = _ledger_path()
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    # Ledger owns the currency state; stale world snapshots must not duplicate it.
    for room in world.WORLD.rooms.values():
        room.ground_ryo.clear()
    if not isinstance(data, dict):
        return
    for vnum, values in data.items():
        try:
            room = world.WORLD.get(int(vnum))
        except (ValueError, TypeError):
            continue
        if room is not None and isinstance(values, list):
            room.ground_ryo.extend(
                value for value in values if type(value) is int and value > 0
            )


def _amount(word, balance=None):
    """Return a positive coin amount, allowing 'all' where meaningful."""
    if word.lower() == "all" and balance is not None:
        return balance
    return int(word) if re.fullmatch(r"[0-9]+", word) else None


def is_drop_command(args):
    return len(args) == 2 and args[1].lower() == "ryo"


def drop(session, args):
    """drop 500 ryo / drop all ryo."""
    player = session.player
    amount = _amount(args[0], player.ryo)
    if amount is None or amount <= 0:
        session.send("Ryo amount must be a positive whole number.")
        return
    if amount > player.ryo:
        session.send(f"You only have {player.ryo:,} Ryo.")
        return
    room = world.WORLD.get(player.room_vnum)
    if room is None:
        session.send("There is nowhere to drop Ryo here.")
        return
    player.ryo -= amount
    room.ground_ryo.append(amount)
    # Save character balance and separately auto-save physical coins.
    storage.save_player(player)
    save_piles()
    session.send(f"You drop a pile of {amount:,} Ryo.")
    session.broadcast_room(f"{player.name} drops a pile of Ryo.", exclude_self=True)


def is_get_command(query):
    return bool(re.fullmatch(r"(?:ryo|all ryo|[0-9]+ ryo|[0-9]+\.ryo)", query))


def pickup(session, query):
    """get ryo, get 500 ryo, get 2.ryo, or get all ryo."""
    room = world.WORLD.get(session.player.room_vnum)
    if room is None or not room.ground_ryo:
        session.send("There is no Ryo lying here.")
        return
    if query == "all ryo":
        values = list(room.ground_ryo)
    elif query == "ryo":
        values = [room.ground_ryo[0]]
    elif query.endswith(".ryo"):
        index = int(query.partition(".")[0]) - 1
        if index < 0 or index >= len(room.ground_ryo):
            session.send("You don't see that pile of Ryo here.")
            return
        values = [room.ground_ryo[index]]
    else:
        requested = int(query.split()[0])
        if requested <= 0 or requested not in room.ground_ryo:
            session.send("You don't see that pile of Ryo here.")
            return
        values = [requested]
    total = sum(values)
    if total <= 0:
        session.send("There is no Ryo lying here.")
        return
    for amount in values:
        room.ground_ryo.remove(amount)
    # Remove from saved ground before adding to the owner's saved balance.
    save_piles()
    session.player.ryo += total
    storage.save_player(session.player)
    session.send(f"You pick up {total:,} Ryo.")
    session.broadcast_room(f"{session.player.name} picks up some Ryo.", exclude_self=True)


def is_give_command(args):
    return len(args) >= 3 and args[1].lower() == "ryo"


def give(session, args):
    """give 500 ryo Player / give 500 ryo to Player."""
    player = session.player
    amount = _amount(args[0], player.ryo)
    if amount is None or amount <= 0:
        session.send("Ryo amount must be a positive whole number.")
        return
    if amount > player.ryo:
        session.send(f"You only have {player.ryo:,} Ryo.")
        return
    target_words = args[2:]
    if target_words and target_words[0].lower() == "to":
        target_words = target_words[1:]
    if not target_words:
        session.send("Usage: give <amount> ryo <player>")
        return
    query = " ".join(target_words).lower()
    target = next((
        s for s in session.active_sessions()
        if s is not session and s.player
        and s.player.room_vnum == player.room_vnum
        and query in s.player.name.lower()
    ), None)
    if target is None:
        session.send("There's no player here by that name.")
        return
    player.ryo -= amount
    # Save debit before credit, so interrupted writes cannot mint Ryo.
    storage.save_player(player)
    target.player.ryo += amount
    storage.save_player(target.player)
    session.send(f"You give {amount:,} Ryo to {target.player.name}.")
    target.send(f"{player.name} gives you {amount:,} Ryo.")
    for observer in session.active_sessions():
        if (observer is not session and observer is not target and observer.player
                and observer.player.room_vnum == player.room_vnum):
            observer.send(f"{player.name} gives {target.player.name} some Ryo.")
