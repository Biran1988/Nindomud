"""Universal Mangekyo Susanoo with player-customized appearance and combat kit.

Susanoo is not a rolled eye technique: every genuine Mangekyo holder may
summon one. Its color, stance and spectral weapon are character settings,
saved independently from the active chakra-maintained form.
"""

import storage

# Names are intentionally fixed so players cannot inject control codes into
# messages or serialize invalid configurations.
COLORS = {
    "red": "&R",
    "blue": "&B",
    "purple": "&M",
    "green": "&G",
    "gold": "&Y",
    "white": "&W",
    "black": "&D",
    "cyan": "&C",
    "pink": "&[213]",
    "orange": "&[208]",
}
STYLES = {
    # (outgoing melee percent, incoming damage reduction percent)
    "offensive": (25, 5),
    "defensive": (5, 25),
    "balanced": (12, 15),
}
WEAPONS = {
    # outgoing melee percent, accuracy bonus, damage reduction bonus
    "sword": (10, 0, 0),
    "bow": (0, 12, 0),
    "shield": (0, 0, 10),
    "dagger": (5, 8, 0),
    "spear": (8, 6, 0),
    "axe": (15, -3, 0),
    "staff": (5, 3, 5),
    "mace": (12, -2, 0),
}
ACTIVATION_CHAKRA = 40
IDLE_UPKEEP_CHAKRA = 8
COMBAT_UPKEEP_CHAKRA = 18


def eligible(player) -> bool:
    """Never grant access from a stored display preference or staff skills."""
    return bool(player and getattr(player, "bloodline_mangekyo", False)
                and getattr(player, "bloodline_id", None) == "sharingan")


def active(player) -> bool:
    return bool(eligible(player) and getattr(player, "susanoo_active", False))


def _selection(player, field, options, default):
    value = getattr(player, field, default)
    return value if value in options else default


def color(player) -> str:
    return _selection(player, "susanoo_color", COLORS, "purple")


def style(player) -> str:
    return _selection(player, "susanoo_style", STYLES, "balanced")


def weapon(player) -> str:
    return _selection(player, "susanoo_weapon", WEAPONS, "sword")


def _display(player) -> str:
    shade = color(player)
    return f"{COLORS[shade]}{shade.capitalize()}&x"


def menu(player) -> str:
    """Compact status/menu used by SET SUSANOO and SUSANOO status."""
    if not eligible(player):
        return "Susanoo is unlocked for every shinobi with an awakened Mangekyo Sharingan."
    return (
        "&W+----------- SUSANOO -----------+&x\n"
        f" Status: &C{'ACTIVE' if active(player) else 'Inactive'}&x\n"
        f" Color:  {_display(player)}\n"
        f" Style:  &W{style(player).capitalize()}&x\n"
        f" Weapon: &W{weapon(player).capitalize()}&x\n"
        "&W+-------------------------------+&x\n"
        " &Cset susanoo color <name>&x\n"
        " &Cset susanoo style <offensive|defensive|balanced>&x\n"
        " &Cset susanoo weapon <name>&x\n"
        " &Cset susanoo colors&x / &Cset susanoo weapons&x\n"
        " &Csusanoo on&x / &Csusanoo off&x\n"
        f" Chakra: {ACTIVATION_CHAKRA} to activate, "
        f"{COMBAT_UPKEEP_CHAKRA}/combat round, "
        f"{IDLE_UPKEEP_CHAKRA}/idle upkeep."
    )


def command_set(session, args):
    """The SET verb currently owns the Susanoo submenu."""
    if not args or args[0].casefold() != "susanoo":
        session.send("Usage: set susanoo [color|style|weapon] [choice]")
        return
    player = session.player
    if not eligible(player):
        session.send("You need the Mangekyo Sharingan before customizing Susanoo.")
        return
    args = [word.casefold() for word in args[1:]]
    if not args or args[0] in ("menu", "status", "show"):
        session.send(menu(player))
        return
    if len(args) == 1 and args[0] in ("colors", "styles", "weapons"):
        options = {"colors": COLORS, "styles": STYLES, "weapons": WEAPONS}[args[0]]
        session.send(f"Susanoo {args[0]}: " + ", ".join(options))
        return
    field = args[0]
    maps = {"color": (COLORS, "susanoo_color"),
            "style": (STYLES, "susanoo_style"),
            "weapon": (WEAPONS, "susanoo_weapon")}
    if field not in maps or len(args) != 2 or args[1] not in maps[field][0]:
        if field in maps:
            session.send(f"Valid Susanoo {field}s: " + ", ".join(maps[field][0]))
        else:
            session.send("Usage: set susanoo <color|style|weapon> <choice>")
        return
    if field in ("style", "weapon") and (
            getattr(session, "combat_target", None) is not None
            or getattr(session, "pvp_target", None) is not None):
        session.send("Change your Susanoo's combat style and weapon outside battle.")
        return
    setattr(player, maps[field][1], args[1])
    storage.save_player(player)
    session.send(f"&GYour Susanoo's {field} is now {args[1].capitalize()}.&x")
    session.send(menu(player))


