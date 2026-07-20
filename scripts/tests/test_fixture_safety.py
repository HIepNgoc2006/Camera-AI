from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
            "scripts/seed_data.py",
        )
        for relative_path in relative_paths:
            with self.subTest(relative_path=relative_path):
                self.assertTrue(is_fixture_path(relative_path))

    def test_repository_examples_are_safe(self) -> None:
        relative_paths = (
            "packages/test-fixtures/core/identifiers.synthetic.json",
            "packages/test-fixtures/ansvis/event.synthetic.json",
            "packages/test-fixtures/ansvis/event-contract-cases.synthetic.json",
            "packages/test-fixtures/ansvis/timestamps.synthetic.json",
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
            (
                '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","camera_id":"camera-prod-01"}',
                "non-synthetic-identifier",
            ),
            (
                '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","stream":"rtsp://camera.invalid"}',
                "camera-stream-url",
            ),
            (
                '{"_fixture":"SYNTHETIC_TEST_DATA_ONLY","password":"fake-canary"}',
                "credential-field",
            ),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
                    fixture = Path(temp_dir) / "record.synthetic.json"
                    fixture.write_text(payload, encoding="utf-8")
                    violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

                self.assertIn(expected, violations)

    def test_rejects_runtime_constructed_credentialed_url(self) -> None:
        scheme = "https"
        user_info = "synthetic-user" + ":" + "synthetic-pass"
        credentialed_url = f"{scheme}://{user_info}@example.invalid/item"
        payload = json.dumps(
            {
                "_fixture": "SYNTHETIC_TEST_DATA_ONLY",
                "url": credentialed_url,
            }
        )

        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.synthetic.json"
            fixture.write_text(payload, encoding="utf-8")

            violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

        self.assertIn("credentialed-url", violations)

    def test_rejects_unsafe_name_and_missing_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.json"
            fixture.write_text("{}", encoding="utf-8")
            violations = inspect_fixture(fixture, "fixtures/record.json")

        self.assertIn("unsafe-fixture-name", violations)
        self.assertIn("invalid-synthetic-marker", violations)

    def test_rejects_marker_that_is_not_the_exact_json_field(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.synthetic.json"
            fixture.write_text(
                '{"note":"SYNTHETIC_TEST_DATA_ONLY","event_id":"event_test_0001"}',
                encoding="utf-8",
            )
            violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

        self.assertIn("invalid-synthetic-marker", violations)

    def test_rejects_invalid_json_and_binary_fixture_type(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            invalid_json = Path(temp_dir) / "record.synthetic.json"
            invalid_json.write_text("{invalid", encoding="utf-8")
            binary = Path(temp_dir) / "record.synthetic.bin"
            binary.write_bytes(b"\x00\xff")

            json_violations = inspect_fixture(invalid_json, "fixtures/record.synthetic.json")
            binary_violations = inspect_fixture(binary, "fixtures/record.synthetic.bin")

        self.assertIn("invalid-json-fixture", json_violations)
        self.assertIn("disallowed-fixture-type", binary_violations)
        self.assertIn("non-text-fixture", binary_violations)

    def test_rejects_fixture_symlink_without_reading_target(self) -> None:
        fixture = Path("record.synthetic.json")
        with patch.object(Path, "is_symlink", return_value=True):
            violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

        self.assertEqual(violations, ["fixture-symlink"])

    def test_rejects_seed_like_file_outside_seed_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "seed_data.py"
            fixture.write_text("SYNTHETIC_TEST_DATA_ONLY", encoding="utf-8")
            violations = inspect_fixture(fixture, "scripts/seed_data.py")

        self.assertTrue(is_fixture_path("scripts/seed_data.py"))
        self.assertIn("disallowed-fixture-type", violations)
        self.assertIn("unsafe-fixture-name", violations)

    def test_rejects_oversized_content_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-test-") as temp_dir:
            fixture = Path(temp_dir) / "record.synthetic.json"
            fixture.write_text("x" * (MAX_FIXTURE_BYTES + 1), encoding="utf-8")
            violations = inspect_fixture(fixture, "fixtures/record.synthetic.json")

        self.assertIn("oversized-fixture", violations)


if __name__ == "__main__":
    unittest.main()
