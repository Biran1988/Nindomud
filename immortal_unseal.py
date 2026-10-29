"""Immortal-only extraction of a sealed Tailed Beast from its jinchuriki.

This is intentionally separate from Reaper Death Seal, which binds PLAYERS,
never NPCs. Releasing a captured Beast turns it back into a real roaming Mob.
"""
import time

import combat
import config
import data_tailed_beasts
import storage
import tailed_beasts
import world


def _holders():
    """Use live characters first (including linkdead), then offline saves."""
    import session as session_module
    live = {}
    for s in session_module.ACTIVE_SESSIONS:
        p = getattr(s, "player", None)
        if p and getattr(getattr(s, "state", None), "name", "") in ("PLAYING", "LINKDEAD"):
            live[p.name.casefold()] = (p, s)
    result = list(live.values())
    for p in storage.all_players():
        if p.name.casefold() not in live:
            result.append((p, None))
    return result


def _beast_from_words(words):
    value = " ".join(words).strip().casefold().replace("-", "_")
    if value.isdigit():
        return next((b for b in data_tailed_beasts.TAILED_BEASTS if b["tails"] == int(value)), None)
    return next((b for b in data_tailed_beasts.TAILED_BEASTS
                 if b["key"].casefold() == value
                 or b["display_name"].casefold().replace("-", "_") == value), None)


def _clear_jinchuriki(player):
    """Remove powers as well as the ownership field, including rampage buffs."""
    if player.rampage_until:
        boost = tailed_beasts.RAMPAGE_STAT_BOOST_PCT
        for maximum, current in (("maximum_health", "health"),
                                 ("maximum_chakra", "chakra"),
                                 ("maximum_stamina", "stamina")):
            max_now = getattr(player, maximum)
            original = max_now * 100 // (100 + boost)
            setattr(player, maximum, original)
            setattr(player, current, max(1, getattr(player, current) - (max_now - original)))
    player.jinchuriki_beast_key = None
    player.jinchuriki_mastery = 0
    player.rampage_until = 0.0
    player.tailed_beast_mode_active = False


def command(session, args):
    """unseal list | unseal <player> | unseal mob <beast name/1-9>.

    Staff may free beasts from online or offline characters. Prevents more
    than one beast from roaming at once; this cannot create an unowned copy.
    """
    if (not getattr(session, "account", None)
            or session.account.staff_level not in config.STAFF_LEVELS[1:]):
        session.send("&ROnly immortals can unseal Tailed Beasts.&x")
        return
    usage = ("Usage: unseal list | unseal <player> | "
             "unseal mob <beast name or tail number 1-9>")
    if not args:
        session.send(usage)
        return

    parts = list(args)
    requested_beast = None
    mode = parts[0].casefold()
    if mode == "list":
        if len(parts) != 1:
            session.send(usage)
            return
        holders = [(b, p.name) for p, _ in _holders()
                   if (b := data_tailed_beasts.TAILED_BEASTS_BY_KEY.get(
                       getattr(p, "jinchuriki_beast_key", None)))]
        if not holders:
            session.send("No Tailed Beasts are currently sealed in a player.")
            return
        session.send("&WSealed Tailed Beasts:&x\n" +
                     "\n".join(f"  &Y{b['display_name']}&x ({b['tails']}-tail) - {name}"
                                for b, name in sorted(holders, key=lambda x: x[0]["tails"])))
        return

    if mode in ("mob", "beast"):
        requested_beast = _beast_from_words(parts[1:])
        if not requested_beast:
            session.send(usage)
            return
    elif mode == "player":
        if len(parts) != 2:
            session.send(usage)
            return
        parts = parts[1:]

    everyone = _holders()
    if requested_beast:
        found = [(p, s) for p, s in everyone
                 if p.jinchuriki_beast_key == requested_beast["key"]]
    else:
        name = " ".join(parts).casefold()
        found = [(p, s) for p, s in everyone if p.name.casefold() == name
                 and p.jinchuriki_beast_key]

    if not found:
        session.send("No matching sealed Tailed Beast found. Use 'unseal list' to see holders.")
        return
    if len(found) != 1:
        session.send("&RAmbiguous sealed beast ownership: fix duplicate holders before releasing it.&x")
        return
    holder, online_session = found[0]
    beast = data_tailed_beasts.TAILED_BEASTS_BY_KEY.get(holder.jinchuriki_beast_key)
    if not beast:
        session.send("That character has no valid sealed Tailed Beast.")
        return
    if tailed_beasts.any_beast_currently_roaming(combat):
        session.send("&RA Tailed Beast is already loose. Seal, defeat or wait for it to despawn first.&x")
        return

    # Spawn first. A failed spawn must never silently strip the holder
    # of their permanently owned beast.
    try:
        mob = tailed_beasts.release_beast(beast, world, combat)
    except Exception:
        session.send("&RThe beast could not be released; its seal is unchanged.&x")
        return

    original = (holder.jinchuriki_beast_key, holder.jinchuriki_mastery,
                holder.rampage_until, holder.tailed_beast_mode_active,
                holder.maximum_health, holder.health, holder.maximum_chakra,
                holder.chakra, holder.maximum_stamina, holder.stamina)
    try:
        _clear_jinchuriki(holder)
        storage.save_player(holder)
    except Exception:
        (holder.jinchuriki_beast_key, holder.jinchuriki_mastery,
         holder.rampage_until, holder.tailed_beast_mode_active,
         holder.maximum_health, holder.health, holder.maximum_chakra,
         holder.chakra, holder.maximum_stamina, holder.stamina) = original
        combat.remove_mob(mob)
        session.send("&RFailed to save the freed jinchuriki. The seal remains intact.&x")
        return

    if online_session is not None:
        # End involuntary attacks caused by a rampage, but retain ordinary
        # player combat targets unrelated to the former beast's powers.
        if original[2]:
            online_session.combat_target = None
            online_session.pvp_target = None
        online_session.send(f"&R{beast['display_name']} has been extracted from your seal! "
                            "Your Jinchuriki powers fade.&x")
    session.send(f"&GUnsealed {beast['display_name']} from {holder.name}. "
                 f"It now roams in room {mob.room_vnum}.&x")
    import commands
    commands._broadcast_globally(
        tailed_beasts.announcement(beast, freed_from=holder.name)
    )
