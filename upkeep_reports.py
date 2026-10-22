"""Six-minute summaries and slow proficiency growth for maintained jutsu."""

import random
import time

SUMMARY_INTERVAL_SECONDS = 360
MAINTENANCE_GROWTH_INTERVAL_SECONDS = 10


def _costs(chakra, stamina):
    return f"{chakra} Chakra" + (f", {stamina} Stamina" if stamina else "")


def record(player, source: str, chakra: int, stamina: int = 0) -> list:
    """The caller has already charged the resources; only report them here."""
    now = time.monotonic()
    if not getattr(player, "_upkeep_totals", None):
        player._upkeep_totals = {}
        player._upkeep_since = now
    totals = player._upkeep_totals.setdefault(source, [0, 0])
    totals[0] += chakra
    totals[1] += stamina
    return due(player, now)


def due(player, now=None) -> list:
    """Report on schedule even if the last maintained ability has ended."""
    if not getattr(player, "_upkeep_totals", None):
        return []
    if (time.monotonic() if now is None else now) - player._upkeep_since < SUMMARY_INTERVAL_SECONDS:
        return []
    return flush(player)


def flush(player, source=None) -> list:
    """Flush the whole period, or a fading ability's pending total."""
    totals = getattr(player, "_upkeep_totals", {})
    if not totals:
        return []
    if source is not None:
        amounts = totals.pop(source, None)
        if not totals:
            player._upkeep_totals = {}
            player.__dict__.pop("_upkeep_since", None)
        return [f"&C{source} upkeep total: {_costs(*amounts)}.&x"] if amounts else []
    details = "; ".join(f"{name} {_costs(*amounts)}" for name, amounts in totals.items())
    chakra = sum(amounts[0] for amounts in totals.values())
    stamina = sum(amounts[1] for amounts in totals.values())
    player._upkeep_totals = {}
    player.__dict__.pop("_upkeep_since", None)
    return [f"&CUpkeep total: {details} (combined {_costs(chakra, stamina)}).&x"]


def maintain_skill(player, skill_name: str) -> None:
    """One chance at +1 proficiency per ten seconds of paid maintenance."""
    if skill_name not in player.learned_skills or getattr(player, "_immortal_skill_mastery", False):
        return
    import skill_training
    if skill_training.needs_first_practice(player, skill_name):
        return
    current = player.skill_proficiencies.get(skill_name, 0)
    if current >= 100:
        return
    now = time.monotonic()
    timers = getattr(player, "_maintenance_growth_at", None)
    if timers is None:
        player._maintenance_growth_at = {}
        timers = player._maintenance_growth_at
    previous = timers.get(skill_name)
    if previous is None or now - previous < MAINTENANCE_GROWTH_INTERVAL_SECONDS:
        if previous is None:
            timers[skill_name] = now
        return
    timers[skill_name] = now
    if random.randint(1, 100) <= 100 - current:
        player.skill_proficiencies[skill_name] = current + 1


def stop_maintaining(player, skill_name: str) -> None:
    """Require a fresh paid interval after a maintained jutsu ends."""
    getattr(player, "_maintenance_growth_at", {}).pop(skill_name, None)
