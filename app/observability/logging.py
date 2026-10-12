import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure console logging explicitly at the process entry point."""
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def log_stage(run_id: str, stage: str, status: str, duration: float) -> None:
    logging.getLogger("app.workflow").info(
        "run_id=%s stage=%s status=%s duration_seconds=%.6f", run_id, stage, status, duration
    )
