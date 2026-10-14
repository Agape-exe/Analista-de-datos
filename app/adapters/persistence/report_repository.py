import asyncio
from threading import Lock

from sqlalchemy import Engine, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.domain.models.report import AnalysisReport


class Base(DeclarativeBase):
    pass


class StoredReport(Base):
    __tablename__ = "analysis_reports"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class SqlAlchemyAnalysisRepository:
    """Explicit initialization and idempotent replacement by run_id."""

    def __init__(self, engine: Engine) -> None:
        self._lock = Lock()
        self.engine = engine
        self.sessions = sessionmaker(engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def _save(self, report: AnalysisReport) -> None:
        with self._lock, self.sessions.begin() as session:
            session.merge(StoredReport(run_id=report.run_id, payload=report.model_dump_json()))

    async def save(self, report: AnalysisReport) -> None:
        await asyncio.to_thread(self._save, report)

    def _get(self, run_id: str) -> AnalysisReport | None:
        with self._lock, self.sessions() as session:
            row = session.get(StoredReport, run_id)
            return AnalysisReport.model_validate_json(row.payload) if row else None

    async def get(self, run_id: str) -> AnalysisReport | None:
        return await asyncio.to_thread(self._get, run_id)
