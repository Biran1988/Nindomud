"""Silent, crash-safe, background snapshots after in-game builder edits.

All world reads and snapshot construction happen on the asyncio game thread;
only disk I/O runs in a single worker thread. Multiple nearby edits coalesce
into a fresh snapshot, and changes during an active write trigger another.
Reboot and explicit saves wait for the worker before writing the final state.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

_executor = None
_future = None
_dirty = False
_scheduled = False
_retry_handle = None


def mark_dirty() -> None:
    """Called *after* a successful room/mobile/object edit, without messages."""
    global _dirty
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # The MUD always edits inside its asyncio loop. Offline builder
        # scripts/tests can call save_world() explicitly to persist.
        return
    _dirty = True
    if _future is None or _future.done():
        _schedule(loop)


def _schedule(loop, delay: float = 0.0) -> None:
    global _scheduled, _retry_handle
    if _scheduled:
        return
    _scheduled = True
    if delay:
        _retry_handle = loop.call_later(delay, _begin_save, loop)
    else:
        loop.call_soon(_begin_save, loop)


def _begin_save(loop) -> None:
    """Capture the latest game-thread state, then hand disk writes to worker."""
    global _dirty, _scheduled, _executor, _future, _retry_handle
    _scheduled = False
    _retry_handle = None
    if not _dirty or (_future is not None and not _future.done()):
        return
    _dirty = False
    try:
        import storage
        import world_persistence
        import spawn_points

        # Spawn points use a separate authoritative template ledger at boot.
        # Keep it in sync so it cannot replace edited shop/mob/item prototypes
        # with an older version after a restart.
        spawn_points.refresh_template_snapshots()
        snapshot = world_persistence.snapshot_world()
        snapshot["deleted_areas"] = storage.load_world_state().get("deleted_areas", [])
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="world-save")
        _future = _executor.submit(storage.save_world_state, snapshot)
        _future.add_done_callback(lambda f: _notify_completion(loop, f))
    except Exception:
        logging.exception("World autosave failed while preparing snapshot; will retry")
        _dirty = True
        _schedule(loop, 5.0)


def _notify_completion(loop, future) -> None:
    try:
        loop.call_soon_threadsafe(_complete_save, loop, future)
    except RuntimeError:
        # The loop may have stopped during external shutdown. Explicit reboot
        # synchronously flushes before restarting; ordinary process exit
        # cannot schedule more edits.
        pass


def _complete_save(loop, future) -> None:
    global _dirty
    try:
        future.result()
    except Exception:
        logging.exception("World autosave disk write failed; will retry")
        _dirty = True
        _schedule(loop, 5.0)
        return
    if _dirty:
        _schedule(loop)


def wait_for_pending() -> None:
    """Drain prior background writes before a synchronous import or reboot.

    Called on the game's event-loop thread; completion callbacks cannot run
    while it waits. Any already-scheduled snapshot is superseded by the
    caller's newer, synchronous world snapshot.
    """
    global _dirty, _future, _scheduled, _retry_handle
    if _future is not None:
        _future.result()  # Surface disk errors; never reboot on a failed write.
    _dirty = False
    if _retry_handle is not None:
        _retry_handle.cancel()
        _retry_handle = None
    _scheduled = False
