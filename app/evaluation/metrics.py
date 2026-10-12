from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


class TimingRecorder:
    """Record monotonic elapsed seconds for actual executions, including failures."""

    def __init__(self) -> None:
        self.durations: dict[str, float] = {}

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        started = perf_counter()
        try:
            yield
        finally:
            self.durations[stage] = self.durations.get(stage, 0) + perf_counter() - started
