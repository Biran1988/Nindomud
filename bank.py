"""
Bank system, per explicit request: a place for players to safely store
ryo away from death-penalty loss and PvP. combat.handle_player_defeat
(both the PvE and PvP defeat path -- PvP calls straight into it) only
ever operates on player.ryo, never on anything else, so a genuinely
separate field (player.bank_balance) is naturally untouched by it, and
by extension by any other consequence tied to losing a fight. There's
no existing mechanic where another player can take your ON-HAND ryo
directly either (no steal/pickpocket command exists), so a banked
balance is safe from "other players" in the fullest current sense of
that phrase, not just the death-penalty one.

Pays a small, LINEAR (not compounding within one single application)
interest rate -- "very little interest", per explicit request. Applied
LAZILY, on next bank interaction (deposit/withdraw/checking the
balance), based on real elapsed time since bank_last_interest_at --
deliberately NOT a global periodic tick over every saved player. That
would mean repeatedly loading and re-saving every player file on a
timer; storage.all_players() (the only way to reach an offline
player's data) explicitly documents itself as not meant for a hot
path like the pulse loop. Lazy application gets the same player-facing
result (money grows over time) without that cost or risk.
"""

import time

INTEREST_RATE_PER_HOUR = 0.0001  # 0.01%/hour -- reduced 10x per explicit follow-up request (was 0.1%/hour)
MAX_BALANCE = 1_000_000_000  # 1 billion ryo, per explicit request


def apply_interest(player) -> int:
    """Applies any interest earned since bank_last_interest_at, up to
    right now. Returns the amount of interest actually earned (0 if
    none accrued, including a player's very first-ever bank
    interaction -- interest never accrues retroactively before
    bank_last_interest_at has a real timestamp to measure from).
    Always safe to call before any other bank operation; a call with
    nothing to earn just resets the clock rather than doing nothing,
    so a balance of 0 sitting untouched for a long time doesn't create
    a large, unearned windfall the moment something IS deposited.
    Interest is clamped at MAX_BALANCE rather than refused outright --
    unlike a deposit, the player isn't choosing a specific amount here,
    so there's nothing to reject; it just stops growing once it's
    capped."""
    now = time.time()
    if player.bank_last_interest_at == 0.0 or player.bank_balance <= 0:
        player.bank_last_interest_at = now
        return 0

    hours_elapsed = (now - player.bank_last_interest_at) / 3600
    interest = int(player.bank_balance * INTEREST_RATE_PER_HOUR * hours_elapsed)
    interest = min(interest, MAX_BALANCE - player.bank_balance)
    player.bank_last_interest_at = now
    if interest > 0:
        player.bank_balance += interest
    return interest


def deposit(player, amount: int) -> str:
    """Moves `amount` ryo from carried ryo into the bank. Returns ""
    on success, or a human-readable refusal reason (invalid amount,
    not enough carried ryo, or the bank's MAX_BALANCE cap -- refused
    outright rather than silently depositing a smaller amount, telling
    the player exactly how much room is left so they can choose to
    deposit less instead)."""
    if amount <= 0:
        return "Deposit how much?"
    if player.ryo < amount:
        return f"You only have {player.ryo:,} ryo on hand."
    apply_interest(player)
    if player.bank_balance + amount > MAX_BALANCE:
        room_left = MAX_BALANCE - player.bank_balance
        return f"The bank can't hold that much -- you have room for {room_left:,} more ryo (cap: {MAX_BALANCE:,})."
    player.ryo -= amount
    player.bank_balance += amount
    return ""


def withdraw(player, amount: int) -> str:
    """Moves `amount` ryo from the bank back into carried ryo. Returns
    "" on success, or a human-readable refusal reason (invalid amount,
    not enough banked)."""
    if amount <= 0:
        return "Withdraw how much?"
    apply_interest(player)
    if player.bank_balance < amount:
        return f"You only have {player.bank_balance:,} ryo banked."
    player.bank_balance -= amount
    player.ryo += amount
    return ""
