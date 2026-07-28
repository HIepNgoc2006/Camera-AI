from __future__ import annotations

from dataclasses import dataclass

import pytest
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.infrastructure.rate_limit import (
    BURST_REQUESTS,
    SUSTAINED_REQUESTS_PER_SECOND,
    TOKEN_BUCKET_LUA,
    RedisSourceRateLimiter,
)


@dataclass
class BucketState:
    tokens: float
    updated_at: float


class FakeRedisScriptClient:
    """Deterministic test double for the exact token-bucket EVAL contract."""

    def __init__(self) -> None:
        self.now = 0.0
        self.states: dict[str, BucketState] = {}
        self.fail = False
        self.invalid_result: object | None = None

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        if self.fail:
            raise RuntimeError("synthetic Redis outage")
        if self.invalid_result is not None:
            return self.invalid_result
        assert script == TOKEN_BUCKET_LUA
        assert numkeys == 1
        key, raw_rate, raw_capacity, raw_ttl = keys_and_args
        assert isinstance(key, str)
        assert isinstance(raw_rate, int)
        assert isinstance(raw_capacity, int)
        assert isinstance(raw_ttl, int) and raw_ttl > 0
        state = self.states.get(
            key,
            BucketState(tokens=float(raw_capacity), updated_at=self.now),
        )
        elapsed = max(0.0, self.now - state.updated_at)
        tokens = min(float(raw_capacity), state.tokens + elapsed * raw_rate)
        if tokens >= 1:
            result = [1, 0]
            tokens -= 1
        else:
            retry_ms = max(1, int(((1 - tokens) / raw_rate) * 1000 + 0.999))
            result = [0, retry_ms]
        self.states[key] = BucketState(tokens=tokens, updated_at=self.now)
        return result


def test_burst_then_sustained_refill_is_exact() -> None:
    redis = FakeRedisScriptClient()
    limiter = RedisSourceRateLimiter(redis)

    assert all(limiter.check("ansvis.test.source").allowed for _ in range(BURST_REQUESTS))
    limited = limiter.check("ansvis.test.source")
    assert not limited.allowed
    assert limited.retry_after_seconds == 1

    redis.advance(1)
    assert all(
        limiter.check("ansvis.test.source").allowed for _ in range(SUSTAINED_REQUESTS_PER_SECOND)
    )
    assert not limiter.check("ansvis.test.source").allowed


def test_sources_have_isolated_hashed_buckets() -> None:
    redis = FakeRedisScriptClient()
    limiter = RedisSourceRateLimiter(redis, burst_requests=1)

    assert limiter.check("ansvis.test.source-a").allowed
    assert not limiter.check("ansvis.test.source-a").allowed
    assert limiter.check("ansvis.test.source-b").allowed
    assert len(redis.states) == 2
    assert all("ansvis.test.source" not in key for key in redis.states)


@pytest.mark.parametrize("failure_mode", ["outage", "invalid"])
def test_redis_failure_and_invalid_reply_fail_closed(failure_mode: str) -> None:
    redis = FakeRedisScriptClient()
    if failure_mode == "outage":
        redis.fail = True
    else:
        redis.invalid_result = [1]
    limiter = RedisSourceRateLimiter(redis)

    with pytest.raises(AnsvisAdapterError) as raised:
        limiter.check("ansvis.test.source")

    assert raised.value.code == "EVENT_RATE_LIMIT_UNAVAILABLE"


def test_200_rps_for_60_seconds_has_expected_rejection_ratio_without_errors() -> None:
    redis = FakeRedisScriptClient()
    limiter = RedisSourceRateLimiter(redis)
    accepted = 0
    rejected = 0

    for _ in range(12_000):
        decision = limiter.check("ansvis.test.source")
        if decision.allowed:
            accepted += 1
        else:
            rejected += 1
        redis.advance(0.005)

    assert 3_199 <= accepted <= 3_200
    assert 8_800 <= rejected <= 8_801
    assert rejected / 12_000 == pytest.approx(0.7334, abs=0.0001)
