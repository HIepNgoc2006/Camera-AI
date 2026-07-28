"""Strict loader for the single versioned authorization catalog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final, NoReturn, cast

from camera_ai_authorization.models import ScopeDimension

POLICY_VERSION: Final = "rbac_policy_v1"
_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
_OPERATION = re.compile(r"^[a-z][a-z0-9_.-]{2,95}$")
_AUDIT_ACTION = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
_AUTH_SCHEMES = frozenset({"bearer", "bearer_mfa"})
_CONSENT_REQUIREMENTS = frozenset({"required", "contextual", "not_required"})
_FORBIDDEN_ROLE_KEYS = frozenset({"role", "roles", "role_name", "role_names", "role_matrix"})
_MANDATORY_ATTRIBUTES = frozenset(
    {
        "tenant_id",
        "school_id",
        "class_id",
        "guardian_subject_ref",
        "kitchen_zone_id",
        "purpose_code",
        "consent_state",
        "assignment_valid_from",
        "assignment_valid_until",
        "retention_state",
        "legal_hold_state",
        "resource_state",
        "sensitivity",
        "approval_status",
    }
)
_SEPARATE_ACTIONS = frozenset(
    {
        "view_metadata",
        "view_thumbnail",
        "view_original",
        "download",
        "export",
        "correct",
        "review",
        "delete_request",
        "hold_request",
        "hold_approve",
    }
)


class AuthorizationCatalogError(ValueError):
    def __init__(self, code: str = "AUTHZ_CATALOG_INVALID") -> None:
        super().__init__(code)
        self.code = code


def _fail(code: str = "AUTHZ_CATALOG_INVALID") -> NoReturn:
    raise AuthorizationCatalogError(code)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail()
    return cast(dict[str, object], value.copy())


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        _fail()
    return cast(list[object], value)


def _text(value: object, pattern: re.Pattern[str] = _CODE) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail()
    return value


def _texts(value: object) -> tuple[str, ...]:
    items = tuple(_text(item) for item in _list(value))
    if not items or len(items) != len(set(items)):
        _fail()
    return items


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        _fail()
    return value


def _assert_no_role_keys(value: object) -> None:
    if isinstance(value, dict):
        if any(key in _FORBIDDEN_ROLE_KEYS for key in value):
            _fail()
        for child in value.values():
            _assert_no_role_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_role_keys(child)


@dataclass(frozen=True, slots=True)
class PermissionRule:
    permission_code: str
    resource_type: str
    action: str
    scope_dimensions: frozenset[ScopeDimension]
    required_attributes: frozenset[str]
    allowed_purpose_codes: frozenset[str]
    consent_requirement: str
    audit_on_allow: bool
    deny_when_legal_hold_active: bool


@dataclass(frozen=True, slots=True)
class OperationRule:
    operation_id: str
    method: str
    path_template: str
    auth_scheme: str
    permission_code: str
    object_scope_attributes: frozenset[ScopeDimension]
    audit_action: str
    rate_limit_bucket: str


@dataclass(frozen=True, slots=True)
class AuthorizationCatalog:
    policy_version: str
    permissions: MappingProxyType[str, PermissionRule]
    operations: MappingProxyType[str, OperationRule]
    public_error_code: str
    public_http_status: int

    def permission(self, permission_code: str) -> PermissionRule:
        try:
            return self.permissions[permission_code]
        except KeyError:
            _fail("AUTHZ_POLICY_UNAVAILABLE")

    def operation(self, operation_id: str) -> OperationRule:
        try:
            return self.operations[operation_id]
        except KeyError:
            _fail("AUTHZ_POLICY_UNAVAILABLE")


def _permission(
    item: object,
    profiles: dict[str, frozenset[str]],
) -> PermissionRule:
    value = _mapping(item)
    expected = {
        "permission_code",
        "resource_type",
        "action",
        "scope_dimensions",
        "attribute_profile",
        "allowed_purpose_codes",
        "consent_requirement",
        "audit_on_allow",
        "deny_when_legal_hold_active",
    }
    if set(value) != expected:
        _fail()
    profile_name = _text(value["attribute_profile"])
    if profile_name not in profiles:
        _fail()
    try:
        dimensions = frozenset(ScopeDimension(item) for item in _texts(value["scope_dimensions"]))
    except ValueError:
        _fail()
    consent_requirement = _text(value["consent_requirement"])
    if consent_requirement not in _CONSENT_REQUIREMENTS:
        _fail()
    return PermissionRule(
        permission_code=_text(value["permission_code"]),
        resource_type=_text(value["resource_type"]),
        action=_text(value["action"]),
        scope_dimensions=dimensions,
        required_attributes=profiles[profile_name],
        allowed_purpose_codes=frozenset(_texts(value["allowed_purpose_codes"])),
        consent_requirement=consent_requirement,
        audit_on_allow=_boolean(value["audit_on_allow"]),
        deny_when_legal_hold_active=_boolean(value["deny_when_legal_hold_active"]),
    )


def _operation(item: object, permissions: dict[str, PermissionRule]) -> OperationRule:
    value = _mapping(item)
    expected = {
        "operation_id",
        "method",
        "path_template",
        "auth_scheme",
        "permission_code",
        "object_scope_attributes",
        "audit_action",
        "rate_limit_bucket",
    }
    if set(value) != expected:
        _fail()
    operation_id = _text(value["operation_id"], _OPERATION)
    method = value["method"]
    path_template = value["path_template"]
    auth_scheme = value["auth_scheme"]
    audit_action = value["audit_action"]
    if (
        not isinstance(method, str)
        or method not in _METHODS
        or not isinstance(path_template, str)
        or not path_template.startswith("/api/v1/")
        or auth_scheme not in _AUTH_SCHEMES
        or not isinstance(audit_action, str)
        or _AUDIT_ACTION.fullmatch(audit_action) is None
    ):
        _fail()
    permission_code = _text(value["permission_code"])
    permission = permissions.get(permission_code)
    if permission is None:
        _fail()
    try:
        object_scopes = frozenset(
            ScopeDimension(item) for item in _texts(value["object_scope_attributes"])
        )
    except ValueError:
        _fail()
    if object_scopes != permission.scope_dimensions:
        _fail()
    return OperationRule(
        operation_id=operation_id,
        method=method,
        path_template=path_template,
        auth_scheme=str(auth_scheme),
        permission_code=permission_code,
        object_scope_attributes=object_scopes,
        audit_action=str(audit_action),
        rate_limit_bucket=_text(value["rate_limit_bucket"]),
    )


def validate_catalog(document: dict[str, object]) -> AuthorizationCatalog:
    expected = {
        "catalog_schema_version",
        "policy_version",
        "status",
        "default_decision",
        "role_name_matching_forbidden",
        "public_denial",
        "mandatory_abac_attributes",
        "attribute_profiles",
        "permissions",
        "api_operations",
        "supersession",
    }
    if set(document) != expected:
        _fail()
    _assert_no_role_keys(
        {key: value for key, value in document.items() if key != "role_name_matching_forbidden"}
    )
    if (
        type(document["catalog_schema_version"]) is not int
        or document["catalog_schema_version"] != 1
        or document["policy_version"] != POLICY_VERSION
        or document["status"] != "implementation_baseline_inactive"
        or document["default_decision"] != "deny"
        or document["role_name_matching_forbidden"] is not True
    ):
        _fail("AUTHZ_POLICY_UNAVAILABLE")
    if frozenset(_texts(document["mandatory_abac_attributes"])) != _MANDATORY_ATTRIBUTES:
        _fail()

    profiles_document = _mapping(document["attribute_profiles"])
    if set(profiles_document) != {"protected", "sensitive", "dual_control"}:
        _fail()
    profiles = {
        name: frozenset(_texts(attributes)) for name, attributes in profiles_document.items()
    }
    if any(not attributes <= _MANDATORY_ATTRIBUTES for attributes in profiles.values()):
        _fail()

    permission_items = [_permission(item, profiles) for item in _list(document["permissions"])]
    permissions = {item.permission_code: item for item in permission_items}
    if (
        len(permissions) != len(permission_items)
        or len(permissions) < 30
        or not {item.action for item in permission_items} >= _SEPARATE_ACTIONS
    ):
        _fail()

    operation_items = [_operation(item, permissions) for item in _list(document["api_operations"])]
    operations = {item.operation_id: item for item in operation_items}
    route_keys = {(item.method, item.path_template) for item in operation_items}
    if (
        len(operations) != len(operation_items)
        or len(route_keys) != len(operation_items)
        or len(operations) < 25
    ):
        _fail()

    public_denial = _mapping(document["public_denial"])
    if public_denial != {
        "error_code": "AUTHZ_DENIED",
        "http_status": 404,
        "missing_and_unauthorized_identical": True,
    }:
        _fail()
    supersession = _mapping(document["supersession"])
    if (
        supersession.get("published_version_immutable") is not True
        or supersession.get("unknown_or_missing_version") != "deny"
        or len(_texts(supersession.get("review_triggers"))) < 5
    ):
        _fail()
    return AuthorizationCatalog(
        policy_version=POLICY_VERSION,
        permissions=MappingProxyType(permissions),
        operations=MappingProxyType(operations),
        public_error_code="AUTHZ_DENIED",
        public_http_status=404,
    )


def load_catalog(path: Path) -> AuthorizationCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("AUTHZ_POLICY_UNAVAILABLE")
    return validate_catalog(_mapping(document))
