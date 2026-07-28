"""Fail-closed Evidence Storage configuration without secret rendering."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from evidence_service.domain.capacity import AttachmentRatioPolicy
from evidence_service.domain.errors import EvidenceError
from evidence_service.infrastructure.object_storage import validate_storage_endpoint


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    database_url: str

    def __repr__(self) -> str:
        return "DatabaseSettings(database_url=<redacted>)"


@dataclass(frozen=True, slots=True)
class ObjectStorageSettings:
    endpoint: str
    secure: bool
    bucket_ref: str
    access_key_env_ref: str
    secret_key_env_ref: str

    def __repr__(self) -> str:
        return (
            "ObjectStorageSettings("
            f"endpoint={self.endpoint!r}, secure={self.secure!r}, "
            f"bucket_ref={self.bucket_ref!r}, credentials=<redacted>)"
        )


def load_attachment_ratio_policy() -> AttachmentRatioPolicy:
    try:
        expected = float(os.environ["EVIDENCE_EXPECTED_ATTACHMENT_RATIO"])
        threshold = float(os.environ["EVIDENCE_ATTACHMENT_RATIO_ALERT_THRESHOLD"])
        minimum_window = int(os.environ.get("EVIDENCE_ATTACHMENT_RATIO_MINIMUM_WINDOW", "100"))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise EvidenceError("EVIDENCE_CAPACITY_CONFIGURATION_INVALID") from None
    return AttachmentRatioPolicy(
        expected_ratio=expected,
        alert_threshold=threshold,
        minimum_window_events=minimum_window,
    )


def load_database_settings() -> DatabaseSettings:
    value = os.environ.get("EVIDENCE_DATABASE_URI", "")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID") from None
    if parsed.scheme != "postgresql+psycopg" or not parsed.hostname or not parsed.path.strip("/"):
        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
    return DatabaseSettings(database_url=value)


def load_object_storage_settings() -> ObjectStorageSettings:
    endpoint = os.environ.get("EVIDENCE_S3_ENDPOINT", "")
    secure_value = os.environ.get("EVIDENCE_S3_SECURE", "")
    bucket_ref = os.environ.get("EVIDENCE_S3_BUCKET_REF", "")
    if secure_value not in {"true", "false"} or bucket_ref != "evidence-private-v1":
        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
    secure = secure_value == "true"
    return ObjectStorageSettings(
        endpoint=validate_storage_endpoint(endpoint, secure=secure),
        secure=secure,
        bucket_ref=bucket_ref,
        access_key_env_ref="EVIDENCE_S3_ACCESS_KEY",
        secret_key_env_ref="EVIDENCE_S3_SECRET_KEY",
    )
