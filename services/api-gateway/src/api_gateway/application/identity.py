"""Port for forwarding approved authentication calls to Identity Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class IdentityUpstreamUnavailable(RuntimeError):
    """Raised without upstream URL, body, header, or exception details."""


@dataclass(frozen=True, slots=True)
class IdentityUpstreamResponse:
    status_code: int
    content: bytes
    headers: tuple[tuple[str, str], ...] = ()


class IdentityUpstream(Protocol):
    async def forward(
        self,
        *,
        path: str,
        body: bytes,
        authorization: str | None,
        request_id: str,
        source_key: str,
    ) -> IdentityUpstreamResponse: ...
