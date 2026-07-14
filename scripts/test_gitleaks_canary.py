"""Prove that gitleaks rejects a runtime-generated fake ANSVIS secret."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / ".gitleaks.toml"

    with tempfile.TemporaryDirectory(prefix="camera-ai-gitleaks-canary-") as temp_dir:
        canary_value = "gltcanary_" + "A1B2C3D4E5F6G7H8"
        canary_path = Path(temp_dir) / "canary.env"
        canary_path.write_text(
            f"ANSVIS_WEBHOOK_SECRET={canary_value}\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                "gitleaks",
                "dir",
                temp_dir,
                "--config",
                str(config_path),
                "--redact",
                "--no-banner",
                "--no-color",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 1:
        print(f"canary_detection=FAIL status={result.returncode}")
        return 1

    print("canary_detection=PASS")
    print("scanner_output_redacted=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
