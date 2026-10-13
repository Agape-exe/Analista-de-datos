from fastapi import Request

from app.application.use_cases.intake_uploaded_dataset import IntakeUploadedDataset
from app.config.settings import Settings


def get_settings(request: Request) -> Settings:
    """Application-scoped settings, replaceable through dependency overrides."""
    return request.app.state.settings


def get_intake_use_case(request: Request) -> IntakeUploadedDataset:
    return request.app.state.intake_use_case
