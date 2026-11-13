"""Staff single-step ninja rank promotions, separate from staff-level promotion."""
import config


def command(session, args):
    import kage
    import olc
    import storage

    account = getattr(session, "account", None)
    if not account or account.staff_level not in config.STAFF_LEVELS[1:]:
        session.send("Only immortals can promote ninja ranks.")
        return
    if len(args) != 1 or not args[0].isascii() or not args[0].isalpha() or not 2 <= len(args[0]) <= 20:
        session.send("Usage: PROMOTE <playername> (one ninja rank at a time)")
        return
    target, online = olc._find_target_player(args[0])
    if target is None:
        session.send(f"No character named {args[0]} was found.")
        return
    current = target.village_rank
    if current not in kage.RANK_ORDER:
        session.send(f"{target.name}'s ninja rank '{current}' is not in the rank ladder.")
        return
    index = kage.RANK_ORDER.index(current)
    if current == "kage":
        session.send(f"{target.name} is already an appointed Kage.")
        return
    if current == "jonin":
        session.send(f"{target.name} is already Jonin, the highest normal rank. An Implementor may use SETKAGE separately.")
        return
    new_rank = kage.RANK_ORDER[index + 1]

    import data_headbands
    target.village_rank = new_rank
    item = data_headbands.apply_rank_headband(target, new_rank)
    if new_rank == "genin":
        # The normal Genin promotion grants 50 mission points and a headband.
        kage.award_genin_mission_points_if_applicable(online or session, target, new_rank)
    storage.save_player(target)
    kage.announce_rank_up(target.name, new_rank)
    if online:
        online.send(f"&YYou have been promoted from {current.title()} to {new_rank.title()}!&x")
        if item:
            online.send(f"&YYour new headband: {item}.&x")
    session.send(f"&GPromoted {target.name}: {current.title()} -> {new_rank.title()} (saved).&x")
    olc._log(session.player.name, "player", 0,
             f"promoted {target.name} from {current} to {new_rank}")
