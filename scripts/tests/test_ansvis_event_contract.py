from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.check_ansvis_event_contract import (
    CANONICAL_SCHEMA_PATH,
    CANONICAL_VERSION,
    CASE_FIXTURE_PATH,
    CONTRACT_POLICY_INVALID,
    EVENT_AUTH_TOKEN_EXPIRED,
    EVENT_AUTH_TOKEN_INVALID,
    EVENT_BODY_TOO_LARGE,
    EVENT_FIXTURE_PATH,
    EVENT_SCHEMA_INVALID,
    POLICY_PATH,
    REQUEST_SCHEMA_PATH,
    RESPONSE_SCHEMA_PATH,
    TIME_POLICY_PATH,
    ContractError,
    ContractPolicy,
    JsonObject,
    VerifiedSourceAuth,
    canonical_json_bytes,
    load_json,
    load_json_bytes,
    validate_content_boundary,
    validate_contract_policy,
    validate_fixtures,
    validate_request,
    validate_schema_documents,
    verify_source_auth,
)
from scripts.check_time_policy import TimePolicy
from scripts.check_time_policy import validate_policy as validate_time_policy

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_RECEIVED_AT = "2030-01-01T00:00:10Z"
TEST_KEY = bytes(range(32))
EXPECTED_EVENT_TYPES = {
    "attendance.face.observed",
    "camera.health.changed",
    "insight.emotion.observed",
    "task.health.changed",
    "timekeeping.face.observed",
    "violation.littering.suspected",
    "violation.ppe.suspected",
    "violation.smoking.suspected",
    "violation.uniform.suspected",
}
REQUIRED_CASE_CODES = {
    "valid_attendance_face_observed",
    "valid_timekeeping_face_observed",
    "valid_emotion_observed",
    "valid_littering_suspected",
    "valid_smoking_suspected",
    "valid_uniform_suspected",
    "valid_ppe_suspected",
    "valid_camera_health_changed",
    "valid_task_health_changed",
    "invalid_missing_event_type",
    "invalid_unknown_top_level_field",
    "invalid_unknown_attribute",
    "invalid_event_type",
    "invalid_schema_version",
    "invalid_event_type_value_type",
    "invalid_attributes_value_type",
    "invalid_boolean_source_event_id",
    "invalid_naive_event_time",
    "future_event_skew",
    "stale_event_replay_window",
    "invalid_fallback_identity",
    "invalid_bad_signature",
    "primary_identical_retry",
    "primary_conflicting_retry",
    "fallback_identical_retry",
    "accepted_ack",
    "duplicate_ack",
    "masked_error",
}


def _documents() -> tuple[TimePolicy, ContractPolicy]:
    time_policy = validate_time_policy(load_json(REPO_ROOT / TIME_POLICY_PATH))
    policy = validate_contract_policy(load_json(REPO_ROOT / POLICY_PATH), time_policy)
    return time_policy, policy


def _base() -> JsonObject:
    fixture = load_json(REPO_ROOT / EVENT_FIXTURE_PATH)
    request = fixture["request"]
    assert isinstance(request, dict)
    return request


def _objects(value: object) -> list[JsonObject]:
    assert isinstance(value, list)
    objects: list[JsonObject] = []
    for item in value:
        assert isinstance(item, dict)
        assert all(isinstance(key, str) for key in item)
        objects.append(item)
    return objects


def test_machine_contract_and_sanitized_case_matrix_pass() -> None:
    time_policy, policy = _documents()
    validate_schema_documents(
        load_json(REPO_ROOT / REQUEST_SCHEMA_PATH),
        load_json(REPO_ROOT / CANONICAL_SCHEMA_PATH),
        load_json(REPO_ROOT / RESPONSE_SCHEMA_PATH),
        policy,
    )

    count = validate_fixtures(
        load_json(REPO_ROOT / EVENT_FIXTURE_PATH),
        load_json(REPO_ROOT / CASE_FIXTURE_PATH),
        policy,
        time_policy,
    )

    assert count == 43


