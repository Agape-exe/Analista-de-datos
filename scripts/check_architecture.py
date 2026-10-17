"""Check explicit Python imports against the modular hexagonal dependency rules."""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYERS = {"domain", "application", "ports", "adapters"}
PURE_LAYERS = {"domain", "application", "ports", "contracts"}
SHARED_ALLOWED = {
    "domain": {"domain"},
    "contracts": {"domain", "contracts", "config"},
    "ports": {"domain", "contracts", "ports"},
    "application": {"domain", "contracts", "ports", "application", "config"},
    "config": {"domain", "contracts", "config"},
    "adapters": {"domain", "contracts", "ports", "application", "config", "adapters"},
}


def location(path: Path) -> tuple[str, str] | None:
    parts = path.parts
    if len(parts) >= 4 and parts[:2] == ("app", "modules"):
        return parts[2], parts[3]
    if len(parts) >= 3 and parts[:2] == ("app", "shared"):
        return "shared", parts[2]
    return None


def imported_modules(source: str, path: Path) -> Iterator[tuple[int, str]]:
    """Resolve absolute, relative and literal dynamic imports without importing code."""
    tree = ast.parse(source)
    package = list(path.parent.parts)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                prefix = package[: len(package) - node.level + 1]
                base = ".".join([*prefix, *([base] if base else [])])
            if base:
                yield node.lineno, base
            for alias in node.names:
                if alias.name != "*":
                    yield node.lineno, f"{base}.{alias.name}" if base else alias.name
        elif isinstance(node, ast.Call) and node.args:
            name = (
                node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            )
            if name in {"import_module", "__import__"} and isinstance(node.args[0], ast.Constant):
                target = node.args[0].value
                if isinstance(target, str) and not target.startswith("."):
                    yield node.lineno, target


def violation(source: Path, target: str) -> str | None:
    owner_layer = location(source)
    if owner_layer is None:  # app/api and bootstrap are the outer composition boundary.
        return None
    owner, layer = owner_layer
    head = target.split(".")[0]
    if head != "app":
        if layer in PURE_LAYERS and head not in sys.stdlib_module_names | {"pydantic"}:
            return "inner layers may only import the standard library and Pydantic"
        return None
    parts = target.split(".")
    if len(parts) >= 3 and parts[1] == "shared":
        destination = parts[2]
        if owner == "shared":
            permitted = SHARED_ALLOWED.get(layer, set())
        elif layer == "domain":
            permitted = {"domain"}
        elif layer == "ports":
            permitted = {"domain", "contracts", "ports"}
        elif layer == "application":
            permitted = {"domain", "contracts", "ports", "application", "config"}
        else:
            permitted = set(SHARED_ALLOWED)
        if destination not in permitted:
            return f"{layer} cannot depend on shared/{destination}"
        return None
    if len(parts) >= 4 and parts[1] == "modules":
        module, destination = parts[2:4]
        if owner == "shared":
            return "shared cannot depend on a functional module"
        if module != owner:
            if layer != "domain" and destination == "ports":
                return None
            return "modules communicate through ports and shared contracts, not private internals"
        allowed = {
            "domain": {"domain"},
            "ports": {"domain", "ports"},
            "application": {"application", "domain", "ports"},
            "adapters": LAYERS,
        }
        if destination not in allowed.get(layer, set()):
            return f"{layer} cannot depend on {destination}"
        return None
    return "module/shared code cannot depend on the outer composition root or legacy layers"


def check_source(path: Path, source: str) -> list[str]:
    failures = set()
    for line, target in imported_modules(source, path):
        if reason := violation(path, target):
            failures.add(f"{path.as_posix()}:{line}: {target}: {reason}")
    return sorted(failures)


def check_tree(root: Path = ROOT) -> list[str]:
    return [
        error
        for path in sorted((root / "app").rglob("*.py"))
        for error in check_source(path.relative_to(root), path.read_text(encoding="utf-8"))
    ]


def main() -> int:
    failures = check_tree()
    if failures:
        print("\n".join(failures))
        return 1
    count = sum(1 for _ in (ROOT / "app").rglob("*.py"))
    print(f"Architecture OK: {count} Python files; module and hexagonal boundaries respected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
