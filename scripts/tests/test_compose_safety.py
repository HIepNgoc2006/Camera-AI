from __future__ import annotations

import copy
import unittest
from pathlib import Path
from typing import Any

from scripts.check_compose_safety import EXPECTED_SERVICES, validate_compose

REPO_ROOT = Path(__file__).resolve().parents[2]


def safe_config() -> dict[str, Any]:
    services: dict[str, Any] = {}
    for service_name in EXPECTED_SERVICES:
        published = 55432 if service_name == "postgres-test" else 10000
        target = 5432 if service_name == "postgres-test" else 1
        services[service_name] = {
            "image": f"example.invalid/{service_name}:test@sha256:{'a' * 64}",
            "networks": {"local-backend": None},
            "ports": [{"host_ip": "127.0.0.1", "published": published, "target": target}],
            "security_opt": ["no-new-privileges:true"],
            "healthcheck": {"test": ["CMD", "true"]},
            "volumes": [
                {
                    "type": "bind",
                    "source": str(REPO_ROOT / ".local" / "docker-data" / service_name),
                    "target": "/data",
                }
            ],
        }
    return {"services": services, "networks": {"local-backend": {"internal": True}}}


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
        config["networks"]["local-backend"]["internal"] = False

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-internal-network", violations)

    def test_rejects_missing_healthcheck(self) -> None:
        config = safe_config()
        del config["services"]["minio"]["healthcheck"]

        violations = validate_compose(config, REPO_ROOT)
        self.assertIn("missing-healthcheck:minio", violations)


if __name__ == "__main__":
    unittest.main()
