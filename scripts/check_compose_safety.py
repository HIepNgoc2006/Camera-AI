"""Validate the local Compose topology without starting containers or printing secrets."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_SERVICES = frozenset({"minio", "postgres-test", "rabbitmq", "redis"})
INTERNAL_NETWORK = "local-backend"
POSTGRES_TEST_LOOPBACK_NETWORK = "postgres-test-loopback"
SHA256_IMAGE_PATTERN = re.compile(r"@sha256:[0-9a-f]{64}$")
MINIMUM_MEMORY_LIMIT_BYTES = 64 * 1024 * 1024


def _is_non_root_user(value: Any) -> bool:
    user = str(value or "").strip().casefold()
    if not user:
        return False
    primary = user.split(":", maxsplit=1)[0]
    return primary not in {"0", "root"}


def _has_positive_cpu_limit(limits: dict[str, Any]) -> bool:
    try:
        return float(limits.get("cpus", 0)) > 0
    except (TypeError, ValueError):
        return False


def _has_safe_memory_limit(limits: dict[str, Any]) -> bool:
    try:
        return int(limits.get("memory", 0)) >= MINIMUM_MEMORY_LIMIT_BYTES
    except (TypeError, ValueError):
        return False


def validate_compose(config: dict[str, Any], repo_root: Path) -> list[str]:
    violations: list[str] = []
    services = config.get("services", {})
    networks = config.get("networks", {})

    if set(services) != EXPECTED_SERVICES:
        violations.append("unexpected-compose-service-set")

    internal_network = networks.get(INTERNAL_NETWORK, {})
    if internal_network.get("internal") is not True:
        violations.append("missing-internal-network")
    loopback_network = networks.get(POSTGRES_TEST_LOOPBACK_NETWORK, {})
    loopback_driver_options = loopback_network.get("driver_opts", {})
    if (
        loopback_network.get("driver") != "bridge"
        or loopback_network.get("internal") is True
        or str(loopback_driver_options.get("com.docker.network.bridge.host_binding_ipv4"))
        != "127.0.0.1"
    ):
        violations.append("unsafe-postgres-test-loopback-network")

    data_root = (repo_root / ".local" / "docker-data").resolve()
    for service_name, service in services.items():
        image = str(service.get("image", ""))
        if not SHA256_IMAGE_PATTERN.search(image):
            violations.append(f"unpinned-image:{service_name}")

        if service.get("privileged") is True:
            violations.append(f"privileged-service:{service_name}")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            violations.append(f"missing-no-new-privileges:{service_name}")
        if not _is_non_root_user(service.get("user")):
            violations.append(f"missing-non-root-user:{service_name}")
        if not service.get("healthcheck"):
            violations.append(f"missing-healthcheck:{service_name}")

        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        if not _has_positive_cpu_limit(limits):
            violations.append(f"missing-cpu-limit:{service_name}")
        if not _has_safe_memory_limit(limits):
            violations.append(f"missing-memory-limit:{service_name}")

        attached_networks = set(service.get("networks", {}))
        expected_networks = (
            {POSTGRES_TEST_LOOPBACK_NETWORK}
            if service_name == "postgres-test"
            else {INTERNAL_NETWORK}
        )
        if attached_networks != expected_networks:
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
