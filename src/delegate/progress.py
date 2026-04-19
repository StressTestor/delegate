from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from typing import TextIO


class Heartbeat:
    def __init__(self, *, interval_s: float = 15.0, stream: TextIO | None = None):
        self._interval = interval_s
        self._stream = stream or sys.stderr

    @contextmanager
    def running(self, *, label: str):
        stop = threading.Event()
        started = time.monotonic()

        def _tick():
            while not stop.wait(self._interval):
                elapsed = time.monotonic() - started
                self._stream.write(f"[delegate] {label} running, {int(elapsed)}s elapsed\n")
                self._stream.flush()

        t = threading.Thread(target=_tick, daemon=True)
        t.start()
        try:
            yield
        finally:
            stop.set()
            t.join(timeout=self._interval + 1)
