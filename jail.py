"""
The Jail Cell (Section 94), per direct request:

"also add jail player name hours...that player will remain silenced
or jailed for time automatically being released when timer is up."

A single, genuine permanent room (vnum 9920), built once in
content.populate() the same way as every other static room in the
game (matching duel_arena.py's own established pattern). Deliberately
has NO exits at all -- a jailed player genuinely cannot leave through
normal movement, matching confirmed design ("A specific cell/room --
jailed players are teleported to a dedicated jail room and can't
leave until released").

Release (timer expiry OR an early staff release) sends the player to
their home village's own central/starting room, confirmed directly
rather than back to wherever they were originally standing.
"""

JAIL_CELL_VNUM = 9920


def build_jail(world_module) -> None:
    """Registers the jail cell room into world_module.WORLD. Called
    once from content.populate(), matching duel_arena.build_arena's
    own call site."""
    from world import Room
    world_module.WORLD.add_room(Room(
        vnum=JAIL_CELL_VNUM,
        name="Jail Cell",
        description=(
            "A small, bare stone cell with no visible door or exit. Cold "
            "light filters in from somewhere unseen. There's nothing to do "
            "here but wait out the sentence."
        ),
        biome="none",
    ))


def release(player) -> None:
    """Clears jailed_until and sends the player to their home
    village's own starting/central room -- confirmed release
    destination, regardless of where they were before being jailed.
    Used both for a genuine timer expiry and an early staff release,
    so both paths behave identically."""
    import data_villages
    player.jailed_until = 0.0
    village = data_villages.VILLAGES.get(player.village)
    if village:
        player.room_vnum = village["starting_room_vnum"]
