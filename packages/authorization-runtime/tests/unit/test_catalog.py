from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from camera_ai_authorization import AuthorizationCatalogError, ScopeDimension, load_catalog
from camera_ai_authorization.catalog import validate_catalog

REPO_ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = REPO_ROOT / "packages" / "authorization-policy" / "permission-catalog-v1.json"


def document() -> dict[str, object]:
    value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_catalog_loads_one_version_without_role_name_grants() -> None:
    catalog = load_catalog(CATALOG_PATH)

    assert catalog.policy_version == "rbac_policy_v1"
    assert len(catalog.permissions) >= 30
    assert len(catalog.operations) >= 25
    assert not hasattr(catalog, "roles")
    assert catalog.permission("attendance.view_metadata").scope_dimensions == frozenset(
        {
            ScopeDimension.SCHOOL,
            ScopeDimension.CLASS,
            ScopeDimension.GUARDIAN_SUBJECT,
        }
    )


def test_required_sensitive_actions_are_distinct_permission_codes() -> None:
    catalog = load_catalog(CATALOG_PATH)
    required_actions = {
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
    evidence_rules = {
        rule.action: rule.permission_code
        for rule in catalog.permissions.values()
        if rule.resource_type == "evidence"
    }

    assert required_actions <= evidence_rules.keys()
    assert len(evidence_rules.values()) == len(set(evidence_rules.values()))


def test_each_planned_operation_has_all_five_controls_and_catalog_permission() -> None:
    catalog = load_catalog(CATALOG_PATH)

    for operation in catalog.operations.values():
        permission = catalog.permission(operation.permission_code)
        assert operation.auth_scheme
        assert operation.permission_code
        assert operation.object_scope_attributes == permission.scope_dimensions
        assert operation.audit_action
        assert operation.rate_limit_bucket


def test_unknown_policy_version_fails_closed() -> None:
    invalid = document()
    invalid["policy_version"] = "rbac_policy_unknown"

    with pytest.raises(AuthorizationCatalogError, match="AUTHZ_POLICY_UNAVAILABLE"):
        validate_catalog(invalid)


def test_planned_route_without_catalog_permission_fails_ci_contract() -> None:
    invalid = deepcopy(document())
    operations = invalid["api_operations"]
    assert isinstance(operations, list)
    assert isinstance(operations[0], dict)
    operations[0]["permission_code"] = "missing.permission"

    with pytest.raises(AuthorizationCatalogError, match="AUTHZ_CATALOG_INVALID"):
        validate_catalog(invalid)


def test_catalog_rejects_role_name_matching_structure() -> None:
    invalid = document()
    invalid["roles"] = [{"role_name": "synthetic_admin"}]

    with pytest.raises(AuthorizationCatalogError, match="AUTHZ_CATALOG_INVALID"):
        validate_catalog(invalid)
