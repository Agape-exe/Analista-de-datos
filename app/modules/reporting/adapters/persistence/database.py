from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str) -> Engine:
    """Construct an engine explicitly; no connections or DDL on import."""
    return create_engine(database_url)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
