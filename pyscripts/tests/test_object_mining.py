from pyscripts.explore import object_mining


def test_breaker_trips_on_consecutive_failures() -> None:
    breaker = object_mining._MineBreaker()
    for _ in range(object_mining.BREAK_AFTER - 1):
        breaker.record(failed=True)
    assert not breaker.open
    breaker.record(failed=False)
    breaker.record(failed=True)
    assert not breaker.open  # a success resets the streak
    for _ in range(object_mining.BREAK_AFTER):
        breaker.record(failed=True)
    assert breaker.open
    assert breaker.skip() and breaker.skip()
    assert breaker.skipped == 2
