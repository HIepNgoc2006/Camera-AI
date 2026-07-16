from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from identity_service.domain import (
    AssignmentScopeType,
    DomainValidationError,
    Permission,
    PersonType,
    Role,
    RoleAssignment,
    RoleScopeType,
    SessionMetadata,
    UserAccount,
    UserStatus,
)

USER_ID = UUID("00000000-0000-4000-8000-000000000001")
GRANTOR_ID = UUID("00000000-0000-4000-8000-000000000002")
ROLE_ID = UUID("00000000-0000-4000-8000-000000000003")
SCHOOL_ID = UUID("00000000-0000-4000-8000-000000000004")
PERSON_ID = UUID("00000000-0000-4000-8000-000000000005")
ASSIGNMENT_ID = UUID("00000000-0000-4000-8000-000000000006")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000007")
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_user_normalizes_username_and_requires_complete_relationship() -> None:
    user = UserAccount(
        user_id=USER_ID,
        username=" Generic.Account ",
        status=UserStatus.ACTIVE,
        school_id=SCHOOL_ID,
        person_type=PersonType.STAFF,
        person_ref=PERSON_ID,
    )

    assert user.username == "generic.account"

    with pytest.raises(DomainValidationError, match="provided together"):
        UserAccount(
            user_id=USER_ID,
            username="generic.account",
            status=UserStatus.ACTIVE,
            person_type=PersonType.STAFF,
        )


def test_role_and_permission_use_stable_non_pii_codes() -> None:
    role = Role(
        role_id=ROLE_ID,
        scope_type=RoleScopeType.SCHOOL,
        code=" School.Admin ",
        name="School administrator",
    )
    permission = Permission(
        permission_id=UUID("00000000-0000-4000-8000-000000000008"),
        resource="attendance.record",
        action="read",
    )

    assert role.code == "school.admin"
    assert permission.requires_object_scope is True

    with pytest.raises(DomainValidationError, match="stable lowercase code"):
        Permission(
            permission_id=UUID("00000000-0000-4000-8000-000000000009"),
            resource="student profile",
            action="read",
        )


def test_role_assignment_rejects_self_grant_and_incomplete_object_scope() -> None:
    with pytest.raises(DomainValidationError, match="self-granted"):
        RoleAssignment(
            role_assignment_id=ASSIGNMENT_ID,
            user_id=USER_ID,
            role_id=ROLE_ID,
            granted_by=USER_ID,
            scope_type=AssignmentScopeType.GLOBAL,
            valid_from=NOW,
        )

    with pytest.raises(DomainValidationError, match="require school_id and scope_ref"):
        RoleAssignment(
            role_assignment_id=ASSIGNMENT_ID,
            user_id=USER_ID,
            role_id=ROLE_ID,
            granted_by=GRANTOR_ID,
            scope_type=AssignmentScopeType.CLASS,
            valid_from=NOW,
            school_id=SCHOOL_ID,
        )


def test_role_assignment_validates_time_and_school_scope() -> None:
    assignment = RoleAssignment(
        role_assignment_id=ASSIGNMENT_ID,
        user_id=USER_ID,
        role_id=ROLE_ID,
        granted_by=GRANTOR_ID,
        scope_type=AssignmentScopeType.SCHOOL,
        valid_from=NOW,
        school_id=SCHOOL_ID,
        scope_ref=SCHOOL_ID,
        valid_to=NOW + timedelta(days=30),
    )

    assert assignment.scope_ref == assignment.school_id

    with pytest.raises(DomainValidationError, match="cannot precede"):
        RoleAssignment(
            role_assignment_id=ASSIGNMENT_ID,
            user_id=USER_ID,
            role_id=ROLE_ID,
            granted_by=GRANTOR_ID,
            scope_type=AssignmentScopeType.GLOBAL,
            valid_from=NOW,
            valid_to=NOW - timedelta(seconds=1),
        )


def test_session_state_is_credential_free_and_time_bounded() -> None:
    session = SessionMetadata(
        session_id=SESSION_ID,
        user_id=USER_ID,
        expires_at=NOW + timedelta(minutes=10),
    )

    assert session.is_active(NOW) is True
    assert session.is_active(NOW + timedelta(minutes=10)) is False

    revoked = SessionMetadata(
        session_id=SESSION_ID,
        user_id=USER_ID,
        expires_at=NOW + timedelta(minutes=10),
        revoked_at=NOW,
    )
    assert revoked.is_active(NOW) is False


def test_domain_rejects_naive_session_timestamp() -> None:
    with pytest.raises(DomainValidationError, match="timezone"):
        SessionMetadata(
            session_id=SESSION_ID,
            user_id=USER_ID,
            expires_at=datetime(2026, 1, 1),
        )
