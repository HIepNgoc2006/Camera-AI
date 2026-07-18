from __future__ import annotations

from audit_log_service.domain.policies import ACTION_POLICIES, APPROVED_ACTIONS


def test_registry_contains_the_approved_cross_domain_audit_taxonomy() -> None:
    required = {
        "AUTH_LOGIN_SUCCEEDED",
        "CONSENT_WITHDRAWN",
        "ANSVIS_SOURCE_AUTH_DENIED",
        "ATTENDANCE_CORRECTION_DECIDED",
        "TIMEKEEPING_EXPORTED",
        "VIOLATION_REVIEW_DECIDED",
        "EVIDENCE_VIEW_DENIED",
        "REPORT_EXPORT_DOWNLOADED",
        "MODEL_DEPLOYMENT_CHANGED",
        "KEY_COMPROMISE_DECLARED",
        "RETENTION_DELETE_FAILED",
        "BACKUP_RESTORE_FAILED",
        "AUDIT_INTEGRITY_FAILED",
    }

    assert required <= APPROVED_ACTIONS
    assert len(APPROVED_ACTIONS) >= 82
    assert len(APPROVED_ACTIONS) == len(ACTION_POLICIES)
