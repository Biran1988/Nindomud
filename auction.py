"""
Auction House (Section 74). Players list an item from inventory for
bidding, with an optional instant-buyout price. A timed listing
resolves periodically via server.py's main pulse loop (the same
elapsed-time-counter pattern weather/mob-respawn/autosave already
use), not the instant it technically expires -- matching the same
"not a live simulation" trade-off every other periodic system in this
project makes.

No escrow: a bid is just a promise, checked against the bidder's
CURRENT ryo again at resolution time, not held aside the moment they
bid. This is deliberately simpler than tracking escrowed ryo across
however many competing bids come in -- if the highest bidder no longer
has enough ryo when the listing actually closes (spent it elsewhere in
the meantime), the sale to them fails and the item returns to the
seller, rather than falling back to the next-highest bidder. A promise
is a promise; spending the ryo elsewhere before the listing closes
breaks it.

Works whether the seller or winning bidder are online or offline right
now -- every ryo/inventory change goes through _deliver_item/_pay_ryo/
_charge_ryo below, which update a connected player's LIVE Session.player
object directly if they're online, or load/modify/save their file
directly if they're not, so someone online sees the result immediately
rather than only after their next login.
"""

import time

HOUSE_FEE_PERCENT = 5  # cut taken from a successful sale, a ryo sink like any other shop transaction
MIN_DURATION_SECONDS = 300      # 5 minutes
MAX_DURATION_SECONDS = 86400    # 24 hours
DEFAULT_DURATION_SECONDS = 3600  # 1 hour


