from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.settings import Settings, load_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.analysis.max_tool_calls == 8
    assert settings.llm.provider == "disabled"
    assert settings.llm.model is None
    assert settings.uploads.max_dataset_bytes == 0
    assert settings.eda.significance_level == 0.05


def test_environment_and_constructor_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MDA_ANALYSIS__MAX_TOOL_CALLS", "4")
    assert Settings(_env_file=None).analysis.max_tool_calls == 4
    assert Settings(analysis={"max_tool_calls": 2}, _env_file=None).analysis.max_tool_calls == 2
    monkeypatch.setenv("MDA_PERFORMANCE__TIMEOUT_SECONDS", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_external_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "settings.toml"
    config.write_text("[analysis]\nmax_tool_calls = 5\n", encoding="utf-8")
    assert load_settings(config).analysis.max_tool_calls == 5
    monkeypatch.setenv("MDA_ANALYSIS__MAX_TOOL_CALLS", "6")
    assert load_settings(config).analysis.max_tool_calls == 6


def test_dotenv_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / "local.env"
    dotenv.write_text("MDA_ANALYSIS__MAX_TOOL_CALLS=7\n", encoding="utf-8")
    assert Settings(_env_file=dotenv).analysis.max_tool_calls == 7
    monkeypatch.setenv("MDA_ANALYSIS__MAX_TOOL_CALLS", "5")
    assert Settings(_env_file=dotenv).analysis.max_tool_calls == 5


def test_intake_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MDA_DATA_INTAKE__CATEGORICAL_MAX_UNIQUE", "5")
    assert Settings(_env_file=None).data_intake.categorical_max_unique == 5
    monkeypatch.setenv("MDA_DATA_INTAKE__TEMPORAL_PARSE_RATIO", "1.1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_dataset_limit_accepts_zero_and_rejects_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MDA_UPLOADS__MAX_DATASET_BYTES", "0")
    assert Settings(_env_file=None).uploads.max_dataset_bytes == 0
    monkeypatch.setenv("MDA_UPLOADS__MAX_DATASET_BYTES", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
