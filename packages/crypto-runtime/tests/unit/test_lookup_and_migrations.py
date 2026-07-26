"""LOOKUP-V1 domain separation, normalization and migration-check helpers.

All inputs are synthetic and use `.invalid` hosts or obviously fake numbers.
"""

from __future__ import annotations

import pytest
from camera_ai_crypto import (
    LookupDomain,
    LookupHasher,
    LookupNormalizationError,
    NormalizationVersion,
    canonicalize,
    encv1_check_constraint,
    encv1_prefix_check,
)

LOOKUP_KEY = b"synthetic-lookup-key-value-not-real-0001"
TENANT = "tenant_test_0001"
OTHER_TENANT = "tenant_test_0002"


def email_domain(tenant: str = TENANT, name: str = "identity-user-email") -> LookupDomain:
    return LookupDomain(name=name, tenant_ref=tenant, version=NormalizationVersion.EMAIL_V1)


def hasher() -> LookupHasher:
    return LookupHasher(lookup_key=LOOKUP_KEY)


def test_digest_is_deterministic_and_full_length() -> None:
    subject = hasher()

    first = subject.digest("user.test.0001@example.invalid", email_domain())
    second = subject.digest("user.test.0001@example.invalid", email_domain())

    assert first == second
    assert len(first) == 32


def test_email_normalization_folds_case_and_trims() -> None:
    subject = hasher()

    assert subject.matches(
        "  User.Test.0001@Example.INVALID  ",
        email_domain(),
        subject.digest("user.test.0001@example.invalid", email_domain()),
    )


def test_domain_separation_isolates_purposes_and_tenants() -> None:
    subject = hasher()
    value = "user.test.0001@example.invalid"

    base = subject.digest(value, email_domain())
    other_purpose = subject.digest(value, email_domain(name="notification-recipient-email"))
    other_tenant = subject.digest(value, email_domain(tenant=OTHER_TENANT))

    assert base != other_purpose
    assert base != other_tenant
    assert other_purpose != other_tenant


def test_contact_channels_do_not_collide_with_plain_email_domain() -> None:
    subject = hasher()
    value = "user.test.0001@example.invalid"
    contact_email = LookupDomain(
        name="school-guardian-contact",
        tenant_ref=TENANT,
        version=NormalizationVersion.CONTACT_EMAIL_V1,
    )

    assert subject.digest(value, contact_email) != subject.digest(value, email_domain())


def test_phone_normalization_accepts_e164_and_strips_formatting() -> None:
    subject = hasher()
    domain = LookupDomain(
        name="school-guardian-contact",
        tenant_ref=TENANT,
        version=NormalizationVersion.CONTACT_PHONE_V1,
    )

    assert subject.matches("+84 (24) 3999-0001", domain, subject.digest("+842439990001", domain))


@pytest.mark.parametrize(
    ("value", "version"),
    [
        ("not-an-email", NormalizationVersion.EMAIL_V1),
        ("user@@example.invalid", NormalizationVersion.EMAIL_V1),
        ("", NormalizationVersion.EMAIL_V1),
        ("0243999001", NormalizationVersion.CONTACT_PHONE_V1),
        ("+0243999001", NormalizationVersion.CONTACT_PHONE_V1),
    ],
)
def test_invalid_input_fails_closed_without_silent_retry(
    value: str, version: NormalizationVersion
) -> None:
    with pytest.raises(LookupNormalizationError):
        canonicalize(value, version)


def test_device_token_uses_raw_bytes_without_unicode_transform() -> None:
    token = b"\x00\x01synthetic-token-bytes\xff"

    assert canonicalize(token, NormalizationVersion.DEVICE_TOKEN_V1) == token
    with pytest.raises(LookupNormalizationError):
        canonicalize("synthetic-token-string", NormalizationVersion.DEVICE_TOKEN_V1)


def test_weak_lookup_key_is_rejected() -> None:
    with pytest.raises(LookupNormalizationError):
        LookupHasher(lookup_key=b"too-short")


def test_lookup_errors_expose_only_the_stable_code() -> None:
    try:
        canonicalize("not-an-email", NormalizationVersion.EMAIL_V1)
    except LookupNormalizationError as error:
        rendered = f"{error!s} {error!r}"
    else:  # pragma: no cover - invalid input must fail
        raise AssertionError("expected normalization failure")

    assert "not-an-email" not in rendered
    assert rendered.startswith("LOOKUP_NORMALIZATION_INVALID")


def test_migration_check_requires_envelope_prefix_and_minimum_size() -> None:
    condition = encv1_prefix_check("full_name_ciphertext")

    assert condition == (
        "substring(full_name_ciphertext from 1 for 5) = '\\x454e435631'::bytea"
        " AND octet_length(full_name_ciphertext) >= 64"
    )


def test_migration_constraint_names_are_stable_and_identifiers_validated() -> None:
    name, condition = encv1_check_constraint("students", "full_name_ciphertext")

    assert name == "ck_students_full_name_ciphertext_encv1"
    assert "octet_length(full_name_ciphertext)" in condition
    with pytest.raises(ValueError, match="invalid column identifier"):
        encv1_prefix_check("full_name_ciphertext; DROP TABLE students")
