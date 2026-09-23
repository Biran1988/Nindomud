"""
Corpses left behind by defeated mobs (extends combat.py's mob-defeat
flow). A mob's ryo and any loot items move into a Corpse placed in the
room, rather than being credited to the killer instantly -- players
loot it manually with `loot`, or automatically per their `config`
settings (auto_loot_ryo / auto_loot_gear / auto_sac_corpse).

Sacrificing a corpse (manually with `sacrifice`, or automatically via
auto_sac_corpse) always destroys it for a flat SACRIFICE_RYO_REWARD,
even if it's still carrying ryo or items -- anything left un-looted is
simply forfeited, not transferred. An unlooted, un-sacrificed corpse
decays on its own after config.CORPSE_DECAY_SECONDS (5 minutes) so the
world doesn't accumulate corpses indefinitely.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import config
import inventory

CORPSES_BY_ROOM: Dict[int, List["Corpse"]] = {}


@dataclass
class Corpse:
    name: str
    room_vnum: int
    ryo: int = 0
    items: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def is_empty(self) -> bool:
        return self.ryo <= 0 and not self.items


def spawn_corpse(mob_name: str, room_vnum: int, ryo: int, items: List[str]) -> Corpse:
    corpse = Corpse(name=f"the corpse of {mob_name}", room_vnum=room_vnum,
                     ryo=ryo, items=list(items))
    CORPSES_BY_ROOM.setdefault(room_vnum, []).append(corpse)
    return corpse


def corpses_in_room(room_vnum: int) -> List[Corpse]:
    return CORPSES_BY_ROOM.get(room_vnum, [])


def find_corpse(room_vnum: int, query: Optional[str] = None) -> Optional[Corpse]:
    room_corpses = corpses_in_room(room_vnum)
    if not room_corpses:
        return None
    if not query or query.lower() == "all":
        return room_corpses[0]
    query = query.lower()
    for corpse in room_corpses:
        if query in corpse.name.lower():
            return corpse
    return None


def remove_corpse(corpse: Corpse) -> None:
    room_corpses = CORPSES_BY_ROOM.get(corpse.room_vnum, [])
    if corpse in room_corpses:
        room_corpses.remove(corpse)


def loot_ryo(player, corpse: Corpse) -> int:
    amount = corpse.ryo
    if amount > 0:
        player.ryo += amount
        corpse.ryo = 0
    return amount


def loot_gear(player, corpse: Corpse) -> List[str]:
    added, leftover = inventory.add_items(player.inventory, list(corpse.items))
    corpse.items = leftover
    return added


SACRIFICE_RYO_REWARD = 1


def sacrifice(player, corpse: Corpse) -> "tuple[int, list]":
    """Destroy a corpse for a flat ryo reward, regardless of what's still
    on it -- any un-looted ryo/items are forfeited, not transferred.
    Returns (ryo_forfeited, items_forfeited) for messaging."""
    forfeited_ryo = corpse.ryo
    forfeited_items = list(corpse.items)
    remove_corpse(corpse)
    player.ryo += SACRIFICE_RYO_REWARD
    return forfeited_ryo, forfeited_items


def process_decay() -> None:
    now = time.time()
    for room_vnum in list(CORPSES_BY_ROOM.keys()):
        remaining = [c for c in CORPSES_BY_ROOM[room_vnum]
                     if now - c.created_at < config.CORPSE_DECAY_SECONDS]
        CORPSES_BY_ROOM[room_vnum] = remaining
