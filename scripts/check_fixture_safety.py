"""Reject unsafe tracked fixture and seed files without printing their contents."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

MAX_FIXTURE_BYTES = 256 * 1024
SYNTHETIC_MARKER = "SYNTHETIC_TEST_DATA_ONLY"

FIXTURE_DIRECTORY_NAMES = frozenset({"fixture", "fixtures", "seed", "seeds", "test-fixtures"})
ALLOWED_SUFFIXES = frozenset({".csv", ".json", ".jsonl", ".sql", ".toml", ".txt", ".yaml", ".yml"})
POLICY_FILENAMES = frozenset({"readme.md"})

FORBIDDEN_PATTERNS = (
    (
        "credential-field",
        re.compile(
            r"(?i)[\"']?(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
            r"refresh[_-]?token|private[_-]?key)[\"']?\s*[:=]"
        ),
    ),
    ("credentialed-url", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@")),
    ("camera-stream-url", re.compile(r"(?i)\brtsps?://")),
    (
        "biometric-or-media-field",
        re.compile(
            r"(?i)[\"'](?:face_embedding|embedding|face_image|image_base64|frame_base64|"
            r"video_base64|raw_image|raw_frame)[\"']\s*:"
        ),
    ),
    ("embedded-image-data", re.compile(r"(?i)data:image/[a-z0-9.+-]+;base64,")),
    (
        "realistic-person-profile-field",
        re.compile(
            r"(?i)[\"'](?:student_name|parent_name|staff_name|full_name|date_of_birth|"
            r"phone|address|national_id|identity_number)[\"']\s*:"
        ),
    ),
    (
        "private-media-url",
        re.compile(
            r"(?i)https?://(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|"
            r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
            r"[^\s/]+\.local)(?:[/:]|$)"
        ),
    ),
)

EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b")
URL_HOST_PATTERN = re.compile(r"(?i)\bhttps?://([^\s/:@]+)")


def normalized_path(path: str) -> PurePosixPath:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return PurePosixPath(normalized)


def is_fixture_path(path: str) -> bool:
    pure_path = normalized_path(path)
    parts = tuple(part.lower() for part in pure_path.parts)
    name = pure_path.name.lower()
    return any(part in FIXTURE_DIRECTORY_NAMES for part in parts[:-1]) or any(
        token in name for token in (".fixture.", ".sanitized.", ".synthetic.")
    )


def inspect_fixture(path: Path, relative_path: str) -> list[str]:
    """Return stable violation categories without returning fixture content."""

    name = normalized_path(relative_path).name.lower()
    if name in POLICY_FILENAMES:
        return []

    violations: list[str] = []
    if path.is_symlink():
        return ["fixture-symlink"]

    try:
        size = path.stat().st_size
    except OSError:
        return ["unreadable-fixture"]

    if size > MAX_FIXTURE_BYTES:
        violations.append("oversized-fixture")

    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        violations.append("disallowed-fixture-type")

    if not any(token in name for token in (".sanitized.", ".synthetic.")):
        violations.append("unsafe-fixture-name")

    if size > MAX_FIXTURE_BYTES:
        return sorted(set(violations))

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        violations.append("non-text-fixture")
        return sorted(set(violations))
    except OSError:
        violations.append("unreadable-fixture")
        return sorted(set(violations))

    if SYNTHETIC_MARKER not in content:
        violations.append("missing-synthetic-marker")

    for category, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(content):
            violations.append(category)

    for match in EMAIL_PATTERN.finditer(content):
        if not match.group(1).lower().endswith(".invalid"):
            violations.append("real-looking-email")
            break

    for match in URL_HOST_PATTERN.finditer(content):
        if not match.group(1).lower().endswith(".invalid"):
            violations.append("non-reserved-url")
            break

    if path.suffix.lower() == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError:
            violations.append("invalid-json-fixture")

    return sorted(set(violations))


def tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_count = 0
    violations: list[tuple[str, str]] = []

    for relative_path in tracked_files(repo_root):
        if not is_fixture_path(relative_path):
            continue
        if normalized_path(relative_path).name.lower() in POLICY_FILENAMES:
            continue
        fixture_count += 1
        candidate = repo_root / relative_path
        for category in inspect_fixture(candidate, relative_path):
            violations.append((relative_path, category))

    if violations:
        print("fixture_safety=FAIL", file=sys.stderr)
        for path, category in violations:
            print(f"{category}: {path}", file=sys.stderr)
        return 1

    print("fixture_safety=PASS")
    print(f"tracked_fixtures_checked={fixture_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
