"""Validate the sanitized Web BFF session policy and synthetic canaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

POLICY_PATH = Path("packages/web-bff-session-policy/web-bff-session-policy-v1.json")
FIXTURE_PATH = Path(
    "packages/test-fixtures/web-bff-session/web-bff-session-policy-cases.synthetic.json"
)
ROUTE_ACCESS_PATH = Path("apps/web-portal/src/features/auth/domain/route-access.ts")
BFF_SESSION_PATH = Path("apps/web-portal/src/features/auth/domain/bff-session.ts")
AUTH_SOURCE_ROOT = Path("apps/web-portal/src/features/auth")
SESSION_SEAM_PATH = Path("apps/web-portal/src/features/auth/application/session.ts")
RUNBOOK_PATH = Path("docs/security/web-bff-session-policy.md")
QUALITY_PATH = Path("scripts/quality.py")
POLICY_VERSION = "web_bff_session_policy_v1"
AUTHORIZATION_POLICY_VERSION = "rbac_policy_v1"
REQUIRED_BOUNDARIES = {"browser", "web_bff", "api_gateway", "identity_service"}
REQUIRED_STATES = {
    "unauthenticated",
    "mfa_required",
    "mfa_failed",
    "authenticated",
    "expired",
    "revoked",
    "unavailable",
    "malformed",
}
REQUIRED_CANARIES = {
    "browser_storage_token",
    "readable_session_cookie",
    "cookie_transport_downgrade",
    "missing_origin_check",
    "missing_csrf_check",
    "unsafe_redirect_target",
    "token_logging",
    "client_authored_authorization",
    "missing_timeout_authority",
    "refresh_replay",
    "revoked_session",
    "dependency_unavailable",
}
REQUIRED_CANARY_CATEGORIES = {
    "browser_storage_token": "custody",
    "readable_session_cookie": "cookie",
    "cookie_transport_downgrade": "cookie",
    "missing_origin_check": "csrf",
    "missing_csrf_check": "csrf",
    "unsafe_redirect_target": "redirect",
    "token_logging": "observability",
    "client_authored_authorization": "authority",
    "missing_timeout_authority": "timeout",
    "refresh_replay": "refresh",
    "revoked_session": "session_state",
    "dependency_unavailable": "session_state",
}
REQUIRED_FORBIDDEN_OBSERVABILITY = {
    "password",
    "access_token",
    "refresh_token",
    "authorization_header",
    "cookie_header_or_value",
    "mfa_secret_or_code",
    "csrf_value",
    "client_authored_authorization_state",
    "full_request_or_response_body",
    "url_query_or_fragment",
    "personal_or_biometric_data",
}
REQUIRED_AUTHENTICATED_FIELDS = {
    "policyVersion",
    "status",
    "actorId",
    "tenantId",
    "schoolId",
    "mfaState",
    "issuedAt",
    "absoluteExpiresAt",
    "inactivityExpiresAt",
    "warningStartsAt",
    "authorization",
}
REQUIRED_SERVER_AUTHORITY_FIELDS = {
    "actorId",
    "tenantId",
    "schoolId",
    "mfaState",
    "issuedAt",
    "absoluteExpiresAt",
    "inactivityExpiresAt",
    "warningStartsAt",
    "authorization.policyVersion",
    "authorization.permissions",
}
REQUIRED_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUIRED_CSRF_VALUE_LOCATIONS = {"request_header", "form_field"}
REQUIRED_CSRF_FORBIDDEN_LOCATIONS = {
    "url_query",
    "url_fragment",
    "local_storage",
    "session_storage",
    "log_trace_audit_or_error",
}
REQUIRED_REDIRECT_FORBIDDEN_SHAPES = {
    "absolute_url",
    "scheme_relative_url",
    "backslash_path",
    "encoded_separator_or_dot_segment",
    "client_supplied_return_target",
}
REQUIRED_ACTIVATION_GATES = {
    "issue_70_runtime_implementation_and_tests",
    "identity_session_snapshot_contract_with_absolute_and_inactivity_expiry",
    "named_security_ops_approval",
    "approved_cookie_and_timeout_runtime_profile",
    "production_secret_provider",
    "deployment_change_and_rollback_record",
}


def load_documents(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the policy and fixture as JSON objects."""

    return _load_object(root / POLICY_PATH), _load_object(root / FIXTURE_PATH)


