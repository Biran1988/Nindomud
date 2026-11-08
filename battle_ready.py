"""Per-character Battle Ready macro for ordinary combat preparation.

Never grants or bypasses an ability: each option calls the real existing
jutsu/skill command (with its normal costs, cooldowns and practice gate).
Already-active effects are skipped, so repeated BATTLE READY cannot
accidentally switch any toggle off or refresh a paid buff.
"""
import time

# Ordered so instant defenses happen first; delayed Chisei hand signs last.
# Heavy transformations and stealth are opt-in rather than automatic.
OPTIONS = (
    ("barrier", True),
    ("focused mind", True),
    ("sensory detect", True),
    ("samurai sabre", True),
    ("sharingan", False),
    ("byakugan", False),
    ("sage mode", False),
    ("susanoo", False),
    ("silent movement", False),
    ("camouflage", False),
    ("chisei", False),
)

OPTION_DEFAULTS = dict(OPTIONS)
ALIASES = {
    "focus": "focused mind",
    "sensory": "sensory detect",
    "sabre": "samurai sabre",
    "sage": "sage mode",
    "eyes": "sharingan",
}


def settings(player):
    """Return effective settings; older character files have sensible defaults."""
    overrides = getattr(player, "battle_ready_settings", None) or {}
    return {key: bool(overrides.get(key, default)) for key, default in OPTIONS}


def _active(player, key):
    import general_skills
    if key in ("focused mind", "sensory detect", "silent movement", "camouflage"):
        return general_skills.active(player, general_skills.EFFECT_KEYS[key])
    if key == "barrier":
        import status_effects
        return status_effects.has_effect(player.active_status_effects, "barrier")
    if key == "samurai sabre":
        return bool(player.samurai_sabre_active)
    if key == "sharingan":
        return bool(player.sharingan_active)
    if key == "byakugan":
        return bool(player.byakugan_active)
    if key == "sage mode":
        import sage_mode
        return bool(sage_mode.active_contract(player))
    if key == "susanoo":
        import susanoo
        return bool(susanoo.active(player))
    if key == "chisei":
        return "chisei" in player.active_status_effects
    return False


def _available(player, key):
    """Check what the player genuinely learned, without exposing hidden bloodlines."""
    import combat
    import data_jutsu
    import skill_training
    if key in data_jutsu.JUTSU:
        jutsu = data_jutsu.JUTSU[key]
        return bool(combat._can_use_jutsu(player, jutsu, key)
                    and not skill_training.needs_first_practice(
                        player, jutsu["display_name"]))
    if key == "sharingan":
        return ((player.bloodline_id == "sharingan" and player.bloodline_tomoe >= 1)
                or combat._staff_testing_mangekyo(player))
    if key == "byakugan":
        import hyuga
        return hyuga.unlocked(player, "byakugan")
    if key == "sage mode":
        import sage_mode
        chosen = sage_mode.chosen_contract(player)
        return bool(chosen and player.sage_mastery.get(chosen, 0) >= sage_mode.MASTERY_REQUIRED)
    if key == "susanoo":
        import susanoo
        return susanoo.eligible(player)
    return False


def _set_setting(session, name, enabled):
    import storage
    player = session.player
    old = dict(getattr(player, "battle_ready_settings", None) or {})
    updated = dict(old)
    updated[name] = enabled
    player.battle_ready_settings = updated
    try:
        storage.save_player(player)
    except OSError as exc:
        player.battle_ready_settings = old
        session.send(f"&RUnable to save Battle Ready settings: {exc}&x")
        return
    session.send(f"&GBattle Ready: {name.title()} {'ON' if enabled else 'OFF'} (saved).&x")


