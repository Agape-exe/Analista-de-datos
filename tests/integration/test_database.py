from sqlalchemy import text

from app.modules.reporting.adapters.persistence.database import build_engine, build_session_factory


def test_explicit_sqlite_session() -> None:
    engine = build_engine("sqlite:///:memory:")
    try:
        with build_session_factory(engine)() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()
