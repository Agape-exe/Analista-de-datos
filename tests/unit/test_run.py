import pytest

import run
from app.shared.config.settings import Settings


def _run_with_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> dict[str, object]:
    captured = {}
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setattr(run, "load_settings", lambda: settings)
    monkeypatch.setattr(run, "configure_logging", lambda: None)
    monkeypatch.setattr(
        run.uvicorn, "run", lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs)
    )
    run.main()
    return captured


def test_run_uses_loopback_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _run_with_settings(monkeypatch, Settings(_env_file=None))

    assert captured["args"] == ("app.api.main:app",)
    assert captured["kwargs"] == {"host": "127.0.0.1", "port": 9123, "workers": 1}


def test_run_uses_paas_host_in_valid_production(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        deployment={
            "environment": "production",
            "cors_allowed_origins": ["https://analyst.example.test"],
            "allow_local_analysis": False,
        },
        uploads={"max_dataset_bytes": 2_097_152, "max_dictionary_bytes": 262_144},
        persistence={
            "database_url": "postgresql+psycopg://user:password@db.example.test/database",
            "postgres_sslmode": "require",
        },
    )
    captured = _run_with_settings(monkeypatch, settings)

    assert captured["kwargs"] == {"host": "0.0.0.0", "port": 9123, "workers": 1}


def test_run_does_not_start_when_settings_are_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    def invalid_settings() -> Settings:
        raise ValueError("Unsafe production configuration")

    started: list[bool] = []
    monkeypatch.setattr(run, "load_settings", invalid_settings)
    monkeypatch.setattr(run.uvicorn, "run", lambda *args, **kwargs: started.append(True))

    with pytest.raises(ValueError, match="Unsafe production"):
        run.main()

    assert started == []
