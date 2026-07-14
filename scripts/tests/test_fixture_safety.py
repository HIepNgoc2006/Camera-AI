from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_fixture_safety import (
    MAX_FIXTURE_BYTES,
    inspect_fixture,
    is_fixture_path,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class FixtureSafetyTests(unittest.TestCase):
    def test_recognizes_supported_fixture_locations(self) -> None:
        relative_paths = (
            "packages/test-fixtures/core/identifiers.synthetic.json",
            "services/identity/tests/fixtures/user.synthetic.json",
            "scripts/example.sanitized.csv",
        )
        for relative_path in relative_paths:
            with self.subTest(relative_path=relative_path):
                self.assertTrue(is_fixture_path(relative_path))

    def test_repository_examples_are_safe(self) -> None:
        relative_paths = (
            "packages/test-fixtures/core/identifiers.synthetic.json",
            "packages/test-fixtures/ansvis/event.synthetic.json",
        )
        for relative_path in relative_paths:
            with self.subTest(relative_path=relative_path):
                self.assertEqual(inspect_fixture(REPO_ROOT / relative_path, relative_path), [])

    def test_reserved_invalid_contact_values_are_safe(self) -> None:
        payload = (
            '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","email":"test@example.invalid",'
            '"url":"https://media.example.invalid/item"}'
        )
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.synthetic.json"
            fixture.write_text(payload, encoding="utf-8")

            self.assertEqual(inspect_fixture(fixture, "fixtures/record.synthetic.json"), [])

    def test_rejects_sensitive_fixture_categories(self) -> None:
        cases = (
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
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
                    fixture = Path(temp_dir) / "record.synthetic.json"
                    fixture.write_text(payload, encoding="utf-8")
                    violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

                self.assertIn(expected, violations)

    def test_rejects_unsafe_name_and_missing_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.json"
            fixture.write_text("{}", encoding="utf-8")
            violations = inspect_fixture(fixture, "fixtures/record.json")

        self.assertIn("unsafe-fixture-name", violations)
        self.assertIn("missing-synthetic-marker", violations)

    def test_rejects_oversized_content_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.synthetic.json"
            fixture.write_text("x" * (MAX_FIXTURE_BYTES + 1), encoding="utf-8")
            violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

        self.assertIn("oversized-fixture", violations)


if __name__ == "__main__":
    unittest.main()
