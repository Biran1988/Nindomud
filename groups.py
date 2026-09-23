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


def remove_member(group: "Group", member) -> None:
    """Removes one member from a group, promoting the next member to
    leader if the leader left, or disbanding entirely if that was the
    last member. Does NOT clear member.group itself -- the caller
    (cmd_group) does that for the member who's actually leaving, since
    this function only touches the group's OWN bookkeeping."""
    if member in group.members:
        group.members.remove(member)
    if not group.members:
        return
    if group.leader is member:
        group.leader = group.members[0]
    if len(group.members) == 1:
        disband(group)
