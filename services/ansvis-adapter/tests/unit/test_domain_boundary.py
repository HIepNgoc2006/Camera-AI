from __future__ import annotations

import ast
from pathlib import Path


def test_domain_does_not_import_framework_or_infrastructure() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "ansvis_adapter" / "domain"
    forbidden = {"fastapi", "pydantic", "sqlalchemy", "psycopg", "starlette", "uvicorn"}

    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", maxsplit=1)[0])
        assert imported.isdisjoint(forbidden), f"{path.name} imports {imported & forbidden}"
