"""Validate the versioned RBAC/ABAC catalog and its audit-operation references."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "authorization-runtime" / "src"))
sys.path.insert(0, str(REPO_ROOT / "services" / "audit-log-service" / "src"))

from audit_log_service.domain.policies import APPROVED_ACTIONS  # noqa: E402
from camera_ai_authorization.catalog import (  # noqa: E402
    AuthorizationCatalogError,
    load_catalog,
)

CATALOG_PATH = REPO_ROOT / "packages" / "authorization-policy" / "permission-catalog-v1.json"


def main() -> int:
    try:
        catalog = load_catalog(CATALOG_PATH)
        missing_audit_actions = {
            operation.audit_action
            for operation in catalog.operations.values()
            if operation.audit_action not in APPROVED_ACTIONS
        }
        if missing_audit_actions:
            raise AuthorizationCatalogError
    except AuthorizationCatalogError as error:
        print(f"authorization_catalog=FAIL code={error.code}", file=sys.stderr)
        return 1
    print("authorization_catalog=PASS")
    print(f"policy_version={catalog.policy_version}")
    print("runtime_activation=INACTIVE")
    print(f"permissions_checked={len(catalog.permissions)}")
    print(f"planned_m3_operations_checked={len(catalog.operations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
