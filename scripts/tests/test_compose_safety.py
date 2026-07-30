from __future__ import annotations

import copy
import unittest
from pathlib import Path
from typing import Any

from scripts.check_compose_safety import (
    EXPECTED_SERVICES,
    INTERNAL_NETWORK,
    POSTGRES_TEST_LOOPBACK_NETWORK,
    validate_compose,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def safe_config() -> dict[str, Any]:
    services: dict[str, Any] = {}
    for service_name in EXPECTED_SERVICES:
        published = 55432 if service_name == "postgres-test" else 10000
        target = 5432 if service_name == "postgres-test" else 1
        network = (
            POSTGRES_TEST_LOOPBACK_NETWORK if service_name == "postgres-test" else INTERNAL_NETWORK
        )
        services[service_name] = {
            "image": f"example.invalid/{service_name}:test@sha256:{'a' * 64}",
            "user": "65532:65532",
            "networks": {network: None},
            "ports": [{"host_ip": "127.0.0.1", "published": published, "target": target}],
            "security_opt": ["no-new-privileges:true"],
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": 0.5,
                        "memory": 128 * 1024 * 1024,
                    }
                }
            },
            "healthcheck": {"test": ["CMD", "true"]},
            "volumes": [
                {
                    "type": "bind",
                    "source": str(REPO_ROOT / ".local" / "docker-data" / service_name),
                    "target": "/data",
                }
            ],
        }
    return {
        "services": services,
        "networks": {
            INTERNAL_NETWORK: {"internal": True},
            POSTGRES_TEST_LOOPBACK_NETWORK: {
                "driver": "bridge",
                "driver_opts": {"com.docker.network.bridge.host_binding_ipv4": "127.0.0.1"},
            },
        },
    }


class ComposeSafetyTests(unittest.TestCase):
    def test_accepts_safe_compose_topology(self) -> None:
        self.assertEqual(validate_compose(safe_config(), REPO_ROOT), [])

    def test_rejects_unpinned_image_and_external_port(self) -> None:
        config = safe_config()
        service = config["services"]["redis"]
        service["image"] = "redis:latest"
        service["ports"][0]["host_ip"] = "0.0.0.0"

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("unpinned-image:redis", violations)
        self.assertIn("non-loopback-port:redis", violations)

    def test_rejects_postgres_port_conflict_and_unsafe_mount(self) -> None:
        config = copy.deepcopy(safe_config())
        service = config["services"]["postgres-test"]
        service["ports"][0]["published"] = 5432
        service["volumes"][0]["source"] = str(REPO_ROOT)

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("postgres-test-host-port-conflict", violations)
        self.assertIn("unsafe-bind-mount:postgres-test", violations)

    def test_rejects_non_internal_network(self) -> None:
        config = safe_config()
        config["networks"][INTERNAL_NETWORK]["internal"] = False

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-internal-network", violations)

    def test_rejects_unsafe_postgres_test_loopback_network(self) -> None:
        config = safe_config()
        config["networks"][POSTGRES_TEST_LOOPBACK_NETWORK]["driver_opts"][
            "com.docker.network.bridge.host_binding_ipv4"
        ] = "0.0.0.0"

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("unsafe-postgres-test-loopback-network", violations)

    def test_rejects_non_database_service_on_test_loopback_network(self) -> None:
        config = safe_config()
        config["services"]["redis"]["networks"] = {POSTGRES_TEST_LOOPBACK_NETWORK: None}

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("unsafe-network:redis", violations)

    def test_rejects_missing_healthcheck(self) -> None:
        config = safe_config()
        del config["services"]["minio"]["healthcheck"]

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-healthcheck:minio", violations)

    def test_rejects_missing_resource_limits(self) -> None:
        config = safe_config()
        limits = config["services"]["rabbitmq"]["deploy"]["resources"]["limits"]
        del limits["cpus"]
        del limits["memory"]

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-cpu-limit:rabbitmq", violations)
        self.assertIn("missing-memory-limit:rabbitmq", violations)

    def test_rejects_invalid_resource_limits(self) -> None:
        config = safe_config()
        limits = config["services"]["redis"]["deploy"]["resources"]["limits"]
        limits["cpus"] = 0
        limits["memory"] = 32 * 1024 * 1024

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-cpu-limit:redis", violations)
        self.assertIn("missing-memory-limit:redis", violations)

    def test_rejects_missing_or_root_user(self) -> None:
        config = safe_config()
        del config["services"]["postgres-test"]["user"]
        config["services"]["minio"]["user"] = "root:root"

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-non-root-user:postgres-test", violations)
        self.assertIn("missing-non-root-user:minio", violations)


if __name__ == "__main__":
    unittest.main()
