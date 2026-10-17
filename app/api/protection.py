import asyncio
import math
import time
from collections import OrderedDict, deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from app.config.settings import DeploymentSettings


class RequestRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class OperationCapacityExceeded(Exception):
    pass


@dataclass
class InMemoryRequestLimiter:
    """Bounded, process-local limiter for a single low-traffic MVP instance."""

    max_clients: int
    clock: Callable[[], float] = time.monotonic
    _requests: OrderedDict[tuple[str, str], deque[float]] = field(default_factory=OrderedDict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check(self, client: str, scope: str, limit: int, window_seconds: int) -> None:
        now = self.clock()
        key = (client, scope)
        async with self._lock:
            entries = self._requests.get(key)
            if entries is None:
                if len(self._requests) >= self.max_clients:
                    self._requests.popitem(last=False)
                entries = deque()
                self._requests[key] = entries
            else:
                self._requests.move_to_end(key)
            while entries and now - entries[0] >= window_seconds:
                entries.popleft()
            if len(entries) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - entries[0])))
                raise RequestRateLimited(retry_after)
            entries.append(now)


@dataclass
class OperationCapacity:
    """Reject excess expensive operations instead of queuing unbounded work."""

    limit: int
    _active: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        async with self._lock:
            if self._active >= self.limit:
                raise OperationCapacityExceeded
            self._active += 1
        try:
            yield
        finally:
            async with self._lock:
                self._active -= 1


def build_request_limiter(settings: DeploymentSettings) -> InMemoryRequestLimiter:
    return InMemoryRequestLimiter(settings.max_tracked_clients)


def build_operation_capacity(settings: DeploymentSettings) -> OperationCapacity:
    return OperationCapacity(settings.max_concurrent_operations)


async def enforce_request_limit(request: Request, scope: str) -> None:
    settings = request.app.state.settings.deployment
    limits = {
        "upload": settings.max_upload_requests,
        "exploration": settings.max_exploration_requests,
        "report": settings.max_report_requests,
    }
    client = request.client.host if request.client is not None else "unknown"
    try:
        await request.app.state.request_limiter.check(
            client, scope, limits[scope], settings.rate_limit_window_seconds
        )
    except RequestRateLimited as error:
        raise HTTPException(
            429,
            detail={
                "code": "REQUEST_RATE_LIMITED",
                "message": "Too many requests. Try again later.",
            },
            headers={"Retry-After": str(error.retry_after)},
        ) from error


@asynccontextmanager
async def reserve_operation_capacity(request: Request) -> AsyncIterator[None]:
    try:
        async with request.app.state.operation_capacity.acquire():
            yield
    except OperationCapacityExceeded as error:
        raise HTTPException(
            429,
            detail={
                "code": "ANALYSIS_CAPACITY_EXCEEDED",
                "message": "The analysis service is busy. Try again later.",
            },
            headers={"Retry-After": "1"},
        ) from error
