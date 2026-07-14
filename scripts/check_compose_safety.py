"""Validate the local Compose topology without starting containers or printing secrets."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_SERVICES = frozenset({"minio", "postgres-test", "rabbitmq", "redis"})
SHA256_IMAGE_PATTERN = re.compile(r"@sha256:[0-9a-f]{64}$")


def validate_compose(config: dict[str, Any], repo_root: Path) -> list[str]:
    violations: list[str] = []
    services = config.get("services", {})
    networks = config.get("networks", {})

    if set(services) != EXPECTED_SERVICES:
        violations.append("unexpected-compose-service-set")

    internal_networks = {name for name, value in networks.items() if value.get("internal") is True}
    if not internal_networks:
        violations.append("missing-internal-network")

    data_root = (repo_root / ".local" / "docker-data").resolve()
    for service_name, service in services.items():
        image = str(service.get("image", ""))
        if not SHA256_IMAGE_PATTERN.search(image):
            violations.append(f"unpinned-image:{service_name}")

        if service.get("privileged") is True:
            violations.append(f"privileged-service:{service_name}")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            violations.append(f"missing-no-new-privileges:{service_name}")
        if not service.get("healthcheck"):
            violations.append(f"missing-healthcheck:{service_name}")

        attached_networks = set(service.get("networks", {}))
        if not attached_networks or not attached_networks.issubset(internal_networks):
            violations.append(f"unsafe-network:{service_name}")

        for port in service.get("ports", []):
            if str(port.get("host_ip")) != "127.0.0.1":
                violations.append(f"non-loopback-port:{service_name}")
            if service_name == "postgres-test":
                if int(port.get("published", 0)) == 5432:
                    violations.append("postgres-test-host-port-conflict")
                if int(port.get("target", 0)) != 5432:
                    violations.append("postgres-test-invalid-target-port")

        bind_mounts = [
            volume for volume in service.get("volumes", []) if volume.get("type") == "bind"
        ]
        expected_source = (data_root / service_name).resolve()
        if len(bind_mounts) != 1:
            violations.append(f"unexpected-bind-mount-count:{service_name}")
        for volume in bind_mounts:
            source = Path(str(volume.get("source", ""))).resolve()
            if source != expected_source or not source.is_relative_to(data_root):
                violations.append(f"unsafe-bind-mount:{service_name}")

    return sorted(set(violations))


def load_compose_config(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "--profile",
            "test-db",
            "config",
            "--format",
            "json",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    loaded: dict[str, Any] = json.loads(result.stdout)
    return loaded


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        config = load_compose_config(repo_root)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        print("compose_safety=FAIL", file=sys.stderr)
        print("compose-config-unavailable", file=sys.stderr)
        return 1

    violations = validate_compose(config, repo_root)
    if violations:
        print("compose_safety=FAIL", file=sys.stderr)
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1

    print("compose_safety=PASS")
    print(f"services_checked={len(EXPECTED_SERVICES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
