"""Immortal tools for appointing Six Paths descendants.

This overrides only Six Paths eligibility/branch; it does not edit or reroll
a character's natural Indra/Ashura reincarnation or birth resource bonuses.
"""
import config


def command(session, args):
    import olc
    import six_paths
    import storage

    account = getattr(session, "account", None)
    if not account or getattr(account, "staff_level", None) not in config.STAFF_LEVELS[1:]:
        session.send("Only immortals can grant Six Paths descendant status.")
        return
    if len(args) not in (1, 2) or not args[0].isascii() or not args[0].isalpha() or not 2 <= len(args[0]) <= 20:
        session.send("Usage: sixdescendant <player> <indra|ashura|off|status>")
        return
    action = args[1].lower() if len(args) == 2 else "status"
    if action not in ("indra", "ashura", "off", "status"):
        session.send("Usage: sixdescendant <player> <indra|ashura|off|status>")
        return
    target, live = olc._find_target_player(args[0])
    if target is None:
        session.send(f"No character named '{args[0]}' exists.")
        return
    if action == "status":
        branch = target.six_paths_descendant
        birth = target.reincarnation
        session.send(f"{target.name}: Six Paths descendant: {branch.title() if branch else 'None'}; "
                     f"natural reincarnation: {birth.title() if birth else 'None'}.")
        return
    selected = "" if action == "off" else action
    if target.six_paths_descendant == selected:
        session.send(f"{target.name} already has this Six Paths descendant setting.")
        return

    original = target.six_paths_descendant
    active = target.six_paths_active
    target.six_paths_descendant = selected
    # Do not leave an already-active mode with the wrong lineage.
    target.six_paths_active = False
    try:
        unlocks = six_paths.sync_skills(target) if selected else []
        storage.save_player(target)
    except OSError as exc:
        target.six_paths_descendant = original
        target.six_paths_active = active
        session.send(f"Six Paths descendant change could not be saved: {exc}")
        return

    label = f"{selected.title()} (Six Paths descendant)" if selected else "no staff-granted Six Paths ancestry"
    session.send(f"{target.name} now has {label}. Saved to their character file.")
    if live is not None:
        live.send(
            f"&YYour Six Paths ancestry has been {'appointed as ' + selected.title() if selected else 'revoked by an immortal'}.&x"
        )
        for line in unlocks:
            live.send(line)
        if hasattr(live, "send_prompt"):
            live.send_prompt()
