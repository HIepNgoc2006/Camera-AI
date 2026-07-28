from __future__ import annotations

from datetime import UTC, datetime

import pytest
from identity_service.application.errors import AuthenticationError
from identity_service.infrastructure.rate_limit import RedisLoginRateLimiter

NOW = datetime(2030, 1, 1, tzinfo=UTC)


class FakeRedis:
    def __init__(self, results: list[object] | None = None, *, fail: bool = False) -> None:
        self.results = list(results or [0])
        self.fail = fail
        self.calls: list[tuple[object, ...]] = []
        self.deleted: list[str] = []

    def eval(self, script: str, numkeys: int, *values: object) -> object:
        if self.fail:
            raise ConnectionError("synthetic dependency failure")
        self.calls.append((script, numkeys, *values))
        return self.results.pop(0)

    def delete(self, *keys: str) -> object:
        if self.fail:
            raise ConnectionError("synthetic dependency failure")
        self.deleted.extend(keys)
        return len(keys)


def test_redis_limiter_uses_pseudonymous_account_and_source_keys() -> None:
    redis = FakeRedis([0, 17, 1])
    limiter = RedisLoginRateLimiter(redis)
    account = b"a" * 32
    source = "source.synthetic.0001"

    assert limiter.check(account_key=account, source_key=source, now=NOW) is None
    assert limiter.check(account_key=account, source_key=source, now=NOW) == 17
    limiter.failure(account_key=account, source_key=source, now=NOW)
    limiter.success(account_key=account, source_key=source)

    rendered = repr(redis.calls) + repr(redis.deleted)
    assert account.hex() not in rendered
    assert source not in rendered
    assert ":account:" in rendered
    assert ":source:" in rendered


def test_redis_limiter_dependency_or_invalid_reply_fails_closed() -> None:
    for redis in (FakeRedis(fail=True), FakeRedis([object()])):
        limiter = RedisLoginRateLimiter(redis)
        with pytest.raises(AuthenticationError, match="AUTH_RATE_LIMIT_UNAVAILABLE"):
            limiter.check(
                account_key=b"a" * 32,
                source_key="source.synthetic.0001",
                now=NOW,
            )
