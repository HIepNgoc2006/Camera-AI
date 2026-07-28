from __future__ import annotations

import os
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from camera_ai_crypto import DeterministicFakeKeyProvider, EncryptionService, LookupHasher
from notification_service.application.endpoints import EndpointApplicationService
from notification_service.application.lifecycle import DeliveryApplicationService
from notification_service.application.service import NotificationApplicationService
from notification_service.domain.models import (
    Channel,
    ConsentDecision,
    EndpointKind,
    NotificationCommand,
    ProviderResultCategory,
    RecipientAuthorization,
    TrustedSourceContext,
)
from notification_service.infrastructure.crypto import CryptoEndpointProtector
from notification_service.infrastructure.repository import PostgresNotificationRepository
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

NOW = datetime(2026, 7, 28, tzinfo=UTC)
SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _uuid(suffix: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{suffix:012d}")


def _database_uri() -> str:
    raw = os.environ.get("NOTIFICATION_DATABASE_URI", "").strip()
    if not raw:
        pytest.skip("NOTIFICATION_DATABASE_URI is not set for an isolated integration database")
    url = make_url(raw)
    if url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").endswith("_test"):
        pytest.fail("notification integration database must be loopback and end with _test")
    return raw


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_event_id": _uuid(1),
        "idempotency_key": "ntf_integration_000001",
        "tenant_id": _uuid(2),
        "school_id": _uuid(3),
        "subject_ref": _uuid(4),
        "resource_ref": _uuid(5),
        "content_class": "attendance_update",
        "template_code": "notification.attendance.generic",
        "template_version": 1,
        "source_state": "confirmed",
        "source_expires_at": NOW + timedelta(hours=2),
        "notification_expires_at": NOW + timedelta(hours=1),
        "recipient_refs": (_uuid(6),),
        "channels": ("in_app", "push", "email"),
        "request_id": "req_integration_0001",
        "correlation_id": "cor_integration_0001",
    }


class Authorizer:
    def evaluate(
        self, command: NotificationCommand
    ) -> Mapping[tuple[UUID, Channel], RecipientAuthorization]:
        authorization = RecipientAuthorization(
            recipient_ref=_uuid(6),
            tenant_id=_uuid(2),
            school_id=_uuid(3),
            recipient_role="parent_guardian",
            relationship_code="active_linked_child",
            permission_code="notification.attendance.receive",
            purpose_code="attendance_notification",
            recipient_active=True,
            relationship_current=True,
            permission_current=True,
            purpose_active=True,
            consent_decision=ConsentDecision.ALLOWED,
            source_current=True,
            endpoint_active=True,
            endpoint_verified=True,
            endpoint_owned=True,
            channel_preference_enabled=True,
            dependencies_available=True,
        )
        return {
            (recipient, channel): authorization
            for recipient in command.recipient_refs
            for channel in command.channels
        }


