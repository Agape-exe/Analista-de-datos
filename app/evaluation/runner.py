import json
from pathlib import Path

from app.domain.enums.statuses import AnalysisStatus
from app.evaluation.benchmark import BenchmarkDataset, ExperimentRun
from app.evaluation.classification import evaluate_detection
from app.ports.analysis_workflow import AnalysisWorkflow


class ExperimentLogger:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, experiment: ExperimentRun) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        if (
            Path(experiment.experiment_id).name != experiment.experiment_id
            or "\\" in experiment.experiment_id
        ):
            raise ValueError("Experiment ID cannot contain path separators")
        target = self.directory / f"{experiment.experiment_id}.json"
        # Exclusive creation prevents accidental replacement of another experiment.
        with target.open("x", encoding="utf-8") as stream:
            stream.write(experiment.model_dump_json(indent=2))
        return target


class BenchmarkRunner:
    def __init__(self, workflow: AnalysisWorkflow, logger: ExperimentLogger) -> None:
        self.workflow = workflow
        self.logger = logger

    async def run(self, benchmark: BenchmarkDataset, configuration=None) -> ExperimentRun:
        experiment = ExperimentRun(
            benchmark_id=benchmark.benchmark_id, configuration=configuration or {}
        )
        report = await self.workflow.run(benchmark.input)
        experiment.report = report
        experiment.metrics = report.metrics.model_copy(deep=True)
        labels = benchmark.ground_truth.relationship_labels if benchmark.ground_truth else []
        if labels and report.status == AnalysisStatus.SUCCESS:
            score = evaluate_detection(labels, report.relationship_assessments)
            values = score.metrics.model_dump(exclude_none=True)
            experiment.metrics = experiment.metrics.model_copy(update=values)
            experiment.configuration["detection_score"] = json.loads(score.model_dump_json())
        self.logger.save(experiment)
        return experiment


class RepeatabilityRunner:
    """Repeat one benchmark under identical configuration, recording every execution."""

    def __init__(self, benchmark_runner: BenchmarkRunner) -> None:
        self.benchmark_runner = benchmark_runner

    async def run(self, benchmark: BenchmarkDataset, repetitions: int, configuration=None):
        from uuid import uuid4

        from app.evaluation.consistency import ConsistencyRun, conclusion_agreement

        if repetitions < 2:
            raise ValueError("Repeatability evaluation requires at least two repetitions")
        experiments = [
            await self.benchmark_runner.run(benchmark, configuration) for _ in range(repetitions)
        ]
        consistency = ConsistencyRun(
            consistency_id=str(uuid4()),
            benchmark_id=benchmark.benchmark_id,
            experiment_ids=[item.experiment_id for item in experiments],
            repetitions=repetitions,
        )
        reports = [item.report for item in experiments]
        if all(
            report is not None and report.status == AnalysisStatus.SUCCESS for report in reports
        ):
            measured = conclusion_agreement(reports)
            consistency.metrics.conclusion_agreement = measured["conclusion_agreement"]
            consistency.decision_coverage = measured["decision_coverage"]
            consistency.abstention_agreement = measured["abstention_agreement"]
        else:
            consistency.warnings.append(
                "Incomplete executions: conclusion consistency not measured."
            )
        target = (
            self.benchmark_runner.logger.directory
            / f"consistency-{consistency.consistency_id}.json"
        )
        with target.open("x", encoding="utf-8") as stream:
            stream.write(consistency.model_dump_json(indent=2))
        return consistency
