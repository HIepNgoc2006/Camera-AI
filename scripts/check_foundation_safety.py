"""Validate durable repository structure, links, ignore rules, and safe defaults."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REQUIRED_TRACKED_PATHS = frozenset(
    {
        ".dockerignore",
        ".env.example",
        ".github/workflows/quality.yml",
        ".github/workflows/secret-scan.yml",
        ".gitignore",
        "README.md",
        "apps/README.md",
        "compose.yml",
        "docs/README.md",
        "infra/README.md",
        "packages/README.md",
        "scripts/README.md",
        "services/README.md",
        "workers/README.md",
    }
)

EXPECTED_IGNORED_PATHS = (
    ".env",
    ".env.production",
    ".local/docker-data/redis/state.bin",
    "datasets/sample.json",
    "evidence/frame.jpg",
    "implementation-planning/planning/local.md",
    "logs/service.log",
    "models/model.onnx",
    "references/vendor.md",
    "tmp/review.txt",
)

REQUIRED_DOCKERIGNORE_PATTERNS = frozenset(
    {
        ".env",
        ".env.*",
        ".git",
        ".local",
        "AGENTS.md",
        "backups",
        "datasets",
        "evidence",
        "implementation-planning",
        "logs",
        "project-docs",
        "references",
    }
)

FAIL_CLOSED_DEFAULTS = {
    "ANSVIS_DEBUG_ENABLED": "false",
    "BIOMETRIC_PROCESSING_ENABLED": "false",
    "EVIDENCE_BUCKET_PUBLIC": "false",
    "LOG_SENSITIVE_PAYLOADS": "false",
}

PLACEHOLDER_KEYS = frozenset(
    {
        "ANSVIS_WEBHOOK_SECRET",
        "MINIO_ROOT_PASSWORD",
        "MINIO_ROOT_USER",
        "POSTGRES_TEST_PASSWORD",
        "RABBITMQ_PASSWORD",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
    }
)

MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
URI_SCHEME_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def tracked_paths(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}


def tracked_text(repo_root: Path, relative_path: str) -> str:
    """Read the staged/index version so local skip-worktree files remain untouched."""

    result = subprocess.run(
        ["git", "show", f":{relative_path}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def parse_env_example(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def validate_env_example(content: str) -> list[str]:
    values = parse_env_example(content)
    violations: list[str] = []

    for key, expected in FAIL_CLOSED_DEFAULTS.items():
        if values.get(key, "").lower() != expected:
            violations.append(f"unsafe-default:{key}")

    for key in PLACEHOLDER_KEYS:
        if not values.get(key, "").lower().startswith("replace_with_"):
            violations.append(f"non-placeholder:{key}")

    database_uri = values.get("DATABASE_URI", "")
    if not all(token in database_uri for token in ("codex_mcp", "Camera_AI_test", "replace_with_")):
        violations.append("invalid-development-database-placeholder")

    test_database_uri = values.get("TEST_DATABASE_URI", "")
    if not all(token in test_database_uri for token in ("codex_mcp", "Camera_AI_test", "55432")):
        violations.append("invalid-test-database-placeholder")

    return sorted(violations)


def validate_dockerignore(content: str) -> list[str]:
    patterns = {
        line.strip().rstrip("/")
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = REQUIRED_DOCKERIGNORE_PATTERNS - patterns
    return [f"missing-dockerignore-pattern:{pattern}" for pattern in sorted(missing)]


def validate_local_markdown_links(
    markdown_path: str,
    content: str,
    tracked: set[str],
) -> list[str]:
    violations: list[str] = []
    parent = PurePosixPath(markdown_path).parent

    for raw_target in MARKDOWN_LINK_PATTERN.findall(content):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        if not target or target.startswith("#") or target.startswith("/"):
            continue
        if URI_SCHEME_PATTERN.match(target):
            continue

        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        resolved = parent.joinpath(path_part)
        normalized_parts: list[str] = []
        for part in resolved.parts:
            if part == ".":
                continue
            if part == "..":
                if normalized_parts:
                    normalized_parts.pop()
                continue
            normalized_parts.append(part)
        normalized = "/".join(normalized_parts).rstrip("/")

        if normalized not in tracked and not any(
            path.startswith(f"{normalized}/") for path in tracked
        ):
            violations.append(f"broken-local-link:{markdown_path}->{target}")

    return violations


def git_ignored(repo_root: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", relative_path],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    tracked = tracked_paths(repo_root)
    violations: list[str] = []

    for path in sorted(REQUIRED_TRACKED_PATHS - tracked):
        violations.append(f"missing-required-path:{path}")

    for path in EXPECTED_IGNORED_PATHS:
        if not git_ignored(repo_root, path):
            violations.append(f"missing-gitignore-coverage:{path}")
    if git_ignored(repo_root, ".env.example"):
        violations.append("env-example-must-remain-trackable")

    violations.extend(validate_env_example(tracked_text(repo_root, ".env.example")))
    violations.extend(validate_dockerignore(tracked_text(repo_root, ".dockerignore")))

    markdown_paths = sorted(path for path in tracked if path.lower().endswith(".md"))
    for markdown_path in markdown_paths:
        content = tracked_text(repo_root, markdown_path)
        violations.extend(validate_local_markdown_links(markdown_path, content, tracked))

    if violations:
        print("foundation_safety=FAIL", file=sys.stderr)
        for violation in sorted(set(violations)):
            print(violation, file=sys.stderr)
        return 1

    print("foundation_safety=PASS")
    print(f"tracked_markdown_checked={len(markdown_paths)}")
    print(f"ignore_cases_checked={len(EXPECTED_IGNORED_PATHS) + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
