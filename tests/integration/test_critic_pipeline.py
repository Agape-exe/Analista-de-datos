from hashlib import sha256
from pathlib import Path

from app.application.dto.analysis_input import AnalysisInput
from app.bootstrap import build_use_case
from app.config.settings import Settings


def csv_content():
    rows = [
        "Nº contribuyente,Fecha de pago,Distrito del inmueble,Año transferencia del inmueble,"
        "Cantidad pagos,Impuesto pagado (S/),Intereses pagados (S/),Total pagado (S/)"
    ]
    for i in range(60):
        tax = 500 + i * 10.13 + (i % 2) * 200 if i < 59 else 20000
        interest = (i % 5) * 2.11
        rows.append(
            f"{2290000 + i},{i % 20 + 1:02}/{i % 3 + 1:02}/2026,"
            f"{'A' if i % 2 else 'B'},2025,{i % 4 + 1},"
            f"{tax:.2f},{interest:.2f},{tax + interest:.2f}"
        )
    return ("\n".join(rows) + "\n").encode("utf-8-sig")


async def test_default_csv_produces_measured_critic_and_insights_without_a_question(tmp_path: Path):
    source = tmp_path / "payments.csv"
    source.write_bytes(csv_content())
    original = sha256(source.read_bytes()).hexdigest()
    report = await build_use_case(Settings(_env_file=None)).execute(
        AnalysisInput(source={"kind": "csv", "path": source})
    )
    assert report.status == "SUCCESS"
    assert set(report.stage_statuses.values()) == {"SUCCESS"}
    roles = {item.column_name: item.semantic_type for item in report.dataset_profile.columns}
    assert roles["Nº contribuyente"] == "identifier"
    assert roles["Fecha de pago"] == "temporal"
    assert all("Nº contribuyente" not in result.variables for result in report.analysis_results)
    measured = {
        item.analysis_id: item for item in report.analysis_results if item.status == "SUCCESS"
    }
    assert {item.method for item in measured.values()} >= {
        "pearson",
        "spearman",
        "correlation_without_outliers",
        "analyze_subgroups",
        "additive_identity",
    }
    identity = next(item for item in measured.values() if item.method == "additive_identity")
    assert identity.result["identity_confirmed"] is True
    assert identity.result["matched_rows"] == 60
    evidence = {item.evidence_id: item for item in report.evidence}
    assert evidence and report.insights and report.relationship_assessments
    assert all(item.analysis_id in measured for item in evidence.values())
    assert all(item.potentially_spurious is None for item in report.relationship_assessments)
    for insight in report.insights:
        assert insight.evidence_ids and set(insight.evidence_ids) <= evidence.keys()
    assert report.metrics.tool_calls == len(report.analysis_results) <= 8
    assert report.metrics.llm_calls == 0 and report.metrics.tokens_used is None
    assert sha256(source.read_bytes()).hexdigest() == original


async def test_budget_limited_review_states_uncertainty_instead_of_inventing_robustness(
    tmp_path: Path,
):
    source = tmp_path / "payments.csv"
    source.write_bytes(csv_content())
    report = await build_use_case(Settings(_env_file=None)).execute(
        AnalysisInput(
            source={"kind": "csv", "path": source},
            configuration={"analysis": {"max_tool_calls": 1}},
        )
    )
    assert report.metrics.tool_calls == 1
    assert report.status == "SUCCESS" and report.insights
    assert all(item.potentially_spurious is None for item in report.relationship_assessments)
    assert any(
        "No hay comprobaciones de robustez" in limitation
        for item in report.relationship_assessments
        for limitation in item.limitations
    )
