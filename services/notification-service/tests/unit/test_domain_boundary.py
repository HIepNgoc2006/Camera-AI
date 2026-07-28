from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "notification_service" / "domain"
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


def test_issue_65_exposes_no_public_http_route_or_provider_client() -> None:
    service_root = DOMAIN_ROOT.parent
    sources = "\n".join(path.read_text(encoding="utf-8") for path in service_root.rglob("*.py"))
    assert "FastAPI(" not in sources
    assert "APIRouter(" not in sources
    assert "@router." not in sources
    assert "firebase" not in sources.casefold()
    assert "sendgrid" not in sources.casefold()
