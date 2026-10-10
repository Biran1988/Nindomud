"""Persistent, shared four-digit lottery with 24-hour drawings."""

import json
import os
import secrets
import time

import storage

BASE_JACKPOT = 25_000
TICKET_PRICE = 1_000
DRAW_INTERVAL = 24 * 60 * 60


def _path():
    return os.path.join(storage.DATA_DIR, "lottery.json")


def _new(now):
    return {"jackpot": BASE_JACKPOT, "next_draw": now + DRAW_INTERVAL,
            "tickets": [], "last_draw": None, "pending_payouts": []}


def load(now=None):
    now = time.time() if now is None else now
    if not os.path.isfile(_path()):
        return _new(now)
    with open(_path(), encoding="utf-8") as file:
        return json.load(file)


def save(state):
    storage.ensure_dirs()
    path = _path()
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)
    os.replace(temporary, path)


def draw_due(sessions=(), now=None):
    """Settle each elapsed 24-hour period, including after server downtime."""
    now = time.time() if now is None else now
    state = load(now)
    _pay_pending(state, sessions)
    while now >= state["next_draw"]:
        number = f"{secrets.randbelow(10000):04d}"
        winners = [ticket["player"] for ticket in state["tickets"]
                   if ticket["number"] == number]
        prize = state["jackpot"]
        if winners:
            # Each winning ticket gets an equal share; the remainder goes
            # to the first winning ticket, keeping the entire pot paid out.
            amounts = {}
            for index, name in enumerate(winners):
                amounts[name] = amounts.get(name, 0) + prize // len(winners) + (index < prize % len(winners))
            state.setdefault("pending_payouts", []).extend(
                {"player": name, "amount": amount, "draw": state["next_draw"]}
                for name, amount in amounts.items())
            state["jackpot"] = BASE_JACKPOT
        else:
            state["jackpot"] += BASE_JACKPOT
        state["last_draw"] = {"number": number, "winners": winners,
                              "jackpot": prize, "at": state["next_draw"]}
        state["tickets"] = []
        state["next_draw"] += DRAW_INTERVAL
        # Save the result and owed payouts together before any player save.
        save(state)
        _pay_pending(state, sessions)
    return state


def _pay_pending(state, sessions):
    for payout in list(state.get("pending_payouts", [])):
        name, amount, draw = payout["player"], payout["amount"], payout["draw"]
        online = next((s for s in sessions if s.player and s.player.name == name), None)
        player = online.player if online else storage.load_player(name)
        if player is None:
            continue
        if draw not in player.lottery_paid_draws:
            player.bank_balance += amount
            player.lottery_paid_draws.append(draw)
            storage.save_player(player)
            if online:
                online.send(f"&YLottery winner! {amount:,} ryo was deposited in your bank.&x")
                online.send_prompt()
        state["pending_payouts"].remove(payout)
        save(state)


def buy(player, number, sessions=(), now=None):
    now = time.time() if now is None else now
    state = draw_due(sessions, now)
    if any(ticket["player"].casefold() == player.name.casefold() for ticket in state["tickets"]):
        return "You already have a ticket for this draw. Come back after the next drawing."
    if number.lower() != "random" and (len(number) != 4 or not number.isascii() or not number.isdigit()):
        return "Choose exactly four digits, such as 0042, or use 'random'."
    if player.ryo < TICKET_PRICE:
        return f"A ticket costs {TICKET_PRICE:,} ryo; you don't have enough on hand."
    if number.lower() == "random":
        number = f"{secrets.randbelow(10000):04d}"
    player.ryo -= TICKET_PRICE
    storage.save_player(player)
    state["tickets"].append({"player": player.name, "number": number})
    state["jackpot"] += TICKET_PRICE
    save(state)
    return None
