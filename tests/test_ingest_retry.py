import pytest
from fastf1.exceptions import RateLimitExceededError

from pitwall.data import ingest


def test_waits_and_retries_after_rate_limit(monkeypatch):
    sleeps = []
    monkeypatch.setattr(ingest.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitExceededError("any API: 500 calls/h")
        return "done"

    assert ingest._with_rate_limit_retry(flaky) == "done"
    assert len(sleeps) == 2 and sleeps[0] == ingest.RATE_LIMIT_WAIT_S


def test_gives_up_after_max_waits(monkeypatch):
    monkeypatch.setattr(ingest.time, "sleep", lambda s: None)

    def always_limited():
        raise RateLimitExceededError("any API: 500 calls/h")

    with pytest.raises(RateLimitExceededError):
        ingest._with_rate_limit_retry(always_limited, max_waits=2)


def test_other_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(ingest.time, "sleep", lambda s: pytest.fail("should not sleep"))

    def broken():
        raise ValueError("bad data")

    with pytest.raises(ValueError):
        ingest._with_rate_limit_retry(broken)
