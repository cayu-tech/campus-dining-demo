"""Declared Cayu application convention tests."""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
REQUIRED_HOMES = (
    "configuration",
    "agents",
    "prompts",
    "tools",
    "policies",
    "environments",
    "workflows",
    "operations",
    "knowledge",
    "memory",
    "domain",
    "integrations",
    "evals",
    "observability",
)


def test_declared_convention_homes_exist() -> None:
    for relative in REQUIRED_HOMES:
        package = ROOT / relative
        assert package.is_dir(), relative
        assert (package / "__init__.py").is_file(), relative


def test_app_is_a_composition_root() -> None:
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]

    assert classes == []
    assert functions == ["build_app"]
