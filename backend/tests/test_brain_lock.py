"""Per-session brain locks and global semaphore (capacity 3)."""

from __future__ import annotations

import threading
import time

import pytest

from app.config import settings
from app.conversations import BrainLockTimeout, brain_lock


def test_different_sessions_do_not_block_each_other() -> None:
    gate = threading.Event()
    acquired_b = threading.Event()

    def hold_a() -> None:
        with brain_lock("session-a"):
            gate.set()
            time.sleep(0.4)

    def acquire_b() -> None:
        assert gate.wait(timeout=2.0)
        start = time.monotonic()
        with brain_lock("session-b"):
            assert time.monotonic() - start < 0.35
            acquired_b.set()

    t_a = threading.Thread(target=hold_a, name="hold-a")
    t_b = threading.Thread(target=acquire_b, name="acquire-b")
    t_a.start()
    t_b.start()
    assert acquired_b.wait(timeout=2.0)
    t_a.join(timeout=2.0)
    t_b.join(timeout=2.0)


def test_same_session_second_acquire_blocks_until_release() -> None:
    first_entered = threading.Event()
    second_can_enter = threading.Event()
    second_started = threading.Event()

    def hold_first() -> None:
        with brain_lock("session-a"):
            first_entered.set()
            time.sleep(0.35)

    def second_turn() -> None:
        assert first_entered.wait(timeout=2.0)
        second_started.set()
        with brain_lock("session-a"):
            second_can_enter.set()

    t1 = threading.Thread(target=hold_first, name="first")
    t2 = threading.Thread(target=second_turn, name="second")
    t2.start()
    t1.start()
    assert second_started.wait(timeout=2.0)
    time.sleep(0.08)
    assert not second_can_enter.is_set()
    t1.join(timeout=2.0)
    assert second_can_enter.wait(timeout=2.0)
    t2.join(timeout=2.0)


def test_fourth_acquire_waits_while_three_slots_held() -> None:
    release_all = threading.Event()
    three_held = threading.Event()
    held_count = 0
    held_guard = threading.Lock()
    fourth_started = threading.Event()
    fourth_acquired = threading.Event()

    def hold(session: str) -> None:
        nonlocal held_count
        with brain_lock(session):
            with held_guard:
                held_count += 1
                if held_count == 3:
                    three_held.set()
            release_all.wait(timeout=10.0)

    holders = [
        threading.Thread(target=hold, args=(f"s{i}",), name=f"hold-{i}") for i in range(1, 4)
    ]
    for t in holders:
        t.start()
    assert three_held.wait(timeout=5.0)

    def fourth() -> None:
        fourth_started.set()
        with brain_lock("s4"):
            fourth_acquired.set()

    t4 = threading.Thread(target=fourth, name="fourth")
    t4.start()
    assert fourth_started.wait(timeout=2.0)
    time.sleep(0.15)
    assert not fourth_acquired.is_set()
    release_all.set()
    assert fourth_acquired.wait(timeout=2.0)
    for t in holders:
        t.join(timeout=2.0)
    t4.join(timeout=2.0)


def test_no_session_id_uses_default_and_serializes() -> None:
    first_in = threading.Event()
    second_in = threading.Event()
    second_started = threading.Event()

    def first() -> None:
        with brain_lock():
            first_in.set()
            time.sleep(0.25)

    def second() -> None:
        assert first_in.wait(timeout=2.0)
        second_started.set()
        with brain_lock():
            second_in.set()

    t1 = threading.Thread(target=first, name="default-first")
    t2 = threading.Thread(target=second, name="default-second")
    t2.start()
    t1.start()
    assert second_started.wait(timeout=2.0)
    time.sleep(0.05)
    assert not second_in.is_set()
    t1.join(timeout=2.0)
    assert second_in.wait(timeout=2.0)
    t2.join(timeout=2.0)


def test_semaphore_timeout_raises_and_does_not_keep_a_permit(monkeypatch) -> None:
    # hermes_timeout_sec + 5 == 0.2s so the wait stays inside this test.
    monkeypatch.setattr(settings, "hermes_timeout_sec", -4.8)
    release_all = threading.Event()
    three_held = threading.Event()
    held_count = 0
    held_guard = threading.Lock()

    def hold(session: str) -> None:
        nonlocal held_count
        with brain_lock(session):
            with held_guard:
                held_count += 1
                if held_count == 3:
                    three_held.set()
            release_all.wait(timeout=5.0)

    holders = [
        threading.Thread(target=hold, args=(f"cap-{i}",), name=f"cap-{i}") for i in range(3)
    ]
    for thread in holders:
        thread.start()
    assert three_held.wait(timeout=2.0)

    with pytest.raises(BrainLockTimeout):
        with brain_lock("cap-wait"):
            raise AssertionError("permit acquired after timeout")

    # The timed-out waiter must not have released a permit it never took.
    with pytest.raises(BrainLockTimeout):
        with brain_lock("cap-wait-2"):
            raise AssertionError("permit acquired after timeout")

    release_all.set()
    for thread in holders:
        thread.join(timeout=2.0)

    entered = threading.Event()

    def after() -> None:
        with brain_lock("cap-wait"):
            entered.set()

    follower = threading.Thread(target=after, name="cap-after")
    follower.start()
    assert entered.wait(timeout=2.0)
    follower.join(timeout=2.0)
