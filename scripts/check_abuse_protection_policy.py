"""Validate the sanitized DDoS/replay/flood/abuse baseline and inherited limits."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, cast

REQUIRED_SURFACES = {
    "public_web_edge",
    "web_mobile_api",
    "authentication",
    "ansvis_webhook",
    "report_export",
    "signed_evidence_access",
    "object_storage_delivery",
}
REQUIRED_BOUNDARIES = {
    "provider_edge",
    "api_gateway",
    "application_services",
    "queue_and_workers",
    "private_object_storage",
    "security_operations",
}
REQUIRED_THREAT_CATEGORIES = {
    "volumetric_ddos",
    "credential_attack",
    "api_resource_exhaustion",
    "replay_and_duplicate_flood",
    "malformed_or_oversized_payload_flood",
    "report_export_amplification",
    "signed_url_minting_or_reuse_abuse",
    "object_storage_egress_exhaustion",
    "queue_retry_amplification",
    "low_and_slow_distributed_abuse",
}
REQUIRED_ISSUES = {
    "17",
    "35",
    "45",
    "46",
    "59",
    "67",
    "78",
    "89",
    "95",
    "96",
    "112",
    "137",
}
REQUIRED_FORBIDDEN_DIMENSIONS = {
    "access_token",
    "refresh_token",
    "api_key",
    "cookie",
    "credentialed_url",
    "signed_url",
    "raw_source_address",
    "raw_user_identifier",
    "student_or_staff_identifier",
    "camera_or_provider_identifier",
    "bucket_or_object_key",
    "provider_topology",
    "raw_request_or_ansvis_payload",
    "image_video_or_face_data",
}
REQUIRED_INVARIANTS = {
    "api_gateway_remains_the_only_public_api_entry",
    "authentication_authorization_object_scope_consent_retention_and_audit_are_never_bypassed",
    "queue_backpressure_never_replaces_front_door_limits",
    "evidence_never_falls_back_to_public_or_permanent_delivery",
}


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"object expected: {label}")
    return cast(dict[str, Any], value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"list expected: {label}")
    return value


def _json(path: Path) -> dict[str, Any]:
    return _object(json.loads(path.read_text(encoding="utf-8")), str(path))


def _number(node: ast.expr) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _number(node.left) * _number(node.right)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "timedelta"
    ):
        seconds = 0.0
        factors = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}
        for keyword in node.keywords:
            if keyword.arg not in factors:
                raise ValueError("unsupported timedelta component")
            seconds += float(_number(keyword.value)) * factors[keyword.arg]
        return int(seconds)
    raise ValueError("unsupported numeric expression")


def _module_number(path: Path, name: str) -> int | float:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == name:
                return _number(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return _number(node.value)
    raise ValueError(f"numeric constant missing: {path.name}/{name}")


def _class_numbers(path: Path, class_name: str) -> dict[str, int | float]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values: dict[str, int | float] = {}
            for field in node.body:
                if (
                    isinstance(field, ast.AnnAssign)
                    and isinstance(field.target, ast.Name)
                    and field.value is not None
                ):
                    try:
                        values[field.target.id] = _number(field.value)
                    except ValueError:
                        continue
            return values
    raise ValueError(f"class missing: {path.name}/{class_name}")


def _compare_fields(
    failures: list[str],
    observed: dict[str, Any],
    expected: dict[str, Any],
    fields: tuple[str, ...],
    label: str,
) -> None:
    for field in fields:
        if observed.get(field) != expected.get(field):
            failures.append(f"{label} drift: {field}")


def run_checks(
    policy: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """Return deterministic findings without reading runtime traffic or secrets."""

    root = Path(__file__).resolve().parents[1] if repo_root is None else repo_root
    try:
        current = (
            _json(root / "packages/abuse-protection-policy/abuse-protection-policy-v1.json")
            if policy is None
            else policy
        )
        api = _json(root / "packages/api-contract/api-contract-policy-v1.json")
        ansvis = _json(root / "packages/ansvis-event-contract/http-trigger-policy-v1.json")
        evidence = _json(root / "packages/evidence-access-policy/evidence-access-policy-v1.json")
        queue = _json(root / "packages/metrics-runtime/src/camera_ai_metrics/queue_policy_v1.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"policy load failed: {type(error).__name__}"]

    failures: list[str] = []
    if current.get("policy_schema_version") != 1:
        failures.append("policy schema version must be 1")
    if current.get("policy_version") != "abuse_protection_policy_v1":
        failures.append("unexpected policy version")
    if current.get("status") != "implementation_baseline_inactive":
        failures.append("policy must remain an inactive implementation baseline")
    if current.get("runtime_activation") != "blocked_pending_staging_and_provider_evidence":
        failures.append("runtime activation must remain blocked pending evidence")
    if current.get("default_decision") != "deny":
        failures.append("default decision must be deny")

    try:
        scope = set(_list(current.get("scope"), "scope"))
        boundaries = _object(current.get("responsibility_boundaries"), "boundaries")
        controls = _object(current.get("controls"), "controls")
        threats = _list(current.get("threat_scenarios"), "threat_scenarios")
        monitoring = _object(current.get("monitoring_evidence"), "monitoring_evidence")
        issues = _object(current.get("implementation_issue_mapping"), "issue_mapping")
        invariants = set(_list(current.get("degradation_invariants"), "invariants"))
    except ValueError as error:
        return failures + [str(error)]

    if scope != REQUIRED_SURFACES:
        failures.append("required surface set drift")
    if set(boundaries) != REQUIRED_BOUNDARIES:
        failures.append("responsibility boundary set drift")
    if not REQUIRED_INVARIANTS.issubset(invariants):
        failures.append("safe degradation invariant missing")
    if set(issues) != REQUIRED_ISSUES:
        failures.append("mitigation issue mapping drift")

    try:
        sources = _object(current.get("authoritative_sources"), "authoritative_sources")
        expected_sources = {
            "api_contract": (
                "packages/api-contract/api-contract-policy-v1.json",
                api.get("policy_version"),
                "api_contract_policy_v1",
            ),
            "ansvis_contract": (
                "packages/ansvis-event-contract/http-trigger-policy-v1.json",
                ansvis.get("policy_version"),
                "ansvis_http_trigger_policy_v1",
            ),
            "evidence_access": (
                "packages/evidence-access-policy/evidence-access-policy-v1.json",
                evidence.get("policy_version"),
                "evidence_access_policy_v1",
            ),
            "queue_backpressure": (
                "packages/metrics-runtime/src/camera_ai_metrics/queue_policy_v1.json",
                queue.get("policy_version"),
                "queue_operational_policy_v1",
            ),
        }
        if set(sources) != set(expected_sources):
            failures.append("authoritative source set drift")
        for source_code, (path, live_version, required_version) in expected_sources.items():
            source = _object(sources.get(source_code), f"source/{source_code}")
            if source.get("path") != path:
                failures.append(f"authoritative source path drift: {source_code}")
            if source.get("version") != required_version or live_version != required_version:
                failures.append(f"authoritative source version drift: {source_code}")
    except ValueError as error:
        failures.append(str(error))

    threat_ids: set[str] = set()
    categories: set[str] = set()
    for raw_threat in threats:
        try:
            threat = _object(raw_threat, "threat")
            threat_id = threat.get("threat_id")
            category = threat.get("category")
            surfaces = set(_list(threat.get("surfaces"), "threat surfaces"))
            owners = set(_list(threat.get("control_owners"), "threat owners"))
            if not isinstance(threat_id, str) or threat_id in threat_ids:
                failures.append("threat identifiers must be unique strings")
            else:
                threat_ids.add(threat_id)
            if isinstance(category, str):
                categories.add(category)
            if not surfaces or not surfaces.issubset(REQUIRED_SURFACES):
                failures.append(f"unknown threat surface: {threat_id}")
            if not owners or not owners.issubset(REQUIRED_BOUNDARIES):
                failures.append(f"unknown threat owner: {threat_id}")
            if not isinstance(threat.get("safe_degradation"), str):
                failures.append(f"safe degradation missing: {threat_id}")
        except ValueError as error:
            failures.append(str(error))
    if categories != REQUIRED_THREAT_CATEGORIES:
        failures.append("required threat category set drift")

    try:
        api_control = _object(controls.get("api_gateway"), "api gateway control")
        api_buckets = _object(api_control.get("rate_limit_buckets"), "policy API buckets")
        source_buckets = _object(api.get("rate_limit_buckets"), "source API buckets")
        if api_buckets != source_buckets:
            failures.append("API rate-limit bucket drift")

        ansvis_control = _object(controls.get("ansvis_webhook"), "ANSVIS control")
        ansvis_request = _object(ansvis.get("request"), "ANSVIS request")
        ansvis_rate = _object(ansvis.get("rate_limit"), "ANSVIS rate limit")
        ansvis_time = _object(ansvis.get("time"), "ANSVIS time")
        _compare_fields(
            failures,
            ansvis_control,
            {
                "max_body_bytes": ansvis_request.get("max_body_bytes"),
                "sustained_requests_per_second": ansvis_rate.get("sustained_requests_per_second"),
                "burst_requests": ansvis_rate.get("burst_requests"),
                "replay_window_seconds": ansvis_time.get("replay_window_seconds"),
                "future_tolerance_seconds": ansvis_time.get("future_tolerance_seconds"),
            },
            (
                "max_body_bytes",
                "sustained_requests_per_second",
                "burst_requests",
                "replay_window_seconds",
                "future_tolerance_seconds",
            ),
            "ANSVIS control",
        )

        auth_control = _object(controls.get("authentication"), "authentication control")
        gateway_body = _module_number(
            root / "services/api-gateway/src/api_gateway/api/v1/identity.py",
            "MAX_AUTH_BODY_BYTES",
        )
        identity_limits = _class_numbers(
            root / "services/identity-service/src/identity_service/infrastructure/rate_limit.py",
            "RedisLoginRateLimiter",
        )
        auth_expected = {
            "max_body_bytes": gateway_body,
            "account_failure_limit": identity_limits.get("account_limit"),
            "source_failure_limit": identity_limits.get("source_limit"),
            "window_seconds": identity_limits.get("window"),
        }
        _compare_fields(
            failures,
            auth_control,
            auth_expected,
            tuple(auth_expected),
            "authentication control",
        )

        report_control = _object(controls.get("report_export"), "report export control")
        report_defaults = _class_numbers(
            root / "services/report-service/src/report_service/config.py", "ReportSettings"
        )
        _compare_fields(
            failures,
            report_control,
            report_defaults,
            (
                "max_concurrent_exports_per_actor",
                "max_queue_depth",
                "artifact_ttl_seconds",
                "signed_get_ttl_seconds",
            ),
            "report export control",
        )

        signed_control = _object(controls.get("signed_evidence_access"), "signed evidence control")
        signed_profiles = _object(
            _object(evidence.get("signed_get"), "signed_get").get("profiles"), "profiles"
        )
        standard = _object(signed_profiles.get("standard_view"), "standard_view")
        export = _object(signed_profiles.get("export_delivery"), "export_delivery")
        _compare_fields(
            failures,
            signed_control,
            {
                "standard_default_ttl_seconds": standard.get("default_ttl_seconds"),
                "standard_hard_max_ttl_seconds": standard.get("hard_max_ttl_seconds"),
                "export_hard_max_ttl_seconds": export.get("hard_max_ttl_seconds"),
            },
            (
                "standard_default_ttl_seconds",
                "standard_hard_max_ttl_seconds",
                "export_hard_max_ttl_seconds",
            ),
            "signed evidence control",
        )

        queue_control = _object(controls.get("queue_backpressure"), "queue control")
        queue_thresholds = _object(queue.get("thresholds"), "queue thresholds")
        _compare_fields(
            failures,
            queue_control,
            queue_thresholds,
            (
                "warning_depth_messages",
                "warning_depth_for_seconds",
                "critical_depth_messages",
                "critical_drain_eta_seconds",
                "circuit_open_error_ratio",
                "circuit_window_seconds",
            ),
            "queue control",
        )
    except (OSError, ValueError, SyntaxError) as error:
        failures.append(f"authority comparison failed: {type(error).__name__}")

    try:
        from camera_ai_metrics import REGISTRY

        metrics = set(_list(monitoring.get("registered_metrics"), "registered_metrics"))
        unknown_metrics = sorted(metrics.difference(REGISTRY))
        if unknown_metrics:
            failures.append(f"unregistered monitoring metrics: {','.join(unknown_metrics)}")
    except Exception as error:  # pragma: no cover - import failure is the finding
        failures.append(f"metrics registry import failed: {type(error).__name__}")

    try:
        forbidden = set(_list(monitoring.get("forbidden_dimensions"), "forbidden_dimensions"))
        if not REQUIRED_FORBIDDEN_DIMENSIONS.issubset(forbidden):
            failures.append("safe evidence forbidden-dimension set is incomplete")
        if monitoring.get("raw_request_capture_allowed") is not False:
            failures.append("raw request capture must be disabled")
        storage = _object(controls.get("object_storage_delivery"), "storage control")
        if storage.get("bucket_visibility") != "private":
            failures.append("object storage must remain private")
        if storage.get("provider_values_recorded_in_repository") is not False:
            failures.append("provider-specific values must not be recorded in this baseline")
    except ValueError as error:
        failures.append(str(error))

    return failures


def main() -> int:
    failures = run_checks()
    if failures:
        for failure in failures:
            print(f"abuse_protection_policy=FAIL {failure}")
        return 1
    policy = _json(
        Path(__file__).resolve().parents[1]
        / "packages/abuse-protection-policy/abuse-protection-policy-v1.json"
    )
    print("abuse_protection_policy=PASS")
    print(f"policy_version={policy['policy_version']}")
    print(f"surfaces_checked={len(_list(policy['scope'], 'scope'))}")
    print(f"threats_checked={len(_list(policy['threat_scenarios'], 'threat_scenarios'))}")
    print("runtime_activation=INACTIVE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