def _next_id(auctions: dict) -> int:
    used = {int(aid) for aid in auctions.keys()}
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def format_duration(seconds) -> str:
    """Unlike missions.py's own duration formatter (minutes/seconds
    only, fine for a 10-20 minute cooldown), listings can run up to 24
    hours, so this also handles hours -- "1439m 59s" would be
    unreadable for a listing near its full duration."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def has_active_listing(seller_name: str) -> bool:
    """True if seller_name already has a listing posted right now --
    used to cap sellers at one active listing at a time, even though
    nothing about the data model itself would prevent more."""
    return any(entry["seller"] == seller_name for entry in all_listings().values())


def create_listing(seller_name: str, item_name: str, starting_bid: int,
                    duration_seconds: int = DEFAULT_DURATION_SECONDS,
                    buyout_price=None) -> int:
    """Posts a new listing, returning its assigned ID. Does not touch
    the seller's inventory -- the caller (cmd_auction) is responsible
    for removing the item from it first, same division of
    responsibility as bounties.py leaves reward payout to its caller."""
    import storage
    auctions = storage.load_auctions()
    auction_id = _next_id(auctions)
    auctions[str(auction_id)] = {
        "seller": seller_name, "item_name": item_name,
        "starting_bid": starting_bid, "current_bid": starting_bid,
        "current_bidder": None, "buyout_price": buyout_price,
        "expires_at": time.time() + duration_seconds,
    }
    storage.save_auctions(auctions)
    return auction_id


def all_listings() -> dict:
    import storage
    return storage.load_auctions()


def get_listing(auction_id):
    return all_listings().get(str(auction_id))


def _get_ryo(player_name: str):
    """Current ryo for a player, whether online or offline. None if no
    such player exists at all."""
    import storage
    from session import ACTIVE_SESSIONS, State
    for session in ACTIVE_SESSIONS:
        if session.state == State.PLAYING and session.player.name == player_name:
            return session.player.ryo
    player = storage.load_player(player_name)
    return player.ryo if player else None


def _deliver_item(player_name: str, item_name: str) -> None:
    import inventory
    import storage
    from session import ACTIVE_SESSIONS, State
    for session in ACTIVE_SESSIONS:
        if session.state == State.PLAYING and session.player.name == player_name:
            inventory.add_item(session.player.inventory, item_name)
            return
    player = storage.load_player(player_name)
    if player:
        inventory.add_item(player.inventory, item_name)
        storage.save_player(player)


def _pay_ryo(player_name: str, amount: int) -> None:
    import storage
    from session import ACTIVE_SESSIONS, State
    for session in ACTIVE_SESSIONS:
        if session.state == State.PLAYING and session.player.name == player_name:
            session.player.ryo += amount
            return
    player = storage.load_player(player_name)
    if player:
        player.ryo += amount
        storage.save_player(player)


def _charge_ryo(player_name: str, amount: int) -> bool:
    """Returns False (charges nothing) if the player no longer has
    enough -- the "a promise, checked again" mechanic from the module
    docstring."""
    import storage
    from session import ACTIVE_SESSIONS, State
    for session in ACTIVE_SESSIONS:
        if session.state == State.PLAYING and session.player.name == player_name:
            if session.player.ryo < amount:
                return False
            session.player.ryo -= amount
            return True
    player = storage.load_player(player_name)
    if player is None or player.ryo < amount:
        return False
    player.ryo -= amount
    storage.save_player(player)
    return True


def place_bid(auction_id, bidder_name: str, amount: int):
    """Returns (ok, message). Doesn't touch ryo at all -- just checks
    the bidder currently has enough and records the bid; the real
    charge happens at resolution (see module docstring)."""
    import storage
    auctions = storage.load_auctions()
    key = str(auction_id)
    entry = auctions.get(key)
    if not entry:
        return False, "There's no auction with that ID."
    if entry["seller"] == bidder_name:
        return False, "You can't bid on your own listing."
    if amount <= entry["current_bid"]:
        return False, f"Your bid must be higher than the current bid of {entry['current_bid']:,} ryo."
    bidder_ryo = _get_ryo(bidder_name)
    if bidder_ryo is None or amount > bidder_ryo:
        return False, "You don't have that much ryo."
    entry["current_bid"] = amount
    entry["current_bidder"] = bidder_name
    storage.save_auctions(auctions)
    return True, f"You bid {amount:,} ryo."


def buyout_listing(auction_id, buyer_name: str):
    """Immediately resolves the listing at its buyout price, bypassing
    the normal wait-for-expiry flow entirely."""
    import storage
    auctions = storage.load_auctions()
    key = str(auction_id)
    entry = auctions.get(key)
    if not entry:
        return False, "There's no auction with that ID."
    if entry["buyout_price"] is None:
        return False, "This listing has no buyout price -- you'll have to bid."
    if entry["seller"] == buyer_name:
        return False, "You can't buy out your own listing."
    price = entry["buyout_price"]
    if not _charge_ryo(buyer_name, price):
        return False, "You don't have enough ryo for the buyout price."
    fee = price * HOUSE_FEE_PERCENT // 100
    _pay_ryo(entry["seller"], price - fee)
    _deliver_item(buyer_name, entry["item_name"])
    del auctions[key]
    storage.save_auctions(auctions)
    return True, f"You buy it out for {price:,} ryo!"


def cancel_listing(auction_id, requester_name: str):
    """Only the seller can cancel, and only before anyone's bid --
    once a bid is in, that bidder is owed a fair shot at winning it."""
    import storage
    auctions = storage.load_auctions()
    key = str(auction_id)
    entry = auctions.get(key)
    if not entry:
        return False, "There's no auction with that ID."
    if entry["seller"] != requester_name:
        return False, "That's not your listing."
    if entry["current_bidder"] is not None:
        return False, "Someone's already bid on it -- it can't be cancelled now."
    del auctions[key]
    storage.save_auctions(auctions)
    return True, entry["item_name"]


def resolve_auction(auction_id) -> str:
    """Resolves one expired listing -- returns a short description of
    the outcome, for logging/testing. Called from
    process_expired_auctions() below, or directly by tests."""
    import storage
    auctions = storage.load_auctions()
    key = str(auction_id)
    entry = auctions.get(key)
    if not entry:
        return "already resolved"

    if entry["current_bidder"] is None:
        _deliver_item(entry["seller"], entry["item_name"])
        del auctions[key]
        storage.save_auctions(auctions)
        return "no bids, returned to seller"

    winner = entry["current_bidder"]
    price = entry["current_bid"]
    if not _charge_ryo(winner, price):
        _deliver_item(entry["seller"], entry["item_name"])
        del auctions[key]
        storage.save_auctions(auctions)
        return "winning bidder couldn't pay, returned to seller"

    fee = price * HOUSE_FEE_PERCENT // 100
    _pay_ryo(entry["seller"], price - fee)
    _deliver_item(winner, entry["item_name"])
    del auctions[key]
    storage.save_auctions(auctions)
    return f"sold to {winner} for {price} ryo"


def process_expired_auctions() -> None:
    """Called periodically from server.py's main pulse loop."""
    now = time.time()
    for auction_id, entry in list(all_listings().items()):
        if entry["expires_at"] <= now:
            resolve_auction(auction_id)
