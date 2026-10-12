from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(_env_file=None))) as test_client:
        yield test_client
