import pytest
from pydantic import ValidationError

from app.evaluation.benchmark import BenchmarkDataset, ExperimentRun, GroundTruth
from app.evaluation.consistency import ConsistencyRun
from app.evaluation.rubric import HumanEvaluationRubric, RubricCriterion


def test_evaluation_contracts_do_not_invent_metrics() -> None:
    benchmark = BenchmarkDataset(
        benchmark_id="tiny",
        name="Tiny fixture",
        input={"source": {"kind": "csv", "path": "sample.csv"}},
        ground_truth=GroundTruth(),
    )
    experiment = ExperimentRun(benchmark_id=benchmark.benchmark_id)
    consistency = ConsistencyRun(consistency_id="repeat", benchmark_id="tiny", repetitions=3)
    rubric = HumanEvaluationRubric(rubric_id="human", version="1")
    assert experiment.metrics.precision is None
    assert consistency.metrics.insight_consistency is None
    for value in (benchmark, experiment, consistency, rubric):
        assert type(value).model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        RubricCriterion(name="clarity", description="Explain", minimum_score=5, maximum_score=1)
