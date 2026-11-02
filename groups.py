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
GROUP_XP_LEVEL_RANGE = 20


def group_join_violation(candidate, members):
    """Return (reason, offending IP) for attempted joins.

    A group must remain within twenty ninja levels, and no group member may
    share the real socket IP of another. Missing IP data rejects the join
    without automatically punishing a player for unavailable networking data.
    """
    import country_geo
    if candidate is None or not getattr(candidate, "player", None):
        return "Player is unavailable.", None
    candidate_ip = getattr(candidate, "connection_ip", None)
    if not candidate_ip:
        return "Cannot verify your connection IP; grouping is unavailable.", None
    try:
        address = country_geo.address(candidate_ip)
    except ValueError:
        return "Cannot verify your connection IP; grouping is unavailable.", None
    all_members = [m for m in members if m and getattr(m, "player", None)]
    levels = [candidate.player.level] + [m.player.level for m in all_members]
    for member in all_members:
        other_ip = getattr(member, "connection_ip", None)
        if not other_ip:
            return "Cannot verify a member's connection IP; grouping is unavailable.", None
        try:
            if country_geo.address(other_ip) == address:
                return "Two players on the same IP cannot group.", str(address)
        except ValueError:
            return "Cannot verify a member's connection IP; grouping is unavailable.", None
    if max(levels) - min(levels) > GROUP_XP_LEVEL_RANGE:
        return f"Group members must be within {GROUP_XP_LEVEL_RANGE} ninja levels.", None
    return None, None


def xp_eligible(killer, candidate):
    """Defend against existing-group rank drift and stale same-IP sessions."""
    import country_geo
    if not getattr(candidate, "player", None) or not getattr(killer, "player", None):
        return False
    if abs(candidate.player.level - killer.player.level) > GROUP_XP_LEVEL_RANGE:
        return False
    if killer is candidate:
        return True
    a, b = getattr(killer, "connection_ip", None), getattr(candidate, "connection_ip", None)
    if not a or not b:
        return False
    try:
        return country_geo.address(a) != country_geo.address(b)
    except ValueError:
        return False


def enforce_join(session, members):
    """Central security check for both invitation and actual acceptance."""
    reason, ban_ip = group_join_violation(session, members)
    if ban_ip:
        import network_bans
        try:
            network_bans.temporary_ip_ban(ban_ip, duration_seconds=1800)
        except (OSError, ValueError) as error:
            # Never allow a forbidden same-IP group if security storage fails.
            session.send(f"&RGrouping denied; unable to record security ban: {error}&x")
            return False
        session.send("&RSame-IP group attempt: your IP is banned for 30 minutes.&x")
        session.request_close()
        return False
    if reason:
        session.send(reason)
        return False
    return True


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
        group.leader.follow_group_leader = False
        for survivor in group.members:
            if survivor is not group.leader:
                survivor.send(f"&G{group.leader.player.name} is now the group leader.&x")
    if len(group.members) == 1:
        disband(group)
