"""Audited live staff observation of online players, excluding authentication.

Spy state is transient, never saved. Monitor content is not written to disk.
"""
AUTHORIZED = frozenset(("administrator", "implementor"))
SECRET_COMMANDS = frozenset(("password", "passwd", "pass", "changepassword",
                            "setpassword", "resetpassword", "delete", "account"))


def _staff(session):
    return (getattr(getattr(session, "account", None), "staff_level", None) in AUTHORIZED
            and getattr(getattr(session, "state", None), "name", "") == "PLAYING")


def _target(session):
    return (getattr(getattr(session, "account", None), "staff_level", None) == "player"
            and getattr(getattr(session, "state", None), "name", "") == "PLAYING"
            and getattr(session, "player", None) is not None)


def _watchers(target):
    from session import ACTIVE_SESSIONS
    return [s for s in tuple(ACTIVE_SESSIONS)
            if s is not target and getattr(s, "spy_target", None) is target
            and _staff(s) and _target(target)]


def _audit(staff, target, message):
    import olc
    # Audit only who watched whom, not observed messages or commands.
    olc._log(staff.player.name, "spy", target, message)


def command(session, args):
    if not _staff(session):
        session.send("Spy is restricted to administrators and Implementors.")
        return
    if not args or args[0].lower() in ("list", "status"):
        target = getattr(session, "spy_target", None)
        if target is not None and _target(target):
            session.send(f"&CSpy active: {target.player.name}. Use 'spy off' to stop.&x")
        else:
            session.spy_target = None
            session.send("Spy inactive. Usage: spy <online player> | spy off | spy status")
        return
    if args[0].lower() in ("off", "stop"):
        target = getattr(session, "spy_target", None)
        session.spy_target = None
        if target is not None:
            _audit(session, getattr(getattr(target, "player", None), "name", "unknown"), "stopped observation")
        session.send("&CSpy disabled.&x")
        return
    if len(args) != 1:
        session.send("Usage: spy <online player> | spy off | spy status")
        return
    from session import ACTIVE_SESSIONS
    target = next((s for s in tuple(ACTIVE_SESSIONS) if s is not session and _target(s)
                   and s.player.name.casefold() == args[0].casefold()), None)
    if target is None:
        session.send("No connected ordinary player by that name. Staff accounts cannot be monitored.")
        return
    old = getattr(session, "spy_target", None)
    if old is target:
        session.send(f"Already observing {target.player.name}. Use 'spy off' to stop.")
        return
    if old is not None:
        _audit(session, getattr(getattr(old, "player", None), "name", "unknown"), "stopped observation (switched)")
    session.spy_target = target
    _audit(session, target.player.name, "started observation")
    session.send(f"&C[SPY]&x Observing {target.player.name}'s live commands, output, and prompt. "
                 "Authentication and password commands are excluded. Type 'spy off' to stop.")


def forward_input(target, line):
    if not _target(target) or not line.strip():
        return
    word = line.split(None, 1)[0].lower()
    safe_line = "[REDACTED: sensitive command]" if word in SECRET_COMMANDS else line
    for watcher in _watchers(target):
        watcher.send(f"&D[SPY {target.player.name} INPUT]&x {safe_line}")


def forward_output(target, message):
    if _target(target):
        for watcher in _watchers(target):
            watcher.send(f"&D[SPY {target.player.name} OUTPUT]&x {message}")


def forward_prompt(target, prompt):
    if _target(target):
        for watcher in _watchers(target):
            watcher.send(f"&D[SPY {target.player.name} PROMPT]&x {prompt}")


def disconnect(target):
    """Stop watching an offline character or a departing staff session."""
    from session import ACTIVE_SESSIONS
    for watcher in tuple(ACTIVE_SESSIONS):
        if watcher is target:
            watcher.spy_target = None
        elif getattr(watcher, "spy_target", None) is target:
            watcher.spy_target = None
            if _staff(watcher):
                _audit(watcher, getattr(getattr(target, "player", None), "name", "unknown"),
                       "stopped observation (disconnect)")
                watcher.send("&D[SPY]&x Target disconnected. Observation stopped.")