def test_sanitized_matrix_has_unique_required_cases_and_every_event_type() -> None:
    fixture = load_json(REPO_ROOT / CASE_FIXTURE_PATH)
    groups = ("schema_cases", "auth_cases", "idempotency_cases", "response_cases")
    cases = [case for group in groups for case in _objects(fixture[group])]
    case_codes: list[str] = []
    for case in cases:
        case_code = case["case_code"]
        assert isinstance(case_code, str)
        case_codes.append(case_code)

    accepted_event_types: set[str] = set()
    for case in _objects(fixture["schema_cases"]):
        case_code = case["case_code"]
        changes = case.get("set")
        assert isinstance(case_code, str)
        if not case_code.startswith("valid_") or not isinstance(changes, dict):
            continue
        event_type = changes.get("event_type")
        if event_type is not None:
            assert isinstance(event_type, str)
            accepted_event_types.add(event_type)

    assert len(case_codes) == len(set(case_codes))
    assert set(case_codes) >= REQUIRED_CASE_CODES
    assert accepted_event_types == EXPECTED_EVENT_TYPES


def test_strict_json_rejects_duplicate_properties_and_non_finite_numbers() -> None:
    with pytest.raises(ContractError, match=EVENT_SCHEMA_INVALID):
        load_json_bytes(b'{"schema_version":"a","schema_version":"b"}')
    with pytest.raises(ContractError, match=EVENT_SCHEMA_INVALID):
        load_json_bytes(b'{"confidence":NaN}')


def test_rejected_values_are_not_retained_or_echoed_by_contract_errors() -> None:
    time_policy, policy = _documents()
    request = _base()
    rejected_value = "opaque_rejected_test_value"
    request["unexpected_field"] = rejected_value

    with pytest.raises(ContractError, match=EVENT_SCHEMA_INVALID) as captured:
        validate_request(
            request,
            server_received_at=SERVER_RECEIVED_AT,
            policy=policy,
            time_policy=time_policy,
            fallback_key=TEST_KEY,
        )

    assert captured.value.args == (EVENT_SCHEMA_INVALID,)
    assert rejected_value not in str(captured.value)


def test_canonical_serialization_is_order_independent_and_decimal_stable() -> None:
    first: JsonObject = {"z": Decimal("0.750000"), "a": {"n": 1, "v": "test"}}
    second: JsonObject = {"a": {"v": "test", "n": 1}, "z": Decimal("0.75")}

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_json_bytes(first) == b'{"a":{"n":1,"v":"test"},"z":0.75}'


def test_correlation_id_is_not_part_of_semantic_fingerprint() -> None:
    time_policy, policy = _documents()
    first = _base()
    second = copy.deepcopy(first)
    second["correlation_id"] = "corr_test_ansvis_retry_9999"

    normalized_first = validate_request(
        first,
        server_received_at=SERVER_RECEIVED_AT,
        policy=policy,
        time_policy=time_policy,
        fallback_key=TEST_KEY,
    )
    normalized_second = validate_request(
        second,
        server_received_at=SERVER_RECEIVED_AT,
        policy=policy,
        time_policy=time_policy,
        fallback_key=TEST_KEY,
    )

    assert normalized_first["schema_version"] == CANONICAL_VERSION
    assert normalized_first["idempotency_key"] == normalized_second["idempotency_key"]
    assert normalized_first["canonical_fingerprint"] == normalized_second["canonical_fingerprint"]