def test_migration_repository_endpoint_and_append_only_contract() -> None:
    database_uri = _database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    upgraded = False
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        upgraded = True
        inspector = sa.inspect(engine)
        assert set(inspector.get_table_names(schema="notification")) == {
            "audit_outbox",
            "delivery_attempts",
            "notification_cancellations",
            "notification_intents",
            "recipient_deliveries",
            "recipient_endpoints",
        }
        repository = PostgresNotificationRepository(engine)
        service = NotificationApplicationService(
            repository,
            Authorizer(),
            clock=lambda: NOW,
        )
        context = TrustedSourceContext(
            source_service="attendance-service",
            tenant_id=_uuid(2),
            school_id=_uuid(3),
            trusted_identity=True,
            permission_codes=frozenset({"service.notification.request"}),
            delegation_authorized=True,
            runtime_approvals_complete=True,
            policy_version="notification_privacy_policy_v1",
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrent = tuple(
                executor.map(
                    lambda _index: service.accept_intent(_payload(), context),
                    range(2),
                )
            )
        assert sorted(outcome.duplicate for outcome in concurrent) == [False, True]
        first = next(outcome for outcome in concurrent if not outcome.duplicate)
        duplicate = service.accept_intent(_payload(), context)
        rotated_key_payload = _payload()
        rotated_key_payload["idempotency_key"] = "ntf_integration_000002"
        semantic_duplicate = service.accept_intent(rotated_key_payload, context)
        assert first.queued_deliveries == 3
        assert duplicate.duplicate
        assert semantic_duplicate.duplicate
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT count(*) FROM notification.audit_outbox")) == 3
            delivery_id = connection.scalar(
                sa.text(
                    "SELECT delivery_id FROM notification.recipient_deliveries "
                    "WHERE channel = 'in_app'"
                )
            )
        assert isinstance(delivery_id, UUID)

        lifecycle = DeliveryApplicationService(
            repository,
            Authorizer(),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        assert (
            lifecycle.record_provider_result(
                delivery_id=delivery_id,
                category=ProviderResultCategory.TEMPORARY_UNAVAILABLE,
                retry_backlog=4_999,
            )
            is None
        )
        assert (
            lifecycle.cancel(
                notification_id=first.notification_id,
                trigger_code="consent_withdrawn",
                context=context,
            )
            == 3
        )
        assert (
            lifecycle.cancel(
                notification_id=first.notification_id,
                trigger_code="consent_withdrawn",
                context=context,
            )
            == 0
        )
        with engine.connect() as connection:
            assert (
                connection.scalar(sa.text("SELECT count(*) FROM notification.delivery_attempts"))
                == 1
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM notification.recipient_deliveries "
                        "WHERE state = 'cancelled'"
                    )
                )
                == 3
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE notification.delivery_attempts "
                    "SET provider_result_category = 'tampered'"
                )
            )

        endpoint_service = EndpointApplicationService(
            repository,
            CryptoEndpointProtector(
                EncryptionService(DeterministicFakeKeyProvider(seed=b"n" * 32)),
                LookupHasher(b"l" * 32),
            ),
            clock=lambda: NOW,
            identifier_factory=lambda: _uuid(20),
        )
        endpoint_context = TrustedSourceContext(
            source_service="identity-service",
            tenant_id=_uuid(2),
            school_id=_uuid(3),
            trusted_identity=True,
            permission_codes=frozenset({"service.notification.endpoint.manage"}),
            delegation_authorized=True,
            runtime_approvals_complete=True,
            policy_version="notification_privacy_policy_v1",
        )
        endpoint = endpoint_service.register(
            tenant_id=_uuid(2),
            recipient_ref=_uuid(6),
            kind=EndpointKind.DEVICE_TOKEN,
            value=b"synthetic-endpoint",
            context=endpoint_context,
            request_id="req_integration_0001",
            correlation_id="cor_integration_0001",
        )
        endpoint_service.revoke(
            endpoint_id=endpoint.endpoint_id,
            tenant_id=_uuid(2),
            recipient_ref=_uuid(6),
            context=endpoint_context,
            request_id="req_integration_0002",
            correlation_id="cor_integration_0002",
        )
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT state FROM notification.recipient_endpoints "
                        "WHERE endpoint_id = :endpoint_id"
                    ),
                    {"endpoint_id": endpoint.endpoint_id},
                )
                == "revoked"
            )
            assert (
                connection.scalar(
                    sa.text("SELECT count(*) FROM notification.notification_cancellations")
                )
                == 3
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM notification.notification_cancellations "
                        "WHERE trigger_code = 'endpoint_revoked' "
                        "AND recipient_ref IS NOT NULL AND channel IN ('push', 'email')"
                    )
                )
                == 2
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO notification.recipient_endpoints "
                    "(endpoint_id,tenant_id,recipient_ref,kind,endpoint_ciphertext,"
                    "endpoint_lookup_digest,state,verified_at,created_at) "
                    "VALUES (:id,:tenant,:recipient,'device_token',:plaintext,:digest,"
                    "'active',:now,:now)"
                ),
                {
                    "id": _uuid(21),
                    "tenant": _uuid(2),
                    "recipient": _uuid(6),
                    "plaintext": b"not-an-envelope",
                    "digest": b"d" * 32,
                    "now": NOW,
                },
            )
        command.downgrade(config, "base")
        upgraded = False
        assert sa.inspect(engine).has_schema("notification") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
