"""V1 ANSVIS idempotency derivation aligned with the approved contract policy."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ansvis_adapter.application.ports import (
    AuthenticatedSource,
    FallbackIdempotencyKeyProvider,
    IdempotencyDeriver,
)
from ansvis_adapter.domain.errors import AnsvisAdapterError
from ansvis_adapter.domain.idempotency import (
    IdempotencyDescriptor,
    IdempotencyIdentityKind,
)
from ansvis_adapter.domain.models import EventAttributes, NormalizedAnsvisEvent


@dataclass(frozen=True, slots=True)
class IdempotencyPolicy:
    primary_version: str = "source_identity_v1"
    fallback_version: str = "ansvis_fallback_idempotency_v1"
    canonicalization_version: str = "camera_ai_canonical_json_v1"
    time_policy_version: str = "time_policy_v1"
    fallback_time_bucket_seconds: int = 1

    def __post_init__(self) -> None:
        if (
            self.primary_version != "source_identity_v1"
            or self.fallback_version != "ansvis_fallback_idempotency_v1"
            or self.canonicalization_version != "camera_ai_canonical_json_v1"
            or self.time_policy_version != "time_policy_v1"
            or self.fallback_time_bucket_seconds != 1
        ):
            raise ValueError("idempotency policy must match the approved V1 contract")


def _canonical_number(value: Decimal) -> str:
    if not value.is_finite():
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def canonical_json_bytes(value: object) -> bytes:
    """Serialize the restricted canonical V1 value set deterministically."""

    def encode(item: object) -> str:
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
                raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
            return (
                "{"
                + ",".join(
                    json.dumps(key, ensure_ascii=True) + ":" + encode(item[key])
                    for key in sorted(item)
                )
                + "}"
            )
        raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")

    return encode(value).encode("utf-8")


def _canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AnsvisAdapterError("TIME_SOURCE_UNHEALTHY")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_attributes(attributes: EventAttributes) -> dict[str, object]:
    result: dict[str, object] = {}
    for name in (
        "track_id",
        "detection_key",
        "subject_external_id",
        "status",
        "model_version",
        "config_version",
        "rule_code",
        "detection_count",
    ):
        value = getattr(attributes, name)
        if value is not None:
            result[name] = value.value if hasattr(value, "value") else value
    if attributes.confidence is not None:
        result["confidence"] = Decimal(str(attributes.confidence))
    return result


class ContractIdempotencyDeriver(IdempotencyDeriver):
    """Derive the exact source/fallback keys and fingerprint approved by contract V1."""

    def __init__(
        self,
        *,
        fallback_keys: FallbackIdempotencyKeyProvider,
        policy: IdempotencyPolicy | None = None,
    ) -> None:
        self._fallback_keys = fallback_keys
        self._policy = IdempotencyPolicy() if policy is None else policy

    def derive(
        self, event: NormalizedAnsvisEvent, source: AuthenticatedSource
    ) -> IdempotencyDescriptor:
        if (
            event.source_namespace != source.source_namespace
            or event.tenant_ref != source.tenant_ref
            or event.school_ref != source.school_ref
        ):
            raise AnsvisAdapterError("EVENT_SOURCE_MAPPING_DENIED")

        attributes = _canonical_attributes(event.attributes)
        occurred_at = _canonical_timestamp(event.occurred_at)
        if event.source_event_id is not None:
            identity_kind = IdempotencyIdentityKind.SOURCE
            projection: dict[str, object] = {
                "tenant_ref": source.tenant_ref,
                "source_namespace": source.source_namespace,
                "source_event_id": event.source_event_id,
            }
            idempotency_key = (
                "idem_source_v1_" + hashlib.sha256(canonical_json_bytes(projection)).hexdigest()
            )
        else:
            identity_kind = IdempotencyIdentityKind.FALLBACK
            track_id = event.attributes.track_id
            detection_key = event.attributes.detection_key
            if track_id is None or detection_key is None:
                raise AnsvisAdapterError("EVENT_FALLBACK_IDENTITY_INSUFFICIENT")
            try:
                key = self._fallback_keys.key_for(self._policy.fallback_version)
            except Exception:
                raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE") from None
            if key is None or not isinstance(key, bytes) or not 32 <= len(key) <= 128:
                raise AnsvisAdapterError("EVENT_DURABLE_RECEIPT_UNAVAILABLE")
            fallback_projection: dict[str, object] = {
                "version": self._policy.fallback_version,
                "tenant_ref": source.tenant_ref,
                "school_ref": source.school_ref,
                "source_namespace": source.source_namespace,
                "camera_external_id": event.camera_external_id,
                "task_external_id": event.task_external_id,
                "event_type": event.event_type.value,
                "event_time_bucket": str(
                    int(event.occurred_at.timestamp()) // self._policy.fallback_time_bucket_seconds
                ),
                "track_id": track_id,
                "detection_key": detection_key,
            }
            idempotency_key = (
                "idem_fallback_v1_"
                + hmac.digest(key, canonical_json_bytes(fallback_projection), "sha256").hex()
            )

        canonical_event: dict[str, object] = {
            "schema_version": "ansvis_canonical_event_v1",
            "source_namespace": event.source_namespace,
            "source_event_id": event.source_event_id,
            "event_type": event.event_type.value,
            "tenant_ref": event.tenant_ref,
            "school_ref": event.school_ref,
            "camera_external_id": event.camera_external_id,
            "task_external_id": event.task_external_id,
            "occurred_at": occurred_at,
            "attributes": attributes,
            "time_policy_version": self._policy.time_policy_version,
            "idempotency_key": idempotency_key,
        }
        fingerprint = "sha256:" + hashlib.sha256(canonical_json_bytes(canonical_event)).hexdigest()
        return IdempotencyDescriptor(
            identity_kind=identity_kind,
            idempotency_key=idempotency_key,
            canonical_fingerprint=fingerprint,
            canonicalization_version=self._policy.canonicalization_version,
        )
