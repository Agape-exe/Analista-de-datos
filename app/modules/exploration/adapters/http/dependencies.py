from fastapi import Request

from app.modules.exploration.application.use_cases.explore_dataset import ExploreDataset


def get_exploration_use_case(request: Request) -> ExploreDataset:
    return request.app.state.exploration_use_case
