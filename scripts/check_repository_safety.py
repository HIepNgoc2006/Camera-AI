"""Fail closed when tracked paths violate repository safety policy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

MAX_TRACKED_FILE_BYTES = 10 * 1024 * 1024

ALLOWED_ENV_EXAMPLES = {
    ".env.example",
    ".env.local.example",
    ".env.staging.example",
    ".env.production.example",
}

FORBIDDEN_DIRECTORY_NAMES = {
    ".agents",
    ".codex",
    ".local",
    "artifacts",
    "assets",
    "backups",
    "camera-exports",
    "checkpoints",
    "credentials",
    "database-dumps",
    "datasets",
    "evidence",
    "executive-summary",
    "exports",
    "face-db",
    "github-workflow",
    "implementation-planning",
    "logs",
    "models",
    "private",
    "project-docs",
    "references",
    "runs",
    "secrets",
    "tmp",
    "training-data",
}

FORBIDDEN_SUFFIXES = {
    ".avi",
    ".backup",
    ".db",
    ".dump",
    ".engine",
    ".jks",
    ".kdbx",
    ".key",
    ".keystore",
    ".mkv",
    ".mov",
    ".mp4",
    ".onnx",
    ".p12",
    ".pem",
    ".pfx",
    ".pt",
    ".pth",
    ".sqlite",
    ".sqlite3",
    ".weights",
}

FORBIDDEN_COMPOUND_SUFFIXES = (".dump.sql", ".sql.bak", ".sql.gz")


def classify_path(path: str, size: int) -> str | None:
    """Return a policy category without reading or printing file contents."""

    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    pure_path = PurePosixPath(normalized)
    lower_parts = tuple(part.lower() for part in pure_path.parts)
    lower_name = pure_path.name.lower()

    if lower_name == "agents.md":
        return "local-agent-rules"

    if any(part in FORBIDDEN_DIRECTORY_NAMES for part in lower_parts[:-1]):
        return "local-or-sensitive-directory"

    if lower_name.startswith(".env") and lower_name not in ALLOWED_ENV_EXAMPLES:
        return "unsafe-environment-file"

    if "service-account" in lower_name and lower_name.endswith(".json"):
        return "service-account-file"

    if lower_name.endswith(FORBIDDEN_COMPOUND_SUFFIXES):
        return "dump-or-backup-file"

    if pure_path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return "secret-data-media-or-model-file"

    if lower_name.endswith(".license") or lower_name.startswith("license") and lower_name.endswith(".json"):
        return "license-file"

    if size > MAX_TRACKED_FILE_BYTES:
        return "oversized-tracked-file"

    return None


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
    violations: list[tuple[str, str]] = []
    paths = tracked_files(repo_root)

    for relative_path in paths:
        candidate = repo_root / relative_path
        size = candidate.stat().st_size if candidate.is_file() else 0
        category = classify_path(relative_path, size)
        if category:
            violations.append((relative_path, category))

    if violations:
        print("repository_safety=FAIL", file=sys.stderr)
        for path, category in violations:
            print(f"{category}: {path}", file=sys.stderr)
        return 1

    print("repository_safety=PASS")
    print(f"tracked_paths_checked={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
