import asyncio

import pytest

from app.shared.adapters.http.protection import (
    InMemoryRequestLimiter,
    OperationCapacity,
    OperationCapacityExceeded,
    RequestRateLimited,
)


@pytest.mark.asyncio
async def test_request_limiter_releases_expired_window() -> None:
    now = [0.0]
    limiter = InMemoryRequestLimiter(max_clients=2, clock=lambda: now[0])
    await limiter.check("client", "upload", limit=1, window_seconds=10)
    with pytest.raises(RequestRateLimited) as error:
        await limiter.check("client", "upload", limit=1, window_seconds=10)
    assert error.value.retry_after == 10
    now[0] = 10.0
    await limiter.check("client", "upload", limit=1, window_seconds=10)


@pytest.mark.asyncio
async def test_operation_capacity_releases_after_error() -> None:
    capacity = OperationCapacity(limit=1)
    with pytest.raises(RuntimeError):
        async with capacity.acquire():
            with pytest.raises(OperationCapacityExceeded):
                async with capacity.acquire():
                    pass
            raise RuntimeError("simulated failure")
    async with capacity.acquire():
        await asyncio.sleep(0)
