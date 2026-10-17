from app.modules.reporting.application.services.insights import _limitations, describe_result
from app.shared.domain.models.analysis import AnalysisResult


def test_subgroups_are_summarized_without_raw_json():
    result = AnalysisResult(
        analysis_id="groups",
        method="analyze_subgroups",
        variables=["tax", "interest"],
        status="SUCCESS",
        sample_size=105,
        result={
            "group_by": "district",
            "groups": [
                {"group": "A", "correlation": -0.137296, "sample_size": 100},
                {"group": "B", "correlation": 0.996436, "sample_size": 5},
            ],
        },
    )
    text = describe_result(result)
    assert "2 grupos" in text and "-0.137" in text and "n=5" in text
    assert "pocas observaciones" in text
    assert '"groups"' not in text and "0.996436" not in text
    assert result.result["groups"][1]["correlation"] == 0.996436


def test_correlation_avoids_duplicate_effect_and_tiny_p_decimals():
    result = AnalysisResult(
        analysis_id="p",
        method="pearson",
        variables=["x", "y"],
        status="SUCCESS",
        result={"correlation": 0.160279629},
        effect_size=0.160279629,
        p_value=2e-209,
        sample_size=36645,
    )
    text = describe_result(result)
    assert "0.16" in text and "p < 0.001" in text
    assert "Tamaño del efecto" not in text and "e-209" not in text


def test_causality_warnings_are_translated_and_deduplicated():
    assert _limitations(
        [
            "Correlation measures association and does not establish causation.",
            "La asociación estadística no demuestra causalidad.",
        ]
    ) == ["Los resultados describen asociaciones y no prueban causalidad."]
