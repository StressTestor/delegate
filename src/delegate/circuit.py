from __future__ import annotations

import threading
from collections import deque


class CircuitBreaker:
    """Sliding-window failure-rate circuit breaker."""

    def __init__(self, *, window: int, threshold: float):
        if window <= 0:
            raise ValueError("window must be positive")
        if not 0 < threshold < 1:
            raise ValueError("threshold must be in (0, 1)")
        self._window = deque(maxlen=window)
        self._threshold = threshold
        self._lock = threading.Lock()

    def record(self, *, success: bool) -> None:
        with self._lock:
            self._window.append(success)

    def tripped(self) -> bool:
        with self._lock:
            if len(self._window) < self._window.maxlen:
                return False
            failures = sum(1 for x in self._window if not x)
            return (failures / self._window.maxlen) > self._threshold
