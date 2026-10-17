from pathlib import Path

from app.agents.association import AssociationAgent
from app.application.dto.agent import AgentContext
from app.application.dto.analysis_input import AnalysisInput, resolve_configuration
from app.application.services.dataset_registry import DatasetRegistry
from app.bootstrap import build_data_understanding
from app.config.settings import Settings


def write_dataset(path: Path, rows: int = 60) -> None:
    lines = ["income,spend,noise,region"]
    for number in range(rows):
        noise = (number * 37) % 11
        region = "north" if number % 2 else "south"
        lines.append(f"{number},{number * 2 + number % 3},{noise},{region}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def screened_context(path: Path) -> tuple[AgentContext, DatasetRegistry]:
    settings = Settings(_env_file=None)
    analysis_input = AnalysisInput(source={"kind": "csv", "path": path})
    understood = await build_data_understanding(settings).understand(analysis_input)
    datasets = DatasetRegistry()
    datasets.register(understood.dataset)
    return (
        AgentContext(
            run_id="association-run",
            input=analysis_input,
            configuration=resolve_configuration(settings, analysis_input.configuration),
            dataset_id=understood.dataset.dataset_id,
            dataset_profile=understood.profile,
        ),
        datasets,
    )


async def test_association_agent_ranks_strongest_pair_first(tmp_path: Path) -> None:
    path = tmp_path / "screening.csv"
    write_dataset(path)
    context, datasets = await screened_context(path)

    result = await AssociationAgent(datasets, Settings(_env_file=None).eda).run(context)

    assert result.status == "SUCCESS"
    associations = result.update.associations
    assert associations
    assert set(associations[0].variables) == {"income", "spend"}
    assert {item.method for item in associations if set(item.variables) == {"income", "spend"}} >= {
        "pearson",
        "spearman",
    }


async def test_association_agent_skips_without_registered_dataset(tmp_path: Path) -> None:
    path = tmp_path / "screening.csv"
    write_dataset(path)
    context, _ = await screened_context(path)

    result = await AssociationAgent(DatasetRegistry(), Settings(_env_file=None).eda).run(context)

    assert result.status == "SKIPPED"
    assert result.update.associations is None
    assert result.warnings
