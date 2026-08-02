"""Bounded HTTP adapter for the private Identity Service upstream."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

import httpx

from api_gateway.application.identity import (
    IdentityUpstreamResponse,
    IdentityUpstreamUnavailable,
)

_PATH_PATTERN = re.compile(
    r"^/api/v1/auth/(?:login|refresh|logout|logout-all|session/snapshot|mfa/enroll|"
    r"sessions/[0-9a-f-]{36}/revoke)$"
)
_SAFE_RESPONSE_HEADERS = frozenset({"content-type", "retry-after", "x-request-id"})


@dataclass(frozen=True, slots=True)
class HttpxIdentityUpstream:
    base_url: str
    transport: httpx.AsyncBaseTransport | None = None
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        try:
            url = httpx.URL(self.base_url)
            host = url.host
            if (
                url.scheme not in {"http", "https"}
                or host is None
                or url.userinfo
                or url.query
                or url.fragment
                or url.path not in {"", "/"}
                or not 0.1 <= self.timeout_seconds <= 10.0
            ):
                raise ValueError
            if url.scheme == "http" and not _is_loopback(host):
                raise ValueError
        except Exception:
            raise IdentityUpstreamUnavailable from None

    async def forward(
        self,
        *,
        path: str,
        body: bytes,
        authorization: str | None,
        request_id: str,
        source_key: str,
    ) -> IdentityUpstreamResponse:
        if _PATH_PATTERN.fullmatch(path) is None:
            raise IdentityUpstreamUnavailable
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            "X-Client-Source": source_key,
        }
        if authorization is not None:
            headers["Authorization"] = authorization
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                transport=self.transport,
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.post(path, content=body, headers=headers)
            safe_headers = tuple(
                (name, value)
                for name, value in response.headers.items()
                if name.lower() in _SAFE_RESPONSE_HEADERS
            )
            return IdentityUpstreamResponse(
                status_code=response.status_code,
                content=response.content,
                headers=safe_headers,
            )
        except Exception:
            raise IdentityUpstreamUnavailable from None


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
