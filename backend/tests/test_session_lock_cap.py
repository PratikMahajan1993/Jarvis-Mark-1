"""Session lock map stays bounded and never drops a held lock."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.conversations import _SESSION_LOCK_CAP, _SESSION_LOCKS, brain_lock


def setup_function() -> None:
    _SESSION_LOCKS.clear()


def teardown_function() -> None:
    _SESSION_LOCKS.clear()


def test_over_cap_drops_unlocked_locks_and_keeps_the_new_one() -> None:
    for i in range(_SESSION_LOCK_CAP):
        with brain_lock(f"idle-{i}"):
            pass
    assert len(_SESSION_LOCKS) == _SESSION_LOCK_CAP

    with brain_lock("idle-new"):
        assert "idle-new" in _SESSION_LOCKS
        assert len(_SESSION_LOCKS) <= _SESSION_LOCK_CAP

    assert "idle-new" in _SESSION_LOCKS
    assert len(_SESSION_LOCKS) <= _SESSION_LOCK_CAP
    assert any(f"idle-{i}" not in _SESSION_LOCKS for i in range(_SESSION_LOCK_CAP))


def test_held_lock_survives_eviction() -> None:
    entered = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with brain_lock("pinned"):
            entered.set()
            assert release.wait(timeout=5.0)

    thread = threading.Thread(target=hold, name="pinned-hold")
    thread.start()
    assert entered.wait(timeout=2.0)

    try:
        for i in range(_SESSION_LOCK_CAP + 40):
            with brain_lock(f"extra-{i}"):
                pass
        assert "pinned" in _SESSION_LOCKS
        assert _SESSION_LOCKS["pinned"].locked()
        assert len(_SESSION_LOCKS) <= _SESSION_LOCK_CAP
    finally:
        release.set()
        thread.join(timeout=2.0)

    assert not thread.is_alive()


def test_over_cap_does_not_delete_locks_that_are_acquired() -> None:
    held: list[threading.Lock] = []
    try:
        for i in range(_SESSION_LOCK_CAP + 1):
            lock = threading.Lock()
            lock.acquire()
            _SESSION_LOCKS[f"held-{i}"] = lock
            held.append(lock)
        with brain_lock("extra"):
            for i in range(_SESSION_LOCK_CAP + 1):
                assert f"held-{i}" in _SESSION_LOCKS
                assert _SESSION_LOCKS[f"held-{i}"].locked()
    finally:
        for lock in held:
            if lock.locked():
                lock.release()
