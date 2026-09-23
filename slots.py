"""
Slot machine gambling (Section 53) -- a second gambling mechanic
alongside the chou-han dealer flag (commands.cmd_gamble), themed as a
standing machine rather than a table game. Four wager tiers, each with
its own independently-accumulating progressive jackpot that grows from
a cut of every pull at that tier, persisted to disk (storage.py) since
it's a value shared across every player, not tied to one player's save
file the way everything else in this project is.

Symbols, rarest last (so TIERS.index-style reasoning reads low-to-high
value): cherry, bell, bar, seven. Three matching sevens hits the
tier's full accumulated jackpot; three of anything else pays a fixed
multiplier of the wager; two matching pays a small consolation
multiplier; no match loses the wager (a cut of which still seeds the
jackpot pool).
"""

import random

TIERS = [1, 25, 100, 1000]  # ryo cost per pull, also the tier's identifier

# Weighted so rarer symbols show up less often -- higher weight = more common.
SYMBOL_WEIGHTS = {
    "cherry": 40,
    "bell": 30,
    "bar": 20,
    "seven": 10,
}
SYMBOLS = list(SYMBOL_WEIGHTS.keys())
WEIGHTS = list(SYMBOL_WEIGHTS.values())

SYMBOL_DISPLAY = {
    "cherry": "&RCherry&x",
    "bell": "&YBell&x",
    "bar": "&CBar&x",
    "seven": "&O7&x",
}

# Multiplier of the wager for three-of-a-kind, per non-jackpot symbol.
THREE_OF_A_KIND_MULTIPLIER = {
    "cherry": 8,
    "bell": 20,
    "bar": 50,
}
TWO_OF_A_KIND_MULTIPLIER = 2
JACKPOT_SYMBOL = "seven"
JACKPOT_CONTRIBUTION_PCT = 10  # % of every wager (win or lose) added to that tier's pool
JACKPOT_SEED_RYO = {1: 20, 25: 500, 100: 2000, 1000: 20000}  # what a pool resets to after a hit


def _spin_reel() -> str:
    return random.choices(SYMBOLS, weights=WEIGHTS, k=1)[0]


def spin() -> list:
    """Three independently-spun reels."""
    return [_spin_reel(), _spin_reel(), _spin_reel()]


def display_reels(reels: list) -> str:
    return " | ".join(SYMBOL_DISPLAY[s] for s in reels)


def get_jackpot(tier: int) -> int:
    import storage
    jackpots = storage.load_jackpots()
    return jackpots.get(str(tier), JACKPOT_SEED_RYO.get(tier, tier * 20))


def _set_jackpot(tier: int, amount: int) -> None:
    import storage
    jackpots = storage.load_jackpots()
    jackpots[str(tier)] = amount
    storage.save_jackpots(jackpots)


def pull(tier: int, wager_ryo: int) -> dict:
    """Resolves one pull. Returns a dict: reels, outcome ("jackpot",
    "three", "two", "none"), symbol (for "three", which symbol hit),
    payout (ryo won, 0 if none), and jackpot_after (the tier's pool
    once this pull's contribution/reset is applied)."""
    contribution = max(1, wager_ryo * JACKPOT_CONTRIBUTION_PCT // 100)
    jackpot = get_jackpot(tier) + contribution

    reels = spin()
    payout = 0
    outcome = "none"
    symbol = None

    if reels[0] == reels[1] == reels[2]:
        if reels[0] == JACKPOT_SYMBOL:
            outcome = "jackpot"
            payout = jackpot
            jackpot = JACKPOT_SEED_RYO.get(tier, tier * 20)
        else:
            outcome = "three"
            symbol = reels[0]
            payout = wager_ryo * THREE_OF_A_KIND_MULTIPLIER[symbol]
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        outcome = "two"
        payout = wager_ryo * TWO_OF_A_KIND_MULTIPLIER

    _set_jackpot(tier, jackpot)

    return {
        "reels": reels, "outcome": outcome, "symbol": symbol,
        "payout": payout, "jackpot_after": jackpot,
    }
