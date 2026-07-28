from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from evidence_service.domain.errors import EvidenceError
from evidence_service.infrastructure.object_storage import (
    MinioPrivateObjectStorage,
    validate_storage_endpoint,
)
from minio import Minio
from minio.commonconfig import Filter, Tag
from minio.datatypes import PostPolicy
from minio.lifecycleconfig import Expiration, LifecycleConfig


class FakeMinio:
    def __init__(self) -> None:
        self.policy: PostPolicy | None = None
        self.get_arguments: dict[str, object] = {}
        self.public_policy = ""
        self.lifecycle_days: tuple[int, ...] = (15, 30, 180, 365)
        self.created_bucket = False
        self.versioning_config: object | None = None
        self.lifecycle_config: object | None = None

    def presigned_post_policy(self, policy: PostPolicy) -> dict[str, str]:
        self.policy = policy
        return {
            "key": "evidence/v1/ab/ab000000000000000000000000000001",
            "policy": "synthetic-policy",
            "x-amz-signature": "synthetic-signature",
        }

    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        **kwargs: object,
    ) -> str:
        self.get_arguments = {
            "bucket_name": bucket_name,
            "object_name": object_name,
            **kwargs,
        }
        return "https://private.invalid/synthetic"

    def bucket_exists(self, bucket_name: str) -> bool:
        del bucket_name
        return True

    def get_bucket_policy(self, bucket_name: str) -> str:
        del bucket_name
        return self.public_policy

    def get_bucket_versioning(self, bucket_name: str) -> SimpleNamespace:
        del bucket_name
        return SimpleNamespace(status="Enabled")

    def get_bucket_lifecycle(self, bucket_name: str) -> SimpleNamespace:
        del bucket_name
        return SimpleNamespace(
            rules=tuple(
                SimpleNamespace(
                    status="Enabled",
                    expiration=SimpleNamespace(days=days),
                    rule_filter=SimpleNamespace(
                        tag=SimpleNamespace(key="retention_days", value=str(days))
                    ),
                )
                for days in self.lifecycle_days
            )
        )

    def make_bucket(self, bucket_name: str) -> None:
        del bucket_name
        self.created_bucket = True

    def set_bucket_versioning(self, bucket_name: str, config: object) -> None:
        del bucket_name
        self.versioning_config = config

    def set_bucket_lifecycle(self, bucket_name: str, config: object) -> None:
        del bucket_name
        self.lifecycle_config = config


def adapter(client: FakeMinio | None = None) -> tuple[MinioPrivateObjectStorage, FakeMinio]:
    fake = client or FakeMinio()
    return (
        MinioPrivateObjectStorage(
            cast(Minio, cast(Any, fake)),
            allowed_bucket_refs=frozenset({"evidence-private-v1"}),
            upload_origin="http://127.0.0.1:9000",
            expected_lifecycle_days=frozenset({15, 30, 180, 365}),
        ),
        fake,
    )


def test_endpoint_and_upload_origin_reject_remote_plaintext_or_credentials() -> None:
    assert validate_storage_endpoint("127.0.0.1:9000", secure=False) == "127.0.0.1:9000"
    assert (
        validate_storage_endpoint("storage.internal:9000", secure=True) == "storage.internal:9000"
    )
    with pytest.raises(EvidenceError, match="EVIDENCE_CONFIGURATION_INVALID"):
        validate_storage_endpoint("storage.internal:9000", secure=False)
    with pytest.raises(EvidenceError, match="EVIDENCE_CONFIGURATION_INVALID"):
        validate_storage_endpoint("user:secret@127.0.0.1:9000", secure=False)
    with pytest.raises(EvidenceError, match="EVIDENCE_CONFIGURATION_INVALID"):
        MinioPrivateObjectStorage(
            cast(Minio, cast(Any, FakeMinio())),
            allowed_bucket_refs=frozenset({"evidence-private-v1"}),
            upload_origin="http://storage.internal:9000",
            expected_lifecycle_days=frozenset({15, 30, 180, 365}),
        )


def test_presigned_post_binds_key_content_type_size_and_short_expiry() -> None:
    storage, fake = adapter()
    url, fields = storage.presign_upload(
        bucket_ref="evidence-private-v1",
        object_key="evidence/v1/ab/ab000000000000000000000000000001",
        content_type="image/png",
        maximum_size=1024,
        retention_days=30,
        ttl_seconds=60,
    )

    assert url == "http://127.0.0.1:9000/evidence-private-v1"
    assert dict(fields)["x-amz-signature"] == "synthetic-signature"
    assert fake.policy is not None
    policy_state = vars(fake.policy)
    assert policy_state["_lower_limit"] == 1
    assert policy_state["_upper_limit"] == 1024
    assert policy_state["_conditions"]["eq"] == {
        "key": "evidence/v1/ab/ab000000000000000000000000000001",
        "Content-Type": "image/png",
        "x-amz-tagging": "retention_days=30",
    }


def test_signed_get_uses_exact_version_and_private_bucket_verification() -> None:
    storage, fake = adapter()
    storage.verify_private_bucket("evidence-private-v1")
    result = storage.presign_get(
        bucket_ref="evidence-private-v1",
        object_key="evidence/v1/ab/ab000000000000000000000000000001",
        provider_version="synthetic-version-1",
        response_disposition="attachment",
        ttl_seconds=60,
    )
    assert result == "https://private.invalid/synthetic"
    assert fake.get_arguments["version_id"] == "synthetic-version-1"
    assert fake.get_arguments["response_headers"] == {"response-content-disposition": "attachment"}

    fake.public_policy = (
        '{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject"}]}'
    )
    with pytest.raises(EvidenceError, match="EVIDENCE_CONFIGURATION_INVALID"):
        storage.verify_private_bucket("evidence-private-v1")


def test_bucket_lifecycle_must_cover_each_configured_retention_class() -> None:
    storage, fake = adapter()
    fake.lifecycle_days = (30,)
    with pytest.raises(EvidenceError, match="EVIDENCE_CONFIGURATION_INVALID"):
        storage.verify_private_bucket("evidence-private-v1")


def test_provisioning_enables_versioning_and_tagged_lifecycle_rules() -> None:
    storage, fake = adapter()
    storage.provision_private_bucket("evidence-private-v1")
    assert fake.versioning_config is not None
    assert fake.lifecycle_config is not None
    rules = cast(LifecycleConfig, fake.lifecycle_config).rules
    expirations: set[int | None] = set()
    tags: set[tuple[str, str]] = set()
    for rule in rules:
        expirations.add(cast(Expiration, rule.expiration).days)
        tag = cast(Tag, cast(Filter, rule.rule_filter).tag)
        tags.add((tag.key, tag.value))
    assert expirations == {15, 30, 180, 365}
    assert tags == {
        ("retention_days", "15"),
        ("retention_days", "30"),
        ("retention_days", "180"),
        ("retention_days", "365"),
    }
