"""High-level Bukijutsu sword schools: mutually exclusive, trainable combat styles.

A style must be learned and selected, and a sword must actually be wielded.
Every successful ordinary sword strike pays its stamina cost and can advance
the selected school's proficiency through the normal usage progression.
"""
import data_weapons

# Keys are saved in player.sword_style; order is the progression order.
STYLES = {
    "Iaijutsu": {
        "level": 85, "accuracy": 8, "damage": 8, "stamina": 2,
        "description": "A fast draw-and-cut school emphasizing an accurate opening.",
    },
    "Katori Shinto Ryu": {
        "level": 110, "accuracy": 10, "damage": 12, "stamina": 3,
        "description": "Disciplined all-round swordsmanship with balanced strikes.",
    },
    "Niten Ichi Ryu": {
        "level": 140, "accuracy": 7, "damage": 18, "stamina": 4,
        "dual": True,
        "description": "Two-sword fighting; requires a sword in each hand.",
    },
    "Yagyu Shinkage Ryu": {
        "level": 175, "accuracy": 16, "damage": 16, "stamina": 4,
        "description": "Measured, precise counter-cutting and tight blade control.",
    },
    "Ono-ha Itto Ryu": {
        "level": 215, "accuracy": 8, "damage": 28, "stamina": 6,
        "description": "Decisive centerline cuts with powerful single-strike force.",
    },
    "Jigen Ryu": {
        "level": 250, "accuracy": -8, "damage": 45, "stamina": 10,
        "description": "The most aggressive school: overwhelming cuts, high cost, less precision.",
    },
}


def _is_sword(item) -> bool:
    return bool(item and data_weapons.weapon_type_for_item(item) == "sword")


def selected(player):
    """Return (name, definition) only when the style can affect combat."""
    name = getattr(player, "sword_style", "")
    style = STYLES.get(name)
    if (style is None or getattr(player, "primary_class", None) != "bukijutsu"
            or getattr(player, "level", 0) < style["level"]
            or name not in getattr(player, "learned_skills", ())):
        return None
    gear = getattr(player, "equipment", {}) or {}
    if not _is_sword(gear.get("wielded")):
        return None
    if style.get("dual") and not _is_sword(gear.get("offhand")):
        return None
    if getattr(player, "stamina", 0) < style["stamina"]:
        return None
    return name, style


def _power(player, style_name):
    """Partial potency from the outset; full potency at 100% mastery."""
    pct = max(0, min(100, player.skill_proficiencies.get(style_name, 0)))
    return 0.25 + 0.75 * (pct / 100.0)


def accuracy_bonus(player):
    active = selected(player)
    if not active:
        return 0
    name, data = active
    import signature_moves
    return round(data["accuracy"] * _power(player, name) *
                 signature_moves.multiplier(player, name))


def damage_bonus(player, damage):
    active = selected(player)
    if not active:
        return damage
    name, data = active
    import signature_moves
    boost = data["damage"] * _power(player, name) * signature_moves.multiplier(player, name)
    return max(1, int(damage * (1 + boost / 100)))


def successful_strike(player, session):
    """Spend stamina and train only for a landed player sword swing."""
    active = selected(player)
    if not active:
        return
    name, data = active
    player.stamina -= data["stamina"]
    import combat
    combat.grow_skill_from_usage(player, name, session=session)


def command(session, args):
    player = session.player
    words = " ".join(args).strip()
    if not words or words.casefold() in ("list", "help"):
        session.send("&YSword Schools&x &D(Bukijutsu, one active school at a time)&x")
        for name, data in STYLES.items():
            status = ("&Glearned&x" if name in player.learned_skills else
                      "&Dlocked&x")
            active = " &Y[ACTIVE]&x" if player.sword_style == name else ""
            session.send(f"  Lv {data['level']:>3}  {name}  ({status}){active}")
            session.send(f"       {data['description']}")
        session.send("Syntax: swordstyle <name> | swordstyle off")
        return
    if words.casefold() in ("off", "none", "clear", "normal"):
        player.sword_style = ""
        session.send("&YYou return to ordinary swordsmanship.&x")
        import storage
        storage.save_player(player)
        return
    matches = [name for name in STYLES if name.casefold().startswith(words.casefold())]
    if len(matches) != 1:
        session.send("Unknown or ambiguous school. Use SWORDSTYLE LIST.")
        return
    name = matches[0]
    data = STYLES[name]
    if player.primary_class != "bukijutsu":
        session.send("Only Bukijutsu shinobi can adopt these sword schools.")
        return
    if player.level < data["level"] or name not in player.learned_skills:
        session.send(f"{name} requires Bukijutsu level {data['level']}.")
        return
    if not _is_sword(player.equipment.get("wielded")):
        session.send("You must wield a sword to use a sword school.")
        return
    if data.get("dual") and not _is_sword(player.equipment.get("offhand")):
        session.send("Niten Ichi Ryu requires a sword in both hands.")
        return
    player.sword_style = name
    session.send(f"&YYou enter {name}.&x {data['description']}")
    import storage
    storage.save_player(player)
