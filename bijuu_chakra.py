"""Naruto-style Jinchuriki sealed chakra and mutually earned beast cooperation.

This module does not touch world rooms, player save directories or beast
ownership. The save fields live on Player and are optional for old saves.
"""
import random
import time

import data_tailed_beasts

VOICES = {
    "shukaku": "Shukaku jeers: Show me that your will is stronger than sand!",
    "matatabi": "Matatabi murmurs: Power needs composure, not fear.",
    "isobu": "Isobu says: Even the deepest current can grow calm.",
    "son_goku": "Son Goku growls: Earn respect. A chain cannot command it.",
    "kokuo": "Kokuo says: Patience and resolve will carry us forward.",
    "saiken": "Saiken bubbles: Perhaps an unlikely friendship will endure.",
    "chomei": "Chomei cheers: Together we can take flight!",
    "gyuki": "Gyuki rumbles: A true partnership is not a demand.",
    "kurama": "Kurama asks: Are you searching for a weapon or an ally?",
}
AURAS = {
    "shukaku": "Golden sand sweeps around the host.",
    "matatabi": "Spectral blue flames surround the host.",
    "isobu": "Coral armor ripples through a tidal chakra cloak.",
    "son_goku": "Molten red lava chakra surges around the host.",
    "kokuo": "White steam bursts from the host's chakra mantle.",
    "saiken": "Acidic green bubbles coil in the air.",
    "chomei": "Luminous emerald wings unfold from the chakra cloak.",
    "gyuki": "Purple-black ink tendrils spread around the host.",
    "kurama": "Golden fox-shaped chakra erupts around the host.",
}
FORMS = ("Sealed", "Unstable Leakage", "Version 1 Cloak",
         "Tailed Chakra Cloak", "Cooperative Chakra Mode",
         "Full Bijuu Avatar")


def _beast(player):
    return data_tailed_beasts.TAILED_BEASTS_BY_KEY.get(player.jinchuriki_beast_key)


def capacity(player):
    b = _beast(player)
    if not b:
        return 0
    return min(25000, max(250, player.maximum_chakra // 2 +
                           b["tails"] * 180 + player.level * 5))


def _status(session):
    p = session.player
    b = _beast(p)
    session.send(
        f"&WJinchuriki: {b['display_name']} ({b['tails']} tails)&x\n"
        f"&BSealed Chakra: {p.bijuu_chakra_reserve}/{capacity(p)}&x  "
        f"Bond: {p.bijuu_bond}%  Control: {p.bijuu_control}%  "
        f"Mastery: {p.jinchuriki_mastery}%\n"
        f"Form: {FORMS[max(0, min(5, p.bijuu_form))]}"
        + (f" ({p.bijuu_tails} tails)" if p.bijuu_form == 3 else "") +
        "\nBIJUU MIND, COMMUNE, TRAIN, DRAW <amount>, HEAL <hp>, LEAK, CLOAK, "
        "TAILS <n>, LINK, AVATAR, RELEASE, SHARE <player> <amount>."
    )


