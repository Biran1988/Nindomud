"""
Player grouping (Section 65).

A group is a purely session-level construct -- not persisted to any
player's save file, since it only makes sense while its members are
actually online (much like session.pvp_target/combat_target). Formed by following a player and having that player enter 'group all',
and its main mechanical effect is splitting a mob kill's XP reward
evenly across every group member who's in the same room as the kill
and still alive, rather than the killer alone taking the full reward
(see combat.handle_mob_defeat). Ryo, loot, and mission progress stay
solo -- only requested to share XP, not everything.
"""

MAX_GROUP_SIZE = 6
GROUP_XP_LEVEL_RANGE = 20

# Authenticate exceptions using the account identity, never a character name.
# Staff status comes from the live, authenticated Account.
GROUP_TEST_ACCOUNTS = frozenset({"kinto", "jared"})
GROUP_ACCESS_DENIED = "Unable to join this group under the current group access rules."


def _group_test_exempt(session) -> bool:
    account = getattr(session, "account", None)
    account_name = str(getattr(account, "name", "") or "").casefold()
    return bool(account is not None and account_name in GROUP_TEST_ACCOUNTS
                or (account is not None and getattr(account, "staff_level", "player") != "player"))


def _pair_requires_ip_check(a, b):
    return not (_group_test_exempt(a) or _group_test_exempt(b))


def group_join_violation(candidate, members):
    """Return (reason, offending IP) for attempted joins.

    A group must remain within twenty ninja levels, and no group member may
    share the real socket IP of another. Missing IP data rejects the join
    without automatically punishing a player for unavailable networking data.
    """
    import country_geo
    if candidate is None or not getattr(candidate, "player", None):
        return "Player is unavailable.", None
    all_members = [m for m in members if m and getattr(m, "player", None)]
    levels = [candidate.player.level] + [m.player.level for m in all_members]
    for member in all_members:
        if not _pair_requires_ip_check(candidate, member):
            continue  # approved testing account or authenticated immortal
        candidate_ip = getattr(candidate, "connection_ip", None)
        other_ip = getattr(member, "connection_ip", None)
        if not candidate_ip or not other_ip:
            return GROUP_ACCESS_DENIED, None
        try:
            address = country_geo.address(candidate_ip)
            if country_geo.address(other_ip) == address:
                return GROUP_ACCESS_DENIED, str(address)
        except ValueError:
            return GROUP_ACCESS_DENIED, None
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
    if not _pair_requires_ip_check(killer, candidate):
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
            session.send(f"&R{GROUP_ACCESS_DENIED}&x")
            return False
        session.send("&RYour connection has been temporarily restricted.&x")
        session.request_close()
        return False
    if reason:
        session.send(reason)
        return False
    return True


def assist_group_attack(attacker, mob) -> None:
    """Pull eligible group members into the same NPC fight, not PvP."""
    group = getattr(attacker, "group", None)
    if not group or attacker not in group.members or not getattr(attacker, "player", None):
        return
    if getattr(mob, "health", 0) <= 0:
        return
    import general_skills
    import element_choice
    for member in list(group.members):
        if (member is attacker or getattr(member, "group", None) is not group
                or not getattr(member, "player", None)
                or getattr(getattr(member, "state", None), "name", "") != "PLAYING"
                or getattr(member, "combat_target", None) is not None
                or getattr(member, "pvp_target", None) is not None):
            continue
        player = member.player
        if (player.room_vnum != mob.room_vnum or player.health <= 0
                or not xp_eligible(attacker, member)
                or player.reaper_seal_id or player.izanami_trapped
                or player.tsukuyomi_frozen or player.downed_by
                or player.position == "sleeping"
                or "asleep" in player.active_status_effects
                or element_choice.in_choice(player)
                or getattr(member, "controlled_clone", None) is not None):
            continue
        if (getattr(mob, "chunin_exam_owner", "")
                and mob.chunin_exam_owner != player.name):
            continue
        general_skills.break_camouflage(member)
        member.combat_target = mob
        player.recently_defeated_timer = 0.0
        member.send(f"&RYou rush to assist your group against {mob.name}!&x")
        attacker.send(f"&C{player.name} joins your fight against {mob.name}!&x")


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
        if getattr(member, "follow_target", None) is group.leader:
            member.follow_target = None


def follow_leader_step(leader, direction: str, previous_room: int, new_room: int) -> None:
    """Move followers through normal exits, whether grouped or not.

    The following relationship can exist before group formation. Every
    follower still pays stamina and passes ordinary movement restrictions.
    """
    from session import ACTIVE_SESSIONS
    import commands
    for member in list(ACTIVE_SESSIONS):
        if member is leader:
            continue
        direct_follow = getattr(member, "follow_target", None) is leader
        legacy_follow = (
            getattr(member, "group", None) is not None
            and member.group is getattr(leader, "group", None)
            and member.group.leader is leader
            and getattr(member, "follow_group_leader", False)
        )
        if not (direct_follow or legacy_follow):
            continue
        if (not getattr(member, "player", None)
                or getattr(getattr(member, "state", None), "name", "") != "PLAYING"
                or member.player.room_vnum != previous_room):
            continue
        if member.combat_target is not None or member.pvp_target is not None:
            member.send("&YYou cannot follow while fighting!&x")
            continue
        if member.pending_cast is not None:
            member.send("&YYou cannot follow while preparing a jutsu!&x")
            continue
        member.send(f"&CYou follow {leader.player.name} {direction}.&x")
        commands.dispatch(member, direction, [])
        if member.player.room_vnum != new_room:
            member.send("&YYou could not keep up with your leader. Catch up to continue following.&x")


def remove_member(group: "Group", member) -> None:
    """Removes one member from a group, promoting the next member to
    leader if the leader left, or disbanding entirely if that was the
    last member. Does NOT clear member.group itself -- the caller
    (cmd_group) does that for the member who's actually leaving, since
    this function only touches the group's OWN bookkeeping."""
    member.follow_group_leader = False
    if getattr(member, "follow_target", None) is group.leader:
        member.follow_target = None
    if member in group.members:
        group.members.remove(member)
    if not group.members:
        return
    if group.leader is member:
        group.leader = group.members[0]
        group.leader.follow_group_leader = False
        group.leader.follow_target = None
        for survivor in group.members:
            if survivor is not group.leader:
                if survivor.follow_group_leader:
                    survivor.follow_target = group.leader
                survivor.send(f"&G{group.leader.player.name} is now the group leader.&x")
    if len(group.members) == 1:
        disband(group)
