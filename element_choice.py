"""Protected, persistent level-25 choice of a second chakra nature."""

import content
import data_kekkei_genkai
import storage
import world

ELEMENTS = ("fire", "water", "wind", "earth", "lightning")
ALLOWED_COMMANDS = {"help", "say", "ooc", "village", "vchat", "vc", "quit"}


def pending(player) -> bool:
    return bool(player and player.level >= data_kekkei_genkai.ELEMENTAL_RELEASE_REVEAL_LEVEL
                and not player.chakra_nature_secondary_revealed)


def in_choice(player) -> bool:
    return (pending(player) and not getattr(player, "_immortal_skill_mastery", False)
            and player.element_choice_return_room_vnum is not None)


def prompt(session) -> None:
    player = session.player
    choices = ", ".join(e for e in ELEMENTS if e != player.chakra_nature)
    session.send(
        f"&CChoose your second chakra nature. Your first is {player.chakra_nature.capitalize()}.&x\n"
        f"Choices: {choices}. Type 'choose <element>' or the element name.\n"
        "Use 'help <element>' to see its possible Kekkei Genkai combinations. "
        "Only help and chat commands are available until you choose."
    )


def begin(session) -> bool:
    player = session.player
    if session.account and session.account.staff_level != "player":
        return False
    if not pending(player):
        return False
    kage_vnum = content._VILLAGE_ROOMS.get(player.village, {}).get("kage")
    room = world.WORLD.get(kage_vnum) if kage_vnum is not None else None
    if room is None:
        return False
    first_time = player.element_choice_return_room_vnum is None
    if first_time:
        player.element_choice_return_room_vnum = player.room_vnum
        if not player.chakra_nature:
            import biomes
            player.chakra_nature = biomes.roll_chakra_nature()
        player.chakra_nature_revealed = True
    # Clear every ongoing fight/cast before moving into the safe chamber.
    session.combat_target = None
    if session.pvp_target is not None:
        session.pvp_target.pvp_target = None
        session.pvp_target = None
    session.pending_cast = None
    moved = player.room_vnum != room.vnum
    player.room_vnum = room.vnum
    if first_time or moved:
        storage.save_player(player)
        session.send(f"&CYou are brought to {room.name} to choose your second chakra nature. You are protected here.&x")
        prompt(session)
    return True


def choose(session, answer: str) -> None:
    player = session.player
    if not pending(player):
        session.send("You have already chosen your second chakra nature.")
        return
    choice = answer.strip().lower()
    if choice not in ELEMENTS or choice == player.chakra_nature:
        session.send("Choose a different nature: " + ", ".join(
            e for e in ELEMENTS if e != player.chakra_nature) + ".")
        return
    player.chakra_nature_secondary = choice
    player.chakra_nature_secondary_revealed = True
    known_before = set(player.learned_skills)
    data_kekkei_genkai.sync_elemental_release(player)
    release = player.elemental_release_id
    return_vnum = player.element_choice_return_room_vnum
    player.element_choice_return_room_vnum = None
    if return_vnum is not None and world.WORLD.get(return_vnum) is not None:
        player.room_vnum = return_vnum
    storage.save_player(player)
    session.send(f"&YYour second chakra nature is {choice.capitalize()}.&x"
                 + (f" Your natures form {data_kekkei_genkai.ELEMENTAL_RELEASE_NAMES[release]}!" if release else ""))
    for skill in player.learned_skills:
        if skill not in known_before:
            session.send(f"&YYou have learned {skill}!&x")
    session.send("Your choice is complete. You may use all commands again.")


def handle_command(session, line: str) -> bool:
    """Return True when a pending choice consumes the input."""
    if session.account and session.account.staff_level != "player":
        return False
    if not pending(session.player):
        return False
    if not begin(session):
        session.send("Your village Kage chamber is unavailable; contact an administrator.")
        return False
    words = line.strip().split()
    if not words:
        prompt(session)
        return True
    verb = words[0].lower()
    if verb == "choose" or (verb in ELEMENTS and len(words) == 1):
        choose(session, " ".join(words[1:]) if verb == "choose" else verb)
        return True
    if verb in ALLOWED_COMMANDS:
        return False
    session.send("Choose your second nature first. Only help and chat commands are available.")
    prompt(session)
    return True
