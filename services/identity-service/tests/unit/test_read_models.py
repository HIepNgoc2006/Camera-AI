from __future__ import annotations

from uuid import UUID

import pytest
from identity_service.domain import UserAccount, UserStatus
from identity_service.schemas.read_models import (
    PermissionRead,
    RoleAssignmentRead,
    RoleRead,
    SessionRead,
    UserRead,
)
from pydantic import ValidationError

FORBIDDEN_FIELD_FRAGMENTS = {
    "password",
    "token",
    "hash",
    "cipher",
    "secret",
    "credential",
    "recovery",
    "fingerprint",
    "ip",
    "user_agent",
}


def test_identity_read_models_contain_no_credential_fields() -> None:
    for model in (UserRead, RoleRead, PermissionRead, RoleAssignmentRead, SessionRead):
        for field_name in model.model_fields:
            assert not any(fragment in field_name for fragment in FORBIDDEN_FIELD_FRAGMENTS)


def test_user_read_validates_from_domain_and_rejects_extra_sensitive_field() -> None:
    user = UserAccount(
        user_id=UUID("00000000-0000-4000-8000-000000000001"),
        username="generic.account",
        status=UserStatus.ACTIVE,
    )
    assert UserRead.model_validate(user).status is UserStatus.ACTIVE

    with pytest.raises(ValidationError):
        UserRead.model_validate(
            {
                "user_id": str(user.user_id),
                "school_id": None,
                "username": user.username,
                "person_type": None,
                "person_ref": None,
                "status": "active",
                "password_hash": "fake-hash-marker",
            }
        )
