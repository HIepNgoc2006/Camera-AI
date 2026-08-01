"""Validate the versioned ANSVIS event contract using sanitized deterministic fixtures."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import partial
from pathlib import Path
from typing import Never, TypeAlias

from scripts.check_time_policy import (
    TIME_EVENT_FUTURE,
    TIME_REPLAY_WINDOW_EXCEEDED,
    TIME_SOURCE_UNHEALTHY,
    TimePolicy,
    TimePolicyError,
    canonical_utc,
    evaluate_event_case,
    parse_rfc3339,
)
from scripts.check_time_policy import (
    validate_policy as validate_time_policy,
)

CONTRACT_DIR = Path("packages/ansvis-event-contract")
REQUEST_SCHEMA_PATH = CONTRACT_DIR / "http-trigger-request-v1.schema.json"
CANONICAL_SCHEMA_PATH = CONTRACT_DIR / "canonical-event-v1.schema.json"
RESPONSE_SCHEMA_PATH = CONTRACT_DIR / "http-trigger-response-v1.schema.json"
POLICY_PATH = CONTRACT_DIR / "http-trigger-policy-v1.json"
TIME_POLICY_PATH = Path("packages/time-policy/time-policy-v1.json")
EVENT_FIXTURE_PATH = Path("packages/test-fixtures/ansvis/event.synthetic.json")
CASE_FIXTURE_PATH = Path("packages/test-fixtures/ansvis/event-contract-cases.synthetic.json")

SYNTHETIC_MARKER = "SYNTHETIC_TEST_DATA_ONLY"
CONTRACT_VERSION = "ansvis_http_trigger_v1"
CANONICAL_VERSION = "ansvis_canonical_event_v1"
ACK_VERSION = "ansvis_http_trigger_ack_v1"
POLICY_VERSION = "ansvis_http_trigger_policy_v1"
TIME_POLICY_VERSION = "time_policy_v1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SAFE_INTEGER_MAX = 9_007_199_254_740_991

CONTRACT_POLICY_INVALID = "EVENT_CONTRACT_POLICY_INVALID"
EVENT_SCHEMA_INVALID = "EVENT_SCHEMA_INVALID"
EVENT_TYPE_UNSUPPORTED = "EVENT_TYPE_UNSUPPORTED"
EVENT_FALLBACK_IDENTITY_INSUFFICIENT = "EVENT_FALLBACK_IDENTITY_INSUFFICIENT"
EVENT_CONTENT_TYPE_UNSUPPORTED = "EVENT_CONTENT_TYPE_UNSUPPORTED"
EVENT_BODY_TOO_LARGE = "EVENT_BODY_TOO_LARGE"
EVENT_RATE_LIMITED = "EVENT_RATE_LIMITED"
EVENT_RATE_LIMIT_UNAVAILABLE = "EVENT_RATE_LIMIT_UNAVAILABLE"
EVENT_AUTH_TOKEN_EXPIRED = "EVENT_AUTH_TOKEN_EXPIRED"
EVENT_AUTH_TOKEN_INVALID = "EVENT_AUTH_TOKEN_INVALID"
EVENT_SOURCE_UNAUTHORIZED = "EVENT_SOURCE_UNAUTHORIZED"
EVENT_REPLAY_DETECTED = "EVENT_REPLAY_DETECTED"

ERROR_CODES = frozenset(
    {
        EVENT_BODY_TOO_LARGE,
        EVENT_CONTENT_TYPE_UNSUPPORTED,
        "EVENT_DURABLE_RECEIPT_UNAVAILABLE",
        EVENT_AUTH_TOKEN_EXPIRED,
        EVENT_AUTH_TOKEN_INVALID,
        EVENT_FALLBACK_IDENTITY_INSUFFICIENT,
        "EVENT_IDEMPOTENCY_CONFLICT",
        EVENT_RATE_LIMITED,
        EVENT_RATE_LIMIT_UNAVAILABLE,
        EVENT_REPLAY_DETECTED,
        EVENT_SCHEMA_INVALID,
        "EVENT_SOURCE_MAPPING_DENIED",
        EVENT_SOURCE_UNAUTHORIZED,
        EVENT_TYPE_UNSUPPORTED,
        TIME_EVENT_FUTURE,
        "TIME_FRACTION_PRECISION",
        "TIME_OFFSET_UNKNOWN",
        TIME_REPLAY_WINDOW_EXCEEDED,
        TIME_SOURCE_UNHEALTHY,
        "TIME_TIMESTAMP_INVALID",
        "TIME_TIMESTAMP_NAIVE",
    }
)

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "source_namespace",
        "source_event_id",
        "event_type",
        "tenant_ref",
        "school_ref",
        "camera_external_id",
        "task_external_id",
        "event_time",
        "correlation_id",
        "attributes",
    }
)
CANONICAL_FIELDS = frozenset(
    {
        "schema_version",
        "source_namespace",
        "source_event_id",
        "event_type",
        "tenant_ref",
        "school_ref",
        "camera_external_id",
        "task_external_id",
        "occurred_at",
        "correlation_id",
        "attributes",
        "idempotency_key",
        "canonical_fingerprint",
        "time_policy_version",
    }
)
ATTRIBUTE_FIELDS = frozenset(
    {
        "track_id",
        "detection_key",
        "subject_external_id",
        "confidence",
        "status",
        "model_version",
        "config_version",
        "rule_code",
        "detection_count",
    }
)
EVENT_TYPES = frozenset(
    {
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
)
HEALTH_EVENT_TYPES = frozenset({"camera.health.changed", "task.health.changed"})
HEALTH_STATES = frozenset({"delayed", "offline", "online", "running", "stopped", "unknown"})
FORBIDDEN_FIELDS = frozenset(
    {
        "authorization",
        "camera_address",
        "cookie",
        "face_embedding",
        "image",
        "image_base64",
        "media_url",
        "password",
        "private_key",
        "raw_payload",
        "rtsp_url",
        "token",
        "video",
        "video_base64",
    }
)
PROCESSING_ORDER = [
    "capture_trusted_receipt_time_and_request_id",
    "verify_receiver_clock_health",
    "enforce_content_type_body_size_and_rate_limit",
    "authenticate_source_and_bearer_token",
    "validate_event_timestamp_and_replay_nonce",
    "validate_schema_event_time_and_event_type",
    "validate_source_camera_task_mapping",
    "derive_idempotency_and_canonical_fingerprint",
    "commit_durable_receipt_before_ack",
]
HTTP_OUTCOMES: dict[str, object] = {
    "accepted": 202,
    "duplicate": 200,
    "schema_invalid": 422,
    "authentication_failed": 401,
    "replay_or_conflict": 409,
    "unsupported_content_type": 415,
    "body_too_large": 413,
    "rate_limited": 429,
    "durable_receipt_unavailable": 503,
}
STABLE_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
STABLE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
EXTERNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CORRELATION_ID = re.compile(r"^corr_[A-Za-z0-9_-]{8,120}$")
REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
RECEIPT_ID = re.compile(r"^receipt_[A-Za-z0-9_-]{8,120}$")
IDEMPOTENCY_KEY = re.compile(r"^idem_(?:source|fallback)_v1_[0-9a-f]{64}$")
FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")
BEARER_TOKEN = re.compile(r"^Bearer [A-Za-z0-9._~-]{32,2048}$")

# OpenGrep 1.22 only partially parses the equivalent Python 3.12 PEP 695 syntax.
JsonValue: TypeAlias = object  # noqa: UP040
JsonObject: TypeAlias = dict[str, object]  # noqa: UP040


class ContractError(ValueError):
    """Fail with a stable code and never retain rejected content in the exception."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str = EVENT_SCHEMA_INVALID) -> Never:
    raise ContractError(code)


