"""Naruto-themed connection and progression messages.

The broadcast helper deliberately looks up the ACTIVE_SESSIONS list at call
time, so leveling.py and jobs.py can report progress without circular imports.
Only real, online characters trigger a server-wide announcement.
"""


def arrival(name: str) -> str:
    return (
        "&[208][SHINOBI ARRIVAL]&x "
        f"&[223]{name}&x steps from the shadows and enters the shinobi world."
    )


def departure(name: str) -> str:
    return (
        "&[244][SHINOBI DEPARTURE]&x "
        f"&[223]{name}&x vanishes into the shadows. Until our paths cross again."
    )


def welcome(player, village_name: str) -> str:
    return (
        "\n&[208]+----------------------------------------------+&x\n"
        f"&[223]  WELCOME TO YOUR NINJA WAY, {player.name.upper()}&x\n"
        f"&[244]  {village_name}  |  {player.village_rank.title()}&x\n"
        "&[208]+----------------------------------------------+&x\n"
        "&[223]Your journey continues. Forge your own nindo.&x"
    )


def farewell(name: str) -> str:
    return (
        "\n&[208]+----------------------------------------------+&x\n"
        f"&[223]  UNTIL NEXT TIME, {name.upper()}&x\n"
        "&[244]  Your progress is saved. Your legend awaits.&x\n"
        "&[208]+----------------------------------------------+&x"
    )


def announce_level(player, level: int, job: str = None) -> None:
    """Tell other online players about each *earned* combat or job level.

    The earning player already receives the detailed level-up message, so
    exclude their session to avoid duplicate notices. Offline migrations,
    admin stat edits, and leveling tests without a live player do not generate
    fake public announcements.
    """
    from session import ACTIVE_SESSIONS, State

    online = [s for s in tuple(ACTIVE_SESSIONS)
              if s.state == State.PLAYING and s.player is not None]
    if not any(s.player is player for s in online):
        return

    if job:
        notice = (
            "&[208][JOB LEVEL UP]&x "
            f"&[223]{player.name}&x has reached &[51]{job.title()} Level {level}&x!"
        )
    else:
        notice = (
            "&[208][SHINOBI LEVEL UP]&x "
            f"&[223]{player.name}&x has reached &[51]Ninja Level {level}&x!"
        )

    for other in online:
        if other.player is not player:
            other.send(notice)
