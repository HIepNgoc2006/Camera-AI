"""Publisher adapter behaviour with a fake channel; no broker is contacted."""

from __future__ import annotations

import json

import pytest
from event_outbox_worker.config import EXCHANGE_NAME
from event_outbox_worker.publisher import PUBLISH_FAILED, RabbitMqEventPublisher

BROKER_URL = "amqp://127.0.0.1:5672/%2F"
PAYLOAD = {"schema_version": "normalized_event_v1", "status": "accepted"}


class FakeChannel:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[tuple[str, str, bytes]] = []
        self.closed = False
        self.connection = FakeConnection()

    def basic_publish(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        properties: object,
        mandatory: bool = False,
    ) -> None:
        del properties
        self.mandatory = mandatory
        if self.fail:
            raise ConnectionError("socket reset with payload echo: " + body.decode())
        self.published.append((exchange, routing_key, body))

    def close(self) -> None:
        self.closed = True


def make_publisher(channel: FakeChannel) -> RabbitMqEventPublisher:
    return RabbitMqEventPublisher(
        BROKER_URL,
        channel_factory=lambda url: channel,
        properties_factory=lambda: object(),
    )


def test_publish_sends_canonical_json_to_the_pinned_exchange() -> None:
    channel = FakeChannel()
    publisher = make_publisher(channel)

    assert publisher.ensure_connected() is True
    publisher.publish(topic="events.attendance.face.observed", payload=PAYLOAD)

    exchange, routing_key, body = channel.published[0]
    assert exchange == EXCHANGE_NAME
    assert routing_key == "events.attendance.face.observed"
    assert json.loads(body) == PAYLOAD
    assert body == json.dumps(PAYLOAD, sort_keys=True, separators=(",", ":")).encode()
    assert channel.mandatory is True


def test_unroutable_message_fails_instead_of_silent_broker_acknowledgment() -> None:
    class Unroutable(FakeChannel):
        def basic_publish(
            self,
            exchange: str,
            routing_key: str,
            body: bytes,
            properties: object,
            mandatory: bool = False,
        ) -> None:
            if mandatory:
                import pika

                raise pika.exceptions.UnroutableError([])
            super().basic_publish(exchange, routing_key, body, properties, mandatory)

    channel = Unroutable()
    publisher = make_publisher(channel)
    assert publisher.ensure_connected()
    with pytest.raises(RuntimeError, match=PUBLISH_FAILED):
        publisher.publish(topic="events.test.unbound", payload=PAYLOAD)
    assert channel.closed
    assert channel.published == []


def test_publish_without_connection_fails_with_stable_code() -> None:
    publisher = make_publisher(FakeChannel())

    with pytest.raises(RuntimeError, match=PUBLISH_FAILED):
        publisher.publish(topic="events.test.topic", payload=PAYLOAD)


def test_publish_failure_is_redacted_and_resets_the_channel() -> None:
    channel = FakeChannel(fail=True)
    publisher = make_publisher(channel)
    publisher.ensure_connected()

    with pytest.raises(RuntimeError) as excinfo:
        publisher.publish(topic="events.test.topic", payload=PAYLOAD)

    rendered = f"{excinfo.value!s} {excinfo.value!r}"
    assert rendered.startswith(PUBLISH_FAILED)
    assert "schema_version" not in rendered
    assert "socket reset" not in rendered
    assert excinfo.value.__cause__ is None
    assert channel.closed is True
    assert channel.connection.closed is True
    assert publisher.ensure_connected() is True  # factory re-invoked after reset


class FakeConnection:
    closed = False

    def close(self) -> None:
        self.closed = True


def test_shutdown_closes_the_owned_broker_connection() -> None:
    channel = FakeChannel()
    publisher = make_publisher(channel)
    assert publisher.ensure_connected()
    publisher.close()
    assert channel.closed and channel.connection.closed


def test_ensure_connected_returns_false_on_broker_outage_without_raising() -> None:
    def failing_factory(url: str) -> FakeChannel:
        raise ConnectionError("dial tcp refused for " + url)

    publisher = RabbitMqEventPublisher(BROKER_URL, channel_factory=failing_factory)

    assert publisher.ensure_connected() is False


def test_repr_never_contains_broker_url_or_credentials() -> None:
    publisher = make_publisher(FakeChannel())

    assert BROKER_URL not in repr(publisher)
    assert "127.0.0.1" not in repr(publisher)
