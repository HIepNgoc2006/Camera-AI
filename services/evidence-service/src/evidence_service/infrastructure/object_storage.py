"""MinIO/S3 private object storage adapter with bounded signed requests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit

from minio import Minio
from minio.commonconfig import ENABLED, Filter, Tag
from minio.datatypes import PostPolicy
from minio.error import S3Error
from minio.lifecycleconfig import (
    AbortIncompleteMultipartUpload,
    Expiration,
    LifecycleConfig,
    Rule,
)
from minio.versioningconfig import VersioningConfig

from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.media import probe_header
from evidence_service.domain.models import MediaKind, StoredObjectFacts


def validate_storage_endpoint(endpoint: str, *, secure: bool) -> str:
    try:
        parsed = urlsplit(("https://" if secure else "http://") + endpoint)
    except ValueError:
        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID") from None
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
    if not secure and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
    return endpoint


class MinioPrivateObjectStorage:
    def __init__(
        self,
        client: Minio,
        *,
        allowed_bucket_refs: frozenset[str],
        upload_origin: str,
        expected_lifecycle_days: frozenset[int],
    ) -> None:
        if (
            not allowed_bucket_refs
            or not expected_lifecycle_days
            or any(days < 1 for days in expected_lifecycle_days)
        ):
            raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
        try:
            parsed_origin = urlsplit(upload_origin)
        except ValueError:
            raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID") from None
        if (
            parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.hostname
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
            or (
                parsed_origin.scheme == "http"
                and parsed_origin.hostname not in {"127.0.0.1", "localhost", "::1"}
            )
        ):
            raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
        self._client = client
        self._allowed_bucket_refs = allowed_bucket_refs
        self._upload_origin = upload_origin.rstrip("/")
        self._expected_lifecycle_days = expected_lifecycle_days

    def _bucket(self, bucket_ref: str) -> str:
        if bucket_ref not in self._allowed_bucket_refs:
            raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
        return bucket_ref

    def verify_private_bucket(self, bucket_ref: str) -> None:
        bucket = self._bucket(bucket_ref)
        try:
            if not self._client.bucket_exists(bucket):
                raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE")
            try:
                policy_document = self._client.get_bucket_policy(bucket)
            except S3Error as exc:
                if exc.code in {"NoSuchBucketPolicy", "NoSuchPolicy"}:
                    policy_document = ""
                else:
                    raise
            if policy_document:
                policy = json.loads(policy_document)
                statements = policy.get("Statement", [])
                if not isinstance(statements, list):
                    raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
                for statement in statements:
                    principal = statement.get("Principal") if isinstance(statement, dict) else None
                    if (
                        isinstance(statement, dict)
                        and statement.get("Effect") == "Allow"
                        and (
                            principal == "*"
                            or (isinstance(principal, dict) and principal.get("AWS") == "*")
                        )
                    ):
                        raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
            versioning = self._client.get_bucket_versioning(bucket)
            if getattr(versioning, "status", None) != "Enabled":
                raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
            lifecycle = self._client.get_bucket_lifecycle(bucket)
            rules = getattr(lifecycle, "rules", None)
            if not rules:
                raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
            enabled_expirations = {
                (days, getattr(tag, "key", None), getattr(tag, "value", None))
                for rule in rules
                if getattr(rule, "status", None) == "Enabled"
                for days in (getattr(getattr(rule, "expiration", None), "days", None),)
                for tag in (getattr(getattr(rule, "rule_filter", None), "tag", None),)
                if isinstance(days, int)
            }
            expected = {
                (days, "retention_days", str(days)) for days in self._expected_lifecycle_days
            }
            if not expected <= enabled_expirations:
                raise EvidenceError("EVIDENCE_CONFIGURATION_INVALID")
        except EvidenceError:
            raise
        except Exception:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None

    def presign_upload(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        content_type: str,
        maximum_size: int,
        retention_days: int,
        ttl_seconds: int,
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        bucket = self._bucket(bucket_ref)
        if (
            not 1 <= ttl_seconds <= 300
            or not 1 <= maximum_size <= 250 * 1024 * 1024
            or retention_days not in self._expected_lifecycle_days
        ):
            raise EvidenceError("EVIDENCE_REQUEST_INVALID")
        try:
            policy = PostPolicy(bucket, datetime.now(UTC) + timedelta(seconds=ttl_seconds))
            policy.add_equals_condition("key", object_key)
            policy.add_equals_condition("Content-Type", content_type)
            policy.add_equals_condition("x-amz-tagging", f"retention_days={retention_days}")
            policy.add_content_length_range_condition(1, maximum_size)
            result = self._client.presigned_post_policy(policy)
            return f"{self._upload_origin}/{bucket}", tuple(sorted(result.items()))
        except Exception:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None

    def provision_private_bucket(self, bucket_ref: str) -> None:
        bucket = self._bucket(bucket_ref)
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
            self._client.set_bucket_versioning(bucket, VersioningConfig(ENABLED))
            rules = [
                Rule(
                    ENABLED,
                    rule_filter=Filter(tag=Tag("retention_days", str(days))),
                    rule_id=f"retention-{days}-days",
                    expiration=Expiration(days=days),
                    abort_incomplete_multipart_upload=AbortIncompleteMultipartUpload(
                        days_after_initiation=1
                    ),
                )
                for days in sorted(self._expected_lifecycle_days)
            ]
            self._client.set_bucket_lifecycle(bucket, LifecycleConfig(rules))
            self.verify_private_bucket(bucket_ref)
        except EvidenceError:
            raise
        except Exception:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None

    def inspect(
        self,
        *,
        bucket_ref: str,
        object_key: str,
    ) -> StoredObjectFacts:
        bucket = self._bucket(bucket_ref)
        response: Any = None
        try:
            stat = self._client.stat_object(bucket, object_key)
            if stat.size is None or stat.size > 250 * 1024 * 1024:
                raise EvidenceError("EVIDENCE_MEDIA_TOO_LARGE")
            response = self._client.get_object(bucket, object_key)
            digest = hashlib.sha256()
            header = bytearray()
            total = 0
            while True:
                chunk = cast(bytes, response.read(64 * 1024))
                if not chunk:
                    break
                total += len(chunk)
                if total > 250 * 1024 * 1024:
                    raise EvidenceError("EVIDENCE_MEDIA_TOO_LARGE")
                digest.update(chunk)
                if len(header) < 65_536:
                    header.extend(chunk[: 65_536 - len(header)])
            if total != stat.size:
                raise EvidenceError("EVIDENCE_MEDIA_INVALID")
            if not stat.version_id:
                raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE")
            probe = probe_header(bytes(header))
            width = probe.width
            height = probe.height
            duration_ms: int | None = None
            if probe.media_kind is MediaKind.VIDEO:
                raise EvidenceError("EVIDENCE_MEDIA_PROBE_UNAVAILABLE")
            return StoredObjectFacts(
                object_key=object_key,
                provider_version=str(stat.version_id),
                size_bytes=total,
                sha256=digest.hexdigest(),
                content_type=probe.content_type,
                header=bytes(header),
                width=width,
                height=height,
                duration_ms=duration_ms,
            )
        except EvidenceError:
            raise
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}:
                raise EvidenceError("EVIDENCE_OBJECT_MISSING") from None
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None
        except Exception:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def presign_get(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        provider_version: str | None,
        response_disposition: str,
        ttl_seconds: int,
    ) -> str:
        bucket = self._bucket(bucket_ref)
        if response_disposition not in {"inline", "attachment"} or not 1 <= ttl_seconds <= 300:
            raise EvidenceError("EVIDENCE_ACCESS_INVALID")
        response_headers: dict[str, str | list[str] | tuple[str]] = {
            "response-content-disposition": response_disposition
        }
        try:
            return self._client.presigned_get_object(
                bucket,
                object_key,
                expires=timedelta(seconds=ttl_seconds),
                response_headers=response_headers,
                version_id=provider_version,
            )
        except Exception:
            raise EvidenceError("EVIDENCE_URL_ISSUE_FAILED") from None

    def delete(
        self,
        *,
        bucket_ref: str,
        object_key: str,
        provider_version: str | None,
    ) -> None:
        try:
            self._client.remove_object(
                self._bucket(bucket_ref),
                object_key,
                version_id=provider_version,
            )
        except Exception:
            raise EvidenceError("EVIDENCE_STORAGE_UNAVAILABLE") from None