def validate_documents(policy: dict[str, Any], fixture: dict[str, Any]) -> list[str]:
    """Return stable validation errors without echoing document values."""

    errors: list[str] = []
    _expect(policy.get("policy_schema_version") == 1, "policy schema version", errors)
    _expect(policy.get("policy_id") == POLICY_VERSION, "policy id", errors)
    _expect(policy.get("policy_version") == POLICY_VERSION, "policy version", errors)
    _expect(
        policy.get("status") == "implementation_baseline_inactive",
        "policy inactive status",
        errors,
    )
    _expect(policy.get("default_decision") == "deny", "default deny", errors)
    _expect(
        isinstance(policy.get("runtime_activation"), str)
        and cast(str, policy["runtime_activation"]).startswith("blocked_"),
        "runtime activation blocked",
        errors,
    )

    boundaries = _mapping(policy.get("trust_boundaries"))
    _expect(set(boundaries) == REQUIRED_BOUNDARIES, "trust boundaries", errors)
    sources = _mapping(policy.get("authoritative_sources"))
    identity_source = _mapping(sources.get("identity_session"))
    authorization_source = _mapping(sources.get("authorization"))
    _expect(identity_source.get("owner") == "identity_service", "identity owner", errors)
    _expect(
        identity_source.get("policy_version") == "session_policy_v1",
        "identity policy version",
        errors,
    )
    _expect(
        authorization_source.get("policy_version") == AUTHORIZATION_POLICY_VERSION,
        "authorization policy version",
        errors,
    )
    web_boundary = _mapping(boundaries.get("web_bff"))
    gateway_boundary = _mapping(boundaries.get("api_gateway"))
    _expect(
        "only_backend_entrypoint_for_web_bff" in _string_list(gateway_boundary.get("owns")),
        "API Gateway only backend entrypoint",
        errors,
    )
    _expect(
        "final_business_object_authorization" in _string_list(web_boundary.get("must_not_own")),
        "Web BFF not final object authorization",
        errors,
    )

    custody = _mapping(policy.get("token_custody"))
    _expect(
        custody.get("access_and_refresh_material_location")
        == "server_only_web_bff_or_identity_boundary",
        "server-only token custody",
        errors,
    )
    for key in (
        "browser_storage_allowed",
        "browser_readable_cookie_allowed",
        "url_query_fragment_or_html_allowed",
        "analytics_or_client_state_allowed",
        "log_trace_audit_or_error_allowed",
    ):
        _expect(custody.get(key) is False, f"token custody {key}", errors)

    cookie = _mapping(policy.get("session_cookie"))
    transport = _mapping(cookie.get("secure_transport"))
    _expect(cookie.get("http_only") is True, "cookie HttpOnly", errors)
    _expect(cookie.get("same_site") == "Strict", "cookie SameSite", errors)
    _expect(cookie.get("path") == "/", "cookie path", errors)
    _expect(cookie.get("domain_attribute") == "absent_host_only", "host-only cookie", errors)
    _expect(
        cookie.get("value_source") == "opaque_server_generated_value_not_recorded_in_policy",
        "opaque cookie value source",
        errors,
    )
    _expect(cookie.get("cache_control") == "private, no-store", "session cache control", errors)
    name_profile = _mapping(cookie.get("name_profile"))
    _expect(
        name_profile.get("production_and_non_loopback")
        == "server_configured_name_with___Host-_prefix",
        "cookie secure name profile",
        errors,
    )
    _expect(
        name_profile.get("loopback_plaintext_development")
        == "separate_nonproduction_server_configured_name",
        "cookie loopback name profile",
        errors,
    )
    _expect(cookie.get("web_may_extend_lifetime") is False, "cookie lifetime owner", errors)
    _expect(
        transport.get("production_and_non_loopback") == "required",
        "cookie secure transport",
        errors,
    )
    _expect(
        transport.get("plaintext_http") == "loopback_development_only",
        "plaintext loopback boundary",
        errors,
    )

    csrf = _mapping(policy.get("csrf_and_origin"))
    _expect(csrf.get("origin_required") is True, "origin required", errors)
    _expect(
        set(_string_list(csrf.get("unsafe_methods"))) == REQUIRED_UNSAFE_METHODS,
        "unsafe method coverage",
        errors,
    )
    _expect(
        csrf.get("allowed_origin_source") == "server_side_exact_same_origin_allowlist",
        "same-origin authority",
        errors,
    )
    _expect(
        csrf.get("session_bound_anti_csrf_value_required") is True,
        "anti-CSRF required",
        errors,
    )
    _expect(csrf.get("wildcard_or_null_origin_allowed") is False, "origin fail closed", errors)
    _expect(
        set(_string_list(csrf.get("anti_csrf_value_locations"))) == REQUIRED_CSRF_VALUE_LOCATIONS,
        "anti-CSRF value locations",
        errors,
    )
    _expect(
        set(_string_list(csrf.get("anti_csrf_value_forbidden_locations")))
        == REQUIRED_CSRF_FORBIDDEN_LOCATIONS,
        "anti-CSRF forbidden locations",
        errors,
    )
    _expect(
        csrf.get("failure_behavior") == "deny_without_identity_or_session_detail",
        "CSRF failure behavior",
        errors,
    )

    redirects = _mapping(policy.get("safe_redirects"))
    _expect(
        redirects.get("source") == "server_side_route_code_allowlist",
        "redirect authority",
        errors,
    )
    _expect(redirects.get("fallback") == "/login", "redirect fallback", errors)
    _expect(
        set(_string_list(redirects.get("forbidden_shapes"))) == REQUIRED_REDIRECT_FORBIDDEN_SHAPES,
        "redirect forbidden shapes",
        errors,
    )

    snapshot = _mapping(policy.get("session_snapshot"))
    _expect(
        snapshot.get("policy_version_required") == POLICY_VERSION,
        "snapshot policy version",
        errors,
    )
    _expect(
        snapshot.get("authorization_policy_version_required") == AUTHORIZATION_POLICY_VERSION,
        "snapshot authorization version",
        errors,
    )
    _expect(set(_string_list(snapshot.get("states"))) == REQUIRED_STATES, "session states", errors)
    _expect(
        set(_string_list(snapshot.get("authenticated_required_fields")))
        == REQUIRED_AUTHENTICATED_FIELDS,
        "authenticated snapshot fields",
        errors,
    )
    _expect(
        set(_string_list(snapshot.get("server_authoritative_fields")))
        == REQUIRED_SERVER_AUTHORITY_FIELDS,
        "server authoritative fields",
        errors,
    )
    _expect(
        snapshot.get("client_authored_authority_allowed") is False,
        "client authority denied",
        errors,
    )
    _expect(
        snapshot.get("cookie_presence_is_authorization") is False,
        "cookie presence not authorization",
        errors,
    )
    _expect(
        snapshot.get("backend_reauthorization_required") is True,
        "backend reauthorization",
        errors,
    )

    timeout = _mapping(policy.get("timeout_contract"))
    _expect(timeout.get("absolute_timeout_owner") == "identity_service", "absolute owner", errors)
    _expect(
        timeout.get("inactivity_timeout_owner") == "identity_service",
        "inactivity owner",
        errors,
    )
    _expect(
        timeout.get("numeric_duration_values_in_web_policy") is False,
        "no copied timeout duration",
        errors,
    )
    _expect(
        timeout.get("web_may_invent_or_extend_lifetime") is False,
        "Web cannot extend lifetime",
        errors,
    )
    _expect(
        timeout.get("boundary_rule") == "now_at_or_after_either_expiry_is_expired",
        "timeout boundary",
        errors,
    )
    _expect(
        timeout.get("missing_or_invalid_metadata_behavior") == "malformed_deny",
        "invalid timeout metadata",
        errors,
    )
    _expect(
        timeout.get("warning_behavior") == "display_only_never_refresh_or_extend",
        "warning cannot extend session",
        errors,
    )
    _expect(not _contains_number(timeout), "timeout contract contains no numeric value", errors)

    decisions = _mapping(policy.get("state_decisions"))
    _expect(set(decisions) == REQUIRED_STATES, "state decision coverage", errors)
    _expect(
        decisions.get("unavailable") == "deny_with_stable_unavailable_state",
        "unavailable fails closed",
        errors,
    )
    _expect(
        decisions.get("malformed") == "deny_with_stable_malformed_state",
        "malformed fails closed",
        errors,
    )

    refresh = _mapping(policy.get("refresh_and_revocation"))
    _expect(refresh.get("refresh_rotation_required") is True, "refresh rotation", errors)
    _expect(
        refresh.get("rotated_refresh_replay_behavior") == "revoke_family_clear_cookie_and_deny",
        "refresh replay revoke",
        errors,
    )
    _expect(
        refresh.get("refresh_dependency_unavailable_behavior")
        == "deny_without_stale_session_extension",
        "refresh dependency failure",
        errors,
    )
    _expect(
        refresh.get("logout_behavior") == "identity_revoke_then_clear_cookie",
        "logout revocation order",
        errors,
    )
    _expect(
        refresh.get("logout_all_behavior") == "identity_revoke_all_then_clear_cookie",
        "logout-all revocation order",
        errors,
    )
    _expect(
        refresh.get("clear_cookie_without_confirmed_revoke")
        == "allowed_only_as_local_deny_not_as_revocation_success",
        "local clear is not revocation success",
        errors,
    )

    forbidden = set(_string_list(policy.get("forbidden_observability_fields")))
    _expect(
        forbidden == REQUIRED_FORBIDDEN_OBSERVABILITY,
        "forbidden observability fields",
        errors,
    )
    canaries = set(_string_list(policy.get("required_canaries")))
    _expect(canaries == REQUIRED_CANARIES, "required canaries", errors)

    review = _mapping(policy.get("review_record"))
    for key in (
        "customer_or_production_data_used",
        "credential_or_session_value_recorded",
        "runtime_or_production_activation_included",
    ):
        _expect(review.get(key) is False, f"review record {key}", errors)
    _expect(
        set(_string_list(review.get("activation_requires"))) == REQUIRED_ACTIVATION_GATES,
        "runtime activation gates",
        errors,
    )

    _expect(
        fixture.get("_fixture") == "SYNTHETIC_TEST_DATA_ONLY",
        "synthetic fixture marker",
        errors,
    )
    _expect(fixture.get("policy_version") == POLICY_VERSION, "fixture policy version", errors)
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("fixture cases")
        return errors

    case_ids: set[str] = set()
    observed_canaries: set[str] = set()
    for raw_case in cases:
        case = _mapping(raw_case)
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.startswith("test_"):
            errors.append("fixture case id")
            continue
        if case_id in case_ids:
            errors.append("fixture duplicate case id")
        case_ids.add(case_id)
        expected = case.get("expected_decision")
        actual = evaluate_case(case, forbidden)
        if not isinstance(expected, str) or actual != expected:
            errors.append(f"fixture decision {case_id}")
        canary_name = case_id.removeprefix("test_")
        observed_canaries.add(canary_name)
        required_category = REQUIRED_CANARY_CATEGORIES.get(canary_name)
        if required_category is not None and case.get("category") != required_category:
            errors.append(f"fixture canary category {case_id}")

    _expect(observed_canaries >= REQUIRED_CANARIES, "fixture canary coverage", errors)
    return errors


