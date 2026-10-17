from pathlib import Path

import pytest

from scripts.check_architecture import check_source, check_tree

ROOT = Path(__file__).resolve().parents[2]


def test_application_respects_hexagonal_and_module_boundaries() -> None:
    assert check_tree(ROOT) == []


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("app/modules/data_intake/domain/rules.py", "import pandas"),
        ("app/modules/critical_review/domain/rules.py", "from fastapi import Request"),
        (
            "app/modules/analysis/application/service.py",
            "from app.modules.analysis.adapters.analytics import correlation",
        ),
        (
            "app/modules/analysis/application/service.py",
            "from app.modules.exploration.application import service",
        ),
        (
            "app/modules/data_intake/ports/source.py",
            "from app.modules.data_intake.application import service",
        ),
        (
            "app/shared/contracts/request.py",
            "from app.modules.analysis.ports import agent",
        ),
        (
            "app/modules/reporting/application/service.py",
            "from app.bootstrap import build_repository",
        ),
        ("app/shared/domain/model.py", "from app.shared.config import settings"),
        (
            "app/modules/analysis/application/agents/example.py",
            "from ...adapters.analytics import correlation",
        ),
        (
            "app/modules/analysis/application/service.py",
            "import importlib\nimportlib.import_module('sqlalchemy')",
        ),
    ],
)
def test_checker_rejects_inverted_or_private_dependencies(path: str, source: str) -> None:
    assert check_source(Path(path), source)


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("app/shared/domain/model.py", "from pydantic import BaseModel"),
        (
            "app/modules/analysis/application/service.py",
            "from app.modules.data_intake.ports.datasource import DataSource",
        ),
        (
            "app/modules/analysis/application/agents/example.py",
            "from ...ports.relationship_screening import RelationshipScreening",
        ),
        (
            "app/modules/exploration/adapters/tool.py",
            "from scipy import stats",
        ),
        (
            "app/bootstrap.py",
            "from app.modules.exploration.adapters.relationship_screening import "
            "RelationshipScreeningAdapter",
        ),
    ],
)
def test_checker_accepts_inward_dependencies_and_composition(path: str, source: str) -> None:
    assert check_source(Path(path), source) == []


def test_capability_modules_own_implementation_not_empty_placeholders() -> None:
    modules = ROOT / "app/modules"
    assert {p.name for p in modules.iterdir() if p.is_dir() and p.name != "__pycache__"} == {
        "data_intake",
        "exploration",
        "analysis",
        "critical_review",
        "reporting",
    }
    for module in modules.iterdir():
        if module.is_dir() and module.name != "__pycache__":
            assert any(p.name != "__init__.py" for p in (module / "application").rglob("*.py"))


def test_frameworks_are_confined_to_adapters_and_composition() -> None:
    for path in (ROOT / "app").rglob("*.py"):
        relative = path.relative_to(ROOT)
        if path.name == "__init__.py":
            continue
        assert not check_source(relative, path.read_text(encoding="utf-8"))
