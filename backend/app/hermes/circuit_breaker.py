"""Hermes gateway circuit breaker.

Closed while the gateway is healthy. Three consecutive gateway failures open
the circuit. After 60s it allows one half-open health probe. A failed probe
opens it again. A successful gateway turn closes it.

A successful ``/health`` response while the circuit is already closed does not
clear the failure count. Health answering while chat is failing must not hide
those failures.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3
RECOVERY_TIMEOUT_SEC = 60.0

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = FAILURE_THRESHOLD,
        recovery_timeout: float = RECOVERY_TIMEOUT_SEC,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._now = now or time.monotonic
        self._lock = threading.Lock()
        self.state = CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self._probe_inflight = False

    def reset(self) -> None:
        with self._lock:
            self.state = CLOSED
            self.failures = 0
            self.opened_at = 0.0
            self._probe_inflight = False

    def before_health_probe(self) -> bool:
        """Whether this turn may spend the gateway ``/health`` probe.

        Open circuits return False so the caller uses the existing Hermes-miss
        path. Once the recovery window has elapsed, exactly one caller is
        allowed through (half-open).
        """
        with self._lock:
            if self.state == CLOSED:
                return True
            if self.state == OPEN:
                if self._now() - self.opened_at < self.recovery_timeout:
                    return False
                if self._probe_inflight:
                    return False
                self.state = HALF_OPEN
                self._probe_inflight = True
                return True
            if self._probe_inflight:
                return False
            self._probe_inflight = True
            return True

    def after_health_probe(self, ok: bool) -> None:
        """Record the probe that ``before_health_probe`` allowed."""
        with self._lock:
            if self.state == HALF_OPEN:
                self._probe_inflight = False
                if ok:
                    self._close_locked()
                else:
                    self._on_failure_locked()
                return
            if not ok:
                self._on_failure_locked()

    def record_success(self) -> None:
        """A completed gateway turn. Closes the circuit."""
        with self._lock:
            self._close_locked()

    def record_failure(self) -> None:
        """A gateway transport failure (timeout, HTTP error, unreachable)."""
        with self._lock:
            self._on_failure_locked()

    def _close_locked(self) -> None:
        self.state = CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self._probe_inflight = False

    def _on_failure_locked(self) -> None:
        self.failures += 1
        self._probe_inflight = False
        if self.state == HALF_OPEN or self.failures >= self.failure_threshold:
            opened = self.state != OPEN
            self.state = OPEN
            self.opened_at = self._now()
            if opened:
                log.warning(
                    "Hermes gateway circuit opened after %s consecutive failures",
                    self.failures,
                )


gateway_circuit = CircuitBreaker()
