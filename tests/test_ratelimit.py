import time
from delegate.ratelimit import RateLimiter


def test_allows_within_cap():
    rl = RateLimiter(rpm=60)  # 1/sec minimum spacing
    start = time.monotonic()
    rl.acquire()
    rl.acquire()  # will sleep ~1s
    rl.acquire()
    elapsed = time.monotonic() - start
    assert 1.8 <= elapsed <= 3.0, f"expected ~2s, got {elapsed}"

def test_high_rpm_effectively_no_sleep():
    rl = RateLimiter(rpm=6000)  # 10ms spacing
    start = time.monotonic()
    for _ in range(5):
        rl.acquire()
    assert time.monotonic() - start < 0.2
