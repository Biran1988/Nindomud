"""Appointed leadership, invite-only PvP entry and future hideout assignments.

No world rooms are created or overwritten. This registry lives inside /data.
"""
import json
import os
import tempfile
import time
import config
import storage
import pvp_organizations as pvp

INVITE_LIFETIME = 48 * 3600

def _path():
    return os.path.join(storage.DATA_DIR, "pvp_organizations.json")

def _read():
    try:
        with open(_path(), encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except FileNotFoundError:
        return {}

def _save(reg):
    os.makedirs(storage.DATA_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".org-", suffix=".tmp", dir=storage.DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _path())
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def _leader(key):
    name = _read().get(key, {}).get("leader", "")
    return name if isinstance(name, str) else ""

def _hideout(key):
    value = _read().get(key, {}).get("hideout_vnum", 0)
    return value if type(value) is int and value > 0 else 0

def _staff(session):
    return bool(getattr(session, "account", None) and
                session.account.staff_level in config.STAFF_LEVELS[1:])

def _online(session, name):
    matches = [s for s in session.active_sessions()
               if getattr(s, "player", None) and s.player.name.casefold() == name.casefold()]
    return matches[0] if len(matches) == 1 else None

def _is_leader(player):
    key = pvp.membership(player)
    return bool(key and _leader(key).casefold() == player.name.casefold())

def _village_ok(player, key):
    villages = pvp.ORGANIZATIONS[key][1]
    return not villages or player.village in villages

def _busy(session):
    if (pvp._busy(session) or getattr(session, "combat_target", None) is not None or
            getattr(session.player, "tsukuyomi_frozen", False)):
        return True
    return False

def _clear(player):
    player.pvp_organization_invite = ""
    player.pvp_organization_invited_by = ""
    player.pvp_organization_invite_expires_at = 0.0

def _pending(player):
    key = getattr(player, "pvp_organization_invite", "")
    by = getattr(player, "pvp_organization_invited_by", "")
    until = getattr(player, "pvp_organization_invite_expires_at", 0)
    if key in pvp.ORGANIZATIONS and by and until > time.time() and _leader(key).casefold() == by.casefold():
        return key, by
    return "", ""

def command(session, args):
    player = session.player
    action = args[0].lower() if args else "status"
    key = pvp.membership(player)
    if action in ("list", "help"):
        registry = _read()
        lines = ["&C-- PvP Organizations --&x"]
        for ident, (name, villages, description) in pvp.ORGANIZATIONS.items():
            leader = registry.get(ident, {}).get("leader", "") or "Unappointed"
            eligible = ", ".join(villages) if villages else "all villages"
            lines.append(f"  &W{name}&x ({ident}) - {description} [{eligible}; Leader: {leader}]")
        lines.extend(["Only an immortal-appointed leader may invite players; members must accept.",
                      "PvP applies only between rival organizations. Nonmembers and allies are protected.",
                      "Consensual arena duels remain open to all. Safe rooms stay safe.",
                      "Commands: organization status | invite <player> | accept | decline | leave | members [org] | hideout"])
        if _staff(session):
            lines.append("Immortals: organization appoint <org> <player> | unappoint <org> | sethideout <org> <vnum|none>")
        session.send("\n".join(lines))
        return
    if action in ("status", "info"):
        session.send(f"&COrganization:&x {pvp.display_name(key)}")
        if key:
            session.send(f"&CLeader:&x {_leader(key) or 'Unappointed'}")
            session.send("&YPvP on:&x Rival-organization PvP is allowed outside safe zones.")
            vnum = _hideout(key)
            session.send(f"&CHideout:&x {'Room '+str(vnum) if vnum else 'Not yet assigned'}")
        else:
            session.send("&GPvP protected:&x Nonmembers cannot be attacked outside consensual duels.")
        invited, by = _pending(player)
        if invited and not key:
            session.send(f"&YInvitation:&x {by} invited you to {pvp.display_name(invited)}. Use 'organization accept' or 'organization decline'.")
        remaining = pvp._cooldown_left(player, time.time())
        if remaining:
            session.send(f"Next membership change in {remaining // 3600}h {(remaining % 3600 + 59)//60}m.")
        return
    if action == "members":
        target_org = pvp.resolve(" ".join(args[1:])) if len(args) > 1 else key
        if not target_org:
            session.send("Usage: organization members <organization>")
            return
        names = sorted(s.player.name for s in session.active_sessions()
                       if getattr(s, "player", None) and pvp.membership(s.player) == target_org)
        session.send(f"{pvp.display_name(target_org)} (leader {_leader(target_org) or 'unappointed'}): " + (", ".join(names) or "No members online"))
        return
    if action == "hideout":
        if not key:
            session.send("You do not belong to an organization.")
        else:
            vnum = _hideout(key)
            session.send(f"{pvp.display_name(key)} hideout: " +
                         (f"Room {vnum} assigned; access awaits the completed hideout area." if vnum
                          else "No hideout has been constructed and assigned yet."))
        return
    if action == "join":
        session.send("Direct joining is disabled. An appointed leader must invite you, then you accept.")
        return
    if action == "appoint":
        if not _staff(session):
            session.send("Only immortals may appoint leaders.")
            return
        org_key = pvp.resolve(" ".join(args[1:-1])) if len(args) >= 3 else ""
        if not org_key:
            session.send("Usage: organization appoint <organization> <character>")
            return
        name = args[-1]
        online = _online(session, name)
        target = online.player if online else storage.load_player(name)
        if not target or target.name.casefold() != name.casefold():
            session.send("No saved character with that name.")
            return
        if (pvp.membership(target) not in ("", org_key) or not _village_ok(target, org_key) or
                (online and _busy(online))):
            session.send("That character cannot lead this organization (affiliation, village, or combat).")
            return
        reg = _read()
        if any(other != org_key and v.get("leader", "").casefold() == target.name.casefold()
               for other, v in reg.items()):
            session.send("That character already leads a different organization.")
            return
        reg[org_key] = {"leader": target.name, "hideout_vnum": _hideout(org_key)}
        target.pvp_organization = org_key
        target.pvp_organization_changed_at = time.time()
        _clear(target)
        storage.save_player(target)
        _save(reg)
        session.send(f"&G{target.name} appointed as leader of {pvp.display_name(org_key)}.&x")
        if online and online is not session:
            online.send(f"&YYou were appointed leader of {pvp.display_name(org_key)}. Use 'organization invite <player>'.&x")
        return
    if action == "unappoint":
        if not _staff(session):
            session.send("Only immortals may dismiss organization leaders.")
            return
        org_key = pvp.resolve(" ".join(args[1:]))
        if not org_key:
            session.send("Usage: organization unappoint <organization>")
            return
        reg = _read()
        entry = reg.get(org_key, {})
        reg[org_key] = {"leader": "", "hideout_vnum": entry.get("hideout_vnum", 0)}
        _save(reg)
        session.send(f"Leadership of {pvp.display_name(org_key)} is vacant. Existing members remain.")
        return
    if action == "sethideout":
        if not _staff(session):
            session.send("Only immortals may assign hideouts.")
            return
        org_key = pvp.resolve(" ".join(args[1:-1])) if len(args) >= 3 else ""
        if not org_key:
            session.send("Usage: organization sethideout <org> <existing-room-vnum|none>")
            return
        vnum = 0
        if args[-1].lower() not in ("none", "clear"):
            try:
                vnum = int(args[-1])
            except ValueError:
                session.send("Supply an existing room VNUM or 'none'.")
                return
            import world
            if vnum <= 0 or not world.WORLD.get(vnum):
                session.send("That room has not been built yet.")
                return
        reg = _read()
        if vnum and any(other != org_key and rec.get("hideout_vnum") == vnum
                        for other, rec in reg.items()):
            session.send("That hideout room already belongs to another organization.")
            return
        reg[org_key] = {"leader": _leader(org_key), "hideout_vnum": vnum}
        _save(reg)
        session.send(f"{pvp.display_name(org_key)} hideout " + (f"assigned to {vnum}." if vnum else "cleared."))
        return
    if action == "invite":
        if not key or not _is_leader(player):
            session.send("Only your organization's immortal-appointed leader may issue invitations.")
            return
        if len(args) != 2:
            session.send("Usage: organization invite <online-player>")
            return
        invited_session = _online(session, args[1])
        if not invited_session or invited_session is session:
            session.send("That player must be online and cannot be yourself.")
            return
        target = invited_session.player
        if pvp.membership(target) or not _village_ok(target, key) or _busy(invited_session):
            session.send("That player is ineligible or currently fighting.")
            return
        if _pending(target)[0]:
            session.send("That player already has an active invitation.")
            return
        target.pvp_organization_invite = key
        target.pvp_organization_invited_by = player.name
        target.pvp_organization_invite_expires_at = time.time() + INVITE_LIFETIME
        storage.save_player(target)
        session.send(f"Invited {target.name} to {pvp.display_name(key)} for 48 hours.")
        invited_session.send(f"&Y{player.name}, leader of {pvp.display_name(key)}, invites you to join.&x")
        invited_session.send("&RJoining enables PvP against rival organizations.&x Type 'organization accept' or 'organization decline'.")
        return
    if action == "decline":
        if not getattr(player, "pvp_organization_invite", ""):
            session.send("No invitation to decline.")
            return
        inviter = player.pvp_organization_invited_by
        _clear(player)
        storage.save_player(player)
        session.send("Organization invitation declined.")
        leader = _online(session, inviter)
        if leader and leader is not session:
            leader.send(f"{player.name} declined your invitation.")
        return
    if action == "accept":
        invited, inviter = _pending(player)
        if not invited:
            _clear(player)
            storage.save_player(player)
            session.send("No valid invitation; it may have expired or its leader changed.")
            return
        if key or not _village_ok(player, invited) or _busy(session):
            session.send("You cannot join another organization or accept while fighting.")
            return
        if pvp._cooldown_left(player, time.time()):
            session.send("Your 24-hour membership-change cooldown has not expired.")
            return
        player.pvp_organization = invited
        player.pvp_organization_changed_at = time.time()
        _clear(player)
        storage.save_player(player)
        session.send(f"&RYou joined {pvp.display_name(invited)} by invitation. Rival PvP enabled.&x")
        leader = _online(session, inviter)
        if leader and leader is not session:
            leader.send(f"{player.name} accepted your invitation.")
        return
    if action == "leave":
        if not key:
            session.send("You are not in a PvP organization.")
            return
        if _is_leader(player):
            session.send("An immortal must replace or dismiss your leadership before you can leave.")
            return
        if _busy(session) or pvp._cooldown_left(player, time.time()):
            session.send("You cannot leave during combat or within 24 hours of your last membership change.")
            return
        player.pvp_organization = ""
        player.pvp_organization_changed_at = time.time()
        _clear(player)
        storage.save_player(player)
        session.send("&GYou left your organization and are PvP-protected.&x")
        return
    session.send("Usage: organization list | status | invite <player> | accept | decline | leave | members [org] | hideout")
