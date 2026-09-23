"""
Duels (Section 89, continued) -- the actual mechanic layered on top of
the Arena built in duel_arena.py, per direct request/design:

"What you described but it transfers combatants to an 10 room arena
with several biomes. When combat ends they are returned to the room
they came from."

A Duel is a genuinely new, separate session-level construct (matching
groups.py/trade.py's own pattern) -- not persisted anywhere, since it
only makes sense between two currently-online, currently-consenting
players. Confirmed design across several follow-ups:

- Invite/accept flow, same shape as group/team/trade's own "propose,
  the other side confirms" pattern.
- Once accepted, both combatants are moved into the Arena
  IMMEDIATELY, each to one of the two designated starting rooms
  (duel_arena.ARENA_START_VNUM_A / _B) -- confirmed design: they
  start in DIFFERENT rooms and have to find each other, a genuinely
  maze-like search, not a simple "walk into the same room."
- A duel ends ONLY on a genuine defeat -- confirmed directly, no
  yield/concede option at all.
- The loser (and the winner) are returned to whatever room they were
  ORIGINALLY in before the duel began -- each player's own
  pre-duel room_vnum is remembered for exactly this.
- Confirmed design: NO penalties at all for the loser -- unlike a
  normal PvP defeat (real XP loss, ryo loss, forced hospital trip),
  a duel loss just restores some health/chakra/stamina and sends
  both players home. This is deliberately handled as its OWN defeat
  path (see combat.handle_player_defeat's own duel branch), not a
  variant of the normal one, since "purely a friendly/formal match"
  means none of the normal consequences should apply at all.
"""

DUEL_RETURN_HEALTH_PCT = 50  # confirmed design: "health/chakra/stamina restored a bit", not a full heal


class Duel:
    def __init__(self, session_a, session_b):
        self.session_a = session_a
        self.session_b = session_b
        self.accepted = False
        # Each side's room from BEFORE the duel began -- remembered
        # here so both can be sent back to exactly where they
        # started once the duel ends, regardless of how far they've
        # wandered through the arena by then.
        self.origin_room_a = None
        self.origin_room_b = None

    def other(self, session):
        return self.session_b if session is self.session_a else self.session_a


def start_duel(session_a, session_b) -> Duel:
    duel = Duel(session_a, session_b)
    session_a.duel = duel
    session_b.duel = duel
    return duel


def cancel_duel(duel: Duel) -> None:
    """Discards a pending (not yet begun) duel proposal -- used for an
    explicit decline/cancel before acceptance. A duel that has
    actually BEGUN is ended via end_duel below instead, which also
    handles the arena-to-origin-room return trip."""
    duel.session_a.duel = None
    duel.session_b.duel = None


def begin_duel(duel: Duel) -> None:
    """Moves both combatants into the Arena's two starting rooms,
    remembering where each one actually came from first. Called the
    moment BOTH sides have accepted -- confirmed design, the duel
    starts immediately on acceptance, no separate "ready" step."""
    import duel_arena

    duel.origin_room_a = duel.session_a.player.room_vnum
    duel.origin_room_b = duel.session_b.player.room_vnum
    duel.session_a.player.room_vnum = duel_arena.ARENA_START_VNUM_A
    duel.session_b.player.room_vnum = duel_arena.ARENA_START_VNUM_B


def end_duel(duel: Duel, loser_session) -> None:
    """Ends an in-progress duel on a genuine defeat (confirmed design:
    the only way a duel ends). Confirmed NO penalties at all for the
    loser -- both combatants are simply healed to
    DUEL_RETURN_HEALTH_PCT of their own maximums and returned to
    whatever room they were in before the duel began, with nothing
    else touched (no XP loss, no ryo loss, no forced hospital trip --
    see combat.handle_player_defeat's own separate duel branch,
    which this is called from instead of the normal defeat path)."""
    winner_session = duel.other(loser_session)
    for session, origin_room in (
        (duel.session_a, duel.origin_room_a),
        (duel.session_b, duel.origin_room_b),
    ):
        player = session.player
        player.room_vnum = origin_room
        player.health = max(player.health, int(player.maximum_health * DUEL_RETURN_HEALTH_PCT / 100))
        player.chakra = max(player.chakra, int(player.maximum_chakra * DUEL_RETURN_HEALTH_PCT / 100))
        player.stamina = max(player.stamina, int(player.maximum_stamina * DUEL_RETURN_HEALTH_PCT / 100))
        session.duel = None

    loser_session.send("&DThe duel is over. You are returned home, no worse for wear.&x")
    winner_session.send(f"&GYou defeat {loser_session.player.name} in the duel! Both of you are returned home.&x")
