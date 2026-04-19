from delegate.circuit import CircuitBreaker


def test_does_not_trip_when_window_not_full():
    cb = CircuitBreaker(window=10, threshold=0.5)
    for _ in range(5):
        cb.record(success=False)
    assert not cb.tripped()

def test_trips_when_half_fail_with_full_window():
    cb = CircuitBreaker(window=10, threshold=0.5)
    for _ in range(5):
        cb.record(success=True)
    for _ in range(5):
        cb.record(success=False)
    # Exactly 50% fails — `>` threshold means NOT tripped.
    assert not cb.tripped()

def test_trips_when_over_threshold():
    cb = CircuitBreaker(window=10, threshold=0.5)
    for _ in range(4):
        cb.record(success=True)
    for _ in range(6):
        cb.record(success=False)
    assert cb.tripped()

def test_sliding_window_forgets_old():
    cb = CircuitBreaker(window=5, threshold=0.5)
    for _ in range(5):
        cb.record(success=False)  # all fail
    assert cb.tripped()
    for _ in range(5):
        cb.record(success=True)  # replace all with successes
    assert not cb.tripped()
