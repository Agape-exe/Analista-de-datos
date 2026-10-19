import asyncio

from fastapi.testclient import TestClient

from app.modules.critical_review.application.services.grounded_queries import (
    answer_grounded_query,
)
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import AnalysisResult
from app.shared.domain.models.dataset import ColumnProfile, DatasetProfile
from app.shared.domain.models.evidence import Evidence, RelationshipAssessment
from app.shared.domain.models.metrics import ExperimentMetrics
from app.shared.domain.models.report import AnalysisReport


def make_report() -> AnalysisReport:
    return AnalysisReport(
        run_id="aud039-test",
        status=AnalysisStatus.SUCCESS,
        dataset_profile=DatasetProfile(
            dataset_id="dataset-test",
            row_count=60,
            columns=[
                ColumnProfile(column_name="publicidad", data_type="int64"),
                ColumnProfile(column_name="ventas", data_type="int64"),
            ],
        ),
        analysis_results=[
            AnalysisResult(
                analysis_id="analysis-001",
                method="pearson",
                variables=["publicidad", "ventas"],
                status=AnalysisStatus.SUCCESS,
                effect_size=0.81,
                sample_size=60,
            ),
        ],
        evidence=[
            Evidence(
                evidence_id="evidence-001",
                analysis_id="analysis-001",
                description="Se calculó una correlación de Pearson.",
            ),
        ],
        relationship_assessments=[
            RelationshipAssessment(
                variables=["publicidad", "ventas"],
                evidence_ids=["evidence-001"],
                potentially_spurious=None,
                rationale="No se dispone de controles suficientes.",
            ),
        ],
        metrics=ExperimentMetrics(tool_calls=1),
        warnings=["No se ha demostrado causalidad."],
    )


def test_catalog_is_restricted(client: TestClient):
    response = client.get("/questions/catalog")

    assert response.status_code == 200
    assert "perfil" in response.json()["questions"]
    assert "relaciones" in response.json()["questions"]


def test_dataset_profile_has_verifiable_references():
    result = answer_grounded_query(make_report(), "perfil")

    assert result.status == "ANSWERED"
    assert "60 filas" in result.answer
    assert result.references[0].path == "/dataset_profile/row_count"


def test_relationship_remains_indeterminate():
    result = answer_grounded_query(make_report(), "relaciones")

    assert result.status == "ANSWERED"
    assert "indeterminada" in result.answer
    assert result.references[0].path == "/relationship_assessments/0"


def test_evidence_has_original_analysis_id():
    result = answer_grounded_query(make_report(), "evidencias")

    assert result.status == "ANSWERED"
    assert result.references[0].analysis_id == "analysis-001"
    assert result.references[0].evidence_id == "evidence-001"


def test_unknown_questions_abstain():
    result = answer_grounded_query(make_report(), "predice las ventas")

    assert result.status == "ABSTAINED"
    assert result.references == []


def test_missing_evidence_abstains():
    report = make_report()
    report.evidence = []

    result = answer_grounded_query(report, "evidencias")

    assert result.status == "ABSTAINED"
    assert result.references == []


def test_unmeasured_metrics_are_not_invented():
    report = make_report()
    report.metrics = ExperimentMetrics()

    result = answer_grounded_query(report, "metricas")

    assert result.status == "ABSTAINED"
    assert result.references == []


def test_measured_zero_is_preserved():
    report = make_report()
    report.metrics = ExperimentMetrics(llm_calls=0)

    result = answer_grounded_query(report, "metricas")

    assert result.status == "ANSWERED"
    assert "llm_calls=0" in result.answer


def test_http_query_uses_saved_report(client: TestClient):
    asyncio.run(client.app.state.report_repository.save(make_report()))

    response = client.post(
        "/reports/aud039-test/questions",
        json={"question": "relaciones"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ANSWERED"
    assert response.json()["references"]


def test_http_unknown_report_returns_404(client: TestClient):
    response = client.post(
        "/reports/nonexistent/questions",
        json={"question": "perfil"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REPORT_NOT_FOUND"