def _activate(session, form, tails=0):
    p = session.player
    required = {
        1: (1, 0, 0, 0),
        2: (25, 20, 0, 10),
        3: (35 + tails * 8, min(95, 20 + tails * 7), 0, 15 + tails * 5),
        4: (100, 70, 70, 50),
        5: (150, 90, 90, 80),
    }
    level, control, bond, mastery = required[form]
    if (p.level < level or p.bijuu_control < control or
            p.bijuu_bond < bond or p.jinchuriki_mastery < mastery):
        session.send(f"Requires level {level}, control {control}%, "
                     f"bond {bond}%, mastery {mastery}%.")
        return
    cost = 15 + form * 12
    if p.bijuu_chakra_reserve < cost:
        session.send("Your separate sealed chakra reserve is too low.")
        return
    if (form == 3 and tails >= 3 and p.bijuu_bond < 60
            and random.randint(1, 100) <= min(35, 5 + tails * 3 - p.bijuu_bond // 5)):
        p.bijuu_chakra_reserve -= cost // 2
        p.stamina = max(0, p.stamina - max(1, p.maximum_stamina // 8))
        session.send("&RThe beast rejects your forced transformation! "
                     "Wild chakra tears through your stamina.&x")
        return
    p.bijuu_chakra_reserve -= cost
    p.bijuu_form = form
    p.bijuu_tails = tails if form == 3 else 0
    b = _beast(p)
    session.send(f"&R{b['display_name']} awakens: {FORMS[form]}!&x")
    session.broadcast_room(f"&Y{AURAS[b['key']]}&x", exclude_self=True)


def command(session, args):
    p = session.player
    b = _beast(p)
    if not b:
        session.send("You have no Tailed Beast sealed inside you.")
        return
    action = args[0].lower() if args else "status"
    if action == "status":
        _status(session)
        return
    if action in {"release", "off"}:
        p.bijuu_form = p.bijuu_tails = 0
        session.send("You draw your tailed-beast chakra back inside the seal.")
        return
    if p.rampage_until:
        session.send("You cannot negotiate with the beast during a rampage.")
        return
    if action in {"mind", "mindscape", "commune"}:
        if session.combat_target or session.pvp_target:
            session.send("You must be out of combat to face the inner seal.")
            return
        session.send(f"&CYou confront {b['display_name']} in your inner mindscape.&x")
        session.send(f"&Y{VOICES[b['key']]}&x")
        session.send("&GThe beast acknowledges your partnership.&x" if p.bijuu_bond >= 70
                     else "&YThe beast remains wary of you.&x")
        if action != "commune":
            return
        if time.time() < p.bijuu_last_commune + 180:
            session.send("The inner seal needs time before your next conversation.")
            return
        p.bijuu_last_commune = time.time()
        p.bijuu_bond = min(100, p.bijuu_bond + 2)
        p.jinchuriki_mastery = min(100, p.jinchuriki_mastery + 1)
        session.send(f"Your bond deepens to {p.bijuu_bond}%.")
        return
    if action == "train":
        if session.combat_target or session.pvp_target:
            session.send("Finish fighting before training your beast control.")
            return
        if time.time() < p.bijuu_last_train + 120 or p.bijuu_chakra_reserve < 40:
            session.send("Training requires 40 sealed chakra and a 2-minute cooldown.")
            return
        p.bijuu_last_train = time.time()
        p.bijuu_chakra_reserve -= 40
        p.bijuu_control = min(100, p.bijuu_control + 2)
        p.jinchuriki_mastery = min(100, p.jinchuriki_mastery + 1)
        session.send(f"Control: {p.bijuu_control}%. Mastery: {p.jinchuriki_mastery}%.")
        return
    if action == "draw":
        try:
            amount = int(args[1])
        except (IndexError, ValueError):
            session.send("Usage: bijuu draw <1-5000>")
            return
        if not 1 <= amount <= 5000:
            session.send("Draw an amount between 1 and 5000.")
            return
        amount = min(amount, p.bijuu_chakra_reserve, p.maximum_chakra - p.chakra)
        if amount <= 0:
            session.send("Your sealed reserve is empty or your normal Chakra is full.")
            return
        p.bijuu_chakra_reserve -= amount
        p.chakra += amount
        if amount >= 50:
            p.jinchuriki_mastery = min(100, p.jinchuriki_mastery + (2 if amount >= 200 else 1))
        if p.bijuu_control < 20 and amount >= p.maximum_chakra // 3:
            p.stamina = max(0, p.stamina - max(1, amount // 10))
            session.send("&RThe borrowed chakra strains your body!&x")
        session.send(f"&BYou draw {amount} chakra from {b['display_name']}'s reserve.&x")
        return
    if action == "heal":
        if p.bijuu_control < 35 or p.jinchuriki_mastery < 15:
            session.send("Healing with tailed-beast chakra requires 35% control and 15% mastery.")
            return
        if p.health <= 0:
            session.send("You cannot heal while defeated.")
            return
        now = time.time()
        ready_at = p.cooldowns.get("bijuu_heal", 0)
        if now < ready_at:
            session.send(f"Bijuu healing is recovering for {int(ready_at - now) + 1} seconds.")
            return
        try:
            requested = int(args[1])
        except (IndexError, ValueError):
            session.send("Usage: bijuu heal <hit points> (2 sealed chakra per HP; 30s cooldown).")
            return
        amount = min(max(0, requested), max(1, p.maximum_health // 4),
                     p.maximum_health - p.health, p.bijuu_chakra_reserve // 2)
        if amount <= 0:
            session.send("You need missing health and at least 2 sealed chakra to heal.")
            return
        p.bijuu_chakra_reserve -= amount * 2
        p.health += amount
        p.cooldowns["bijuu_heal"] = now + 30
        session.send(f"&GYour tailed beast lends restorative chakra: +{amount} health for {amount * 2} sealed chakra.&x")
        return
    if action in {"leak", "cloak", "link", "cooperate", "avatar"}:
        _activate(session, {"leak": 1, "cloak": 2, "link": 4,
                            "cooperate": 4, "avatar": 5}[action])
        return
    if action == "tails":
        try:
            tails = int(args[1])
        except (IndexError, ValueError):
            tails = 0
        if not 1 <= tails <= b["tails"]:
            session.send(f"Use BIJUU TAILS <1-{b['tails']}>.")
            return
        _activate(session, 3, tails)
        return
    if action == "share":
        if p.bijuu_form < 4:
            session.send("Only cooperative Bijuu Mode can share chakra.")
            return
        try:
            target_name, amount = args[1].lower(), int(args[2])
        except (IndexError, ValueError):
            session.send("Usage: bijuu share <grouped player> <1-5000>")
            return
        if not 1 <= amount <= 5000:
            session.send("The share amount must be 1 to 5000.")
            return
        group = getattr(session, "group", None)
        recipients = getattr(group, "members", []) if group else []
        target_session = next((member for member in recipients
                               if member is not session and getattr(member, "player", None)
                               and member.player.name.lower() == target_name
                               and member.player.room_vnum == p.room_vnum), None)
        if not target_session:
            session.send("The recipient must be a grouped player in your room.")
            return
        target = target_session.player
        amount = min(amount, p.bijuu_chakra_reserve,
                     target.maximum_chakra - target.chakra)
        if amount <= 0:
            session.send("No sealed chakra is available for this transfer.")
            return
        p.bijuu_chakra_reserve -= amount
        target.chakra += amount
        session.send(f"You share {amount} Bijuu Chakra with {target.name}.")
        target_session.send(f"&Y{p.name} shares {amount} tailed-beast chakra with you!&x")
        return
    if action == "bomb":
        session.send("Use PERFORM TAILED BEAST BOMB against a hostile target.")
        return
    _status(session)


def tick(session):
    """Independent sealed bank regeneration and paid cloak upkeep."""
    p = session.player
    if not _beast(p):
        return
    cap = capacity(p)
    p.bijuu_chakra_reserve = min(cap, max(0, p.bijuu_chakra_reserve) +
                                max(2, cap // 350 + p.bijuu_bond // 15))
    if not p.bijuu_form:
        return
    cost = 3 + p.bijuu_form * 6 + (p.bijuu_tails if p.bijuu_form == 3 else 0)
    if p.bijuu_chakra_reserve < cost or p.health <= 0:
        p.bijuu_form = p.bijuu_tails = 0
        session.send("&RYour chakra cloak collapses as the sealed reserve runs dry!&x")
        return
    p.bijuu_chakra_reserve -= cost
    if p.bijuu_form >= 2:
        p.chakra = min(p.maximum_chakra, p.chakra + 2 + p.bijuu_form * 2)
    if p.bijuu_form == 1 and p.bijuu_control < 35:
        p.stamina = max(0, p.stamina - max(1, p.maximum_stamina // 100))
    if random.randint(1, 100) <= 3:
        p.jinchuriki_mastery = min(100, p.jinchuriki_mastery + 1)
