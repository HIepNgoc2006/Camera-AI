"""Validate the fail-closed AI shadow-mode and human-review policy."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Never

POLICY_PATH = Path("packages/ai-shadow-review-policy/ai-shadow-review-policy-v1.json")
FIXTURE_PATH = Path(
    "packages/test-fixtures/ai-shadow-review/ai-shadow-review-policy-cases.synthetic.json"
)
SYNTHETIC_MARKER = "SYNTHETIC_TEST_DATA_ONLY"

AI_POLICY_INVALID = "AI_POLICY_INVALID"
AI_INPUT_INVALID = "AI_INPUT_INVALID"
STABLE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
REASON_CODE = re.compile(r"^AI_[A-Z0-9_]{2,63}$")

LIFECYCLE_STATES = (
    "disabled",
    "shadow",
    "review_required",
    "accepted",
    "production",
)
CONFIDENCE_BANDS = ("unknown", "low", "medium", "high")
VISIBILITY_STATES = ("unknown", "partial_visibility", "clear")
TEMPORAL_EVIDENCE = ("none", "single_frame", "multi_frame")
REVIEW_OUTCOMES = (
    "not_reviewed",
    "confirmed",
    "rejected",
    "needs_more_evidence",
)
PRODUCTION_GATES = (
    "dataset_provenance_approved",
    "evaluation_sample_gate_met",
    "false_positive_review_completed",
    "false_negative_review_completed",
    "latency_capacity_evidence_passed",
    "owner_approval_recorded",
    "model_version_recorded",
    "config_version_recorded",
    "task_version_recorded",
    "rollback_trigger_recorded",
)
REASON_CODES = {
    "policy_disabled": "AI_POLICY_DISABLED",
    "pipeline_unknown": "AI_PIPELINE_UNKNOWN",
    "input_invalid": AI_INPUT_INVALID,
    "consent_required": "AI_CONSENT_REQUIRED",
    "visibility_unknown": "AI_VISIBILITY_UNKNOWN",
    "partial_visibility": "AI_PARTIAL_VISIBILITY",
    "temporal_evidence_required": "AI_TEMPORAL_EVIDENCE_REQUIRED",
    "low_confidence": "AI_LOW_CONFIDENCE",
    "human_review_required": "AI_HUMAN_REVIEW_REQUIRED",
    "shadow_evaluation_only": "AI_SHADOW_EVALUATION_ONLY",
    "business_rule_required": "AI_BUSINESS_RULE_REQUIRED",
    "human_review_confirmed": "AI_HUMAN_REVIEW_CONFIRMED",
    "human_review_rejected": "AI_HUMAN_REVIEW_REJECTED",
    "more_evidence_required": "AI_MORE_EVIDENCE_REQUIRED",
}


class AiPolicyError(ValueError):
    """Fail with a stable code without echoing rejected policy or fixture data."""

    def __init__(self, code: str = AI_POLICY_INVALID) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str = AI_POLICY_INVALID) -> Never:
    raise AiPolicyError(code)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail()
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        _fail()
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        _fail(AI_INPUT_INVALID)
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        _fail()
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail()
    return value


def _text_tuple(value: object) -> tuple[str, ...]:
    result = tuple(_text(item) for item in _list(value))
    if len(result) != len(set(result)):
        _fail()
    return result


def _load_json(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail()
    return _mapping(value)


def _require_exact_keys(value: dict[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        _fail()


@dataclass(frozen=True, slots=True)
class PipelinePolicy:
    consent_requirement: str
    output_label: str
    human_review: str
    temporal_evidence_requirement: str


@dataclass(frozen=True, slots=True)
class AiShadowReviewPolicy:
    policy_version: str
    lifecycle_states: frozenset[str]
    transitions: dict[str, frozenset[str]]
    transition_authorities: dict[str, str]
    confidence_bands: frozenset[str]
    visibility_states: frozenset[str]
    temporal_evidence: frozenset[str]
    review_outcomes: frozenset[str]
    pipelines: dict[str, PipelinePolicy]
    production_gates: frozenset[str]
    reason_codes: dict[str, str]


@dataclass(frozen=True, slots=True)
class Decision:
    decision: str
    reason_code: str
    business_conclusion_allowed: bool = False


def _validate_lifecycle(
    value: object,
) -> tuple[frozenset[str], dict[str, frozenset[str]], dict[str, str]]:
    lifecycle = _mapping(value)
    _require_exact_keys(
        lifecycle,
        {
            "states",
            "allowed_transitions",
            "transition_authorities",
            "production_requires_state",
            "direct_shadow_to_production_allowed",
        },
    )
    states = _text_tuple(lifecycle["states"])
    if states != LIFECYCLE_STATES:
        _fail()
    if lifecycle["production_requires_state"] != "accepted" or _boolean(
        lifecycle["direct_shadow_to_production_allowed"]
    ):
        _fail()

    expected_transitions = {
        "disabled": ("shadow",),
        "shadow": ("review_required", "accepted", "disabled"),
        "review_required": ("shadow", "accepted", "disabled"),
        "accepted": ("shadow", "production", "disabled"),
        "production": ("shadow", "disabled"),
    }
    raw_transitions = _mapping(lifecycle["allowed_transitions"])
    if set(raw_transitions) != set(expected_transitions):
        _fail()
    transitions: dict[str, frozenset[str]] = {}
    for state, expected in expected_transitions.items():
        actual = _text_tuple(raw_transitions[state])
        if actual != expected or any(target not in states for target in actual):
            _fail()
        transitions[state] = frozenset(actual)
    if "production" in transitions["shadow"]:
        _fail()
    expected_authorities = {
        "disabled_to_shadow": "ai_governance_approver",
        "shadow_to_review_required": "ai_reviewer",
        "shadow_to_accepted": "ai_governance_approver",
        "shadow_to_disabled": "ai_operator",
        "review_required_to_shadow": "ai_operator",
        "review_required_to_accepted": "ai_governance_approver",
        "review_required_to_disabled": "ai_operator",
        "accepted_to_shadow": "ai_operator",
        "accepted_to_production": "project_owner",
        "accepted_to_disabled": "ai_operator",
        "production_to_shadow": "ai_operator",
        "production_to_disabled": "incident_commander",
    }
    authorities = _mapping(lifecycle["transition_authorities"])
    if authorities != expected_authorities:
        _fail()
    return (
        frozenset(states),
        transitions,
        {key: _text(value) for key, value in authorities.items()},
    )


def _validate_common_controls(
    value: object,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    controls = _mapping(value)
    _require_exact_keys(
        controls,
        {
            "automatic_disciplinary_conclusion_allowed",
            "shadow_business_record_mutation_allowed",
            "missing_policy_behavior",
            "missing_or_ambiguous_input_outcome",
            "consent_missing_behavior",
            "allowed_confidence_bands",
            "review_required_confidence_bands",
            "allowed_visibility_states",
            "allowed_temporal_evidence",
            "allowed_review_outcomes",
            "reviewer_requirements",
            "audit_summary_fields",
            "forbidden_log_fields",
        },
    )
    if (
        _boolean(controls["automatic_disciplinary_conclusion_allowed"])
        or _boolean(controls["shadow_business_record_mutation_allowed"])
        or controls["missing_policy_behavior"] != "deny"
        or controls["missing_or_ambiguous_input_outcome"] != "review_required"
        or controls["consent_missing_behavior"] != "deny"
    ):
        _fail()
    confidence = _text_tuple(controls["allowed_confidence_bands"])
    visibility = _text_tuple(controls["allowed_visibility_states"])
    temporal = _text_tuple(controls["allowed_temporal_evidence"])
    review = _text_tuple(controls["allowed_review_outcomes"])
    if (
        confidence != CONFIDENCE_BANDS
        or _text_tuple(controls["review_required_confidence_bands"]) != ("unknown", "low")
        or visibility != VISIBILITY_STATES
        or temporal != TEMPORAL_EVIDENCE
        or review != REVIEW_OUTCOMES
    ):
        _fail()
    if _text_tuple(controls["reviewer_requirements"]) != (
        "authenticated",
        "authorized_for_object_scope",
        "assigned_review_scope",
        "approved_purpose_code",
        "conflict_declared",
        "decision_reason_code",
        "audit_required",
    ):
        _fail()
    if _text_tuple(controls["audit_summary_fields"]) != (
        "policy_version",
        "pipeline_code",
        "model_version_ref",
        "config_version_ref",
        "task_version_ref",
        "reviewer_ref",
        "decision_code",
        "reason_code",
        "correlation_id",
    ):
        _fail()
    if _text_tuple(controls["forbidden_log_fields"]) != (
        "image",
        "image_base64",
        "video",
        "face_embedding",
        "raw_ansvis_payload",
        "signed_url",
        "credential",
        "personal_name",
    ):
        _fail()
    return (
        frozenset(confidence),
        frozenset(visibility),
        frozenset(temporal),
        frozenset(review),
    )


def _expected_pipeline_documents() -> dict[str, dict[str, object]]:
    return {
        "facial_recognition": {
            "data_class": "critical",
            "consent_requirement": "required",
            "output_label": "face_match_candidate",
            "human_review": "conditional",
            "temporal_evidence_requirement": "none",
            "business_record_requires_separate_rule": True,
            "allowed_non_decision_outcomes": ["unknown", "review_required"],
        },
        "littering_detection": {
            "data_class": "high",
            "consent_requirement": "contextual",
            "output_label": "suspected_littering",
            "human_review": "always",
            "temporal_evidence_requirement": "multi_frame",
            "single_frame_confirmation_allowed": False,
            "allowed_non_decision_outcomes": ["unknown", "review_required"],
        },
        "smoking_detection": {
            "data_class": "high",
            "consent_requirement": "contextual",
            "output_label": "suspected_smoking",
            "human_review": "always",
            "temporal_evidence_requirement": "contextual_sequence",
            "confirmed_wording_before_review_allowed": False,
            "allowed_non_decision_outcomes": ["unknown", "review_required"],
        },
        "student_uniform_detection": {
            "data_class": "high",
            "consent_requirement": "contextual",
            "output_label": "suspected_uniform_noncompliance",
            "human_review": "always",
            "temporal_evidence_requirement": "none",
            "forced_classification_when_obscured_allowed": False,
            "allowed_non_decision_outcomes": [
                "unknown",
                "partial_visibility",
                "review_required",
            ],
        },
        "kitchen_ppe_detection": {
            "data_class": "high",
            "consent_requirement": "contextual",
            "output_label": "suspected_ppe_noncompliance",
            "human_review": "always",
            "temporal_evidence_requirement": "none",
            "forced_classification_when_obscured_allowed": False,
            "allowed_non_decision_outcomes": [
                "unknown",
                "partial_visibility",
                "review_required",
            ],
        },
    }


def _validate_pipelines(value: object) -> dict[str, PipelinePolicy]:
    documents = _mapping(value)
    expected = _expected_pipeline_documents()
    if set(documents) != set(expected):
        _fail()
    pipelines: dict[str, PipelinePolicy] = {}
    for pipeline_code, expected_document in expected.items():
        document = _mapping(documents[pipeline_code])
        if document != expected_document:
            _fail()
        pipelines[pipeline_code] = PipelinePolicy(
            consent_requirement=_text(document["consent_requirement"]),
            output_label=_text(document["output_label"]),
            human_review=_text(document["human_review"]),
            temporal_evidence_requirement=_text(document["temporal_evidence_requirement"]),
        )
    return pipelines


def _validate_production_enable(value: object) -> frozenset[str]:
    production = _mapping(value)
    expected = {
        "all_required_gates": list(PRODUCTION_GATES),
        "required_evidence_fields": [
            "metric_profile_ref",
            "evaluation_report_ref",
            "dataset_manifest_hash",
            "dataset_consent_review_ref",
            "latency_capacity_report_ref",
            "approval_record_ref",
            "model_version_ref",
            "config_version_ref",
            "task_version_ref",
            "rollback_record_ref",
        ],
        "per_pipeline_metric_profile_required": True,
        "activation_change_record_required": True,
        "unknown_or_missing_gate_behavior": "deny",
    }
    if production != expected:
        _fail()
    return frozenset(PRODUCTION_GATES)


def _validate_rollback(value: object) -> None:
    rollback = _mapping(value)
    expected = {
        "target_scope": [
            "pipeline_code",
            "model_version_ref",
            "config_version_ref",
            "task_version_ref",
        ],
        "cross_pipeline_enable_allowed": False,
        "audit_evidence_deletion_allowed": False,
        "rollback_targets_last_approved_version": True,
        "emergency_disable_requires_reason_and_audit": True,
    }
    if rollback != expected:
        _fail()


def validate_policy(document: dict[str, object]) -> AiShadowReviewPolicy:
    """Validate immutable v1 semantics and return the runtime-safe projection."""

    _require_exact_keys(
        document,
        {
            "policy_id",
            "policy_version",
            "schema_version",
            "status",
            "runtime_activation",
            "owner_code",
            "approver_code",
            "purpose_code",
            "data_class",
            "published_versions_immutable",
            "lifecycle",
            "common_controls",
            "pipelines",
            "production_enable",
            "rollback_disable",
            "stable_reason_codes",
        },
    )
    fixed_values = {
        "policy_id": "ai_shadow_review_policy_v1",
        "policy_version": "ai_shadow_review_policy_v1",
        "status": "baseline_only",
        "runtime_activation": "disabled",
        "owner_code": "ai_governance",
        "approver_code": "project_owner",
        "purpose_code": "safe_ai_evaluation",
        "data_class": "high",
    }
    if (
        any(document.get(key) != value for key, value in fixed_values.items())
        or _integer(document["schema_version"]) != 1
        or not _boolean(document["published_versions_immutable"])
    ):
        _fail()

    states, transitions, transition_authorities = _validate_lifecycle(document["lifecycle"])
    confidence, visibility, temporal, review = _validate_common_controls(
        document["common_controls"]
    )
    pipelines = _validate_pipelines(document["pipelines"])
    production_gates = _validate_production_enable(document["production_enable"])
    _validate_rollback(document["rollback_disable"])

    reason_codes = _mapping(document["stable_reason_codes"])
    if reason_codes != REASON_CODES or any(
        REASON_CODE.fullmatch(_text(code)) is None for code in reason_codes.values()
    ):
        _fail()
    return AiShadowReviewPolicy(
        policy_version=_text(document["policy_version"]),
        lifecycle_states=states,
        transitions=transitions,
        transition_authorities=transition_authorities,
        confidence_bands=confidence,
        visibility_states=visibility,
        temporal_evidence=temporal,
        review_outcomes=review,
        pipelines=pipelines,
        production_gates=production_gates,
        reason_codes={key: _text(value) for key, value in reason_codes.items()},
    )


def transition_authorized(
    current_state: str,
    target_state: str,
    actor_authority: str,
    policy: AiShadowReviewPolicy,
) -> bool:
    """Require both an allowed lifecycle edge and its responsible authority."""

    if (
        current_state not in policy.lifecycle_states
        or target_state not in policy.transitions[current_state]
    ):
        return False
    transition_code = f"{current_state}_to_{target_state}"
    return policy.transition_authorities.get(transition_code) == actor_authority


def production_gates_complete(provided_gates: set[str], policy: AiShadowReviewPolicy) -> bool:
    """Require the exact named gate set; this does not activate production."""

    return provided_gates == policy.production_gates


def evaluate_case(case: dict[str, object], policy: AiShadowReviewPolicy) -> Decision:
    """Evaluate a sanitized case without returning or logging input content."""

    required = {
        "case_code",
        "pipeline_code",
        "lifecycle_state",
        "confidence_band",
        "visibility",
        "temporal_evidence",
        "consent_status",
        "human_review_outcome",
        "expected_decision",
        "expected_reason_code",
    }
    _require_exact_keys(case, required)
    pipeline_code = _text(case["pipeline_code"])
    lifecycle_state = _text(case["lifecycle_state"])
    confidence = _text(case["confidence_band"])
    visibility = _text(case["visibility"])
    temporal = _text(case["temporal_evidence"])
    consent = _text(case["consent_status"])
    review_outcome = _text(case["human_review_outcome"])
    if pipeline_code not in policy.pipelines:
        _fail(policy.reason_codes["pipeline_unknown"])
    if (
        lifecycle_state not in policy.lifecycle_states
        or confidence not in policy.confidence_bands
        or visibility not in policy.visibility_states
        or temporal not in policy.temporal_evidence
        or review_outcome not in policy.review_outcomes
        or consent not in {"granted", "denied", "missing", "not_applicable"}
    ):
        _fail(AI_INPUT_INVALID)

    pipeline = policy.pipelines[pipeline_code]
    if lifecycle_state == "disabled":
        return Decision("blocked", policy.reason_codes["policy_disabled"])
    if (
        pipeline.consent_requirement == "required"
        and consent != "granted"
        or pipeline.consent_requirement == "contextual"
        and consent in {"denied", "missing"}
    ):
        return Decision("blocked", policy.reason_codes["consent_required"])
    if visibility == "unknown":
        return Decision("non_decision", policy.reason_codes["visibility_unknown"])
    if visibility == "partial_visibility":
        return Decision("non_decision", policy.reason_codes["partial_visibility"])
    if (
        pipeline.temporal_evidence_requirement in {"multi_frame", "contextual_sequence"}
        and temporal != "multi_frame"
    ):
        return Decision("review_required", policy.reason_codes["temporal_evidence_required"])
    if confidence in {"unknown", "low"}:
        return Decision("review_required", policy.reason_codes["low_confidence"])
    if lifecycle_state == "shadow":
        return Decision("shadow_recorded", policy.reason_codes["shadow_evaluation_only"])
    if review_outcome == "needs_more_evidence":
        return Decision("review_required", policy.reason_codes["more_evidence_required"])
    if review_outcome == "confirmed":
        return Decision("review_confirmed", policy.reason_codes["human_review_confirmed"])
    if review_outcome == "rejected":
        return Decision("review_rejected", policy.reason_codes["human_review_rejected"])
    if pipeline.human_review == "always":
        return Decision("review_required", policy.reason_codes["human_review_required"])
    return Decision("candidate_only", policy.reason_codes["business_rule_required"])


def validate_fixture(document: dict[str, object], policy: AiShadowReviewPolicy) -> int:
    """Validate all synthetic compatibility cases against the policy."""

    _require_exact_keys(document, {"_fixture", "policy_version", "cases"})
    if (
        document["_fixture"] != SYNTHETIC_MARKER
        or document["policy_version"] != policy.policy_version
    ):
        _fail()
    cases = _list(document["cases"])
    if len(cases) < 10:
        _fail()
    case_codes: set[str] = set()
    for value in cases:
        case = _mapping(value)
        case_code = _text(case.get("case_code"))
        if STABLE_CODE.fullmatch(case_code) is None or case_code in case_codes:
            _fail()
        case_codes.add(case_code)
        decision = evaluate_case(case, policy)
        if (
            decision.decision != _text(case["expected_decision"])
            or decision.reason_code != _text(case["expected_reason_code"])
            or decision.business_conclusion_allowed
        ):
            _fail()
    return len(cases)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        policy = validate_policy(_load_json(repo_root / POLICY_PATH))
        case_count = validate_fixture(_load_json(repo_root / FIXTURE_PATH), policy)
    except AiPolicyError as error:
        print(f"ai_shadow_review_policy=FAIL code={error.code}", file=sys.stderr)
        return 1
    print("ai_shadow_review_policy=PASS")
    print(f"policy_version={policy.policy_version}")
    print(f"pipelines_checked={len(policy.pipelines)}")
    print(f"synthetic_cases_checked={case_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
