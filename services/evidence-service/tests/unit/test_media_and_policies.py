from __future__ import annotations

import re
import struct

import pytest
from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.media import IMAGE_LIMIT, probe_header, validate_media
from evidence_service.domain.models import AccessAction, EvidenceState, MediaKind
from evidence_service.domain.policies import (
    PolicyActivation,
    access_ttl,
    new_object_key,
    require_transition,
    selection_bounds,
    validate_selection,
)


def png_header(width: int = 640, height: int = 480) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


def test_object_keys_are_random_opaque_and_contain_no_logical_identifiers() -> None:
    first = new_object_key()
    second = new_object_key()

    assert first != second
    assert re.fullmatch(r"evidence/v1/[0-9a-f]{2}/[0-9a-f]{32}", first)
    assert all(
        forbidden not in first
        for forbidden in ("tenant", "school", "student", "event", "camera", "task")
    )


def test_magic_mime_extension_dimensions_and_size_must_agree() -> None:
    probe = validate_media(
        header=png_header(),
        declared_content_type="image/png",
        extension=".png",
        size_bytes=1024,
        expected_kind=MediaKind.IMAGE,
        trusted_width=640,
        trusted_height=480,
        trusted_duration_ms=None,
    )
    assert probe.content_type == "image/png"
    assert (probe.width, probe.height) == (640, 480)

    with pytest.raises(EvidenceError, match="EVIDENCE_MEDIA_INVALID"):
        validate_media(
            header=png_header(),
            declared_content_type="image/jpeg",
            extension="jpg",
            size_bytes=1024,
            expected_kind=MediaKind.IMAGE,
            trusted_width=640,
            trusted_height=480,
            trusted_duration_ms=None,
        )
    with pytest.raises(EvidenceError, match="EVIDENCE_MEDIA_TOO_LARGE"):
        validate_media(
            header=png_header(),
            declared_content_type="image/png",
            extension="png",
            size_bytes=IMAGE_LIMIT + 1,
            expected_kind=MediaKind.IMAGE,
            trusted_width=640,
            trusted_height=480,
            trusted_duration_ms=None,
        )


def test_unrecognized_or_truncated_magic_is_rejected() -> None:
    with pytest.raises(EvidenceError, match="EVIDENCE_MEDIA_INVALID"):
        probe_header(b"not-media-and-never-a-real-student-image")
    with pytest.raises(EvidenceError, match="EVIDENCE_MEDIA_INVALID"):
        probe_header(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    ("event_type", "bounds"),
    [
        ("student_attendance", (1, 4)),
        ("staff_timekeeping", (1, 4)),
        ("emotion_insight", (0, 0)),
        ("littering", (5, 20)),
        ("smoking", (6, 20)),
        ("student_uniform", (2, 5)),
        ("kitchen_ppe", (2, 6)),
    ],
)
def test_selection_bounds_match_approved_business_baseline(
    event_type: str,
    bounds: tuple[int, int],
) -> None:
    assert selection_bounds(event_type) == bounds
    validate_selection(event_type, bounds[0])
    validate_selection(event_type, bounds[1])


def test_selection_and_state_machine_fail_closed() -> None:
    with pytest.raises(EvidenceError, match="EVIDENCE_SELECTION_INVALID"):
        validate_selection("smoking", 5)
    with pytest.raises(EvidenceError, match="EVIDENCE_SELECTION_POLICY_UNAVAILABLE"):
        validate_selection("invented_pipeline", 1)
    require_transition(EvidenceState.PENDING_UPLOAD, EvidenceState.QUARANTINED)
    with pytest.raises(EvidenceError, match="EVIDENCE_STATE_CONFLICT"):
        require_transition(EvidenceState.PENDING_UPLOAD, EvidenceState.AVAILABLE)


def test_runtime_activation_requires_all_named_approvals_and_ttl_is_bounded() -> None:
    assert PolicyActivation().active is False
    assert (
        PolicyActivation(
            privacy_legal_approved=True,
            security_ops_approved=True,
            business_owner_approved=True,
        ).active
        is True
    )
    assert access_ttl(AccessAction.VIEW_ORIGINAL, None) == 60
    assert access_ttl(AccessAction.VIEW_ORIGINAL, 300) == 300
    assert access_ttl(AccessAction.EXPORT, 120) == 120
    with pytest.raises(EvidenceError, match="EVIDENCE_ACCESS_INVALID"):
        access_ttl(AccessAction.EXPORT, 121)
