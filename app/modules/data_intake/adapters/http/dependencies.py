from fastapi import Request

from app.modules.data_intake.application.use_cases.intake_uploaded_dataset import (
    IntakeUploadedDataset,
)
from app.modules.data_intake.application.use_cases.preview_dataset import PreviewDataset


def get_intake_use_case(request: Request) -> IntakeUploadedDataset:
    return request.app.state.intake_use_case


def get_preview_use_case(request: Request) -> PreviewDataset:
    return request.app.state.preview_use_case