def test_same_identity_with_different_content_is_detectable_as_conflict() -> None:
    time_policy, policy = _documents()
    first = _base()
    second = copy.deepcopy(first)
    attributes = second["attributes"]
    assert isinstance(attributes, dict)
    attributes["status"] = "offline"

    normalized_first = validate_request(
        first,
        server_received_at=SERVER_RECEIVED_AT,
        policy=policy,
        time_policy=time_policy,
        fallback_key=TEST_KEY,
    )
    normalized_second = validate_request(
        second,
        server_received_at=SERVER_RECEIVED_AT,
        policy=policy,
        time_policy=time_policy,
        fallback_key=TEST_KEY,
    )

    assert normalized_first["idempotency_key"] == normalized_second["idempotency_key"]
    assert normalized_first["canonical_fingerprint"] != normalized_second["canonical_fingerprint"]


def test_fallback_identity_fails_closed_without_stable_detection_inputs() -> None:
    time_policy, policy = _documents()
    request = _base()
    request["source_event_id"] = None
    attributes = request["attributes"]
    assert isinstance(attributes, dict)
    attributes.pop("detection_key")

    with pytest.raises(ContractError, match="EVENT_FALLBACK_IDENTITY_INSUFFICIENT"):
        validate_request(
            request,
            server_received_at=SERVER_RECEIVED_AT,
            policy=policy,
            time_policy=time_policy,
            fallback_key=TEST_KEY,
        )


def test_bearer_source_auth_requires_verified_short_lived_token() -> None:
    time_policy, policy = _documents()
    source = "ansvis.test.source"
    authorization_header = "Bearer fixture_" + "x" * 32
    verified_auth = VerifiedSourceAuth(
        valid=True,
        trusted_issuer=True,
        active=True,
        source_namespace=source,
        audience=policy.auth_audience,
        issued_at="2029-12-31T23:59:00Z",
        expires_at="2030-01-01T00:04:00Z",
    )
    verify_source_auth(
        authorization_header=authorization_header,
        verified_auth=verified_auth,
        body_source_namespace=source,
        server_received_at=SERVER_RECEIVED_AT,
        clock_state="healthy",
        transport_is_https=True,
        policy=policy,
        time_policy=time_policy,
    )

    with pytest.raises(ContractError, match=EVENT_AUTH_TOKEN_INVALID):
        verify_source_auth(
            authorization_header=authorization_header,
            verified_auth=VerifiedSourceAuth(
                valid=False,
                trusted_issuer=True,
                active=True,
                source_namespace=source,
                audience=policy.auth_audience,
                issued_at="2029-12-31T23:59:00Z",
                expires_at="2030-01-01T00:04:00Z",
            ),
            body_source_namespace=source,
            server_received_at=SERVER_RECEIVED_AT,
            clock_state="healthy",
            transport_is_https=True,
            policy=policy,
            time_policy=time_policy,
        )

    with pytest.raises(ContractError, match=EVENT_AUTH_TOKEN_EXPIRED):
        verify_source_auth(
            authorization_header=authorization_header,
            verified_auth=VerifiedSourceAuth(
                valid=True,
                trusted_issuer=True,
                active=True,
                source_namespace=source,
                audience=policy.auth_audience,
                issued_at="2029-12-31T23:55:10Z",
                expires_at=SERVER_RECEIVED_AT,
            ),
            body_source_namespace=source,
            server_received_at=SERVER_RECEIVED_AT,
            clock_state="healthy",
            transport_is_https=True,
            policy=policy,
            time_policy=time_policy,
        )


def test_content_boundary_rejects_before_business_processing() -> None:
    _, policy = _documents()

    with pytest.raises(ContractError, match=EVENT_BODY_TOO_LARGE):
        validate_content_boundary(
            "application/json",
            b"x" * (policy.max_body_bytes + 1),
            1,
            policy,
        )


def test_policy_drift_fails_closed() -> None:
    time_policy = validate_time_policy(load_json(REPO_ROOT / TIME_POLICY_PATH))
    document = load_json(REPO_ROOT / POLICY_PATH)
    request = document["request"]
    assert isinstance(request, dict)
    request["max_body_bytes"] = 1_000_000

    with pytest.raises(ContractError, match=CONTRACT_POLICY_INVALID):
        validate_contract_policy(document, time_policy)
