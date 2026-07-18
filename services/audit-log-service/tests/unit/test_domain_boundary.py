from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "audit_log_service" / "domain"
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
