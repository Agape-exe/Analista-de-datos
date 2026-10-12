from fastapi import Request

from app.config.settings import Settings


def get_settings(request: Request) -> Settings:
    """Application-scoped settings, replaceable through dependency overrides."""
    return request.app.state.settings
