from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Strict, JSON-serializable contract base."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