def evaluate_case(case: dict[str, Any], forbidden_fields: set[str]) -> str:
    """Evaluate one sanitized canary using the policy's deterministic deny rules."""

    category = case.get("category")
    inputs = _mapping(case.get("input"))
    if category == "session_state":
        state = inputs.get("state")
        if state == "unavailable":
            return "unavailable"
        if state == "mfa_required" and inputs.get("source") == "server_validated":
            return "mfa_challenge"
        if state != "authenticated":
            return "deny"
        valid = (
            inputs.get("source") == "server_validated"
            and inputs.get("policy_version") == POLICY_VERSION
            and inputs.get("authorization_policy_version") == AUTHORIZATION_POLICY_VERSION
            and inputs.get("absolute_expiry") == "future"
            and inputs.get("inactivity_expiry") == "future"
        )
        return "allow_route_guard" if valid else "deny"
    if category == "custody":
        return "allow" if inputs.get("access_material_location") == "server_only" else "reject"
    if category == "cookie":
        secure_required = inputs.get("environment") != "loopback_development"
        valid = (
            inputs.get("http_only") is True
            and inputs.get("same_site") == "Strict"
            and inputs.get("host_only") is True
            and (inputs.get("secure") is True or not secure_required)
        )
        return "allow" if valid else "reject"
    if category == "csrf":
        if inputs.get("unsafe_method") is not True:
            return "allow"
        return (
            "allow"
            if inputs.get("origin_validated") is True and inputs.get("csrf_validated") is True
            else "reject"
        )
    if category == "redirect":
        target = inputs.get("target")
        valid = (
            inputs.get("source") == "server_allowlist"
            and isinstance(target, str)
            and _is_safe_redirect(target)
        )
        return "allow" if valid else "reject"
    if category == "observability":
        fields = set(_string_list(inputs.get("fields")))
        return "reject" if fields & forbidden_fields else "allow"
    if category == "authority":
        return "allow" if inputs.get("source") == "server_validated" else "reject"
    if category == "timeout":
        valid = (
            inputs.get("owner") == "identity_service"
            and inputs.get("web_extends_lifetime") is False
        )
        return "allow" if valid else "reject"
    if category == "refresh":
        return "revoke_and_deny" if inputs.get("rotated_token_replayed") is True else "allow"
    return "reject"


