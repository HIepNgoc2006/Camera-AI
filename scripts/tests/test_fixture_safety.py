from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.check_fixture_safety import (
    MAX_FIXTURE_BYTES,
    inspect_fixture,
    is_fixture_path,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "relative_path",
    (
        "packages/test-fixtures/core/identifiers.synthetic.json",
        "services/identity/tests/fixtures/user.synthetic.json",
        "scripts/example.sanitized.csv",
    ),
)
def test_recognizes_supported_fixture_locations(relative_path: str) -> None:
    assert is_fixture_path(relative_path)


@pytest.mark.parametrize(
    "relative_path",
    (
        "packages/test-fixtures/core/identifiers.synthetic.json",
        "packages/test-fixtures/ansvis/event.synthetic.json",
    ),
)
def test_repository_examples_are_safe(relative_path: str) -> None:
    assert inspect_fixture(REPO_ROOT / relative_path, relative_path) == []


def test_reserved_invalid_contact_values_are_safe() -> None:
    payload = (
        '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","email":"test@example.invalid",'
        '"url":"https://media.example.invalid/item"}'
    )
    with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
        fixture = Path(temp_dir) / "record.synthetic.json"
        fixture.write_text(payload, encoding="utf-8")

        assert inspect_fixture(fixture, "fixtures/record.synthetic.json") == []


@pytest.mark.parametrize(
    ("payload", "expected"),
    (
        (
            '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","student_name":"Synthetic"}',
            "realistic-person-profile-field",
        ),
        (
            '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","image_base64":"synthetic"}',
            "biometric-or-media-field",
        ),
        (
            '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","media_url":"http://127.0.0.1/frame"}',
            "private-media-url",
        ),
        (
            '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","email":"person@example.com"}',
            "real-looking-email",
        ),
        (
            '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","url":"https://example.com/item"}',
            "non-reserved-url",
        ),
    ),
)
def test_rejects_sensitive_fixture_categories(payload: str, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
        fixture = Path(temp_dir) / "record.synthetic.json"
        fixture.write_text(payload, encoding="utf-8")

        assert expected in inspect_fixture(fixture, "fixtures/record.synthetic.json")


def test_rejects_unsafe_name_and_missing_marker() -> None:
    with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
        fixture = Path(temp_dir) / "record.json"
        fixture.write_text("{}", encoding="utf-8")
        violations = inspect_fixture(fixture, "fixtures/record.json")

    assert "unsafe-fixture-name" in violations
    assert "missing-synthetic-marker" in violations


def test_rejects_oversized_content_without_reading_it() -> None:
    with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
        fixture = Path(temp_dir) / "record.synthetic.json"
        fixture.write_text("x" * (MAX_FIXTURE_BYTES + 1), encoding="utf-8")
        violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

    assert "oversized-fixture" in violations