def _reject_constant(_: str) -> Never:
    _fail()


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def load_json_bytes(data: bytes) -> JsonValue:
    """Parse strict JSON with duplicate-name and non-finite-number rejection."""

    try:
        decoded = data.decode("utf-8", errors="strict")
        value: JsonValue = json.loads(
            decoded,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, InvalidOperation):
        _fail()
    return value


def load_json(path: Path) -> JsonObject:
    try:
        value = load_json_bytes(path.read_bytes())
    except OSError:
        _fail(CONTRACT_POLICY_INVALID)
    return _mapping(value, CONTRACT_POLICY_INVALID)


def _mapping(value: JsonValue | object, code: str = EVENT_SCHEMA_INVALID) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(code)
    return value


def _list(value: JsonValue | object, code: str = EVENT_SCHEMA_INVALID) -> list[JsonValue]:
    if not isinstance(value, list):
        _fail(code)
    return value


def _text(value: JsonValue | object, code: str = EVENT_SCHEMA_INVALID) -> str:
    if not isinstance(value, str):
        _fail(code)
    return value


def _integer(value: JsonValue | object, code: str = EVENT_SCHEMA_INVALID) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(code)
    return value


def _decimal(value: JsonValue | object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        _fail()
    result = Decimal(value)
    if not result.is_finite():
        _fail()
    return result


def _string_list(value: JsonValue | object, code: str = CONTRACT_POLICY_INVALID) -> list[str]:
    return [_text(item, code) for item in _list(value, code)]


def _canonical_number(value: Decimal) -> str:
    if not value.is_finite():
        _fail()
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Serialize the restricted V1 value set deterministically for hashing."""

    def encode(item: JsonValue) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int):
            return str(item)
        if isinstance(item, Decimal):
            return _canonical_number(item)
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=True, allow_nan=False)
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict):
            if any(not isinstance(key, str) or not key.isascii() for key in item):
                _fail()
            return (
                "{"
                + ",".join(
                    json.dumps(key, ensure_ascii=True) + ":" + encode(item[key])
                    for key in sorted(item)
                )
                + "}"
            )
        _fail()

    return encode(value).encode("utf-8")


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _external_id(value: JsonValue | object) -> str:
    if isinstance(value, bool):
        _fail()
    if isinstance(value, int):
        if value < 0 or value > SAFE_INTEGER_MAX:
            _fail()
        return str(value)
    if isinstance(value, str) and EXTERNAL_ID.fullmatch(value) is not None:
        return value
    _fail()


def _stable_ref(value: JsonValue | object) -> str:
    text = _text(value)
    if STABLE_REF.fullmatch(text) is None:
        _fail()
    return text


def _stable_code(value: JsonValue | object) -> str:
    text = _text(value)
    if STABLE_CODE.fullmatch(text) is None:
        _fail()
    return text


@dataclass(frozen=True, slots=True)
class ContractPolicy:
    policy_version: str
    method: str
    path: str
    content_types: frozenset[str]
    max_body_bytes: int
    auth_audience: str
    max_access_token_lifetime_seconds: int
    event_types: frozenset[str]
    attribute_allowlist: frozenset[str]
    sustained_requests_per_second: int
    burst_requests: int


def validate_contract_policy(document: JsonObject, time_policy: TimePolicy) -> ContractPolicy:
    expected_top = {
        "policy_id",
        "policy_version",
        "status",
        "owner_code",
        "approver_code",
        "purpose_code",
        "data_class",
        "effective_at",
        "expiry_trigger",
        "terminal_action",
        "request",
        "authentication",
        "time",
        "rate_limit",
        "idempotency",
        "event_types",
        "attribute_allowlist",
        "forbidden_fields_recursive",
        "processing_order",
        "http_outcomes",
    }
    fixed = {
        "policy_id": "ansvis_http_trigger",
        "policy_version": POLICY_VERSION,
        "status": "active",
        "owner_code": "ansvis_integration",
        "approver_code": "project_owner",
        "purpose_code": "event_ingestion",
        "data_class": "high",
        "expiry_trigger": "superseded_or_security_change",
        "terminal_action": "retire_and_replace",
    }
    if set(document) != expected_top or any(
        document.get(key) != value for key, value in fixed.items()
    ):
        _fail(CONTRACT_POLICY_INVALID)
    try:
        parse_rfc3339(document.get("effective_at"), 6)
    except TimePolicyError:
        _fail(CONTRACT_POLICY_INVALID)

    request = _mapping(document.get("request"), CONTRACT_POLICY_INVALID)
    if request != {
        "method": "POST",
        "path": "/integration/ansvis/events",
        "content_types": ["application/json"],
        "max_body_bytes": 65_536,
    }:
        _fail(CONTRACT_POLICY_INVALID)

    authentication = _mapping(document.get("authentication"), CONTRACT_POLICY_INVALID)
    if authentication != {
        "scheme": "ansvis-login-bearer-v1",
        "transport": "https_required",
        "integration_mode": "ansvis_login_required",
        "authorization_header": "Authorization",
        "token_prefix": "Bearer ",
        "token_verification": "signature_or_active_introspection",
        "required_security_properties": [
            "trusted_issuer",
            "ingestion_audience",
            "registered_source_subject",
            "issued_at",
            "expires_at",
            "revocable_token_id",
        ],
        "audience": "camera-ai-ansvis-ingestion",
        "max_access_token_lifetime_seconds": 300,
        "credential_handling": "dedicated_source_credential_outside_contract",
        "source_mapping": "verified_token_subject_to_registered_source",
    }:
        _fail(CONTRACT_POLICY_INVALID)

    time = _mapping(document.get("time"), CONTRACT_POLICY_INVALID)
    if time != {
        "policy_version": time_policy.policy_version,
        "future_tolerance_seconds": 30,
        "replay_window_seconds": 300,
        "replay_nonce_field": "source_event_id",
        "fallback_replay_identity": "versioned_keyed_idempotency",
        "critical_clock_state": "fail_closed",
    }:
        _fail(CONTRACT_POLICY_INVALID)

    rate = _mapping(document.get("rate_limit"), CONTRACT_POLICY_INVALID)
    if rate != {
        "scope": "source_namespace",
        "sustained_requests_per_second": 50,
        "burst_requests": 200,
        "rejection_status": 429,
    }:
        _fail(CONTRACT_POLICY_INVALID)

    idempotency = _mapping(document.get("idempotency"), CONTRACT_POLICY_INVALID)
    required_fallback = [
        "tenant_ref",
        "school_ref",
        "source_namespace",
        "camera_external_id",
        "task_external_id",
        "event_type",
        "event_time",
        "attributes.track_id",
        "attributes.detection_key",
    ]
    if idempotency != {
        "primary_version": "source_identity_v1",
        "primary_fields": ["tenant_ref", "source_namespace", "source_event_id"],
        "fallback_version": "ansvis_fallback_idempotency_v1",
        "fallback_algorithm": "hmac-sha256",
        "fallback_key_source": "approved_secret_manager_reference",
        "fallback_time_bucket_seconds": 1,
        "fallback_required_fields": required_fallback,
        "canonicalization_version": "camera_ai_canonical_json_v1",
        "fingerprint_algorithm": "sha256",
        "fingerprint_excluded_fields": ["correlation_id"],
        "identical_duplicate_outcome": "duplicate",
        "conflicting_duplicate_outcome": "reject_and_quarantine",
    }:
        _fail(CONTRACT_POLICY_INVALID)

    event_types = frozenset(_string_list(document.get("event_types")))
    attributes = frozenset(_string_list(document.get("attribute_allowlist")))
    if event_types != EVENT_TYPES or attributes != ATTRIBUTE_FIELDS:
        _fail(CONTRACT_POLICY_INVALID)
    forbidden = frozenset(_string_list(document.get("forbidden_fields_recursive")))
    if forbidden != FORBIDDEN_FIELDS:
        _fail(CONTRACT_POLICY_INVALID)
    if _string_list(document.get("processing_order")) != PROCESSING_ORDER:
        _fail(CONTRACT_POLICY_INVALID)
    outcomes = _mapping(document.get("http_outcomes"), CONTRACT_POLICY_INVALID)
    if outcomes != HTTP_OUTCOMES:
        _fail(CONTRACT_POLICY_INVALID)

    return ContractPolicy(
        policy_version=POLICY_VERSION,
        method="POST",
        path="/integration/ansvis/events",
        content_types=frozenset({"application/json"}),
        max_body_bytes=65_536,
        auth_audience="camera-ai-ansvis-ingestion",
        max_access_token_lifetime_seconds=300,
        event_types=event_types,
        attribute_allowlist=attributes,
        sustained_requests_per_second=_integer(rate["sustained_requests_per_second"]),
        burst_requests=_integer(rate["burst_requests"]),
    )


def validate_schema_documents(
    request_schema: JsonObject,
    canonical_schema: JsonObject,
    response_schema: JsonObject,
    policy: ContractPolicy,
) -> None:
    if (
        request_schema.get("$schema") != SCHEMA_DIALECT
        or request_schema.get("additionalProperties") is not False
        or frozenset(_string_list(request_schema.get("required"))) != TOP_LEVEL_FIELDS
    ):
        _fail(CONTRACT_POLICY_INVALID)
    request_properties = _mapping(request_schema.get("properties"), CONTRACT_POLICY_INVALID)
    event_type = _mapping(request_properties.get("event_type"), CONTRACT_POLICY_INVALID)
    attributes = _mapping(request_properties.get("attributes"), CONTRACT_POLICY_INVALID)
    attribute_properties = _mapping(attributes.get("properties"), CONTRACT_POLICY_INVALID)
    expected_conditionals: list[JsonValue] = [
        {
            "if": {
                "properties": {"event_type": {"enum": sorted(HEALTH_EVENT_TYPES)}},
                "required": ["event_type"],
            },
            "then": {"properties": {"attributes": {"required": ["status"]}}},
        },
        {
            "if": {
                "properties": {"source_event_id": {"type": "null"}},
                "required": ["source_event_id"],
            },
            "then": {"properties": {"attributes": {"required": ["track_id", "detection_key"]}}},
        },
    ]
    if (
        frozenset(_string_list(event_type.get("enum"))) != policy.event_types
        or attributes.get("additionalProperties") is not False
        or frozenset(attribute_properties) != policy.attribute_allowlist
        or canonical_json_bytes(_list(request_schema.get("allOf")))
        != canonical_json_bytes(expected_conditionals)
    ):
        _fail(CONTRACT_POLICY_INVALID)

    if (
        canonical_schema.get("$schema") != SCHEMA_DIALECT
        or canonical_schema.get("additionalProperties") is not False
        or frozenset(_string_list(canonical_schema.get("required"))) != CANONICAL_FIELDS
    ):
        _fail(CONTRACT_POLICY_INVALID)
    canonical_properties = _mapping(canonical_schema.get("properties"), CONTRACT_POLICY_INVALID)
    canonical_event_type = _mapping(canonical_properties.get("event_type"), CONTRACT_POLICY_INVALID)
    canonical_attributes = _mapping(canonical_properties.get("attributes"), CONTRACT_POLICY_INVALID)
    canonical_attribute_properties = _mapping(
        canonical_attributes.get("properties"), CONTRACT_POLICY_INVALID
    )
    if (
        frozenset(_string_list(canonical_event_type.get("enum"))) != policy.event_types
        or canonical_attributes.get("additionalProperties") is not False
        or frozenset(canonical_attribute_properties) != policy.attribute_allowlist
        or canonical_json_bytes(_list(canonical_schema.get("allOf")))
        != canonical_json_bytes(expected_conditionals)
    ):
        _fail(CONTRACT_POLICY_INVALID)

    if response_schema.get("$schema") != SCHEMA_DIALECT:
        _fail(CONTRACT_POLICY_INVALID)
    variants = _list(response_schema.get("oneOf"), CONTRACT_POLICY_INVALID)
    if len(variants) != 2:
        _fail(CONTRACT_POLICY_INVALID)
    error_variant = _mapping(variants[1], CONTRACT_POLICY_INVALID)
    error_properties = _mapping(error_variant.get("properties"), CONTRACT_POLICY_INVALID)
    error_code = _mapping(error_properties.get("error_code"), CONTRACT_POLICY_INVALID)
    if frozenset(_string_list(error_code.get("enum"))) != ERROR_CODES:
        _fail(CONTRACT_POLICY_INVALID)


def validate_content_boundary(
    content_type: str,
    body: bytes,
    requests_in_window: int,
    policy: ContractPolicy,
) -> None:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized not in policy.content_types:
        _fail(EVENT_CONTENT_TYPE_UNSUPPORTED)
    if len(body) > policy.max_body_bytes:
        _fail(EVENT_BODY_TOO_LARGE)
    if requests_in_window > policy.burst_requests:
        _fail(EVENT_RATE_LIMITED)


def _validate_attributes(value: JsonValue, event_type: str, policy: ContractPolicy) -> JsonObject:
    attributes = _mapping(value)
    if not set(attributes).issubset(policy.attribute_allowlist) or len(attributes) > 9:
        _fail()
    normalized: JsonObject = {}
    for key, child in attributes.items():
        if key in {"track_id", "subject_external_id"}:
            normalized[key] = _external_id(child)
        elif key == "detection_key":
            normalized[key] = _stable_ref(child)
        elif key == "confidence":
            confidence = _decimal(child)
            exponent = confidence.as_tuple().exponent
            if not isinstance(exponent, int):
                _fail()
            fractional_digits = max(0, -exponent)
            if confidence < 0 or confidence > 1 or fractional_digits > 6:
                _fail()
            normalized[key] = confidence
        elif key == "status":
            status = _text(child)
            if status not in HEALTH_STATES:
                _fail()
            normalized[key] = status
        elif key in {"model_version", "config_version", "rule_code"}:
            normalized[key] = _stable_code(child)
        elif key == "detection_count":
            count = _integer(child)
            if count < 0 or count > 1000:
                _fail()
            normalized[key] = count
        else:
            _fail()
    if event_type in HEALTH_EVENT_TYPES and "status" not in normalized:
        _fail()
    return normalized


def _idempotency_key(
    event: JsonObject,
    normalized_attributes: JsonObject,
    occurred_at: datetime,
    fallback_key: bytes,
) -> str:
    source_event_id = event.get("source_event_id")
    if source_event_id is not None:
        projection: JsonObject = {
            "tenant_ref": _stable_ref(event.get("tenant_ref")),
            "source_namespace": _stable_code(event.get("source_namespace")),
            "source_event_id": _external_id(source_event_id),
        }
        return "idem_source_v1_" + _sha256_hex(canonical_json_bytes(projection))

    if "track_id" not in normalized_attributes or "detection_key" not in normalized_attributes:
        _fail(EVENT_FALLBACK_IDENTITY_INSUFFICIENT)
    fallback_projection: JsonObject = {
        "version": "ansvis_fallback_idempotency_v1",
        "tenant_ref": _stable_ref(event.get("tenant_ref")),
        "school_ref": _stable_ref(event.get("school_ref")),
        "source_namespace": _stable_code(event.get("source_namespace")),
        "camera_external_id": _external_id(event.get("camera_external_id")),
        "task_external_id": _external_id(event.get("task_external_id")),
        "event_type": _text(event.get("event_type")),
        "event_time_bucket": str(int(occurred_at.timestamp())),
        "track_id": normalized_attributes["track_id"],
        "detection_key": normalized_attributes["detection_key"],
    }
    digest = hmac.new(fallback_key, canonical_json_bytes(fallback_projection), hashlib.sha256)
    return "idem_fallback_v1_" + digest.hexdigest()


def validate_request(
    document: JsonObject,
    *,
    server_received_at: str,
    policy: ContractPolicy,
    time_policy: TimePolicy,
    fallback_key: bytes,
) -> JsonObject:
    if set(document) != TOP_LEVEL_FIELDS or document.get("schema_version") != CONTRACT_VERSION:
        _fail()
    source_namespace = _stable_code(document.get("source_namespace"))
    source_event_value = document.get("source_event_id")
    source_event_id = None if source_event_value is None else _external_id(source_event_value)
    event_type = _text(document.get("event_type"))
    if event_type not in policy.event_types:
        _fail(EVENT_TYPE_UNSUPPORTED)
    correlation_id = _text(document.get("correlation_id"))
    if CORRELATION_ID.fullmatch(correlation_id) is None:
        _fail()
    attributes = _validate_attributes(document.get("attributes"), event_type, policy)

    event_time_value = document.get("event_time")
    result, detail = evaluate_event_case(
        {
            "vendor_event_time": event_time_value,
            "server_received_at": server_received_at,
        },
        time_policy,
    )
    if result != "accept":
        _fail(detail)
    try:
        occurred_at = parse_rfc3339(event_time_value, time_policy.max_fractional_digits)
    except TimePolicyError as error:
        _fail(error.code)

    normalized: JsonObject = {
        "schema_version": CANONICAL_VERSION,
        "source_namespace": source_namespace,
        "source_event_id": source_event_id,
        "event_type": event_type,
        "tenant_ref": _stable_ref(document.get("tenant_ref")),
        "school_ref": _stable_ref(document.get("school_ref")),
        "camera_external_id": _external_id(document.get("camera_external_id")),
        "task_external_id": _external_id(document.get("task_external_id")),
        "occurred_at": canonical_utc(occurred_at),
        "correlation_id": correlation_id,
        "attributes": attributes,
        "time_policy_version": time_policy.policy_version,
    }
    normalized["idempotency_key"] = _idempotency_key(
        document, attributes, occurred_at, fallback_key
    )
    fingerprint_projection = dict(normalized)
    fingerprint_projection.pop("correlation_id")
    normalized["canonical_fingerprint"] = "sha256:" + _sha256_hex(
        canonical_json_bytes(fingerprint_projection)
    )
    validate_canonical_event(normalized, policy)
    return normalized


def validate_canonical_event(document: JsonObject, policy: ContractPolicy) -> None:
    if set(document) != CANONICAL_FIELDS or document.get("schema_version") != CANONICAL_VERSION:
        _fail()
    if document.get("time_policy_version") != TIME_POLICY_VERSION:
        _fail()
    if _text(document.get("event_type")) not in policy.event_types:
        _fail(EVENT_TYPE_UNSUPPORTED)
    if IDEMPOTENCY_KEY.fullmatch(_text(document.get("idempotency_key"))) is None:
        _fail()
    if FINGERPRINT.fullmatch(_text(document.get("canonical_fingerprint"))) is None:
        _fail()
    _validate_attributes(
        _mapping(document.get("attributes")), _text(document.get("event_type")), policy
    )


@dataclass(frozen=True, slots=True)
class VerifiedSourceAuth:
    valid: bool
    trusted_issuer: bool
    active: bool
    source_namespace: str
    audience: str
    issued_at: str
    expires_at: str


def verify_source_auth(
    *,
    authorization_header: str,
    verified_auth: VerifiedSourceAuth,
    body_source_namespace: str,
    server_received_at: str,
    clock_state: str,
    transport_is_https: bool,
    policy: ContractPolicy,
    time_policy: TimePolicy,
) -> None:
    if clock_state == "critical":
        _fail(TIME_SOURCE_UNHEALTHY)
    if not transport_is_https:
        _fail(EVENT_SOURCE_UNAUTHORIZED)
    if (
        BEARER_TOKEN.fullmatch(authorization_header) is None
        or not verified_auth.valid
        or not verified_auth.trusted_issuer
        or not verified_auth.active
        or verified_auth.audience != policy.auth_audience
    ):
        _fail(EVENT_AUTH_TOKEN_INVALID)
    if STABLE_CODE.fullmatch(verified_auth.source_namespace) is None:
        _fail(EVENT_SOURCE_UNAUTHORIZED)
    try:
        issued_at = parse_rfc3339(verified_auth.issued_at, time_policy.max_fractional_digits)
        expires_at = parse_rfc3339(verified_auth.expires_at, time_policy.max_fractional_digits)
        received_at = parse_rfc3339(server_received_at, time_policy.max_fractional_digits)
    except TimePolicyError:
        _fail(EVENT_AUTH_TOKEN_INVALID)
    if expires_at <= received_at:
        _fail(EVENT_AUTH_TOKEN_EXPIRED)
    if (
        issued_at > received_at + timedelta(seconds=time_policy.future_tolerance_seconds)
        or expires_at <= issued_at
        or (expires_at - issued_at).total_seconds() > policy.max_access_token_lifetime_seconds
    ):
        _fail(EVENT_AUTH_TOKEN_INVALID)
    if verified_auth.source_namespace != body_source_namespace:
        _fail(EVENT_SOURCE_UNAUTHORIZED)


def validate_response(document: JsonObject) -> None:
    if "outcome" in document:
        if set(document) != {
            "schema_version",
            "outcome",
            "receipt_id",
            "request_id",
            "correlation_id",
        }:
            _fail()
        if document.get("schema_version") != ACK_VERSION or document.get("outcome") not in {
            "accepted",
            "duplicate",
        }:
            _fail()
        if RECEIPT_ID.fullmatch(_text(document.get("receipt_id"))) is None:
            _fail()
        if REQUEST_ID.fullmatch(_text(document.get("request_id"))) is None:
            _fail()
        if CORRELATION_ID.fullmatch(_text(document.get("correlation_id"))) is None:
            _fail()
        return
    if set(document) != {"error_code", "message", "request_id"}:
        _fail()
    if _text(document.get("error_code")) not in ERROR_CODES:
        _fail()
    message = _text(document.get("message"))
    if (
        not 1 <= len(message) <= 160
        or REQUEST_ID.fullmatch(_text(document.get("request_id"))) is None
    ):
        _fail()


def _set_path(document: JsonObject, dotted_path: str, value: JsonValue) -> None:
    parts = dotted_path.split(".")
    target = document
    for part in parts[:-1]:
        target = _mapping(target.get(part))
    target[parts[-1]] = value


def _remove_path(document: JsonObject, dotted_path: str) -> None:
    parts = dotted_path.split(".")
    target = document
    for part in parts[:-1]:
        target = _mapping(target.get(part))
    target.pop(parts[-1], None)


def _mutated(base: JsonObject, case: JsonObject) -> JsonObject:
    document = copy.deepcopy(base)
    for path, value in _mapping(case.get("set", {})).items():
        _set_path(document, path, value)
    for path in _string_list(case.get("remove", []), EVENT_SCHEMA_INVALID):
        _remove_path(document, path)
    return document


def _expected_case(case: JsonObject, operation: Callable[[], object]) -> object | None:
    expected = _text(case.get("expected_result"))
    try:
        result = operation()
    except ContractError as error:
        if expected != "reject" or error.code != _text(case.get("expected_error_code")):
            _fail(CONTRACT_POLICY_INVALID)
        return None
    if expected != "accept":
        _fail(CONTRACT_POLICY_INVALID)
    return result


def validate_fixtures(
    event_fixture: JsonObject,
    cases_fixture: JsonObject,
    policy: ContractPolicy,
    time_policy: TimePolicy,
) -> int:
    if (
        event_fixture.get("_fixture") != SYNTHETIC_MARKER
        or event_fixture.get("contract_version") != CONTRACT_VERSION
        or cases_fixture.get("_fixture") != SYNTHETIC_MARKER
        or cases_fixture.get("contract_version") != CONTRACT_VERSION
    ):
        _fail(CONTRACT_POLICY_INVALID)
    base = _mapping(event_fixture.get("request"))
    server_received_at = _text(cases_fixture.get("server_received_at"))
    test_key = bytes(range(32))
    count = 0
    accepted_event_types: set[str] = set()

    schema_cases = _list(cases_fixture.get("schema_cases"), CONTRACT_POLICY_INVALID)
    for item in schema_cases:
        case = _mapping(item, CONTRACT_POLICY_INVALID)
        document = _mutated(base, case)
        result = _expected_case(
            case,
            partial(
                validate_request,
                document,
                server_received_at=server_received_at,
                policy=policy,
                time_policy=time_policy,
                fallback_key=test_key,
            ),
        )
        if result is not None:
            accepted_event_types.add(
                _text(_mapping(result, CONTRACT_POLICY_INVALID).get("event_type"))
            )
        count += 1
    if accepted_event_types != policy.event_types:
        _fail(CONTRACT_POLICY_INVALID)

    raw_body = canonical_json_bytes(base)
    auth_cases = _list(cases_fixture.get("auth_cases"), CONTRACT_POLICY_INVALID)
    for item in auth_cases:
        case = _mapping(item, CONTRACT_POLICY_INVALID)
        auth_state = _text(case.get("auth_state"), CONTRACT_POLICY_INVALID)
        if auth_state not in {"valid", "invalid"}:
            _fail(CONTRACT_POLICY_INVALID)
        verified_auth = VerifiedSourceAuth(
            valid=auth_state == "valid",
            trusted_issuer=True,
            active=True,
            source_namespace=_text(case.get("authenticated_source"), CONTRACT_POLICY_INVALID),
            audience=policy.auth_audience,
            issued_at=_text(case.get("issued_at"), CONTRACT_POLICY_INVALID),
            expires_at=_text(case.get("expires_at"), CONTRACT_POLICY_INVALID),
        )
        _expected_case(
            case,
            partial(
                verify_source_auth,
                authorization_header="Bearer fixture_" + "x" * 32,
                verified_auth=verified_auth,
                body_source_namespace=_text(base["source_namespace"]),
                server_received_at=server_received_at,
                clock_state="healthy",
                transport_is_https=case.get("https") is True,
                policy=policy,
                time_policy=time_policy,
            ),
        )
        count += 1

    idempotency_cases = _list(cases_fixture.get("idempotency_cases"), CONTRACT_POLICY_INVALID)
    for item in idempotency_cases:
        case = _mapping(item, CONTRACT_POLICY_INVALID)
        first_request = copy.deepcopy(base)
        if "source_event_id" in case:
            first_request["source_event_id"] = case["source_event_id"]
        second_request = copy.deepcopy(first_request)
        second_request["correlation_id"] = case["second_correlation_id"]
        if "second_status" in case:
            _mapping(second_request["attributes"])["status"] = case["second_status"]
        first = validate_request(
            first_request,
            server_received_at=server_received_at,
            policy=policy,
            time_policy=time_policy,
            fallback_key=test_key,
        )
        second = validate_request(
            second_request,
            server_received_at=server_received_at,
            policy=policy,
            time_policy=time_policy,
            fallback_key=test_key,
        )
        same_identity = first["idempotency_key"] == second["idempotency_key"]
        same_content = first["canonical_fingerprint"] == second["canonical_fingerprint"]
        outcome = "duplicate" if same_identity and same_content else "conflict"
        if outcome != _text(case.get("expected_outcome")):
            _fail(CONTRACT_POLICY_INVALID)
        count += 1

    response_cases = _list(cases_fixture.get("response_cases"), CONTRACT_POLICY_INVALID)
    for item in response_cases:
        case = _mapping(item, CONTRACT_POLICY_INVALID)
        response = _mapping(case.get("response"), CONTRACT_POLICY_INVALID)
        _expected_case(case, partial(validate_response, response))
        count += 1

    boundary_cases = (
        ("application/json", raw_body, 1, "accept"),
        ("text/plain", raw_body, 1, EVENT_CONTENT_TYPE_UNSUPPORTED),
        ("application/json", b"x" * (policy.max_body_bytes + 1), 1, EVENT_BODY_TOO_LARGE),
        ("application/json", raw_body, policy.burst_requests + 1, EVENT_RATE_LIMITED),
    )
    for content_type, body, request_count, expected in boundary_cases:
        try:
            validate_content_boundary(content_type, body, request_count, policy)
        except ContractError as error:
            if error.code != expected:
                _fail(CONTRACT_POLICY_INVALID)
        else:
            if expected != "accept":
                _fail(CONTRACT_POLICY_INVALID)
        count += 1
    return count


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        time_policy = validate_time_policy(load_json(repo_root / TIME_POLICY_PATH))
        policy = validate_contract_policy(load_json(repo_root / POLICY_PATH), time_policy)
        validate_schema_documents(
            load_json(repo_root / REQUEST_SCHEMA_PATH),
            load_json(repo_root / CANONICAL_SCHEMA_PATH),
            load_json(repo_root / RESPONSE_SCHEMA_PATH),
            policy,
        )
        count = validate_fixtures(
            load_json(repo_root / EVENT_FIXTURE_PATH),
            load_json(repo_root / CASE_FIXTURE_PATH),
            policy,
            time_policy,
        )
    except (ContractError, TimePolicyError) as error:
        code = error.code
        print(f"ansvis_contract=FAIL code={code}", file=sys.stderr)
        return 1
    print("ansvis_contract=PASS")
    print(f"policy_version={policy.policy_version}")
    print(f"synthetic_cases_checked={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
