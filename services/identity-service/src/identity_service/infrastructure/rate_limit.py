"""Atomic Redis login throttling without retaining raw account or source values."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from identity_service.application.errors import AuthenticationError

_CHECK_SCRIPT = """
local account_count = tonumber(redis.call('GET', KEYS[1]) or '0')
local source_count = tonumber(redis.call('GET', KEYS[2]) or '0')
if account_count >= tonumber(ARGV[1]) or source_count >= tonumber(ARGV[2]) then
  local account_ttl = redis.call('TTL', KEYS[1])
  local source_ttl = redis.call('TTL', KEYS[2])
  return math.max(account_ttl, source_ttl, 1)
end
return 0
"""

_FAILURE_SCRIPT = """
local account_count = redis.call('INCR', KEYS[1])
local source_count = redis.call('INCR', KEYS[2])
if account_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
if source_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
return 1
"""


class RedisCommands(Protocol):
    def eval(self, script: str, numkeys: int, *values: object) -> object: ...

    def delete(self, *keys: str) -> object: ...


@dataclass(frozen=True, slots=True)
class RedisLoginRateLimiter:
    """Per-account and per-source limiter; any state error denies authentication."""

    client: RedisCommands
    namespace: str = "camera-ai:identity:login:v1"
    account_limit: int = 5
    source_limit: int = 20
    window: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if (
            not self.namespace.startswith("camera-ai:identity:")
            or not 1 <= self.account_limit <= 100
            or not self.account_limit <= self.source_limit <= 1_000
            or not timedelta(seconds=30) <= self.window <= timedelta(hours=1)
        ):
            raise AuthenticationError("AUTH_DEPENDENCY_UNAVAILABLE")

    def check(self, *, account_key: bytes, source_key: str, now: datetime) -> int | None:
        del now
        account, source = self._keys(account_key, source_key)
        try:
            result = self.client.eval(
                _CHECK_SCRIPT,
                2,
                account,
                source,
                self.account_limit,
                self.source_limit,
            )
            if isinstance(result, bool) or not isinstance(result, (int, str, bytes)):
                raise ValueError
            retry_after = int(result)
            return None if retry_after <= 0 else retry_after
        except Exception:
            raise AuthenticationError("AUTH_RATE_LIMIT_UNAVAILABLE") from None

    def failure(self, *, account_key: bytes, source_key: str, now: datetime) -> None:
        del now
        account, source = self._keys(account_key, source_key)
        try:
            self.client.eval(
                _FAILURE_SCRIPT,
                2,
                account,
                source,
                int(self.window.total_seconds()),
            )
        except Exception:
            raise AuthenticationError("AUTH_RATE_LIMIT_UNAVAILABLE") from None

    def success(self, *, account_key: bytes, source_key: str) -> None:
        del source_key
        try:
            self.client.delete(self._account_key(account_key))
        except Exception:
            raise AuthenticationError("AUTH_RATE_LIMIT_UNAVAILABLE") from None

    def _keys(self, account_key: bytes, source_key: str) -> tuple[str, str]:
        account = self._account_key(account_key)
        source_digest = hashlib.sha256(
            b"camera-ai|identity-source-v1|" + source_key.encode()
        ).hexdigest()
        return account, f"{self.namespace}:source:{source_digest}"

    def _account_key(self, account_key: bytes) -> str:
        digest = hashlib.sha256(b"camera-ai|identity-account-v1|" + account_key).hexdigest()
        return f"{self.namespace}:account:{digest}"