def _show_config(session):
    player = session.player
    configured = settings(player)
    lines = ["&WBattle Ready configuration&x",
             "  The command attempts enabled, learned buffs in sequence."]
    for name, _ in OPTIONS:
        state = "&GON&x " if configured[name] else "&DOFF&x"
        availability = ("active" if _active(player, name)
                        else "learned" if _available(player, name) else "locked")
        lines.append(f"  {name.title():18s} [{state}]  {availability}")
    lines.extend(("", "Syntax:",
                  "  battle ready                  Activate configured preparations",
                  "  battle ready config           View this menu",
                  "  battle ready <jutsu> on|off    Save one selection",
                  "  config battle ready <jutsu> on|off",
                  "  config battle ready           View this menu",
                  "  battle ready status           Show currently active preparations",
                  "Already active buffs are never toggled off. Chakra and Stamina are",
                  "paid normally; unavailable or unpracticed skills are skipped."))
    session.send("\n".join(lines))


def _cast(session, key):
    """Call the original implementation, never fake a buff or skip resource checks."""
    import commands
    player = session.player
    if key in ("barrier", "focused mind", "sensory detect", "silent movement", "camouflage"):
        commands.cmd_use_jutsu(session, key, ["on"] if key != "barrier" else [])
    elif key == "samurai sabre":
        commands.cmd_use_jutsu(session, key, [])
    elif key == "sharingan":
        commands.cmd_sharingan(session, [])
    elif key == "byakugan":
        import hyuga
        hyuga.cmd_byakugan(session, ["on"])
    elif key == "sage mode":
        import sage_mode
        sage_mode.command(session, ["on"])
    elif key == "susanoo":
        import susanoo
        susanoo.command(session, ["on"])
    elif key == "chisei":
        commands.cmd_use_jutsu(session, key, ["on"])


def _prepare(session):
    import combat
    import status_effects
    player = session.player
    if player is None:
        return
    if combat._is_action_blocked(player) or status_effects.has_effect(
            player.active_status_effects, "silenced"):
        session.send("You cannot focus your chakra to prepare for battle right now.")
        return
    if (getattr(session, "pending_cast", None) is not None
            or getattr(session, "pending_action", None) is not None):
        session.send("Finish your current action before using Battle Ready.")
        return
    if getattr(session, "is_busy", lambda: False)():
        session.send("Finish your current action before using Battle Ready.")
        return
    enabled = settings(player)
    done, unchanged, unavailable, failed = [], [], [], []
    session.send("&CBattle Ready: preparing your selected techniques...&x")
    for key, _default in OPTIONS:
        if not enabled[key]:
            continue
        if _active(player, key):
            unchanged.append(key)
            continue
        if not _available(player, key):
            unavailable.append(key)
            continue
        if key == "camouflage" and (
                getattr(session, "combat_target", None) is not None
                or getattr(session, "pvp_target", None) is not None):
            unavailable.append(key)
            continue
        # Respect each ability's real cooldown/resources. The regular command
        # remains the authority for restrictions beyond these checks.
        _cast(session, key)
        if _active(player, key):
            done.append(key)
        elif key == "chisei" and getattr(session, "pending_cast", None) is not None:
            done.append("chisei (channeling)")
        else:
            failed.append(key)
    def label(items):
        return ", ".join(name.title() for name in items) if items else "none"
    session.send(
        f"&WBattle Ready summary:&x Activated: {label(done)}. "
        f"Already active: {label(unchanged)}. "
        f"Unavailable: {label(unavailable)}. "
        f"Not activated: {label(failed)}."
    )


def command(session, args):
    """BATTLE READY [CONFIG|STATUS|<name> ON/OFF]; also accepts BREADY."""
    words = [str(a).casefold() for a in args]
    if words and words[0] == "ready":
        words = words[1:]
    if words and words[0] == "config":
        words = words[1:]
        if not words:
            _show_config(session)
            return
    if not words or words == ["on"]:
        _prepare(session)
        return
    if words == ["status"]:
        player = session.player
        lines = ["&WBattle Ready status&x"]
        for key, _ in OPTIONS:
            if _active(player, key):
                lines.append("  &GActive&x  " + key.title())
        if len(lines) == 1:
            lines.append("  No configured preparation is currently active.")
        session.send("\n".join(lines))
        return
    if len(words) >= 2 and words[-1] in ("on", "off"):
        name = " ".join(words[:-1])
        name = ALIASES.get(name, name)
        if name in OPTION_DEFAULTS:
            _set_setting(session, name, words[-1] == "on")
            return
    _show_config(session)
