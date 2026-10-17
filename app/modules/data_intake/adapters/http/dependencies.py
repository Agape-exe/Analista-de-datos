from fastapi import Request

from app.modules.data_intake.application.use_cases.intake_uploaded_dataset import (
    IntakeUploadedDataset,
)


def get_intake_use_case(request: Request) -> IntakeUploadedDataset:
    return request.app.state.intake_use_case
