from __future__ import annotations

import threading
import time


class RateLimiter:
    """Minimum inter-request spacing based on rpm. Thread-safe.

    Holds the lock across time.sleep() by design: this serializes
    concurrent acquirers through the gate, enforcing the rpm cap
    globally rather than per-caller. Do not release the lock before
    sleeping — that would let N callers all observe "no wait needed"
    simultaneously and stampede the provider.
    """

    def __init__(self, rpm: int):
        if rpm <= 0:
            raise ValueError("rpm must be positive")
        self._min_spacing = 60.0 / rpm
        self._last_ts: float = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._min_spacing - (now - self._last_ts)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._last_ts = now
