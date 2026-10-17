import pytest

from app.modules.analysis.application.agents.association import AssociationAgent
from app.shared.application.errors import DatasetRegistryError
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentContext
from app.shared.contracts.analysis_input import AnalysisInput, resolve_configuration
from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.dataset import DatasetProfile


def context() -> AgentContext:
    value = AnalysisInput(source={"kind": "stored", "dataset_id": "dataset"})
    return AgentContext(
        run_id="port-test",
        input=value,
        configuration=resolve_configuration(Settings(_env_file=None), value.configuration),
        dataset_id="dataset",
        dataset_profile=DatasetProfile(dataset_id="dataset", row_count=40),
    )


class FakeScreening:
    def __init__(self, result: AnalysisResult) -> None:
        self.result = result
        self.calls = []

    async def screen(self, dataset_id, profile, minimum_sample_size):
        self.calls.append((dataset_id, profile, minimum_sample_size))
        return self.result


async def test_agent_accepts_screening_port_without_a_dataset_or_statistics_engine() -> None:
    fake = FakeScreening(
        AnalysisResult(
            method="relationship_ranking",
            status="SUCCESS",
            result={
                "top_relationships": [
                    {
                        "x": "x",
                        "y": "y",
                        "method": "pearson",
                        "score": 0.9,
                        "strength": 0.9,
                        "p_value": 0.001,
                        "adjusted_p_value": 0.002,
                        "sample_size": 40,
                    }
                ]
            },
        )
    )
    request = context()
    result = await AssociationAgent(fake).run(request)
    assert result.status == "SUCCESS"
    assert result.update.associations[0].variables == ["x", "y"]
    assert fake.calls == [("dataset", request.dataset_profile, 20)]


@pytest.mark.parametrize("status", ["SKIPPED", "FAILED"])
async def test_non_successful_screening_remains_an_advisory_omission(status) -> None:
    fake = FakeScreening(
        AnalysisResult(method="relationship_ranking", status=status, warnings=["not evaluable"])
    )
    result = await AssociationAgent(fake).run(context())
    assert result.status == "SKIPPED"
    assert result.warnings == ["Association screening: not evaluable"]
    assert result.update.associations is None


async def test_unavailable_dataset_keeps_the_existing_omission_contract() -> None:
    class MissingDataset:
        async def screen(self, dataset_id, profile, minimum_sample_size):
            raise DatasetRegistryError("not registered")

    result = await AssociationAgent(MissingDataset()).run(context())
    assert result.status == "SKIPPED"
    assert result.warnings == ["Association screening unavailable: not registered"]
