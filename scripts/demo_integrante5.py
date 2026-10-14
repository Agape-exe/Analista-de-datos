"""Demonstrate only member 5 using explicitly precomputed test inputs."""

import argparse
import asyncio
from pathlib import Path

from app.adapters.llm.disabled import DisabledLLMProvider
from app.adapters.reporting.markdown import MarkdownReportRenderer
from app.agents.insight import InsightAgent
from app.application.dto.finalization import FinalizationInput
from app.application.use_cases.finalize_analysis import FinalizeAnalysis
from app.bootstrap import build_repository
from app.config.settings import Settings
from app.evaluation.classification import RelationshipLabel, evaluate_detection
from app.evaluation.rubric import default_rubric


async def main(input_path: Path, output: Path) -> None:
    packet = FinalizationInput.model_validate_json(input_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None, persistence={"database_url": f"sqlite:///{output / 'reports.db'}"}
    )
    repository = build_repository(settings)
    try:
        use_case = FinalizeAnalysis(InsightAgent(DisabledLLMProvider()), settings, repository)
        report = await use_case.execute(packet)
        (output / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        (output / "report.md").write_text(MarkdownReportRenderer().render(report), encoding="utf-8")
        (output / "rubric.json").write_text(
            default_rubric().model_dump_json(indent=2), encoding="utf-8"
        )
        labels = [RelationshipLabel(variables=["descuento", "ventas"], potentially_spurious=True)]
        # Illustrative scoring, not experimental validation of statistical algorithms.
        score = evaluate_detection(labels, report.relationship_assessments)
        (output / "fixture-score.json").write_text(
            score.model_dump_json(indent=2), encoding="utf-8"
        )
        assert await repository.get(report.run_id) == report
        print("DEMO con fixtures: no calcula estadísticas ni valida el sistema completo.")
        print(f"Estado: {report.status}; insights: {len(report.insights)}; salida: {output}")
    finally:
        repository.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("examples/integrante5_input.json"))
    parser.add_argument("--output", type=Path, default=Path("experiments/integrante5-demo"))
    args = parser.parse_args()
    asyncio.run(main(args.input, args.output))
