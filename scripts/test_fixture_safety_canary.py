"""Prove fixture violations fail safely without printing the synthetic value."""

from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.check_fixture_safety import inspect_fixture


def main() -> int:
    canary_field = "ANSVIS_" + "WEBHOOK_" + "SECRET"
    canary_value = "fixture_canary_" + "A1B2C3D4E5F6"
    content = (
        f'{{\n  "_fixture": "SYNTHETIC_TEST_DATA_ONLY",\n  "{canary_field}": "{canary_value}"\n}}\n'
    )

    with tempfile.TemporaryDirectory(prefix="camera-ai-fixture-canary-") as temp_dir:
        fixture = Path(temp_dir) / "event.synthetic.json"
        fixture.write_text(content, encoding="utf-8")
        violations = inspect_fixture(fixture, "fixtures/event.synthetic.json")

    if "credential-field" not in violations:
        print("fixture_canary=FAIL")
        return 1

    print("fixture_canary=PASS")
    print("fixture_content_redacted=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
