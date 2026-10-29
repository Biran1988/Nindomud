"""Administrator bulk proficiency editor for existing learned skills.

All reads include offline character saves and live or link-dead characters.
This command never awards a skill the character has not already learned.
"""
import data_jutsu
import skill_training
import storage


USAGE = (
    "Usage: setallprac who <skill or jutsu> | "
    "setallprac <skill or jutsu> <1-100>"
)


def _characters():
    """Live state overrides disk snapshots, including protected link-dead players."""
    import session as session_module
    players = {p.name.casefold(): (p, False) for p in storage.all_players()}
    for s in session_module.ACTIVE_SESSIONS:
        if s.player and getattr(s.state, "name", "") not in ("CLOSED",):
            players[s.player.name.casefold()] = (s.player, True)
    return [players[key] for key in sorted(players)]


def _resolve_name(query, characters):
    query = query.strip().casefold()
    names = {}
    for key, spec in data_jutsu.JUTSU.items():
        name = spec["display_name"]
        names[name.casefold()] = name
        names.setdefault(key.casefold(), name)
    for player, _ in characters:
        for name in (*player.learned_skills, *player.skill_proficiencies.keys()):
            names.setdefault(name.casefold(), name)

    if query in names:
        return names[query], ()
    # Unique prefixes are useful for lengthy jutsu names, but a partial
    # match must not silently select one of multiple real techniques.
    found = sorted({name for key, name in names.items() if key.startswith(query)})
    if len(found) == 1:
        return found[0], ()
    return None, tuple(found)


def _learned(player, skill_name):
    return any(s.casefold() == skill_name.casefold()
               for s in (*player.learned_skills, *player.skill_proficiencies.keys()))


def _actual_key(player, skill_name):
    for name in (*player.skill_proficiencies.keys(), *player.learned_skills):
        if name.casefold() == skill_name.casefold():
            return name
    return skill_name


def command(session, args):
    if not session.account or session.account.staff_level not in ("administrator", "implementor"):
        session.send("Only Administrators and Implementors may change global skill proficiency.")
        return

    if not args:
        session.send(USAGE)
        return

    listing = args[0].casefold() == "who"
    if listing:
        query = " ".join(args[1:]).strip()
    else:
        if len(args) < 2:
            session.send(USAGE)
            return
        query = " ".join(args[:-1]).strip()
        try:
            percentage = int(args[-1])
        except ValueError:
            session.send(USAGE)
            return
        if not 1 <= percentage <= 100:
            session.send("Proficiency must be a whole percentage from 1 to 100.")
            return

    if not query:
        session.send(USAGE)
        return

    try:
        characters = _characters()
    except (OSError, ValueError) as error:
        session.send(f"Could not read player saves: {error}")
        return

    skill_name, ambiguous = _resolve_name(query, characters)
    if skill_name is None:
        if ambiguous:
            session.send("Ambiguous skill or jutsu. Be more specific: "
                         + ", ".join(ambiguous[:12]))
        else:
            session.send(f"Unknown skill or jutsu: {query}.")
        return

    applicable = [(player, live) for player, live in characters
                  if _learned(player, skill_name)]

    if listing:
        lines = [f"&W{skill_name}: existing character proficiencies&x"]
        for player, live in applicable:
            key = _actual_key(player, skill_name)
            amount = player.skill_proficiencies.get(key, 0)
            tag = "online" if live else "offline"
            lines.append(f"  {player.name:<20} {amount:>3}% ({tag})")
        lines.append(f"{len(applicable)} character(s) know this skill.")
        session.send_paginated("\n".join(lines))
        return

    updated = 0
    errors = []
    for player, live in applicable:
        key = _actual_key(player, skill_name)
        previous = player.skill_proficiencies.get(key)
        practiced_before = list(player.practiced_skills)
        player.skill_proficiencies[key] = percentage
        # This is an administrator-granted teacher-equivalent proficiency,
        # not a new jutsu unlock. Preserve the ordinary practiced-once
        # gate by marking skills already learned, never adding new skills.
        if any(name.casefold() == key.casefold() for name in player.learned_skills):
            skill_training.mark_practiced(player, key)
        try:
            storage.save_player(player)
        except (OSError, ValueError) as error:
            if previous is None:
                player.skill_proficiencies.pop(key, None)
            else:
                player.skill_proficiencies[key] = previous
            player.practiced_skills = practiced_before
            errors.append(f"{player.name}: {error}")
            continue
        updated += 1

    session.send(
        f"&YSet {skill_name} to {percentage}% for {updated} existing "
        f"character(s); {len(characters) - len(applicable)} without that "
        f"skill skipped, {len(errors)} save failure(s).&x"
    )
    for error in errors[:5]:
        session.send(f"&R{error}&x")
