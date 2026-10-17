import asyncio
from pathlib import Path

from app.bootstrap import build_repository
from app.modules.reporting.application.agents.insight import InsightAgent
from app.modules.reporting.application.dto import FinalizationInput
from app.modules.reporting.application.evaluation.benchmark import BenchmarkDataset
from app.modules.reporting.application.evaluation.runner import BenchmarkRunner, ExperimentLogger
from app.modules.reporting.application.use_cases.finalize_analysis import FinalizeAnalysis
from app.shared.adapters.llm.disabled import DisabledLLMProvider
from app.shared.config.settings import Settings
from app.shared.domain.models.report import AnalysisReport


async def test_standalone_finalization_preserves_links_and_persists(tmp_path: Path):
    root = Path(__file__).parents[2]
    packet = FinalizationInput.model_validate_json(
        (root / "examples/integrante5_input.json").read_text()
    )
    settings = Settings(
        _env_file=None, persistence={"database_url": f"sqlite:///{tmp_path / 'report.db'}"}
    )
    repository = build_repository(settings)
    try:
        report = await FinalizeAnalysis(
            InsightAgent(DisabledLLMProvider()), settings, repository
        ).execute(packet)
        assert report.status == "SUCCESS"
        assert report.configuration["execution_scope"] == "finalization_only"
        assert len(report.insights) == 1
        assert report.insights[0].evidence_ids == ["e1", "e2"]
        assert report.relationship_assessments == packet.relationship_assessments
        assert report.metrics.precision is None
        assert report.metrics.time_to_first_insight >= 0
        assert await repository.get(packet.run_id) == report
    finally:
        repository.engine.dispose()


async def test_benchmark_skipped_does_not_get_quality_scores(tmp_path: Path):
    class PendingWorkflow:
        async def run(self, value):
            return AnalysisReport(run_id="run", status="SKIPPED")

    benchmark = BenchmarkDataset(
        benchmark_id="controlled",
        name="test fixture",
        input={"source": {"kind": "csv", "path": "unused.csv"}},
        ground_truth={
            "relationship_labels": [{"variables": ["x", "y"], "potentially_spurious": True}]
        },
    )
    experiment = await BenchmarkRunner(PendingWorkflow(), ExperimentLogger(tmp_path)).run(benchmark)
    assert experiment.metrics.precision is None
    assert (tmp_path / f"{experiment.experiment_id}.json").exists()


async def test_parallel_repository_saves_are_retrievable(tmp_path: Path):
    repository = build_repository(
        Settings(_env_file=None, persistence={"database_url": f"sqlite:///{tmp_path / 'runs.db'}"})
    )
    try:
        reports = [AnalysisReport(run_id=f"r{i}", status="SKIPPED") for i in range(4)]
        await asyncio.gather(*(repository.save(report) for report in reports))
        actual = await asyncio.gather(*(repository.get(report.run_id) for report in reports))
        assert actual == reports
    finally:
        repository.engine.dispose()


async def test_repeatability_runner_logs_each_run_and_consistency(tmp_path: Path):
    from uuid import uuid4

    from app.modules.reporting.application.evaluation.runner import RepeatabilityRunner
    from app.shared.domain.models.evidence import RelationshipAssessment

    class ControlledWorkflow:
        async def run(self, value):
            return AnalysisReport(
                run_id=str(uuid4()),
                status="SUCCESS",
                relationship_assessments=[
                    RelationshipAssessment(variables=["x", "y"], potentially_spurious=True)
                ],
            )

    benchmark = BenchmarkDataset(
        benchmark_id="fixture",
        name="controlled test input",
        input={"source": {"kind": "csv", "path": "not-read.csv"}},
        ground_truth={
            "relationship_labels": [{"variables": ["x", "y"], "potentially_spurious": True}]
        },
    )
    runner = RepeatabilityRunner(BenchmarkRunner(ControlledWorkflow(), ExperimentLogger(tmp_path)))
    result = await runner.run(benchmark, 3, {"provider": "fixture"})
    assert result.metrics.conclusion_agreement == 1
    assert result.decision_coverage == 1
    assert len(set(result.experiment_ids)) == 3
    assert len(list(tmp_path.glob("*.json"))) == 4
