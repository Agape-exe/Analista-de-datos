from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from app.domain.models.base import DomainModel
from app.domain.models.dataset import ProfilingOptions


class AnalysisSettings(DomainModel):
    mode: Literal["fast", "standard"]
    max_hypotheses: int = Field(ge=1)
    max_tool_calls: int = Field(ge=0)
    max_critic_cycles: int = Field(ge=0)
    minimum_sample_size: int = Field(ge=2)


class PerformanceSettings(DomainModel):
    timeout_seconds: float = Field(gt=0)
    parallel_tools: bool


class LLMSettings(DomainModel):
    provider: str
    model: str | None = None
    temperature: float = Field(ge=0, le=2)
    max_retries: int = Field(ge=0)


class EvaluationSettings(DomainModel):
    repetitions: int = Field(ge=1)


class PersistenceSettings(DomainModel):
    database_url: str = Field(min_length=1)


class UploadSettings(DomainModel):
    max_dataset_bytes: int = Field(
        ge=0, description="Dataset upload limit in bytes; 0 is unlimited"
    )
    max_dictionary_bytes: int = Field(gt=0)
    chunk_size_bytes: int = Field(gt=0)
    temporary_directory: Path | None = None


class EdaSettings(DomainModel):
    """Policy for exploratory profiling, association screening and chart data."""

    significance_level: float = Field(gt=0, lt=1)
    top_relationships: int = Field(ge=1)
    max_pairs: int = Field(ge=1)
    max_categories: int = Field(ge=2)
    max_cached_datasets: int = Field(ge=1)
    top_categories: int = Field(ge=1)
    max_histogram_bins: int = Field(ge=1)
    outlier_iqr_multiplier: float = Field(gt=0)
    outlier_mad_threshold: float = Field(gt=0)
    max_outlier_examples: int = Field(ge=0)
    normality_alpha: float = Field(gt=0, lt=1)
    mutual_information_neighbors: int = Field(ge=1)
    mutual_information_max_rows: int = Field(ge=2)
    max_scatter_points: int = Field(ge=2)
    max_box_outliers: int = Field(ge=0)
    random_seed: int = Field(ge=0)


class Settings(BaseSettings):
    """Defaults < external TOML < dotenv < environment < constructor."""

    model_config = SettingsConfigDict(
        env_prefix="MDA_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="forbid",
        toml_file=Path(__file__).with_name("defaults.toml"),
    )
    analysis: AnalysisSettings
    performance: PerformanceSettings
    llm: LLMSettings
    evaluation: EvaluationSettings
    persistence: PersistenceSettings
    data_intake: ProfilingOptions
    uploads: UploadSettings
    eda: EdaSettings

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            TomlConfigSettingsSource(
                settings_cls, toml_file=Path(__file__).with_name("defaults.toml")
            ),
        )


def load_settings(config_path: Path | None = None) -> Settings:
    """Load an optional external file without losing packaged defaults."""
    if config_path is None:
        return Settings()

    class ExternalSettings(Settings):
        model_config = SettingsConfigDict(toml_file=config_path)

    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    return ExternalSettings()