def validate_implementation(root: Path) -> list[str]:
    """Check the tracked Web mapping, fail-closed seam, runbook, and quality gate."""

    errors: list[str] = []
    try:
        route_access = (root / ROUTE_ACCESS_PATH).read_text(encoding="utf-8")
        bff_session = (root / BFF_SESSION_PATH).read_text(encoding="utf-8")
        session_seam = (root / SESSION_SEAM_PATH).read_text(encoding="utf-8")
        runbook = (root / RUNBOOK_PATH).read_text(encoding="utf-8")
        quality = (root / QUALITY_PATH).read_text(encoding="utf-8")
        auth_sources = "\n".join(
            source.read_text(encoding="utf-8")
            for pattern in ("*.ts", "*.tsx")
            for source in sorted((root / AUTH_SOURCE_ROOT).rglob(pattern))
            if ".test." not in source.name
        )
    except OSError:
        return ["implementation file unreadable"]

    route_markers = {
        '"web_bff_session_policy_v1" as const': "Web policy constant",
        '"rbac_policy_v1" as const': "authorization policy constant",
        "validateAuthenticatedSessionSnapshot": "snapshot validator",
        "hasExactKeys": "strict snapshot shape",
        "Math.min(absoluteExpiresAt, inactivityExpiresAt)": "either-expiry rule",
        "nowTime < effectiveExpiry": "exclusive expiry boundary",
        'session.mfaState !== "verified"': "MFA validation",
        "authorization.permissions": "permission snapshot validation",
        'return { kind: "expired" }': "expired snapshot classification",
        'return { kind: "invalid" }': "invalid snapshot classification",
    }
    for marker, label in route_markers.items():
        _expect(marker in route_access, f"implementation {label}", errors)
    for field in sorted(REQUIRED_AUTHENTICATED_FIELDS - {"authorization", "status"}):
        _expect(field in route_access, f"implementation snapshot field {field}", errors)

    bff_markers = {
        "BFF_SESSION_STATES": "BFF state catalog",
        "evaluateAuthenticatedSessionSnapshot": "shared snapshot classification",
        "hasExactStateShape": "strict non-authenticated state shape",
        'case "mfa_required"': "MFA-required state mapping",
        'case "mfa_failed"': "MFA-failed state mapping",
        'case "unavailable"': "unavailable state mapping",
        'case "malformed"': "malformed state mapping",
        "toRouteSession": "route-session mapping",
    }
    for marker, label in bff_markers.items():
        _expect(marker in bff_session, f"implementation {label}", errors)
    for state in sorted(REQUIRED_STATES):
        _expect(f'"{state}"' in bff_session, f"implementation state {state}", errors)

    for forbidden_marker in (
        "localStorage",
        "sessionStorage",
        "document.cookie",
    ):
        _expect(
            forbidden_marker not in auth_sources,
            "implementation browser custody marker",
            errors,
        )
    _expect("return null;" in session_seam, "fail-closed session seam", errors)
    _expect(POLICY_VERSION in session_seam, "session seam policy version", errors)
    _expect(POLICY_VERSION in runbook, "runbook policy version", errors)
    _expect(
        "Runtime status: inactive and fail-closed" in runbook,
        "runbook inactive status",
        errors,
    )
    _expect(
        '"web-bff-session-policy"' in quality,
        "quality gate registration",
        errors,
    )
    return errors


def _load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.as_posix()}")
    return cast(dict[str, Any], value)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return []
    return cast(list[str], value)


def _contains_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return any(_contains_number(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_number(item) for item in value)
    return False


def _is_safe_redirect(target: str) -> bool:
    if (
        not target.startswith("/")
        or target.startswith("//")
        or "\\" in target
        or "?" in target
        or "#" in target
    ):
        return False
    lowered = target.lower()
    if "%2f" in lowered or "%5c" in lowered or "%2e" in lowered:
        return False
    return not any(segment in {".", ".."} for segment in target.split("/"))


def _expect(condition: bool, label: str, errors: list[str]) -> None:
    if not condition:
        errors.append(label)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        policy, fixture = load_documents(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"web_bff_session_policy=FAIL type={type(exc).__name__}", file=sys.stderr)
        return 1

    errors = validate_documents(policy, fixture)
    errors.extend(validate_implementation(root))
    if errors:
        for error in errors:
            print(f"web_bff_session_policy=FAIL check={error}", file=sys.stderr)
        return 1

    cases = cast(list[object], fixture["cases"])
    print(f"web_bff_session_policy=PASS policy_version={POLICY_VERSION} cases={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
