import pytest
from pydantic import ValidationError

from app.bootstrap import build_repository
from app.shared.config.settings import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "deployment": {
            "environment": "production",
            "cors_allowed_origins": ["https://analyst.example.test"],
            "allow_local_analysis": False,
            "max_concurrent_operations": 1,
        },
        "uploads": {"max_dataset_bytes": 2_097_152, "max_dictionary_bytes": 262_144},
        "persistence": {
            "database_url": "postgresql+psycopg://user:password@db.example.test/database",
            "postgres_sslmode": "require",
        },
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_defaults_preserve_local_analysis_and_local_cors() -> None:
    settings = Settings(_env_file=None)
    assert settings.deployment.environment == "development"
    assert settings.deployment.allow_local_analysis
    assert "http://localhost:5173" in settings.deployment.cors_allowed_origins
    assert settings.uploads.max_dataset_bytes == 0


def test_production_requires_explicit_safe_configuration() -> None:
    settings = production_settings()
    assert settings.persistence.database_url.startswith("postgresql+psycopg://")
    assert settings.persistence.postgres_sslmode == "require"
    assert settings.uploads.max_dataset_bytes == 2_097_152


def test_production_uses_secure_setting_when_url_omits_sslmode() -> None:
    assert production_settings().persistence.effective_postgres_sslmode() == "require"


@pytest.mark.parametrize("url_sslmode", ["disable", "prefer"])
def test_production_rejects_weak_sslmode_in_database_url(url_sslmode: str) -> None:
    with pytest.raises(ValidationError, match="sslmode"):
        production_settings(
            persistence={
                "database_url": (
                    "postgresql+psycopg://user:password@db.example.test/database"
                    f"?sslmode={url_sslmode}"
                ),
                "postgres_sslmode": "disable" if url_sslmode == "disable" else "require",
            }
        )


def test_production_rejects_conflicting_url_and_setting_sslmode() -> None:
    with pytest.raises(ValidationError, match="sslmode must match"):
        production_settings(
            persistence={
                "database_url": "postgresql+psycopg://user:password@db.example.test/database?sslmode=verify-full",
                "postgres_sslmode": "require",
            }
        )


def test_production_accepts_matching_verify_full_sslmode() -> None:
    settings = production_settings(
        persistence={
            "database_url": "postgresql+psycopg://user:password@db.example.test/database?sslmode=verify-full",
            "postgres_sslmode": "verify-full",
        }
    )
    assert settings.persistence.effective_postgres_sslmode() == "verify-full"


@pytest.mark.parametrize(
    "deployment, uploads, persistence",
    [
        (
            {"environment": "production", "cors_allowed_origins": ["*"]},
            {"max_dataset_bytes": 2_097_152, "max_dictionary_bytes": 262_144},
            {"database_url": "postgresql+psycopg://user:password@db.example.test/database"},
        ),
        (
            {
                "environment": "production",
                "cors_allowed_origins": ["http://analyst.example.test"],
                "allow_local_analysis": False,
            },
            {"max_dataset_bytes": 2_097_152, "max_dictionary_bytes": 262_144},
            {"database_url": "postgresql+psycopg://user:password@db.example.test/database"},
        ),
        (
            {
                "environment": "production",
                "cors_allowed_origins": ["https://analyst.example.test"],
                "allow_local_analysis": False,
            },
            {"max_dataset_bytes": 0, "max_dictionary_bytes": 262_144},
            {"database_url": "postgresql+psycopg://user:password@db.example.test/database"},
        ),
        (
            {
                "environment": "production",
                "cors_allowed_origins": ["https://analyst.example.test"],
                "allow_local_analysis": False,
            },
            {"max_dataset_bytes": 2_097_152, "max_dictionary_bytes": 262_144},
            {"database_url": "sqlite:///:memory:"},
        ),
        (
            {
                "environment": "production",
                "cors_allowed_origins": ["https://analyst.example.test"],
                "allow_local_analysis": False,
            },
            {"max_dataset_bytes": 2_097_153, "max_dictionary_bytes": 262_144},
            {"database_url": "postgresql+psycopg://user:password@db.example.test/database"},
        ),
    ],
)
def test_production_rejects_insecure_configuration(
    deployment: dict[str, object], uploads: dict[str, int], persistence: dict[str, str]
) -> None:
    with pytest.raises(ValidationError, match="Unsafe production|CORS origins"):
        Settings(_env_file=None, deployment=deployment, uploads=uploads, persistence=persistence)


def test_postgresql_repository_uses_tls_and_small_resilient_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Repository:
        def __init__(self, engine: object) -> None:
            self.engine = engine

        def initialize(self) -> None:
            return None

    def create_engine(url: str, **options: object) -> object:
        captured["url"] = url
        captured["options"] = options
        return object()

    monkeypatch.setattr("sqlalchemy.create_engine", create_engine)
    monkeypatch.setattr(
        "app.modules.reporting.adapters.persistence.report_repository.SqlAlchemyAnalysisRepository",
        Repository,
    )
    build_repository(production_settings())

    assert captured["url"] == "postgresql+psycopg://user:password@db.example.test/database"
    assert captured["options"] == {
        "connect_args": {"sslmode": "require"},
        "pool_pre_ping": True,
        "pool_size": 1,
        "max_overflow": 0,
        "pool_recycle": 300,
    }


def test_postgresql_verify_full_preserves_pool_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Repository:
        def __init__(self, engine: object) -> None:
            self.engine = engine

        def initialize(self) -> None:
            return None

    def create_engine(url: str, **options: object) -> object:
        captured["options"] = options
        return object()

    monkeypatch.setattr("sqlalchemy.create_engine", create_engine)
    monkeypatch.setattr(
        "app.modules.reporting.adapters.persistence.report_repository.SqlAlchemyAnalysisRepository",
        Repository,
    )
    build_repository(
        production_settings(
            persistence={
                "database_url": "postgresql+psycopg://user:password@db.example.test/database?sslmode=verify-full",
                "postgres_sslmode": "verify-full",
            }
        )
    )

    assert captured["options"] == {
        "connect_args": {"sslmode": "verify-full"},
        "pool_pre_ping": True,
        "pool_size": 1,
        "max_overflow": 0,
        "pool_recycle": 300,
    }
