"""
Roulette (Section 55) -- a third gambling mechanic, distinct from
chou-han (dice) and the slot machines (ryo), wagered in MISSION POINTS
instead of ryo. Mission points are a scarcer, more "earned" currency
(from completing missions, spent on village Kage perks), so this is
meant to feel like the higher-stakes table game of the three, with a
genuine choice between a safe bet and a long-shot bet -- unlike the
slots' fixed tiers or chou-han's flat 50/50 call.

European wheel (single zero, 37 pockets: 0 plus 1-36), not the American
double-zero wheel -- the extra 00 pocket only exists to worsen the
house edge and adds nothing to the player experience here.

Bet types:
  - number <0-36>  : straight-up bet on one pocket, pays 36x total
                      (35:1 profit + the original stake back)
  - red / black    : even-money color bet, pays 2x total
  - odd / even     : even-money parity bet (0 counts as neither), pays 2x
  - low / high     : even-money 1-18 / 19-36 bet, pays 2x

0 is green and loses every bet except a straight 'number 0' bet.
"""

import random

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = set(range(1, 37)) - RED_NUMBERS

STRAIGHT_PAYOUT_MULTIPLIER = 36  # total returned (35:1 profit + original stake)
EVEN_MONEY_PAYOUT_MULTIPLIER = 2  # total returned (1:1 profit + original stake)

OUTSIDE_BET_TYPES = {"red", "black", "odd", "even", "low", "high"}


def pocket_color(number: int) -> str:
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def colored_number(number: int) -> str:
    """RED is red, BLACK renders as dim gray/dark (there's no true
    black in this palette, and dark gray reads as 'black' against a
    typical terminal), GREEN for the 0."""
    color = pocket_color(number)
    code = {"red": "&R", "black": "&D", "green": "&G"}[color]
    return f"{code}{number} ({color.capitalize()})&x"


def spin() -> int:
    return random.randint(0, 36)


def resolve_bet(bet_type: str, bet_value, wager: int, result: int) -> int:
    """Returns the total points returned to the player (0 if they lost).
    bet_value is the target number for 'number' bets, ignored otherwise."""
    color = pocket_color(result)

    if bet_type == "number":
        return wager * STRAIGHT_PAYOUT_MULTIPLIER if result == bet_value else 0

    if result == 0:
        return 0  # green loses every outside bet

    if bet_type == "red":
        won = color == "red"
    elif bet_type == "black":
        won = color == "black"
    elif bet_type == "odd":
        won = result % 2 == 1
    elif bet_type == "even":
        won = result % 2 == 0
    elif bet_type == "low":
        won = 1 <= result <= 18
    elif bet_type == "high":
        won = 19 <= result <= 36
    else:
        won = False

    return wager * EVEN_MONEY_PAYOUT_MULTIPLIER if won else 0
