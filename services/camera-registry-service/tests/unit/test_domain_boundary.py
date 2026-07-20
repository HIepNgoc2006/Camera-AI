from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "camera_registry_service" / "domain"
SERVICE_ROOT = DOMAIN_ROOT.parent
FORBIDDEN_IMPORTS = {
    "alembic",
    "fastapi",
    "pydantic",
    "psycopg",
    "redis",
    "sqlalchemy",
    "starlette",
}


def test_domain_has_no_framework_or_infrastructure_imports() -> None:
    violations: list[str] = []
    for path in sorted(DOMAIN_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", maxsplit=1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                roots = {node.module.split(".", maxsplit=1)[0]}
            else:
                continue
            for root in roots & FORBIDDEN_IMPORTS:
                violations.append(f"{path.name}:{node.lineno}:{root}")
    assert violations == []


def test_service_exposes_no_public_http_route_or_ansvis_client() -> None:
    sources = "\n".join(path.read_text(encoding="utf-8") for path in SERVICE_ROOT.rglob("*.py"))
    for forbidden in ("FastAPI(", "APIRouter(", "@router.", "CameraAddress", "rtsp://"):
        assert forbidden not in sources


def test_repository_contains_no_cross_schema_query() -> None:
    source = (SERVICE_ROOT / "infrastructure" / "repository.py").read_text(encoding="utf-8")
    for cross_schema in ("school.", "identity.", "privacy.", "audit.", "integration.", "events."):
        assert cross_schema not in source
