"""Shared two-second cooldown between actively cast combat jutsu.

Individual per-technique cooldowns remain independent. This layer sits at
commands.cmd_use_jutsu, the common entry point for full names, PERFORM,
one-word shortcuts and direct Taijutsu/Bukijutsu commands.

Only *successful initiation* starts the global timer: an invalid target,
an unlearned ability, a missing resource or a still-cooling technique
does not waste the player's shared cooldown.
"""
import time

DURATION_SECONDS = 2.0
COOLDOWN_KEY = "_global_jutsu_cooldown"

# Passive skills, out-of-combat utility skills, stance/mode toggles and
# maintenance commands should not interrupt combat's jutsu cadence.
EXEMPT_TYPES = frozenset({
    "combat_passive", "counter", "silent_genjutsu_passive",
    "numbered_attack_scroll",
    "general_utility", "track", "track_upgrade", "work_clone", "room_trap",
    "stance", "dual_wield", "mist", "sabre_buff", "hyuga_mode", "eight_gate",
    "six_paths_mode", "chisei",
})
EXEMPT_KEYS = frozenset({"soto uke", "weapon expert"})


def applies(jutsu_key: str, target_words) -> bool:
    import data_jutsu

    jutsu = data_jutsu.JUTSU.get(jutsu_key)
    if not jutsu or jutsu_key in EXEMPT_KEYS:
        return False
    if jutsu.get("jutsu_type") in EXEMPT_TYPES:
        return False
    # Dismissing an already active Mangekyo flame is not a new cast.
    if (jutsu_key == "amaterasu" and target_words
            and target_words[0].casefold() == "extinguish"):
        return False
    # Closing an existing pocket is a release, not a new cast.
    if (jutsu_key == "kamui pocket dimension" and target_words
            and target_words[0].casefold() in {"close", "collapse", "dismiss"}):
        return False
    return True


def ready(session, now=None) -> bool:
    player = session.player
    now = time.time() if now is None else now
    remaining = player.cooldowns.get(COOLDOWN_KEY, 0.0) - now
    if remaining > 0:
        session.send(f"&YYou must recover before using another jutsu! "
                     f"({remaining:.1f}s remaining)&x")
        return False
    return True


def snapshot(session) -> tuple:
    """Inspect all common cast-start markers without altering combat."""
    player = session.player
    return (
        dict(player.cooldowns),
        player.health, player.chakra, player.stamina,
        list(player.inventory),
        dict(player.active_status_effects),
        getattr(session, "pending_cast", None),
        getattr(session, "pending_action", None),
    )


def succeeded(session, before: tuple) -> bool:
    """True if the engine actually started or resolved an active ability."""
    player = session.player
    (cooldowns_before, health, chakra, stamina,
     inventory, effects, pending_cast, pending_action) = before
    # The timer itself must not count as proof of a successful cast.
    cooldowns_before.pop(COOLDOWN_KEY, None)
    cooldowns_now = {k: v for k, v in player.cooldowns.items()
                     if k != COOLDOWN_KEY}
    if cooldowns_before != cooldowns_now:
        return True
    if (player.health, player.chakra, player.stamina) != (health, chakra, stamina):
        return True
    if list(player.inventory) != inventory:
        return True
    if dict(player.active_status_effects) != effects:
        return True
    if getattr(session, "pending_cast", None) is not pending_cast:
        return True
    if getattr(session, "pending_action", None) is not pending_action:
        return True
    return False


def start(session, now=None) -> None:
    now = time.time() if now is None else now
    player = session.player
    player.cooldowns[COOLDOWN_KEY] = max(
        player.cooldowns.get(COOLDOWN_KEY, 0.0),
        now + DURATION_SECONDS,
    )
