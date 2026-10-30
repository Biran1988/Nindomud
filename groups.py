"""
Player grouping (Section 65).

A group is a purely session-level construct -- not persisted to any
player's save file, since it only makes sense while its members are
actually online (much like session.pvp_target/combat_target). Formed
via 'group invite <player>' (same room required) + 'group accept',
and its main mechanical effect is splitting a mob kill's XP reward
evenly across every group member who's in the same room as the kill
and still alive, rather than the killer alone taking the full reward
(see combat.handle_mob_defeat). Ryo, loot, and mission progress stay
solo -- only requested to share XP, not everything.
"""

MAX_GROUP_SIZE = 6


class Group:
    def __init__(self, leader):
        self.leader = leader
        self.members = [leader]  # Session objects, leader always included

    def is_full(self) -> bool:
        return len(self.members) >= MAX_GROUP_SIZE

    def member_names(self) -> list:
        return [m.player.name for m in self.members if m.player]


def disband(group: "Group") -> None:
    """Clears every member's group reference -- called when the whole
    group dissolves (leader disbands, or the last two members split
    up and there's no one left to lead)."""
    for member in list(group.members):
        member.group = None
        member.follow_group_leader = False


def follow_leader_step(leader, direction: str, previous_room: int, new_room: int) -> None:
    """Walk consenting group members after a successful leader movement.

    This uses normal player command dispatch, not a teleport or direct
    room assignment: the follower must personally meet every door,
    jail, combat, status, movement cost and room-entry restriction.
    Followers who are separated stay behind until they catch up.
    """
    group = leader.group
    if group is None or group.leader is not leader:
        return
    import commands
    for member in list(group.members):
        if (member is leader or member.group is not group
                or not getattr(member, "follow_group_leader", False)
                or not member.player or not getattr(member, "state", None)
                or member.state.name != "PLAYING"
                or member.player.room_vnum != previous_room):
            continue
        # A follower still fighting somebody must not get dragged away.
        if member.combat_target is not None or member.pvp_target is not None:
            member.send("&YYou cannot follow while fighting!&x")
            continue
        if member.pending_cast is not None:
            member.send("&YYou cannot follow while preparing a jutsu!&x")
            continue
        member.send(f"&CYou follow {leader.player.name} {direction}.&x")
        commands.dispatch(member, direction, [])
        if member.player.room_vnum != new_room:
            member.send("&YYou could not keep up with your group leader. "
                        "Catch up to continue following.&x")


def remove_member(group: "Group", member) -> None:
    """Removes one member from a group, promoting the next member to
    leader if the leader left, or disbanding entirely if that was the
    last member. Does NOT clear member.group itself -- the caller
    (cmd_group) does that for the member who's actually leaving, since
    this function only touches the group's OWN bookkeeping."""
    member.follow_group_leader = False
    if member in group.members:
        group.members.remove(member)
    if not group.members:
        return
    if group.leader is member:
        group.leader = group.members[0]
    if len(group.members) == 1:
        disband(group)
