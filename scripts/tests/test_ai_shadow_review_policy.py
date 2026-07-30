from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_ai_shadow_review_policy import (
    AI_INPUT_INVALID,
    AI_POLICY_INVALID,
    FIXTURE_PATH,
    POLICY_PATH,
    AiPolicyError,
    evaluate_case,
    production_gates_complete,
    transition_authorized,
    validate_fixture,
    validate_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _document(path: Path) -> dict[str, object]:
    value: object = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return value


def _case(case_code: str) -> dict[str, object]:
    fixture = _document(FIXTURE_PATH)
    cases = fixture["cases"]
    assert isinstance(cases, list)
    return next(
        item for item in cases if isinstance(item, dict) and item.get("case_code") == case_code
    )


def test_repository_policy_and_synthetic_cases_are_compatible() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert validate_fixture(_document(FIXTURE_PATH), policy) == 12
    assert set(policy.pipelines) == {
        "facial_recognition",
        "littering_detection",
        "smoking_detection",
        "student_uniform_detection",
        "kitchen_ppe_detection",
    }


def test_shadow_cannot_transition_directly_to_production() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert not transition_authorized("shadow", "production", "project_owner", policy)
    assert not transition_authorized("accepted", "production", "ai_operator", policy)
    assert transition_authorized("accepted", "production", "project_owner", policy)
    decision = evaluate_case(_case("shadow_face_candidate_is_evaluation_only"), policy)
    assert decision.decision == "shadow_recorded"
    assert not decision.business_conclusion_allowed


def test_sensitive_pipeline_results_never_become_automatic_conclusions() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    for case_code in (
        "littering_single_frame_requires_temporal_evidence",
        "smoking_requires_human_review",
        "reviewed_smoking_remains_a_controlled_review_result",
        "uniform_partial_visibility_is_non_decision",
        "ppe_unknown_visibility_is_non_decision",
        "face_candidate_requires_separate_business_rule",
    ):
        assert not evaluate_case(_case(case_code), policy).business_conclusion_allowed


def test_production_requires_the_exact_versioned_gate_set() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    assert production_gates_complete(set(policy.production_gates), policy)
    incomplete = set(policy.production_gates)
    incomplete.remove("rollback_trigger_recorded")
    assert not production_gates_complete(incomplete, policy)
    assert not production_gates_complete(
        {*policy.production_gates, "unapproved_extra_gate"}, policy
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_state",
        "direct_shadow_production",
        "automatic_conclusion",
        "missing_human_review",
        "transition_authority",
        "smoking_wording",
        "littering_single_frame",
        "missing_rollout_gate",
        "cross_pipeline_enable",
    ],
)
def test_policy_rejects_security_semantic_drift(mutation: str) -> None:
    document = copy.deepcopy(_document(POLICY_PATH))
    lifecycle = document["lifecycle"]
    controls = document["common_controls"]
    pipelines = document["pipelines"]
    production = document["production_enable"]
    rollback = document["rollback_disable"]
    assert isinstance(lifecycle, dict)
    assert isinstance(controls, dict)
    assert isinstance(pipelines, dict)
    assert isinstance(production, dict)
    assert isinstance(rollback, dict)

    if mutation == "unknown_state":
        states = lifecycle["states"]
        assert isinstance(states, list)
        states.append("automatic")
    elif mutation == "direct_shadow_production":
        transitions = lifecycle["allowed_transitions"]
        assert isinstance(transitions, dict)
        shadow = transitions["shadow"]
        assert isinstance(shadow, list)
        shadow.append("production")
    elif mutation == "automatic_conclusion":
        controls["automatic_disciplinary_conclusion_allowed"] = True
    elif mutation == "missing_human_review":
        smoking = pipelines["smoking_detection"]
        assert isinstance(smoking, dict)
        del smoking["human_review"]
    elif mutation == "transition_authority":
        authorities = lifecycle["transition_authorities"]
        assert isinstance(authorities, dict)
        authorities["accepted_to_production"] = "ai_operator"
    elif mutation == "smoking_wording":
        smoking = pipelines["smoking_detection"]
        assert isinstance(smoking, dict)
        smoking["output_label"] = "confirmed_smoking"
    elif mutation == "littering_single_frame":
        littering = pipelines["littering_detection"]
        assert isinstance(littering, dict)
        littering["single_frame_confirmation_allowed"] = True
    elif mutation == "missing_rollout_gate":
        gates = production["all_required_gates"]
        assert isinstance(gates, list)
        gates.remove("rollback_trigger_recorded")
    else:
        rollback["cross_pipeline_enable_allowed"] = True

    with pytest.raises(AiPolicyError, match=AI_POLICY_INVALID):
        validate_policy(document)


def test_invalid_confidence_visibility_and_review_values_fail_closed() -> None:
    policy = validate_policy(_document(POLICY_PATH))
    base = _case("shadow_face_candidate_is_evaluation_only")

    for field, invalid_value in (
        ("confidence_band", "very_high"),
        ("visibility", "mostly_clear"),
        ("human_review_outcome", "auto_confirmed"),
    ):
        modified = copy.deepcopy(base)
        modified[field] = invalid_value
        with pytest.raises(AiPolicyError, match=AI_INPUT_INVALID):
            evaluate_case(modified, policy)


def test_missing_biometric_consent_blocks_face_processing() -> None:
    policy = validate_policy(_document(POLICY_PATH))

    decision = evaluate_case(_case("face_candidate_without_consent_is_blocked"), policy)
    assert decision.decision == "blocked"
    assert decision.reason_code == "AI_CONSENT_REQUIRED"
