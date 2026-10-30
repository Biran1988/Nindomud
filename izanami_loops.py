"""Timed Izanami loops: exactly one guess per 15-second reality cycle.

An actual cast starts a persistent cycle using real epoch timestamps, not a
combat pulse counter; attempts cannot be spammed or shortened by relogging.
"""
import math
import random
import time

import data_mangekyo

LOOP_SECONDS = data_mangekyo.IZANAMI_LOOP_SECONDS
WRONG_DAMAGE_PERCENT = data_mangekyo.IZANAMI_WRONG_GUESS_HEALTH_DAMAGE_PCT
# A victim must remain alive to solve the loop. Further failures at 1 HP
# cannot defeat them without an opportunity to make the correct guess.
ALLOWED_COMMANDS = frozenset({
    "guess", "look", "l", "help", "who", "score", "level", "uptime",
    "jinchuriki", "mastery", "jutsu", "inventory", "inv", "skills",
    "prac", "say", "ooc", "quit", "save", "aff",
})


def _caster_session(player):
    name = getattr(player, "izanami_caster_name", None)
    if not name:
        return None
    from session import ACTIVE_SESSIONS, State
    return next(
        (s for s in list(ACTIVE_SESSIONS)
         if s.player and s.player.name.casefold() == name.casefold()
         and s.state == State.PLAYING), None
    )


def _notify_caster(player, message):
    caster = _caster_session(player)
    if caster is not None:
        caster.send(message)


def start(caster_session, target_session, number, *, now=None):
    now = time.time() if now is None else now
    player = target_session.player
    player.izanami_trapped = True
    player.izanami_target_number = number
    player.izanami_caster_name = caster_session.player.name
    player.izanami_loop_ends_at = now + LOOP_SECONDS
    player.izanami_guessed_this_loop = False
    # Cancel combat/queued actions and prevent a pending action from firing
    # after the illusion takes effect. The caster stays free to act.
    target_session.combat_target = None
    target_session.pvp_target = None
    target_session.pending_cast = None
    target_session.pending_action = None
    target_session.chakra_charge = None
    for observer in target_session.active_sessions():
        if observer is not target_session and observer.pvp_target is target_session:
            observer.pvp_target = None


def release(player):
    player.izanami_trapped = False
    player.izanami_target_number = None
    player.izanami_caster_name = None
    player.izanami_loop_ends_at = 0.0
    player.izanami_guessed_this_loop = False


def advance(session, *, now=None, notify=False):
    """Roll the loop forward without letting late server pulses grant retries."""
    player = getattr(session, "player", None)
    if not player or not player.izanami_trapped:
        return False
    now = time.time() if now is None else now
    end = getattr(player, "izanami_loop_ends_at", 0.0)
    if end <= 0:
        # Older saved Izanami victims get a fresh, full 15-second cycle.
        player.izanami_loop_ends_at = now + LOOP_SECONDS
        player.izanami_guessed_this_loop = False
        return False
    if now < end:
        return False
    cycles = math.floor((now - end) / LOOP_SECONDS) + 1
    player.izanami_loop_ends_at = end + cycles * LOOP_SECONDS
    player.izanami_guessed_this_loop = False
    if notify:
        session.send("&CThe fifteen-second Izanami loop repeats. You may guess again: guess 1-25.&x")
    return True


def guess(session, args, *, now=None):
    player = session.player
    if not player.izanami_trapped:
        session.send("Guess what?")
        return
    if len(args) != 1 or not args[0].isdigit() or not 1 <= int(args[0]) <= 25:
        session.send("Guess a number from 1 to 25.")
        return
    now = time.time() if now is None else now
    advance(session, now=now)
    if player.izanami_guessed_this_loop:
        wait = max(1, math.ceil(player.izanami_loop_ends_at - now))
        session.send(f"&RThe moment repeats, but you have already guessed. Wait {wait}s for the next Izanami loop.&x")
        return

    number = int(args[0])
    player.izanami_guessed_this_loop = True
    if number == player.izanami_target_number:
        _notify_caster(player, f"&C{player.name} guessed correctly and escaped your Izanami!&x")
        release(player)
        session.send("&GYou guessed correctly! The Izanami cycle shatters and reality returns.&x")
        return

    maximum_health = max(1, getattr(player, "maximum_health", 1))
    raw_damage = max(1, math.ceil(maximum_health * random.randint(*WRONG_DAMAGE_PERCENT) / 100))
    damage = min(max(0, player.health - 1), raw_damage)
    player.health -= damage
    session.send(
        f"&RIzanami rejects your guess ({number})! The shattered loop inflicts "
        f"{damage} Health damage. Wait for the next 15-second cycle.&x"
    )
    _notify_caster(
        player, f"&R{player.name} guessed {number} incorrectly in your Izanami "
                f"and suffered {damage} Health damage.&x"
    )


def process(sessions=None, *, now=None):
    """One harmless server pulse check; does not damage on its own."""
    from session import ACTIVE_SESSIONS, State
    now = time.time() if now is None else now
    for session in list(ACTIVE_SESSIONS if sessions is None else sessions):
        if getattr(session, "state", None) != State.PLAYING:
            continue
        advance(session, now=now, notify=True)


def blocks_command(session, verb):
    player = getattr(session, "player", None)
    if player and getattr(player, "izanami_trapped", False) and verb.lower() not in ALLOWED_COMMANDS:
        session.send("&RYou are trapped in Izanami! You cannot move, fight, or use jutsu. Wait for the next cycle and guess 1-25.&x")
        return True
    return False
