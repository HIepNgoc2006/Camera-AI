"""RabbitMQ publisher adapter for the ANSVIS adapter's `EventPublisher` port.

Topology contract (recorded in the worker README): one durable topic exchange
`camera-ai.events.v1`; routing key is the normalized event topic; publisher confirms are
mandatory; messages are persistent JSON. Queues, bindings and dead-letter exchanges belong to
consumers and are not declared here.

Failures never expose payload content, broker credentials or pika internals: every error is
re-raised as a bare `RuntimeError("EVENT_OUTBOX_PUBLISH_FAILED")` after the channel is reset so
the next call reconnects.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Protocol

from event_outbox_worker.config import EXCHANGE_NAME

PUBLISH_FAILED = "EVENT_OUTBOX_PUBLISH_FAILED"


class PublishChannel(Protocol):
    """The narrow channel surface the publisher relies on."""

    def basic_publish(
        self, exchange: str, routing_key: str, body: bytes, properties: object
    ) -> None: ...

    def close(self) -> None: ...


def _pika_channel_factory(broker_url: str) -> PublishChannel:
    """Open a blocking connection, enable confirms, and declare the durable exchange."""

    import pika

    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    channel = connection.channel()
    channel.confirm_delivery()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    return channel  # type: ignore[no-any-return]


def _pika_properties() -> object:
    import pika

    return pika.BasicProperties(content_type="application/json", delivery_mode=2)


class RabbitMqEventPublisher:
    """Confirm-mode publisher implementing the adapter's `EventPublisher` protocol."""

    def __init__(
        self,
        broker_url: str,
        *,
        channel_factory: Callable[[str], PublishChannel] | None = None,
        properties_factory: Callable[[], object] | None = None,
    ) -> None:
        self._broker_url = broker_url
        self._channel_factory = channel_factory or _pika_channel_factory
        self._properties_factory = properties_factory or _pika_properties
        self._channel: PublishChannel | None = None

    def ensure_connected(self) -> bool:
        """Open (or verify) the channel; return False instead of raising on broker outage."""

        if self._channel is not None:
            return True
        try:
            self._channel = self._channel_factory(self._broker_url)
        except Exception:
            self._channel = None
            return False
        return True

    def publish(self, *, topic: str, payload: Mapping[str, object]) -> None:
        """Publish one persistent JSON message under confirms, or raise a redacted error."""

        channel = self._channel
        if channel is None:
            raise RuntimeError(PUBLISH_FAILED)
        body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=topic,
                body=body,
                properties=self._properties_factory(),
            )
        except Exception:
            self.close()
            raise RuntimeError(PUBLISH_FAILED) from None

    def close(self) -> None:
        """Drop the channel; the next `ensure_connected` call reconnects."""

        channel, self._channel = self._channel, None
        if channel is None:
            return
        try:
            channel.close()
        except Exception:
            return

    def __repr__(self) -> str:
        connected = self._channel is not None
        return f"RabbitMqEventPublisher(exchange={EXCHANGE_NAME!r}, connected={connected})"
