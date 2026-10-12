import pytest
from pydantic import ValidationError

from app.domain.models.analysis import AnalysisResult


def test_success_json_and_skipped_without_statistics() -> None:
    result = AnalysisResult(method="example", status="SUCCESS", result={"value": 0.2})
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
    assert AnalysisResult(method="example", status="SKIPPED").result is None
    with pytest.raises(ValidationError):
        AnalysisResult(method="example", status="SKIPPED", p_value=0.1)


def test_invalid_probability() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(method="example", status="SUCCESS", p_value=2)