def command(session, args):
    """SUSANOO ON/OFF; without arguments displays the customization menu."""
    player = session.player
    if not eligible(player):
        session.send("Only someone with the Mangekyo Sharingan can summon Susanoo.")
        return
    if not args or args[0].casefold() in ("status", "menu"):
        session.send(menu(player))
        return
    arg = args[0].casefold()
    if len(args) != 1 or arg not in ("on", "off"):
        session.send("Usage: susanoo [on|off|status]. Customize using SET SUSANOO.")
        return
    if arg == "off":
        if not active(player):
            session.send("Your Susanoo is already dormant.")
            return
        player.susanoo_active = False
        storage.save_player(player)
        session.send(f"&DYour {_display(player)} Susanoo disperses into chakra.&x")
        return
    if active(player):
        session.send("Your Susanoo is already active.")
        return
    if player.chakra < ACTIVATION_CHAKRA:
        session.send(f"You need {ACTIVATION_CHAKRA} chakra to summon Susanoo.")
        return
    if getattr(player, "reaper_seal_id", None) or getattr(player, "izanami_trapped", False):
        session.send("You cannot summon Susanoo while sealed or trapped.")
        return
    player.chakra -= ACTIVATION_CHAKRA
    player.susanoo_active = True
    storage.save_player(player)
    session.send(
        f"{COLORS[color(player)]}A {color(player)} Susanoo rises around you, "
        f"bearing a {weapon(player)} in {style(player)} stance!&x")
    import room_actions
    room_actions.emit(
        session, f"{player.name} summons a towering {color(player)} Susanoo "
                 f"with a spectral {weapon(player)}!")


def damage_bonus_percent(player) -> int:
    if not active(player):
        return 0
    return STYLES[style(player)][0] + WEAPONS[weapon(player)][0]


def accuracy_bonus(player) -> int:
    return WEAPONS[weapon(player)][1] if active(player) else 0


def damage_reduction_percent(player) -> int:
    if not active(player):
        return 0
    # Defensive style + shield remains below 40% reduction.
    return STYLES[style(player)][1] + WEAPONS[weapon(player)][2]


def outgoing_damage(player, amount: int) -> int:
    """Add the selected spectral weapon and stance to ordinary melee hits."""
    if amount <= 0 or not active(player):
        return amount
    return max(1, amount * (100 + damage_bonus_percent(player)) // 100)


def incoming_damage(player, amount: int) -> int:
    """Reduce NPC/PvP melee and NPC jutsu damage while chakra holds."""
    if amount <= 0 or not active(player):
        return amount
    return max(1, amount * (100 - damage_reduction_percent(player)) // 100)


def _upkeep(session, cost: int) -> bool:
    """One charge per round/tick, with automatic shutdown on insufficient chakra."""
    player = session.player
    if not active(player):
        if getattr(player, "susanoo_active", False) and not eligible(player):
            player.susanoo_active = False
            storage.save_player(player)
        return False
    if player.chakra < cost:
        player.susanoo_active = False
        storage.save_player(player)
        session.send("&RYour chakra fails and Susanoo shatters around you!&x")
        return True
    player.chakra -= cost
    return False


def combat_upkeep(session) -> bool:
    """Call exactly once for each player during a server combat round."""
    return _upkeep(session, COMBAT_UPKEEP_CHAKRA)


def idle_upkeep(session) -> bool:
    """Call only in the server's regular 10-second idle-upkeep cycle."""
    return _upkeep(session, IDLE_UPKEEP_CHAKRA)
