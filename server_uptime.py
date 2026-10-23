"""Process-local server uptime, reset only when the TCP server starts.

Use monotonic time so manual changes to the system clock cannot alter
the elapsed uptime. Never load/store this value in player/world saves.
"""
import time

_started_at = None


def start() -> None:
    """Mark the beginning of this running server instance."""
    global _started_at
    _started_at = time.monotonic()


def elapsed_seconds() -> int:
    """Return completed running seconds, or zero before server startup."""
    if _started_at is None:
        return 0
    return max(0, int(time.monotonic() - _started_at))


def format_uptime() -> str:
    """Human-readable, fixed-width days/hours/minutes/seconds."""
    total = elapsed_seconds()
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
