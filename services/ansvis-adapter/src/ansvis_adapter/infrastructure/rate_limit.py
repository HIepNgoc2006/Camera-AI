"""Atomic Redis token bucket for the ANSVIS pre-authentication boundary."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from ansvis_adapter.application.ports import RateLimitDecision, SourceRateLimiter
from ansvis_adapter.domain.errors import AnsvisAdapterError

SUSTAINED_REQUESTS_PER_SECOND = 50
BURST_REQUESTS = 200
STATE_TTL_SECONDS = 300

# Redis TIME is used so horizontally scaled adapters share one trusted limiter clock.
# The script returns only an allow bit and a bounded millisecond retry delay.
TOKEN_BUCKET_LUA = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + (tonumber(clock[2]) / 1000000)
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local state = redis.call('HMGET', KEYS[1], 'tokens', 'updated_at')
local tokens = tonumber(state[1])
local updated_at = tonumber(state[2])
if tokens == nil or updated_at == nil then
  tokens = capacity
  updated_at = now
end
local elapsed = math.max(0, now - updated_at)
tokens = math.min(capacity, tokens + (elapsed * rate))
local allowed = 0
local retry_ms = 0
if tokens >= 1 then
  allowed = 1
  tokens = tokens - 1
else
  retry_ms = math.ceil(((1 - tokens) / rate) * 1000)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated_at', now)
redis.call('EXPIRE', KEYS[1], ttl)
return {allowed, retry_ms}
""".strip()


class RedisScriptClient(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        """Execute one Redis script using the client library's normal EVAL contract."""


class RedisSourceRateLimiter(SourceRateLimiter):
    """Shared source-scoped limiter with no local permissive fallback."""

    def __init__(
        self,
        client: RedisScriptClient,
        *,
        sustained_requests_per_second: int = SUSTAINED_REQUESTS_PER_SECOND,
        burst_requests: int = BURST_REQUESTS,
        state_ttl_seconds: int = STATE_TTL_SECONDS,
        key_prefix: str = "camera-ai:ansvis-rate:v1",
    ) -> None:
        if sustained_requests_per_second <= 0:
            raise ValueError("sustained rate must be positive")
        if burst_requests <= 0:
            raise ValueError("burst capacity must be positive")
        if state_ttl_seconds <= 0:
            raise ValueError("state TTL must be positive")
        if not key_prefix or any(character.isspace() for character in key_prefix):
            raise ValueError("Redis key prefix must be a non-empty opaque value")
        self._client = client
        self._rate = sustained_requests_per_second
        self._burst = burst_requests
        self._ttl = state_ttl_seconds
        self._key_prefix = key_prefix

    def check(self, source_namespace: str) -> RateLimitDecision:
        source_digest = hashlib.sha256(source_namespace.encode("utf-8")).hexdigest()
        key = f"{self._key_prefix}:{source_digest}"
        try:
            result = self._client.eval(
                TOKEN_BUCKET_LUA,
                1,
                key,
                self._rate,
                self._burst,
                self._ttl,
            )
            allowed, retry_ms = self._validated_result(result)
        except AnsvisAdapterError:
            raise
        except Exception:
            raise AnsvisAdapterError("EVENT_RATE_LIMIT_UNAVAILABLE") from None
        if allowed == 1:
            return RateLimitDecision(allowed=True)
        return RateLimitDecision(
            allowed=False,
            retry_after_seconds=max(1, math.ceil(retry_ms / 1000)),
        )

    @staticmethod
    def _validated_result(result: object) -> tuple[int, int]:
        if not isinstance(result, (list, tuple)) or len(result) != 2:
            raise AnsvisAdapterError("EVENT_RATE_LIMIT_UNAVAILABLE")
        allowed, retry_ms = result
        if (
            isinstance(allowed, bool)
            or not isinstance(allowed, int)
            or allowed not in (0, 1)
            or isinstance(retry_ms, bool)
            or not isinstance(retry_ms, int)
            or retry_ms < 0
        ):
            raise AnsvisAdapterError("EVENT_RATE_LIMIT_UNAVAILABLE")
        if allowed == 0 and retry_ms == 0:
            raise AnsvisAdapterError("EVENT_RATE_LIMIT_UNAVAILABLE")
        return allowed, retry_ms
