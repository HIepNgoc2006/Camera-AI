from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from consent_service.application.service import ConsentApplicationService
from consent_service.domain.errors import ConsentError
from consent_service.domain.models import (
    AuthorityType,
    ConsentDecisionCode,
    SubjectType,
    TrustedConsentContext,
    TrustedEvaluationContext,
    TrustedPurposeContext,
)
from consent_service.infrastructure.repository import SqlAlchemyConsentRepository
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000101")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000102")
AUTHORITY_ID = UUID("00000000-0000-4000-8000-000000000103")
SUBJECT_ID = UUID("00000000-0000-4000-8000-000000000104")
SECOND_SUBJECT_ID = UUID("00000000-0000-4000-8000-000000000105")

EXPECTED_TABLES = {
    "consent_audit_outbox",
    "consent_events",
    "consents",
    "purposes",
}
EXPECTED_CONSENT_COLUMNS = {
    "consent_id",
    "school_id",
    "subject_type",
    "subject_id",
    "purpose_id",
    "authority_type",
    "authority_ref",
    "status",
    "scope_codes",
    "valid_from",
    "valid_to",
    "withdrawn_at",
    "restricted_at",
    "policy_version",
    "created_at",
    "updated_at",
    "row_version",
}


def _test_database_uri() -> str:
    raw_uri = os.environ.get("CONSENT_DATABASE_URI", "").strip()
    if not raw_uri:
        pytest.skip(
            "CONSENT_DATABASE_URI is required for isolated consent integration verification"
        )
    url = make_url(raw_uri)
    database_name = (url.database or "").casefold()
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database_name.endswith("_test")
    ):
        pytest.fail("consent integration test requires an isolated loopback non-5432 *_test DB")
    return raw_uri


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def _context(subject_id: UUID = SUBJECT_ID) -> TrustedConsentContext:
    return TrustedConsentContext(
        school_id=SCHOOL_ID,
        actor_id=ACTOR_ID,
        subject_type=SubjectType.STUDENT,
        subject_id=subject_id,
        authority_type=AuthorityType.GUARDIAN,
        authority_ref=AUTHORITY_ID,
        authority_verified=True,
    )


def _purpose_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "code": "student_attendance",
        "description": "Synthetic attendance purpose for isolated integration verification.",
        "data_categories": ["attendance", "biometric"],
        "requires_biometric_consent": True,
        "status": "active",
        "version": 1,
        "valid_from": (NOW - timedelta(days=1)).isoformat(),
        "valid_to": (NOW + timedelta(days=30)).isoformat(),
    }


def _request_payload(purpose_id: UUID, subject_id: UUID, suffix: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "purpose_id": str(purpose_id),
        "subject_type": "student",
        "subject_id": str(subject_id),
        "authority_type": "guardian",
        "authority_ref": str(AUTHORITY_ID),
        "scope_codes": ["attendance", "biometric"],
        "policy_version": "consent_v1",
        "valid_from": NOW.isoformat(),
        "valid_to": (NOW + timedelta(days=10)).isoformat(),
        "request_id": f"req_{suffix}",
        "idempotency_key": f"idem_{suffix}",
    }


def _transition_payload(
    consent_id: UUID,
    status: str,
    expected_version: int,
    suffix: str,
    reason_code: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "consent_id": str(consent_id),
        "target_status": status,
        "expected_version": expected_version,
        "request_id": f"req_{suffix}",
        "idempotency_key": f"idem_{suffix}",
    }
    if reason_code is not None:
        payload["reason_code"] = reason_code
    return payload


def _assert_inventory(engine: Engine) -> None:
    inspector = inspect(engine)
    assert inspector.has_schema("privacy")
    assert set(inspector.get_table_names(schema="privacy")) == EXPECTED_TABLES
    assert {
        column["name"] for column in inspector.get_columns("consents", schema="privacy")
    } == EXPECTED_CONSENT_COLUMNS
    assert inspector.get_foreign_keys("consents", schema="privacy") == [
        {
            "name": "fk_consents_purpose_id",
            "constrained_columns": ["purpose_id"],
            "referred_schema": "privacy",
            "referred_table": "purposes",
            "referred_columns": ["purpose_id"],
            "options": {"ondelete": "RESTRICT"},
            "comment": None,
        }
    ]
    with engine.connect() as connection:
        triggers = set(
            connection.scalars(
                sa.text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid IN "
                    "('privacy.consents'::regclass, 'privacy.consent_events'::regclass) "
                    "AND NOT tgisinternal"
                )
            )
        )
    assert triggers == {
        "consent_events_reject_truncate",
        "consent_events_reject_update_delete",
        "consents_reject_delete",
        "consents_reject_truncate",
    }


