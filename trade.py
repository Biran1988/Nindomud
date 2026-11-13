"""
Player-to-player trading (Section 88), per direct request ("Trade
commands" -- one of 3 named in an earlier, explicitly acknowledged gap:
"No tell (private msg), duel (formal 1v1), or trade (player-to-player
exchange) commands").

A trade is a purely session-level construct, exactly like groups.py's
own Group -- not persisted to any player's save file, since it only
makes sense while both parties are actively online and, per confirmed
design, physically together in the same room for the ENTIRE
negotiation. Referenced as session.trade on both participating
sessions (mirroring session.group), not stored on Player at all.

Confirmed design, across 3 direct follow-up questions:
- Full negotiation, not a simple one-step give: each side stages an
  offer (items by name, plus an optional ryo amount) that only they
  can add to or remove from -- you can never touch the other side's
  offer, only your own.
- Both sides must explicitly "trade confirm" before anything moves.
  Confirming locks your CURRENT offer in as final.
- Confirmed as a genuine safety property, not an incidental detail:
  if either side changes their own offer (adds/removes an item,
  changes the ryo amount) AFTER either side has already confirmed,
  BOTH confirmations are reset, forcing a fresh double-confirm on the
  new terms. Otherwise one side could quietly swap out an item after
  the other had already agreed, and the trade would complete on
  terms nobody actually confirmed.
- Same-room only, confirmed directly rather than assumed: unlike a
  team invite (which can target an offline player), a trade requires
  both participants to be together in the same room for the whole
  negotiation. Either player leaving the room cancels the trade
  entirely -- nothing moves, both offers are simply discarded.

The actual item/ryo transfer only ever happens at the moment BOTH
sides are simultaneously confirmed (see complete_trade) -- there is
no partial-completion state, and nothing is ever removed from one
side's inventory before the other side's items are ready to move in
the same instant.
"""


class Trade:
    def __init__(self, session_a, session_b):
        self.session_a = session_a
        self.session_b = session_b
        self.offer_a = {"items": [], "ryo": 0}
        self.offer_b = {"items": [], "ryo": 0}
        self.confirmed_a = False
        self.confirmed_b = False
        # False from proposal until the INVITED side genuinely accepts
        # -- needed so a pending, not-yet-accepted proposal can be
        # told apart from an active, mutually-accepted trade (both
        # sessions' own .trade reference is set the instant the
        # proposal is made, not just after acceptance, so this flag
        # is the only way to distinguish the two states).
        self.accepted = False

    def other(self, session):
        return self.session_b if session is self.session_a else self.session_a

    def my_offer(self, session):
        return self.offer_a if session is self.session_a else self.offer_b

    def their_offer(self, session):
        return self.offer_b if session is self.session_a else self.offer_a

    def is_confirmed(self, session) -> bool:
        return self.confirmed_a if session is self.session_a else self.confirmed_b

    def set_confirmed(self, session, value: bool) -> None:
        if session is self.session_a:
            self.confirmed_a = value
        else:
            self.confirmed_b = value

    def both_confirmed(self) -> bool:
        return self.confirmed_a and self.confirmed_b

    def reset_confirmations(self) -> None:
        """Called whenever EITHER side's offer changes at all -- per
        confirmed design, a genuine safety property, not incidental:
        an offer change after either side has confirmed must clear
        BOTH confirmations, so a trade can never complete on terms
        neither side actually agreed to at the same moment."""
        self.confirmed_a = False
        self.confirmed_b = False


def start_trade(session_a, session_b) -> Trade:
    trade = Trade(session_a, session_b)
    session_a.trade = trade
    session_b.trade = trade
    return trade


def cancel_trade(trade: Trade) -> None:
    """Discards a trade with NOTHING moved -- both offers simply
    vanish. Used both for an explicit 'trade cancel' and for the
    confirmed "leaving the room cancels the whole trade" rule."""
    trade.session_a.trade = None
    trade.session_b.trade = None


def complete_trade(trade: Trade) -> None:
    """Validate the current agreement before moving either offer in memory.

    Offers are not escrow: players can spend money or consume items while
    negotiating. Recheck both sides at the transaction boundary.
    """
    from collections import Counter

    if (not trade.accepted or not trade.both_confirmed()
            or trade.session_a.trade is not trade
            or trade.session_b.trade is not trade):
        raise ValueError("Both players must accept and confirm the current trade.")
    player_a = trade.session_a.player
    player_b = trade.session_b.player
    if player_a.room_vnum != player_b.room_vnum:
        raise ValueError("Both players must be in the same room to trade.")
    for player, offer in ((player_a, trade.offer_a), (player_b, trade.offer_b)):
        if (type(offer["ryo"]) is not int or offer["ryo"] < 0
                or offer["ryo"] > player.ryo):
            raise ValueError("Trade blocked: an offered ryo balance is no longer available.")
        if Counter(offer["items"]) - Counter(player.inventory):
            raise ValueError("Trade blocked: an offered item is no longer available.")
    import crafted_provenance
    # Validate both sides before moving even one item or one ryo. A
    # staged trade can outlive an IP or item change.
    for item in trade.offer_a["items"]:
        if (item not in player_a.inventory
                or crafted_provenance.denied(item, player_a, session=trade.session_a)
                or crafted_provenance.denied(item, player_b, session=trade.session_b)):
            raise ValueError(crafted_provenance.DENIED)
    for item in trade.offer_b["items"]:
        if (item not in player_b.inventory
                or crafted_provenance.denied(item, player_b, session=trade.session_b)
                or crafted_provenance.denied(item, player_a, session=trade.session_a)):
            raise ValueError(crafted_provenance.DENIED)

    for item in trade.offer_a["items"]:
        player_a.inventory.remove(item)
    for item in trade.offer_b["items"]:
        player_b.inventory.remove(item)
    player_a.inventory.extend(trade.offer_b["items"])
    player_b.inventory.extend(trade.offer_a["items"])

    player_a.ryo -= trade.offer_a["ryo"]
    player_b.ryo -= trade.offer_b["ryo"]
    player_a.ryo += trade.offer_b["ryo"]
    player_b.ryo += trade.offer_a["ryo"]

    trade.session_a.trade = None
    trade.session_b.trade = None
