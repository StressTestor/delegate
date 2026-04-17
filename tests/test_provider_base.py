from delegate.providers.base import ProviderResult, Outcome


def test_provider_result_ok():
    r = ProviderResult(outcome=Outcome.OK, duration_s=1.0)
    assert r.is_success()
    assert not r.is_hard_fail()

def test_provider_result_recoverable():
    r = ProviderResult(outcome=Outcome.RATE_LIMITED, duration_s=0.1, detail="429")
    assert not r.is_success()
    assert r.is_recoverable()
    assert not r.is_hard_fail()

def test_provider_result_hard_fail_zen():
    r = ProviderResult(outcome=Outcome.ZEN_TRAP, detail="insufficient balance")
    assert r.is_hard_fail()
    assert not r.is_recoverable()