def test_migration_consent_lifecycle_idempotency_concurrency_and_audit_outbox() -> None:
    database_uri = _test_database_uri()
    engine = sa.create_engine(database_uri, poolclass=sa.pool.NullPool)
    config = _alembic_config()
    upgraded = False
    try:
        command.downgrade(config, "base")
        assert inspect(engine).has_schema("privacy") is False
        command.upgrade(config, "head")
        upgraded = True
        _assert_inventory(engine)

        repository = SqlAlchemyConsentRepository(engine)
        service = ConsentApplicationService(repository, clock=lambda: NOW)
        purpose = service.register_purpose(
            _purpose_payload(),
            TrustedPurposeContext(SCHOOL_ID, ACTOR_ID, can_manage_purposes=True),
        )

        request_payload = _request_payload(purpose.purpose_id, SUBJECT_ID, "1111111111111111")
        requested = service.request_consent(request_payload, _context())
        duplicate = service.request_consent(request_payload, _context())
        assert requested.duplicate is False
        assert duplicate.duplicate is True
        assert duplicate.consent.consent_id == requested.consent.consent_id

        conflict_payload = dict(request_payload)
        conflict_payload["request_id"] = "req_2222222222222222"
        with pytest.raises(ConsentError, match="CONSENT_DUPLICATE_CONFLICT"):
            service.request_consent(conflict_payload, _context())

        grant_payload = _transition_payload(
            requested.consent.consent_id,
            "granted",
            1,
            "3333333333333333",
        )
        granted = service.transition_consent(grant_payload, _context())
        grant_duplicate = service.transition_consent(grant_payload, _context())
        assert granted.consent.row_version == 2
        assert grant_duplicate.duplicate is True

        decision = service.evaluate(
            {
                "schema_version": 1,
                "consent_id": str(granted.consent.consent_id),
                "purpose_id": str(purpose.purpose_id),
                "required_scope_codes": ["biometric"],
                "expected_version": 2,
            },
            TrustedEvaluationContext(SCHOOL_ID, SubjectType.STUDENT, SUBJECT_ID, True),
        )
        assert decision.allowed is True

        withdrawn = service.transition_consent(
            _transition_payload(
                granted.consent.consent_id,
                "withdrawn",
                2,
                "4444444444444444",
                "AUTHORITY_WITHDRAWAL",
            ),
            _context(),
        )
        denied_after_withdrawal = service.evaluate(
            {
                "schema_version": 1,
                "consent_id": str(withdrawn.consent.consent_id),
                "purpose_id": str(purpose.purpose_id),
                "required_scope_codes": ["biometric"],
                "expected_version": 3,
            },
            TrustedEvaluationContext(SCHOOL_ID, SubjectType.STUDENT, SUBJECT_ID, True),
        )
        assert denied_after_withdrawal.reason_code is ConsentDecisionCode.WITHDRAWN

        second = service.request_consent(
            _request_payload(purpose.purpose_id, SECOND_SUBJECT_ID, "5555555555555555"),
            _context(SECOND_SUBJECT_ID),
        )
        competing = (
            _transition_payload(
                second.consent.consent_id,
                "denied",
                1,
                "6666666666666666",
                "POLICY_DENIED",
            ),
            _transition_payload(
                second.consent.consent_id,
                "denied",
                1,
                "7777777777777777",
                "AUTHORITY_UNVERIFIED",
            ),
        )

        def run_transition(payload: dict[str, object]) -> str:
            try:
                return service.transition_consent(
                    payload, _context(SECOND_SUBJECT_ID)
                ).consent.status
            except ConsentError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrency_results = list(executor.map(run_transition, competing))
        assert sum(result == "CONSENT_VERSION_CONFLICT" for result in concurrency_results) == 1
        assert sum(result == "denied" for result in concurrency_results) == 1

        with engine.connect() as connection:
            counts = (
                connection.execute(
                    sa.text(
                        "SELECT "
                        "(SELECT count(*) FROM privacy.consent_events) AS events, "
                        "(SELECT count(*) FROM privacy.consent_audit_outbox) AS intents, "
                        "(SELECT count(*) FROM privacy.consent_audit_outbox "
                        " WHERE delivery_status = 'pending') AS pending, "
                        "(SELECT count(*) FROM privacy.consent_audit_outbox "
                        " WHERE action = 'CONSENT_DENIED' AND result = 'denied') AS denied"
                    )
                )
                .mappings()
                .one()
            )
        assert counts == {"events": 5, "intents": 5, "pending": 5, "denied": 1}

        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE privacy.consent_events SET event_type = 'denied' "
                    "WHERE consent_event_id = :event_id"
                ),
                {"event_id": requested.event.consent_event_id},
            )
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(
                sa.text("DELETE FROM privacy.consents WHERE consent_id = :consent_id"),
                {"consent_id": requested.consent.consent_id},
            )

        command.downgrade(config, "base")
        upgraded = False
        assert inspect(engine).has_schema("privacy") is False
    finally:
        if upgraded:
            command.downgrade(config, "base")
        engine.dispose()
