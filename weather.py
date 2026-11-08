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
import time

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
# Preserve the old 15-minute day / 15-minute night pacing, now divided
# into an actual 24-hour shinobi clock that survives server restarts.
SECONDS_PER_GAME_HOUR = 75
HOURS_PER_DAY = 24
SUNRISE_HOUR = 6
SUNSET_HOUR = 18


def game_hour(now=None) -> int:
    now = time.time() if now is None else now
    return int(now // SECONDS_PER_GAME_HOUR) % HOURS_PER_DAY


def time_of_day(now=None) -> str:
    return "day" if SUNRISE_HOUR <= game_hour(now) < SUNSET_HOUR else "night"


def formatted_time(now=None) -> str:
    hour = game_hour(now)
    return f"{hour % 12 or 12}:00 {'AM' if hour < 12 else 'PM'}"


def clock_status(now=None) -> str:
    return (f"&WShinobi time:&x &Y{formatted_time(now)}&x ({time_of_day(now)}). "
            "One complete shinobi day takes 30 real minutes. "
            "Sunrise 6 AM; sunset 6 PM.")


CURRENT_TIME_OF_DAY = time_of_day()

WEATHER_CHANGE_INTERVAL_SECONDS = 1800  # 30 minutes real-time
DAY_NIGHT_INTERVAL_SECONDS = 1  # sample the world clock once per pulse


def tick_weather() -> None:
    """Picks a new weather state -- could repeat the current one, same
    as real weather not being obligated to change just because time
    passed."""
    global CURRENT_WEATHER
    CURRENT_WEATHER = random.choice(WEATHER_STATES)


def tick_time_of_day() -> bool:
    """Update compatibility state and return True when sunrise/sunset occurs."""
    global CURRENT_TIME_OF_DAY
    old = CURRENT_TIME_OF_DAY
    CURRENT_TIME_OF_DAY = time_of_day()
    return old != CURRENT_TIME_OF_DAY


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
    return 4.5 if time_of_day() == "night" else 0


def status_line() -> str:
    weather_desc = WEATHER_DESCRIPTIONS[CURRENT_WEATHER]
    phase = "daytime" if time_of_day() == "day" else "nighttime"
    return f"{weather_desc} It is {phase} ({formatted_time()})."
