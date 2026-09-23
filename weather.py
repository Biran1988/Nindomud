"""
Weather and day/night cycle (Section 73). A single, world-wide state
(not a per-room/per-biome simulation) -- classic MUD weather. Changes
periodically via a real-time tick from server.py's main pulse loop,
the same "elapsed-time counter, advance on threshold" pattern autosave
and mob respawn already use (see server.py's own pulse loop).

Mechanical effects, not just flavor text:
- Rain/Storm: better luck at every gathering job (Fishing/Mining/
  Lumberjack/Farming/Cooking) -- lower fail chance. Rain nourishes
  crops and fish bite more; the same modifier covers mining/chopping/
  cooking too, rather than carving out an exception, since none of
  them have a clear "weather should make this WORSE" reason either.
- Snow: the opposite -- harsher conditions, higher fail chance across
  the same gathering jobs.
- Storm/Fog: reduced combat accuracy for EVERYONE, player and mob
  alike (poor visibility hurts both sides equally, not just the player).
- Clear: baseline, no modifier either way.
- Night: a small Dodge Chance boost for players (harder to see and
  land a hit on someone in the dark); day is baseline.

Weather and time-of-day tick independently, on their own schedules --
weather changes randomly (could repeat), time-of-day alternates on a
strict schedule (a real place doesn't randomly skip nightfall).
"""

import random

WEATHER_STATES = ["clear", "rain", "storm", "snow", "fog"]
TIME_OF_DAY_STATES = ["day", "night"]

WEATHER_DESCRIPTIONS = {
    "clear": "The sky is clear.",
    "rain": "A steady rain is falling.",
    "storm": "A fierce storm rages, wind and rain lashing everything.",
    "snow": "Snow drifts down silently.",
    "fog": "A thick fog blankets everything, visibility low.",
}

CURRENT_WEATHER = "clear"
CURRENT_TIME_OF_DAY = "day"

WEATHER_CHANGE_INTERVAL_SECONDS = 1800  # 30 minutes real-time
DAY_NIGHT_INTERVAL_SECONDS = 900  # 15 minutes real-time


def tick_weather() -> None:
    """Picks a new weather state -- could repeat the current one, same
    as real weather not being obligated to change just because time
    passed."""
    global CURRENT_WEATHER
    CURRENT_WEATHER = random.choice(WEATHER_STATES)


def tick_time_of_day() -> None:
    """Alternates day/night on its own fixed schedule -- not random."""
    global CURRENT_TIME_OF_DAY
    CURRENT_TIME_OF_DAY = "night" if CURRENT_TIME_OF_DAY == "day" else "day"


def gathering_fail_chance_modifier() -> int:
    """Added directly to a gathering job's base fail chance (fishing/
    mining/lumberjack/farming/cooking's own _fail_chance/_burn_chance
    functions) -- positive makes failure MORE likely, negative makes
    it LESS likely. The caller is responsible for still clamping to
    its own floor, same as it already does for job-level scaling."""
    if CURRENT_WEATHER in ("rain", "storm"):
        return -5
    if CURRENT_WEATHER == "snow":
        return 5
    return 0


def combat_accuracy_modifier() -> int:
    """Added to a to_hit_chance() result (then re-clamped by the
    caller) -- negative during poor-visibility weather, applies
    equally to player and mob attacks alike."""
    if CURRENT_WEATHER in ("storm", "fog"):
        return -5
    return 0


def night_dodge_bonus() -> int:
    """Added to a player's dodge_chance() bonus_percent argument --
    0 during the day, a small boost at night."""
    return 5 if CURRENT_TIME_OF_DAY == "night" else 0


def status_line() -> str:
    weather_desc = WEATHER_DESCRIPTIONS[CURRENT_WEATHER]
    time_desc = "It is daytime." if CURRENT_TIME_OF_DAY == "day" else "It is nighttime."
    return f"{weather_desc} {time_desc}"
