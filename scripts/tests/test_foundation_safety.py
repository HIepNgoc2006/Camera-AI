from __future__ import annotations

import unittest

from scripts.check_foundation_safety import (
    validate_dockerignore,
    validate_env_example,
    validate_local_markdown_links,
)


class FoundationSafetyTests(unittest.TestCase):
    def test_accepts_safe_environment_defaults(self) -> None:
        scheme = "postgresql"
        user_info = "codex_mcp" + ":" + "replace_with_password"
        content = f"""
DATABASE_URI={scheme}://{user_info}@localhost:5432/Camera_AI_test
TEST_DATABASE_URI={scheme}://{user_info}@localhost:55432/Camera_AI_test
ANSVIS_DEBUG_ENABLED=false
BIOMETRIC_PROCESSING_ENABLED=false
EVIDENCE_BUCKET_PUBLIC=false
LOG_SENSITIVE_PAYLOADS=false
ANSVIS_WEBHOOK_SECRET=replace_with_secret
MINIO_ROOT_PASSWORD=replace_with_password
MINIO_ROOT_USER=replace_with_user
POSTGRES_TEST_PASSWORD=replace_with_password
RABBITMQ_PASSWORD=replace_with_password
S3_ACCESS_KEY=replace_with_key
S3_SECRET_KEY=replace_with_secret
"""
        self.assertEqual(validate_env_example(content), [])

    def test_rejects_unsafe_environment_defaults_and_non_placeholder(self) -> None:
        violations = validate_env_example("BIOMETRIC_PROCESSING_ENABLED=true\n")

        self.assertIn("unsafe-default:BIOMETRIC_PROCESSING_ENABLED", violations)
        self.assertIn("non-placeholder:ANSVIS_WEBHOOK_SECRET", violations)

    def test_detects_missing_dockerignore_pattern(self) -> None:
        violations = validate_dockerignore(".git\n.env\n")

        self.assertIn("missing-dockerignore-pattern:.local", violations)

    def test_validates_relative_markdown_links(self) -> None:
        tracked = {"README.md", "apps/README.md", "docs/guide.md"}

        self.assertEqual(validate_local_markdown_links("README.md", "[Apps](apps/)", tracked), [])
        self.assertEqual(
            validate_local_markdown_links("docs/guide.md", "[Root](../README.md)", tracked),
            [],
        )
        self.assertEqual(
            validate_local_markdown_links("README.md", "[Missing](missing.md)", tracked),
            ["broken-local-link:README.md->missing.md"],
        )


if __name__ == "__main__":
    unittest.main()
