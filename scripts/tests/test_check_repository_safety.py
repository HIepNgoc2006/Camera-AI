from __future__ import annotations

import unittest

from scripts.check_repository_safety import MAX_TRACKED_FILE_BYTES, classify_path


class RepositorySafetyPolicyTests(unittest.TestCase):
    def test_allows_implementation_paths_and_examples(self) -> None:
        allowed = (
            ".env.example",
            "services/identity/alembic/versions/001_create_user.sql",
            "apps/web/package.json",
            "docs/security/secret-scanning.md",
        )
        for path in allowed:
            with self.subTest(path=path):
                self.assertIsNone(classify_path(path, 128))

    def test_blocks_sensitive_or_local_only_paths(self) -> None:
        blocked = {
            ".env": "unsafe-environment-file",
            ".env.production": "unsafe-environment-file",
            "AGENTS.md": "local-agent-rules",
            "datasets/sample.json": "local-or-sensitive-directory",
            "evidence/frame.jpg": "local-or-sensitive-directory",
            "references/vendor.md": "local-or-sensitive-directory",
            "secrets/app.pem": "local-or-sensitive-directory",
            "config/service-account-prod.json": "service-account-file",
            "exports/camera.dump.sql": "local-or-sensitive-directory",
            "release/model.onnx": "secret-data-media-or-model-file",
            "video/pilot.mp4": "secret-data-media-or-model-file",
        }
        for path, expected in blocked.items():
            with self.subTest(path=path):
                self.assertEqual(classify_path(path, 128), expected)

    def test_blocks_oversized_generic_file(self) -> None:
        self.assertEqual(
            classify_path("generated/report.bin", MAX_TRACKED_FILE_BYTES + 1),
            "oversized-tracked-file",
        )


if __name__ == "__main__":
    unittest.main()
