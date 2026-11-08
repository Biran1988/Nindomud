"""Per-character Battle Ready macro for ordinary combat preparation.

Never grants or bypasses an ability: each option calls the real existing
jutsu/skill command (with its normal costs, cooldowns and practice gate).
Already-active effects are skipped, so repeated BATTLE READY cannot
accidentally switch any toggle off or refresh a paid buff.
"""
import time

# Existing default preparations stay unchanged. Extra learned jutsu are opt-in.
# Advanced bloodline/tailed-beast modes retain their real activation gates.
# Mutually exclusive stances are ordered strongest first; never replace an
# already active stance. Hand-sign casts go last so they cannot interrupt buffs.
OPTIONS = (
    ("barrier", True),
    ("focused mind", True),
    ("sensory detect", True),
    ("samurai sabre", True),
    ("eight gates", False),
    ("sharingan", False),
    ("byakugan", False),
    ("celestial byakugan", False),
    ("tenseigan chakra mode", False),
    ("sage mode", False),
    ("six paths mode", False),
    ("tailed beast mode", False),
    ("bijuu cloak", False),
    ("susanoo", False),
    ("kamui intangibility", False),
    ("sanchin dachi", False),
    ("neko ashi dachi", False),
    ("kihon dachi", False),
    ("silent movement", False),
    ("camouflage", False),
    ("chisei", False),
    ("hidden mist jutsu", False),
)

OPTION_DEFAULTS = dict(OPTIONS)
ALIASES = {
    "focus": "focused mind",
    "sensory": "sensory detect",
    "sabre": "samurai sabre",
    "gates": "eight gates",
    "gate": "eight gates",
    "sage": "sage mode",
    "eyes": "sharingan",
    "mist": "hidden mist jutsu",
    "sixpaths": "six paths mode",
    "six paths": "six paths mode",
    "beast mode": "tailed beast mode",
    "tailed beast": "tailed beast mode",
    "cloak": "bijuu cloak",
    "tenseigan": "tenseigan chakra mode",
    "celestial": "celestial byakugan",
    "intangibility": "kamui intangibility",
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
    if key == "eight gates":
        import eight_gates
        return eight_gates.active(player) > 0
    if key == "sharingan":
        return bool(player.sharingan_active)
    if key == "byakugan":
        return bool(player.byakugan_active)
    if key == "celestial byakugan":
        return bool(player.celestial_byakugan_active)
    if key == "tenseigan chakra mode":
        return bool(player.tenseigan_active)
    if key == "six paths mode":
        return bool(player.six_paths_active)
    if key == "tailed beast mode":
        return bool(player.tailed_beast_mode_active)
    if key == "bijuu cloak":
        # Never replace a stronger Bijuu form with the weaker cloak.
        return getattr(player, "bijuu_form", 0) >= 2
    if key in ("sanchin dachi", "neko ashi dachi", "kihon dachi"):
        return player.taijutsu_stance == key
    if key == "kamui intangibility":
        return getattr(player, "kamui_intangibility_rounds_left", 0) > 0
    if key == "hidden mist jutsu":
        import hidden_mist
        # A caster may still maintain mist in a room they have left.
        return hidden_mist.owned_room(player) is not None
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
    if key in ("celestial byakugan", "tenseigan chakra mode"):
        import hyuga
        return (hyuga.unlocked(player, key)
                and not skill_training.needs_first_practice(
                    player, data_jutsu.JUTSU[key]["display_name"]))
    if key in data_jutsu.JUTSU:
        jutsu = data_jutsu.JUTSU[key]
        available = bool(combat._can_use_jutsu(player, jutsu, key)
                         and not skill_training.needs_first_practice(
                             player, jutsu["display_name"]))
        if key == "kamui intangibility" and not combat._staff_testing_mangekyo(player):
            return available and bool(player.sharingan_active)
        return available
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
    if key == "eight gates":
        import eight_gates
        return bool(eight_gates.highest_safe(player))
    if key == "six paths mode":
        import six_paths
        return six_paths.eligible(player)
    if key == "tailed beast mode":
        import data_tailed_beasts
        return (player.jinchuriki_beast_key in data_tailed_beasts.TAILED_BEASTS_BY_KEY
                and player.jinchuriki_mastery >= 100)
    if key == "bijuu cloak":
        import data_tailed_beasts
        return (player.jinchuriki_beast_key in data_tailed_beasts.TAILED_BEASTS_BY_KEY
                and player.level >= 25 and player.bijuu_control >= 20
                and player.jinchuriki_mastery >= 10)
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
                  "paid normally; unavailable or unpracticed skills are skipped.",
                  "High-tier eyes, stances, beast modes and Mist are opt-in.",
                  "Stances never replace another active stance; one hand-sign",
                  "cast may be queued at a time."))
    session.send("\n".join(lines))


def _cast(session, key):
    """Call the original implementation, never fake a buff or skip resource checks."""
    import commands
    player = session.player
    if key in ("barrier", "focused mind", "sensory detect", "silent movement", "camouflage"):
        commands.cmd_use_jutsu(session, key, ["on"] if key != "barrier" else [])
    elif key == "samurai sabre":
        commands.cmd_use_jutsu(session, key, [])
    elif key == "eight gates":
        import eight_gates
        eight_gates.command(session, ["safe"])
    elif key == "sharingan":
        commands.cmd_sharingan(session, [])
    elif key == "byakugan":
        import hyuga
        hyuga.cmd_byakugan(session, ["on"])
    elif key in ("celestial byakugan", "tenseigan chakra mode"):
        import hyuga
        hyuga.cast(session, key, ["on"])
    elif key == "six paths mode":
        import six_paths
        six_paths.command(session, ["on"])
    elif key == "tailed beast mode":
        commands.cmd_tailed_beast_mode(session, [])
    elif key == "bijuu cloak":
        import bijuu_chakra
        bijuu_chakra.command(session, ["cloak"])
    elif key in ("sanchin dachi", "neko ashi dachi", "kihon dachi"):
        commands.cmd_use_jutsu(session, key, [])
    elif key in ("kamui intangibility", "hidden mist jutsu"):
        commands.cmd_use_jutsu(session, key, [] if key == "kamui intangibility" else ["on"])
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
        if key in ("sanchin dachi", "neko ashi dachi", "kihon dachi"):
            # Never override an existing manually chosen or earlier stance.
            if player.taijutsu_stance:
                unavailable.append(key)
                continue
        if key == "six paths mode" and getattr(player, "sage_active_contract", ""):
            unavailable.append(key)
            continue
        if key == "tailed beast mode" and getattr(player, "rampage_until", 0):
            unavailable.append(key)
            continue
        if key == "celestial byakugan" and not player.byakugan_active:
            unavailable.append(key)
            continue
        if key == "tenseigan chakra mode" and not player.celestial_byakugan_active:
            unavailable.append(key)
            continue
        # Respect each ability's real cooldown/resources. The regular command
        # remains the authority for restrictions beyond these checks.
        _cast(session, key)
        if _active(player, key):
            done.append(key)
        elif getattr(session, "pending_cast", None) is not None:
            done.append(f"{key} (forming hand signs)")
        else:
            failed.append(key)
        if (getattr(session, "pending_cast", None) is not None
                or getattr(session, "pending_action", None) is not None
                or getattr(session, "is_busy", lambda: False)()):
            if getattr(session, "pending_cast", None) is not None:
                session.send("You are forming hand signs; finish casting before another preparation.")
            session.send("Finish your hand signs or current action, then use BATTLE READY again for remaining preparations.")
            break
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
