from __future__ import annotations

import pytest
from evidence_service.domain.capacity import (
    WORST_CASE_GB_PER_DAY,
    AttachmentRatioPolicy,
)
from evidence_service.domain.errors import EvidenceError


def test_volume_model_matches_issue_worst_case_and_scales_by_attachment_ratio() -> None:
    policy = AttachmentRatioPolicy(expected_ratio=0.05, alert_threshold=0.08)
    assert pytest.approx(285.6) == WORST_CASE_GB_PER_DAY
    assert policy.expected_gb_per_day() == pytest.approx(14.28)
    assert policy.should_alert(attached_events=9, total_events=100) is True
    assert policy.should_alert(attached_events=9, total_events=99) is False


def test_capacity_policy_rejects_unapproved_or_invalid_thresholds() -> None:
    with pytest.raises(EvidenceError, match="EVIDENCE_CAPACITY_CONFIGURATION_INVALID"):
        AttachmentRatioPolicy(expected_ratio=0.10, alert_threshold=0.10)
    with pytest.raises(EvidenceError, match="EVIDENCE_CAPACITY_SAMPLE_INVALID"):
        AttachmentRatioPolicy(expected_ratio=0.05, alert_threshold=0.08).ratio(
            attached_events=2,
            total_events=1,
        )
